"""Three gates for low-noise realtime moderation notifications.

Gate 1 cheaply selects policy candidates, Gate 2 reviews nearby conversation
context, and Gate 3 retrieves human-reviewed cases before notifying Admin/Mod.
"""

from __future__ import annotations

import re
import time

from backend.config import Settings, get_settings
from backend.models.operations import (
    CommonMessage,
    ContextReviewOutput,
    GateResult,
    MessageDecision,
)
from backend.services.operations_store import OperationsStore

_BENIGN_ACTIVITY_PATTERN = (
    r"(?:\bđánh\s+(?:liên\s*quân|game|rank|cờ|cầu|bóng|tennis|golf|đàn|trống|"
    r"máy|răng|giá|dấu|vần|thức|son|phấn|bài)\b|\bchém\s+gió\b|"
    r"\bđập\s+hộp\b|\bxử\s+lý\b|\bgiết\s+thời\s+gian\b)"
)


class OperationsPipeline:
    def __init__(self, store: OperationsStore | None = None, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.store = store or OperationsStore(self.settings)

    def analyze(self, message: CommonMessage, context: list[CommonMessage] | None = None) -> MessageDecision:
        nearby = context or self.store.recent_context(message)
        gate1 = self.gate1(message)
        gate2 = self.gate2(message, nearby, gate1)
        gate3, memory_match = self.gate3(message, gate2)
        decision, severity, confidence = self._decision(gate2)
        needs_incident = decision != "allow" and not memory_match.matched
        duplicate_incident_id = (
            self.store.find_recent_equivalent_incident_id(message, gate2.category)
            if needs_incident
            else None
        )
        if duplicate_incident_id:
            gate3 = gate3.model_copy(
                update={
                    "passed": True,
                    "label": "recent_duplicate",
                    "explanation": "Tin giống hệt đã được gửi trong cửa sổ gần đây; tiếp tục gom incident nhưng không gửi lại.",
                }
            )
        gates = [gate1, gate2, gate3]
        send_to_admin = needs_incident and not duplicate_incident_id
        result = MessageDecision(
            decision=decision,
            category=gate2.category,
            severity=severity,
            risk_score=gate2.risk_score,
            confidence=confidence,
            evidence=list(dict.fromkeys(term for gate in gates for term in gate.evidence))[:8],
            explanation=gate2.explanation,
            model_used=gate2.model_used,
            gates=gates,
            send_to_admin=send_to_admin,
            send_to_member=send_to_admin,
            already_marked=memory_match.matched,
            can_expand=memory_match.can_expand,
            matched_mark_id=memory_match.mark.mark_id if memory_match.mark else None,
            similarity=memory_match.similarity if memory_match.similarity > 0 else None,
            banner=memory_match.banner,
        )

        # Persist the message before incident/audit rows so PostgreSQL foreign
        # keys can enforce every downstream relationship.
        self.store.save_message(message, result, None)
        incident_id = None
        if needs_incident:
            incident = self.store.upsert_incident(message, result)
            incident_id = incident.incident_id
            result = result.model_copy(update={"incident_id": incident_id})
            self.store.link_message_incident(message.message_id, incident_id)
        if incident_id and send_to_admin:
            self.store.add_audit(
                incident_id,
                message.message_id,
                "analysis_completed",
                "system",
                {"decision": decision, "category": gate2.category, "risk_score": result.risk_score},
            )
        elif memory_match.matched:
            self.store.add_audit(
                None,
                message.message_id,
                "duplicate_admin_notification_suppressed",
                "system",
                {
                    "mark_id": memory_match.mark.mark_id if memory_match.mark else None,
                    "similarity": memory_match.similarity,
                    "category": gate2.category,
                },
            )
        elif incident_id and duplicate_incident_id:
            self.store.add_audit(
                incident_id,
                message.message_id,
                "recent_duplicate_notification_suppressed",
                "system",
                {"category": gate2.category, "duplicate_of_incident": duplicate_incident_id},
            )
        return result

    def gate1(self, message: CommonMessage) -> GateResult:
        """Fast filter using active Admin policies plus structural spam rules."""
        started = time.perf_counter()
        text = message.text.strip()
        candidates: list[tuple[float, str, str, list[str], str]] = []

        if len(text) > 9000 or len(text.split()) > 900:
            candidates.append((0.72, "spam", "length_anomaly", ["message quá dài"], "gate1-structure"))
        if len(re.findall(r"https?://", text, re.I)) >= 3:
            candidates.append((0.86, "spam", "link_burst", ["nhiều đường link"], "gate1-structure"))
        if len(text) >= 12 and len(set(text.lower().split())) <= 2:
            candidates.append((0.64, "spam", "repetition", ["lặp từ bất thường"], "gate1-structure"))
        threat_evidence = self._composed_threat_evidence(text)
        if threat_evidence:
            candidates.append(
                (0.94, "violence", "composed_threat", threat_evidence, "gate1-threat-composition")
            )

        action_risk = {"allow": 0.20, "warn": 0.72, "hide": 0.92, "hold_for_review": 0.86}
        for policy in self.store.list_policies():
            if not policy.active or policy.action == "allow":
                continue
            matches = self._matching_terms(text, policy.trigger_terms)
            if matches:
                candidates.append(
                    (
                        action_risk[policy.action],
                        self._canonical_category(policy.category),
                        f"policy:{policy.policy_id}",
                        matches,
                        f"policy-v{policy.version}",
                    )
                )

        if not candidates:
            return GateResult(
                gate="gate1_fast_filter",
                passed=True,
                label="pass",
                category="safe",
                risk_score=0.02,
                explanation="Fast filter không thấy tín hiệu thuộc policy đang bật.",
                model_used="active-policy-fast-filter",
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
        risk, category, label, evidence, model = max(candidates, key=lambda item: item[0])
        return GateResult(
            gate="gate1_fast_filter",
            passed=False,
            label=label,
            category=category,
            risk_score=risk,
            evidence=evidence[:6],
            explanation="Fast filter phát hiện tín hiệu cần đọc thêm ngữ cảnh: " + ", ".join(evidence[:4]) + ".",
            model_used=model,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )

    def gate2(
        self,
        message: CommonMessage,
        context: list[CommonMessage],
        gate1: GateResult,
    ) -> GateResult:
        """Review nearby messages so a keyword alone does not notify Admin."""
        started = time.perf_counter()
        if gate1.passed:
            return GateResult(
                gate="gate2_context_review",
                passed=True,
                label="not_a_conflict_candidate",
                category="safe",
                risk_score=gate1.risk_score,
                explanation="Gate 1 không tạo ứng viên xung đột nên không cần escalation.",
                model_used="local-context-review",
                duration_ms=int((time.perf_counter() - started) * 1000),
            )

        current = message.text.lower()
        all_text = " ".join(item.text for item in [*context, message]).lower()
        evidence = list(gate1.evidence)
        category = gate1.category
        risk = gate1.risk_score
        label = "context_conflict_confirmed"

        direct_target = bool(
            message.parent_message_id
            or re.search(r"(?:\bm\b|\bmày\b|\bmi\b|\bbạn\b|\bnó\b|\bthằng\b|\bcon\b|<@!?\d+>)", current, re.I)
        )
        explicit_threat = bool(self._composed_threat_evidence(current))
        benign_activity = bool(re.search(_BENIGN_ACTIVITY_PATTERN, current, re.I))
        if category == "violence" and benign_activity and not explicit_threat:
            risk = 0.08
            category = "benign_activity"
            label = "context_deescalated_benign_activity"
            evidence.append("'đánh' mang nghĩa hoạt động vô hại")

        joke_signal = bool(re.search(r"(?:\bđùa\b|\bjoke\b|\bhaha+\b|😂|🤣)", all_text, re.I))
        strong_threat = category == "violence" and (direct_target or explicit_threat)
        if joke_signal and not strong_threat:
            risk = max(0.25, risk - 0.28)
            category = "friendly_teasing"
            label = "context_deescalated_joke"
            evidence.append("ngữ cảnh đùa/emoji")

        educational_signal = bool(
            re.search(r"(?:ví dụ|nghĩa là gì|có nghĩa là|trích dẫn|nội quy|từ ngữ|policy|rule)", all_text, re.I)
        )
        if educational_signal and not direct_target and not strong_threat:
            risk = max(0.18, risk - 0.35)
            category = "quoted_or_educational"
            label = "context_deescalated_quote"
            evidence.append("ngữ cảnh trích dẫn/giải thích")

        repeated_hits = sum(
            any(term.lower() in item.text.lower() for term in gate1.evidence)
            for item in context[-self.settings.moderation_context_message_limit :]
        )
        if repeated_hits >= 2 and category not in {"friendly_teasing", "quoted_or_educational"}:
            risk = min(1.0, risk + 0.08)
            label = "repeated_conflict_in_context"
            evidence.append(f"lặp tín hiệu trong {repeated_hits} tin gần đó")
        elif direct_target and category in {"harassment", "hate", "violence"}:
            risk = min(1.0, risk + 0.04)
            evidence.append("nhắm trực tiếp người tham gia")

        explanation = self._context_explanation(category, evidence, len(context))
        model = "local-context-review"
        if (
            category not in {"benign_activity", "friendly_teasing", "quoted_or_educational"}
            and self.settings.operations_use_llm
            and self.settings.openai_api_key
        ):
            try:
                from backend.services.openai_moderation import OpenAIModerationService

                prompt = (
                    "You are Gate 2 of a Vietnamese realtime community moderation system. Return JSON only. "
                    "Review intent using the current message and nearby messages. Do not flag quoted rules, "
                    "educational examples, friendly jokes, or ordinary disagreement without harmful intent.\n"
                    f"Current message: {message.text[:4000]}\n"
                    f"Nearby context: {[item.text[:1000] for item in context[-10:]]}\n"
                    f"Fast-filter result: {gate1.model_dump_json()}"
                )
                llm_result = OpenAIModerationService(self.settings).generate_structured(
                    prompt,
                    ContextReviewOutput,
                    "Operations Gate 2 context review",
                )
                output = llm_result.output
                # A model may add nuance, but cannot erase a deterministic
                # high-confidence threat/scam signal without human review.
                if not (gate1.risk_score >= 0.88 and output.risk_score < 0.55):
                    category = output.category
                    risk = output.risk_score
                    evidence = output.evidence
                    explanation = output.explanation
                    label = "llm_context_review"
                    model = llm_result.model_used
            except Exception:
                model = "local-context-review-fallback"

        return GateResult(
            gate="gate2_context_review",
            passed=risk < 0.55,
            label=label,
            category=category,
            risk_score=min(1.0, risk),
            evidence=list(dict.fromkeys(evidence))[:6],
            explanation=explanation,
            model_used=model,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )

    def gate3(self, message: CommonMessage, gate2: GateResult):
        """Retrieve approved cases and suppress only duplicate Admin alerts."""
        from src.ai_models.contracts import ModerationMemoryMatch

        started = time.perf_counter()
        if gate2.passed:
            match = ModerationMemoryMatch(False, 0.0, True, False)
            return (
                GateResult(
                    gate="gate3_approved_case_retrieval",
                    passed=True,
                    label="retrieval_not_needed",
                    category=gate2.category,
                    risk_score=gate2.risk_score,
                    evidence=gate2.evidence,
                    explanation="Context review không yêu cầu gửi cảnh báo nên bỏ qua truy xuất case.",
                    model_used="moderation-memory",
                    duration_ms=int((time.perf_counter() - started) * 1000),
                ),
                match,
            )

        match = self.store.match_reviewed_case(message.text, gate2.category)
        if match.matched:
            explanation = match.banner or "Case tương tự đã được Admin/Mod xử lý."
            label = "approved_case_match"
            evidence = [*gate2.evidence, f"similarity={match.similarity:.3f}"]
        else:
            explanation = "Không tìm thấy case cùng loại đã được Admin/Mod duyệt; đây là ứng viên mới."
            label = "new_case"
            evidence = gate2.evidence
        return (
            GateResult(
                gate="gate3_approved_case_retrieval",
                passed=match.matched,
                label=label,
                category=gate2.category,
                risk_score=gate2.risk_score,
                evidence=list(dict.fromkeys(evidence))[:6],
                explanation=explanation,
                model_used="moderation-memory-embedding",
                duration_ms=int((time.perf_counter() - started) * 1000),
            ),
            match,
        )

    @staticmethod
    def _matching_terms(text: str, terms: list[str]) -> list[str]:
        matches = []
        for term in terms:
            cleaned = term.strip()
            if cleaned and re.search(rf"(?<!\w){re.escape(cleaned)}(?!\w)", text, re.I):
                matches.append(cleaned)
        return matches

    @staticmethod
    def _composed_threat_evidence(text: str) -> list[str]:
        """Detect a harmful action aimed at a person, including VN chat slang.

        A verb alone is intentionally insufficient: "đánh Liên Quân" is an
        activity, while "t sẽ đánh m" has actor, intent, action and target.
        """
        lowered = text.lower()
        action_pattern = r"(?:đánh|đập|đấm|tát|chém|đâm|giết|xử|phang|hurt|kill)"
        target_pattern = r"(?:m|mày|mi|bạn|nó|thằng\s+\w+|con\s+\w+|<@!?\d+>)"
        actor_pattern = r"(?:tao|t|bố|ông|mẹ)"
        actions = list(re.finditer(rf"(?<!\w){action_pattern}(?!\w)", lowered, re.I))
        if not actions:
            return []
        # If "đánh" is used only as a game/activity collocation, it is not a
        # threat candidate. Any additional harmful verb is still reviewed.
        non_benign_actions = [
            match
            for match in actions
            if not re.search(
                _BENIGN_ACTIVITY_PATTERN,
                lowered[max(0, match.start() - 4) : match.end() + 28],
                re.I,
            )
        ]
        if not non_benign_actions:
            return []

        target = re.search(rf"(?<!\w){target_pattern}(?!\w)", lowered, re.I)
        actor = re.search(rf"(?<!\w){actor_pattern}(?!\w)", lowered, re.I)
        intent = re.search(r"\b(?:sẽ|giờ|cho\s+(?:mày|m)?\s*(?:một\s+)?phát|có\s+thích\s+không)\b", lowered, re.I)
        violent_outcome = re.search(r"\b(?:chết|gãy|máu|nhừ\s+tử|ra\s+bã)\b", lowered, re.I)
        strongest_action = next(
            (match for match in non_benign_actions if match.group(0) in {"chém", "đâm", "giết", "kill"}),
            None,
        )
        composed = bool(
            target
            and (
                (actor and (intent or violent_outcome))
                or (intent and non_benign_actions)
                or strongest_action
            )
        )
        if not composed:
            return []
        evidence = [non_benign_actions[0].group(0)]
        if target:
            evidence.append(f"mục tiêu: {target.group(0)}")
        if intent:
            evidence.append(f"ý định: {intent.group(0)}")
        if violent_outcome:
            evidence.append(f"hậu quả: {violent_outcome.group(0)}")
        return evidence[:4]

    @staticmethod
    def _canonical_category(category: str) -> str:
        normalized = category.strip().lower()
        aliases = {
            "công kích": "harassment",
            "cong kich": "harassment",
            "đe dọa": "violence",
            "de doa": "violence",
            "bạo lực": "violence",
            "bao luc": "violence",
            "lừa đảo": "spam",
            "lua dao": "spam",
        }
        return aliases.get(normalized, normalized or "other")

    @staticmethod
    def _context_explanation(category: str, evidence: list[str], context_count: int) -> str:
        source = ", ".join(f"“{item}”" for item in evidence) if evidence else "không có cụm từ cụ thể"
        prefix = f"Đã đọc {context_count} tin nhắn gần đó. "
        explanations = {
            "spam": f"Tín hiệu {source} giống quảng bá/lừa đảo hoặc phát tán link.",
            "harassment": f"Cụm từ {source} có dấu hiệu nhắm vào người tham gia thay vì phản biện nội dung.",
            "violence": f"Cụm từ {source} có thể là đe doạ hoặc gợi ý gây hại.",
            "hate": f"Cụm từ {source} có dấu hiệu công kích một nhóm người.",
            "friendly_teasing": "Ngữ cảnh cho thấy đây có thể là câu đùa và không có đe doạ cụ thể.",
            "quoted_or_educational": "Từ nhạy cảm xuất hiện trong ngữ cảnh trích dẫn hoặc giải thích.",
            "benign_activity": "Từ 'đánh' đang mô tả chơi game, thể thao hoặc một hoạt động vô hại, không nhắm vào người khác.",
        }
        return prefix + explanations.get(category, "Chưa thấy ý định gây xung đột đủ rõ để escalation.")

    @staticmethod
    def _decision(final: GateResult) -> tuple[str, str, float]:
        risk = final.risk_score
        if final.category == "spam" and risk >= 0.85:
            return "hide", "high", 0.92
        if final.category == "violence" and risk >= 0.80:
            return "hold_for_review", "critical", 0.86
        if final.category in {"harassment", "hate"} and risk >= 0.60:
            return "warn", "high" if risk >= 0.75 else "medium", 0.82
        if risk >= 0.55:
            return "hold_for_review", "medium", 0.70
        return "allow", "low", 0.90
