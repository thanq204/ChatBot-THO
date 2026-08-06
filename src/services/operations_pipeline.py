"""Three-layer moderation gate and incident orchestration.

Gate 1 is deterministic and cheap, Gate 2 maps the message to policy, and
Gate 3 reads the surrounding conversation before a decision is persisted.
The optional LLM seam is deliberately conservative: if the key/model is not
available, the local context gate keeps the demo usable and marks its model.
"""

from __future__ import annotations

import re
import time
from collections import Counter

from src.config import Settings, get_settings
from src.models.operations import CommonMessage, ContextReviewOutput, GateResult, MessageDecision
from src.services.operations_store import OperationsStore


class OperationsPipeline:
    def __init__(self, store: OperationsStore | None = None, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.store = store or OperationsStore(self.settings)

    def analyze(self, message: CommonMessage, context: list[CommonMessage] | None = None) -> MessageDecision:
        context = context or []
        gates = [self.gate1(message), self.gate2(message)]
        gates.append(self.gate3(message, context, gates[1]))
        # A later context pass may add nuance, but it must not erase a
        # deterministic high-confidence spam/threat signal from Gate 1.
        strongest = max(gates[:2], key=lambda gate: gate.risk_score)
        if strongest.risk_score >= 0.80 and strongest.category != "safe" and gates[2].risk_score < strongest.risk_score:
            gates[2] = gates[2].model_copy(update={
                "category": strongest.category,
                "risk_score": strongest.risk_score,
                "evidence": list(dict.fromkeys([*gates[2].evidence, *strongest.evidence]))[:6],
                "explanation": strongest.explanation + " Gate 3 giữ lại tín hiệu chắc chắn này.",
            })
        final = gates[-1]
        decision, severity, confidence = self._decision(final, gates)
        result = MessageDecision(
            decision=decision,
            category=final.category,
            severity=severity,
            risk_score=max(gate.risk_score for gate in gates),
            confidence=confidence,
            evidence=list(dict.fromkeys(term for gate in gates for term in gate.evidence))[:8],
            explanation=final.explanation,
            model_used=final.model_used,
            gates=gates,
        )
        incident_id = None
        self.store.save_message(message, result, None)
        if decision != "allow":
            incident = self.store.upsert_incident(message, result)
            incident_id = incident.incident_id
            self.store.save_message(message, result, incident_id)
            self.store.add_audit(incident_id, message.message_id, "analysis_completed", "system", {"decision": decision, "category": final.category, "risk_score": result.risk_score})
        return result.model_copy(update={"incident_id": incident_id})

    def gate1(self, message: CommonMessage) -> GateResult:
        started = time.perf_counter()
        text = message.text.strip()
        evidence: list[str] = []
        category = "safe"
        risk = 0.0
        label = "pass"
        explanation = "Không thấy mẫu spam hoặc nguy hiểm rõ ràng ở lớp lọc nhanh."
        if len(text) > 9000 or len(text.split()) > 900:
            label, category, risk, evidence = "length_anomaly", "spam", 0.72, ["message quá dài"]
        elif re.search(r"(free money|click (this )?link|giveaway|nhận tiền miễn phí|trúng thưởng|mật khẩu|otp)", text, re.I):
            label, category, risk, evidence = "scam_pattern", "spam", 0.92, [m.group(0) for m in re.finditer(r"(free money|click (this )?link|giveaway|nhận tiền miễn phí|trúng thưởng|mật khẩu|otp)", text, re.I)][:3]
        elif len(re.findall(r"https?://", text, re.I)) >= 3:
            label, category, risk, evidence = "link_burst", "spam", 0.82, ["nhiều đường link"]
        elif len(text) >= 12 and len(set(text.lower().split())) <= 2:
            label, category, risk, evidence = "repetition", "spam", 0.64, ["lặp từ bất thường"]
        return GateResult(gate="gate1_fast_filter", passed=label == "pass", label=label, category=category, risk_score=risk, evidence=evidence, explanation=explanation if not evidence else "Lớp lọc nhanh phát hiện: " + ", ".join(evidence) + ".", model_used="gate1-regex", duration_ms=int((time.perf_counter() - started) * 1000))

    def gate2(self, message: CommonMessage) -> GateResult:
        started = time.perf_counter()
        text = message.text.lower()
        evidence: list[str] = []
        category, risk, label = "safe", 0.04, "safe"
        patterns = [
            ("violence", 0.90, r"(bố mày.{0,30}(đấm|đánh|đập|tát)|(?:đánh|đấm|đập|tát)\s+(?:cho|vào|mày|người)|giết|đánh|đấm|đập|tát|đâm|dox|tìm ra mày|xử mày|kill|hurt|find you)", "threat_signal"),
            # Keep explicit profanity separate from ordinary disagreement. Word
            # boundaries prevent short slang such as "cc" from matching words
            # like "check" by accident.
            ("harassment", 0.72, r"(?:\bngu\b|\bđần\b|\bvô dụng\b|\bvô duyên\b|\bcút\b|\bđéo\b|\bđịt\b|\bđụ\b|\blồn\b|\bcặc\b|\bđm\b|\bdm\b|\bclm\b|\bcc\b|mẹ mày|thằng ngu|im đi|stupid|idiot|shut up)", "profanity_or_personal_attack"),
            ("hate", 0.78, r"(bọn .* nên chết|race slur)", "hateful_generalisation"),
        ]
        for candidate, score, pattern, candidate_label in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                category, risk, label = candidate, score, candidate_label
                evidence.append(match.group(0))
                break
        if category == "safe" and re.search(r"(không đồng ý|sai rồi|check lại|disagree|not true)", text, re.I):
            category, risk, label = "disagreement", 0.28, "fact_disagreement"
            evidence.append(re.search(r"(không đồng ý|sai rồi|check lại|disagree|not true)", text, re.I).group(0))
        return GateResult(gate="gate2_classifier", passed=risk < 0.55, label=label, category=category, risk_score=risk, evidence=evidence, explanation=self._category_explanation(category, evidence), model_used="vietnamese-policy-classifier", duration_ms=int((time.perf_counter() - started) * 1000))

    def gate3(self, message: CommonMessage, context: list[CommonMessage], gate2: GateResult) -> GateResult:
        started = time.perf_counter()
        all_text = " ".join(item.text for item in [*context, message])
        evidence = list(gate2.evidence)
        risk = gate2.risk_score
        category = gate2.category
        label = "context_review"
        model = "local-context-review"
        if category in {"harassment", "violence", "hate"} and re.search(r"(đùa|joke|haha|😂|🤣)", all_text, re.I) and not re.search(r"(giết|đánh|dox|tìm ra mày|hurt|kill)", all_text, re.I):
            risk = max(0.18, risk - 0.25)
            category = "friendly_teasing"
            evidence.append("ngữ cảnh đùa/emoji")
        if category == "disagreement" and re.search(r"(xin lỗi|cảm ơn|giải thích|nguồn|source|please)", all_text, re.I):
            risk = min(risk, 0.18)
            evidence.append("ngữ cảnh xây dựng")
        if message.parent_message_id and category == "safe":
            label = "reply_context_safe"
        if category == "safe":
            explanation = "Đọc cả message và context: chưa có tín hiệu gây hại cụ thể."
        elif category == "friendly_teasing":
            explanation = "Từ khóa nhạy cảm được giảm mức vì context cho thấy đây là đùa, không có đe doạ cụ thể."
        else:
            explanation = self._category_explanation(category, evidence) + " Gate 3 đã đối chiếu với các message liên quan."
        # The LLM hook is opt-in. A missing key or an API/schema failure falls
        # back to this local result instead of breaking ingestion.
        if self.settings.operations_use_llm and self.settings.openai_api_key:
            try:
                from src.services.openai_moderation import OpenAIModerationService

                prompt = (
                    "You are Gate 3, a Vietnamese community context reviewer. Return JSON only. "
                    "Review the current message together with the conversation context. Do not flag "
                    "a keyword without harmful intent. Keep evidence short and quote only terms.\n"
                    f"Current message: {message.text[:4000]}\n"
                    f"Context: {[item.text[:1000] for item in context[-10:]]}\n"
                    f"Gate 2 result: {gate2.model_dump_json()}"
                )
                llm_result = OpenAIModerationService(self.settings).generate_structured(prompt, ContextReviewOutput, "Operations Gate 3")
                output = llm_result.output
                return GateResult(gate="gate3_context_review", passed=output.risk_score < 0.55, label="llm_context_review", category=output.category, risk_score=output.risk_score, evidence=output.evidence, explanation=output.explanation, model_used=llm_result.model_used, duration_ms=int((time.perf_counter() - started) * 1000))
            except Exception:
                model = "local-context-review-fallback"
        return GateResult(gate="gate3_context_review", passed=risk < 0.55, label=label, category=category, risk_score=min(1.0, risk), evidence=list(dict.fromkeys(evidence))[:6], explanation=explanation, model_used=model, duration_ms=int((time.perf_counter() - started) * 1000))

    @staticmethod
    def _category_explanation(category: str, evidence: list[str]) -> str:
        source = ", ".join(f"“{item}”" for item in evidence) if evidence else "không có cụm từ cụ thể"
        return {"spam": f"Các tín hiệu {source} giống quảng bá/lừa đảo hoặc phát tán link.", "harassment": f"Cụm từ {source} nhắm vào người tham gia thay vì phản biện nội dung.", "violence": f"Cụm từ {source} có thể là đe doạ hoặc gợi ý gây hại nên cần review.", "hate": f"Cụm từ {source} có dấu hiệu công kích một nhóm người.", "disagreement": f"Cụm từ {source} thể hiện bất đồng về thông tin nhưng chưa đủ để kết luận công kích.", "friendly_teasing": f"Cụm từ {source} được đọc cùng context đùa nên chưa xem là hành vi vi phạm."}.get(category, "Không có tín hiệu vi phạm rõ ràng.")

    @staticmethod
    def _decision(final: GateResult, gates: list[GateResult]) -> tuple[str, str, float]:
        risk = max(gate.risk_score for gate in gates)
        if final.category == "spam" and risk >= 0.85:
            return "hide", "high", 0.92
        if final.category == "violence" and risk >= 0.80:
            return "hold_for_review", "critical", 0.86
        if final.category in {"harassment", "hate"} and risk >= 0.60:
            return "warn", "high" if risk >= 0.75 else "medium", 0.82
        if risk >= 0.55:
            return "hold_for_review", "medium", 0.70
        return "allow", "low", 0.90
