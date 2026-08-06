"""Conversation-level analysis for the Community Health demo.

The deterministic specialists keep the local demo usable without an LLM. When Gemini is
configured, the same service can replace the final synthesis with a validated JSON call;
the heuristic result remains the safe fallback and is never presented as a calibrated
probability.
"""

from __future__ import annotations

import re
from collections import Counter

from src.config import Settings, get_settings
from src.models.community import (
    ConversationAnalysis,
    ConversationMessage,
    ConversationThread,
    InterventionRecommendation,
    MediationSummary,
    SimilarCase,
)


class ConversationAnalysisService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def analyze(self, thread: ConversationThread, similar_cases: list[SimilarCase] | None = None, allow_remote: bool = True) -> ConversationAnalysis:
        messages = thread.messages
        text = " ".join(message.text for message in messages).strip()
        lowered = text.lower()
        score = self._score(messages)
        stage = self._stage(score, messages)
        tone_trend = self._tone_trend(messages)
        participants = list(dict.fromkeys(message.author_id for message in messages))
        triggers = self._triggers(messages)
        topic = self._topic(lowered)
        causes = self._root_causes(lowered, messages)
        needs = score >= self.settings.escalation_review_threshold or stage in {"critical", "escalating"}
        recommendation = self._recommendation(stage, score)
        model_used = "conversation-specialists-mock"

        heuristic = ConversationAnalysis(
            conversation_stage=stage,
            escalation_score=round(score, 3),
            urgency=self._urgency(score),
            category=self._category(lowered, score),
            risk_level=self._risk_level(score),
            main_topic=topic,
            conflict_summary=self._summary(stage, topic, participants),
            root_causes=causes,
            triggers=triggers,
            participants_in_conflict=participants,
            tone_trend=tone_trend,
            needs_intervention=needs,
            recommended_intervention=recommendation,
            confidence=round(min(0.96, 0.65 + min(len(messages), 6) * 0.04), 3),
            model_used=model_used,
            reviewed_example_ids=[case.feedback_id for case in (similar_cases or [])],
        )
        provider = "gemini" if self.settings.moderation_mode == "gemini" else self.settings.moderation_provider
        if allow_remote and self.settings.moderation_mode != "mock" and provider == "openai" and self.settings.openai_api_key:
            try:
                return self._annotate_trigger_evidence(thread, self._openai_synthesis(thread, heuristic, similar_cases or []))
            except Exception:
                return heuristic.model_copy(update={"model_used": "conversation-specialists-mock-fallback"})
        if allow_remote and self.settings.gemini_api_key and self.settings.moderation_mode == "gemini":
            try:
                return self._annotate_trigger_evidence(thread, self._gemini_synthesis(thread, heuristic, similar_cases or []))
            except Exception:
                # A local radar must remain usable when a remote model is unavailable.
                return heuristic.model_copy(update={"model_used": "conversation-specialists-mock-fallback"})
        return heuristic

    def _openai_synthesis(self, thread: ConversationThread, heuristic: ConversationAnalysis, similar_cases: list[SimilarCase]) -> ConversationAnalysis:
        from src.services.openai_moderation import OpenAIModerationService

        messages = "\n".join(f"[{item.author_id}] {item.text[:1000]}" for item in thread.messages)
        cases = "\n".join(f"- {case.stage}, {case.escalation_score:.0%}, Admin chose {case.admin_selected_action}" for case in similar_cases) or "(none)"
        prompt = f"""You are the Conversation Synthesis Agent in a community conflict-mediation system.
Return only valid JSON matching the provided ConversationAnalysis schema.
Analyze a complete conversation thread, not isolated keywords. Do not infer identity or protected traits.
Escalation score is a risk signal from 0 to 1, not a calibrated probability. Keep participants anonymized.
Use the deterministic specialist pre-analysis as a cross-check, but correct it when context supports another conclusion.
Pre-analysis: {heuristic.model_dump_json()}
Reviewed Admin cases for reference:
{cases}
Thread:
{messages}
"""
        result = OpenAIModerationService(self.settings).generate_structured(
            prompt, ConversationAnalysis, "Conversation Synthesis Agent"
        )
        synthesized = result.output.model_copy(update={
            "model_used": result.model_used,
            "reviewed_example_ids": [case.feedback_id for case in similar_cases],
        })
        return self._apply_safe_guardrail(thread, heuristic, synthesized)

    def _gemini_synthesis(self, thread: ConversationThread, heuristic: ConversationAnalysis, similar_cases: list[SimilarCase]) -> ConversationAnalysis:
        from src.services.gemini_moderation import GeminiModerationService

        messages = "\n".join(f"[{item.author_id}] {item.text[:1000]}" for item in thread.messages)
        cases = "\n".join(f"- {case.stage}, {case.escalation_score:.0%}, Admin chose {case.admin_selected_action}" for case in similar_cases) or "(none)"
        prompt = f"""You are the Conversation Synthesis Agent in a community conflict-mediation system.
Return only valid JSON matching the provided ConversationAnalysis schema.
Analyze a complete conversation thread, not isolated keywords. Do not infer identity or protected traits.
Escalation score is a risk signal from 0 to 1, not a calibrated probability. Keep participants anonymized.
Use the deterministic specialist pre-analysis as a cross-check, but correct it when context supports another conclusion.
Pre-analysis: {heuristic.model_dump_json()}
Reviewed Admin cases for reference:
{cases}
Thread:
{messages}
"""
        result = GeminiModerationService(self.settings)._generate_structured(
            self.settings.gemini_review_model, prompt, ConversationAnalysis, "Conversation Synthesis Agent"
        )
        synthesized = result.output.model_copy(update={
            "model_used": result.model_used,
            "reviewed_example_ids": [case.feedback_id for case in similar_cases],
        })
        return self._apply_safe_guardrail(thread, heuristic, synthesized)

    @staticmethod
    def _apply_safe_guardrail(
        thread: ConversationThread,
        heuristic: ConversationAnalysis,
        synthesized: ConversationAnalysis,
    ) -> ConversationAnalysis:
        """Prevent a remote synthesis from inventing risk in clearly positive threads.

        A disagreement about facts can still be useful and should not become a
        moderation incident unless the source messages contain a concrete trigger.
        The deterministic specialist result is used as a conservative floor here.
        """
        text = " ".join(message.text.lower() for message in thread.messages)
        positive_markers = re.compile(
            r"(cảm ơn|rất hay|rất hữu ích|hữu ích|mình thích|thích phần|tuyệt vời|"
            r"hay quá|great|thank you|thanks|love this|helpful|awesome|excellent)", re.I
        )
        hostile_markers = re.compile(
            r"(ngu|điên|cút|im đi|vô dụng|stupid|idiot|hate|shut up|giết|đánh|"
            r"doạ|đe doạ|kill|hurt|dox|find you)", re.I
        )
        if positive_markers.search(text) and not hostile_markers.search(text) and not heuristic.triggers:
            return synthesized.model_copy(update={
                "conversation_stage": "healthy",
                "escalation_score": 0.0,
                "urgency": "low",
                "category": "safe",
                "risk_level": "low",
                "needs_intervention": False,
                "recommended_intervention": "observe",
                "triggers": [],
            })
        if not hostile_markers.search(text) and not heuristic.triggers:
            # A neutral request, disagreement, or product question must not be
            # promoted to harassment solely because the LLM found the wording
            # dismissive. Keep the source-grounded category and low-risk signal.
            updates = {
                "category": heuristic.category,
                "risk_level": heuristic.risk_level,
                "urgency": heuristic.urgency,
                "triggers": [],
            }
            if synthesized.escalation_score < 0.4:
                updates.update({
                    "escalation_score": min(synthesized.escalation_score, 0.18),
                    "needs_intervention": False,
                    "recommended_intervention": heuristic.recommended_intervention,
                })
            return synthesized.model_copy(update=updates)
        return synthesized

    def recommend(self, thread: ConversationThread, analysis: ConversationAnalysis | None = None) -> InterventionRecommendation:
        analysis = analysis or self.analyze(thread)
        action = analysis.recommended_intervention
        draft = self._draft(action, analysis)
        support = self._youtube_support(action)
        return InterventionRecommendation(
            recommended_action=action,
            reason=self._recommendation_reason(analysis),
            target_users=analysis.participants_in_conflict,
            draft_message=draft,
            expected_outcome=self._expected_outcome(action),
            urgency=analysis.urgency,
            internal_action=action,
            youtube_action=support[0],
            supported=support[1],
            support_reason=support[2],
            model_used=analysis.model_used,
        )

    def mediation(self, thread: ConversationThread, analysis: ConversationAnalysis | None = None) -> MediationSummary:
        analysis = analysis or self.analyze(thread)
        grouped: dict[str, list[str]] = {}
        for message in thread.messages:
            grouped.setdefault(message.author_id, []).append(message.text)
        sides = list(grouped.items())
        side_a = " ".join(sides[0][1])[:500] if sides else "Chưa đủ dữ liệu cho bên A."
        side_b = " ".join(sides[1][1])[:500] if len(sides) > 1 else "Chưa có phản hồi đối chiếu cho bên B."
        return MediationSummary(
            side_a_position=side_a,
            side_b_position=side_b,
            common_ground=["Các bên đang cùng trao đổi về một chủ đề chung.", "Có thể tiếp tục đối thoại nếu giữ ngôn ngữ tôn trọng."],
            core_disagreement=analysis.root_causes or [analysis.main_topic],
            harmful_patterns=[item.reason for item in analysis.triggers] or ["Chưa phát hiện mẫu gây hại rõ ràng."],
            recommended_next_steps=["Tách vấn đề khỏi công kích cá nhân.", "Xác nhận lại dữ kiện trước khi phản hồi.", "Admin duyệt bản nháp trước khi đăng."],
            admin_editable_draft=self._draft("open_mediation", analysis),
            model_used=analysis.model_used,
        )

    @staticmethod
    def _score(messages: list[ConversationMessage]) -> float:
        aggression = re.compile(r"\b(ngu|điên|cút|im đi|vô dụng|stupid|idiot|hate|shut up)\b", re.I)
        threat = re.compile(r"\b(giết|đánh|doạ|đe doạ|kill|hurt|dox|find you)\b", re.I)
        personal = re.compile(r"\b(mày|tao|you are|your family|gia đình mày)\b", re.I)
        constructive = re.compile(r"\b(cảm ơn|xin lỗi|giải thích|đồng ý|agree|please|thanks|sorry)\b", re.I)
        value = 0.0
        has_threat = False
        has_personal_attack = False
        for message in messages:
            is_aggression = bool(aggression.search(message.text))
            is_threat = bool(threat.search(message.text))
            is_personal = bool(personal.search(message.text))
            has_threat = has_threat or is_threat
            has_personal_attack = has_personal_attack or is_aggression or is_personal
            value += 0.17 if is_aggression else 0
            value += 0.34 if is_threat else 0
            value += 0.10 if is_personal else 0
            value += 0.04 if message.text.count("!") >= 2 else 0
            value += 0.05 if len(re.findall(r"[A-ZÀ-ỸĐ]", message.text)) > max(8, len(message.text) // 3) else 0
            value -= 0.04 if constructive.search(message.text) else 0
        if len(messages) >= 4:
            value += 0.06
        if has_threat and has_personal_attack:
            value += 0.15
        return max(0.0, min(1.0, value))

    @staticmethod
    def _stage(score: float, messages: list[ConversationMessage]) -> str:
        if score >= 0.85:
            return "critical"
        if score >= 0.65:
            return "escalating"
        if score >= 0.40:
            return "tense"
        if score >= 0.18:
            return "disagreement"
        if len(messages) >= 2 and any("xin lỗi" in item.text.lower() or "sorry" in item.text.lower() for item in messages):
            return "resolving"
        return "healthy"

    @staticmethod
    def _tone_trend(messages: list[ConversationMessage]) -> str:
        if len(messages) < 2:
            return "stable"
        first = ConversationAnalysisService._score(messages[: max(1, len(messages) // 2)])
        last = ConversationAnalysisService._score(messages[len(messages) // 2 :])
        if last - first > 0.18:
            return "rapidly_declining"
        if last > first + 0.06:
            return "declining"
        if first > last + 0.08:
            return "improving"
        return "stable"

    @staticmethod
    def _urgency(score: float) -> str:
        return "critical" if score >= 0.85 else "high" if score >= 0.65 else "medium" if score >= 0.4 else "low"

    @staticmethod
    def _risk_level(score: float) -> str:
        return "critical" if score >= 0.85 else "high" if score >= 0.65 else "medium" if score >= 0.4 else "low"

    @staticmethod
    def _category(text: str, score: float) -> str:
        if re.search(r"(giết|đánh|doạ|đe doạ|kill|hurt|dox|find you)", text, re.I):
            return "violence"
        if re.search(r"(ngu|điên|cút|vô dụng|stupid|idiot|shut up)", text, re.I):
            return "harassment"
        if re.search(r"(spam|mua ngay|click link|giveaway)", text, re.I):
            return "spam"
        if score >= 0.18:
            return "disagreement"
        return "safe"

    @staticmethod
    def _topic(text: str) -> str:
        topic_words = Counter(re.findall(r"[a-zA-ZÀ-ỹĐđ]{4,}", text))
        for word in ("video", "này", "that", "this", "comment", "bạn", "mình"):
            topic_words.pop(word, None)
        return topic_words.most_common(1)[0][0] if topic_words else "trao đổi chung"

    @staticmethod
    def _root_causes(text: str, messages: list[ConversationMessage]) -> list[str]:
        causes = []
        if re.search(r"(sai|không đúng|fake|bịa|proof|bằng chứng)", text, re.I):
            causes.append("Bất đồng về thông tin hoặc bằng chứng.")
        if re.search(r"(không hiểu|misunderstand|ý là|ý tôi)", text, re.I):
            causes.append("Hiểu khác nhau về ý định hoặc ngữ cảnh.")
        if any(len(message.text) > 500 for message in messages):
            causes.append("Trao đổi dài khiến điểm bất đồng bị khuếch đại.")
        if not causes and len({item.author_id for item in messages}) > 1:
            causes.append("Các bên chưa thống nhất cách diễn giải chủ đề.")
        return causes[:8] or ["Chưa đủ dữ liệu để xác định nguyên nhân gốc."]

    @staticmethod
    def _triggers(messages: list[ConversationMessage]):
        result = []
        patterns = [
            (r"(giết|đánh|dọa|đe dọa|kill|hurt|dox|find you)", "Có ngôn ngữ đe doạ hoặc gợi ý gây hại."),
            (r"(ngu|điên|cút|vô dụng|stupid|idiot|shut up)", "Có công kích hoặc hạ thấp người tham gia."),
        ]
        for index, message in enumerate(messages):
            lower = message.text.lower()
            reason = None
            matched_terms = []
            for pattern, candidate_reason in patterns:
                matched_terms.extend(match.group(0) for match in re.finditer(pattern, lower, re.I))
                if matched_terms and reason is None:
                    reason = candidate_reason
            if not matched_terms and message.text.count("!") >= 2:
                reason = "Cường độ cảm xúc cao qua dấu câu."
            if reason:
                context_note = "Từ/cụm từ này nằm trong comment gốc."
                if message.parent_message_id:
                    context_note = "Từ/cụm từ này xuất hiện trong reply, sau comment trước đó."
                elif index + 1 < len(messages):
                    context_note = "Từ/cụm từ này xuất hiện ở comment mở đầu thread."
                result.append({"message_id": message.message_id, "text": message.text[:300], "reason": reason, "matched_terms": list(dict.fromkeys(matched_terms)), "context_note": context_note})
        return result[:5]

    @staticmethod
    def _annotate_trigger_evidence(thread: ConversationThread, analysis: ConversationAnalysis) -> ConversationAnalysis:
        """Attach short, source-grounded terms so the UI can show evidence, not a rewritten sentence."""
        local_triggers = {item["message_id"]: item for item in ConversationAnalysisService._triggers(thread.messages)}
        triggers = []
        for trigger in analysis.triggers:
            local = local_triggers.get(trigger.message_id)
            if local:
                triggers.append(trigger.model_copy(update={"matched_terms": local["matched_terms"], "context_note": local["context_note"]}))
            else:
                triggers.append(trigger)
        return analysis.model_copy(update={"triggers": triggers})

    @staticmethod
    def _recommendation(stage: str, score: float) -> str:
        if stage == "critical" or score >= 0.85:
            return "temporary_cooldown"
        if stage == "escalating" or score >= 0.65:
            return "open_mediation"
        if stage == "tense":
            return "private_nudge"
        if stage == "disagreement":
            return "ask_for_clarification"
        return "observe"

    @staticmethod
    def _summary(stage: str, topic: str, participants: list[str]) -> str:
        return f"Thread về {topic} đang ở trạng thái {stage}; có {len(participants)} người tham gia được hệ thống nhận diện theo mã ẩn danh."

    @staticmethod
    def _recommendation_reason(analysis: ConversationAnalysis) -> str:
        return f"Escalation score {analysis.escalation_score:.0%}, stage {analysis.conversation_stage}, trend {analysis.tone_trend}. Admin cần duyệt trước khi có hành động trên nền tảng."

    @staticmethod
    def _expected_outcome(action: str) -> str:
        return {
            "observe": "Theo dõi tiếp diễn biến mà chưa can thiệp.",
            "private_nudge": "Giảm nhiệt mà không làm thread công khai căng hơn.",
            "ask_for_clarification": "Làm rõ ý định và dữ kiện tranh luận.",
            "open_mediation": "Đưa các bên về mục tiêu giải quyết vấn đề.",
            "temporary_cooldown": "Ngăn leo thang ngay lập tức trong khi Admin xem xét.",
        }.get(action, "Giảm rủi ro và tạo điểm kiểm soát cho Admin.")

    @staticmethod
    def _draft(action: str, analysis: ConversationAnalysis) -> str:
        if action == "ask_for_clarification":
            return "Mọi người giúp làm rõ dữ kiện/ý định của ý kiến trên trước khi tiếp tục nhé. Hãy tập trung vào vấn đề, không công kích cá nhân."
        if action in {"open_mediation", "private_nudge"}:
            return "Mình thấy cuộc trao đổi đang nóng lên. Hãy tạm dừng công kích cá nhân và nói rõ điểm bạn muốn làm rõ; Admin sẽ hỗ trợ kết nối các bên."
        if action == "temporary_cooldown":
            return "Thread tạm thời được đưa vào cooldown để Admin kiểm tra. Vui lòng không đăng thêm nội dung công kích hoặc đe doạ."
        return "Chưa cần gửi phản hồi; tiếp tục quan sát diễn biến của thread."

    @staticmethod
    def _youtube_support(action: str) -> tuple[str, bool, str]:
        mapping = {
            "observe": ("no_write", True, "Không cần YouTube write API."),
            "private_nudge": ("admin_draft_only", False, "YouTube public comment không có private nudge trực tiếp trong MVP."),
            "ask_for_clarification": ("comment_draft", False, "MVP chỉ tạo draft; Admin phải duyệt và OAuth mới có thể đăng."),
            "open_mediation": ("comment_draft", False, "MVP chỉ tạo draft; chưa tự đăng lên YouTube."),
            "temporary_cooldown": ("hold_for_review", False, "YouTube action cần quyền channel và được mô phỏng trong local demo."),
        }
        return mapping.get(action, ("admin_review", False, "Hành động cần Admin duyệt."))
def _fixed_local_score(messages: list[ConversationMessage]) -> float:
    aggression = re.compile(r"\b(ngu|\u0111i\u00ean|c\u00fat|im \u0111i|v\u00f4 d\u1ee5ng|stupid|idiot|hate|shut up)\b", re.I)
    threat = re.compile(r"\b(gi\u1ebft|\u0111\u00e1nh|d\u1ecda|\u0111e d\u1ecda|t\u00ecm ra m\u00e0y|kill|hurt|dox|find you)\b", re.I)
    personal = re.compile(r"\b(m\u00e0y|tao|you are|your family|gia \u0111\u00ecnh m\u00e0y)\b", re.I)
    value = 0.0
    has_threat = False
    has_personal_attack = False
    for message in messages:
        is_aggression = bool(aggression.search(message.text))
        is_threat = bool(threat.search(message.text))
        is_personal = bool(personal.search(message.text))
        has_threat = has_threat or is_threat
        has_personal_attack = has_personal_attack or is_aggression or is_personal
        value += 0.17 if is_aggression else 0
        value += 0.34 if is_threat else 0
        value += 0.10 if is_personal else 0
        value += 0.04 if message.text.count("!") >= 2 else 0
    if len(messages) >= 4:
        value += 0.06
    if has_threat and has_personal_attack:
        value += 0.15
    return max(0.0, min(1.0, value))


# Compatibility override for the older source copy whose literal regexes were
# committed with mojibake. It keeps the mock/local analysis deterministic.
ConversationAnalysisService._score = staticmethod(_fixed_local_score)
