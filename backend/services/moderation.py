"""Provider-agnostic moderation orchestration; OpenAI is primary in the project .env."""

from __future__ import annotations

import asyncio
import logging

from backend.agents.moderation_graph import ModerationAgentGraph
from backend.config import Settings, get_settings
from backend.models.moderation import MemberSubmission, ModerationResult
from backend.services.gemini_moderation import GeminiModerationError, GeminiModerationService, GeminiStageResult
from backend.services.openai_moderation import OpenAIModerationError, OpenAIModerationService

logger = logging.getLogger(__name__)


class ModerationConfigurationError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.user_message = message


class ModerationEngine:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.gemini = GeminiModerationService(self.settings)
        self.openai = OpenAIModerationService(self.settings)
        # `moderation_mode=gemini` remains a backwards-compatible explicit Gemini switch.
        self.provider = "gemini" if self.settings.moderation_mode == "gemini" else self.settings.moderation_provider
        self.service = self.openai if self.provider == "openai" else self.gemini
        self.agent_graph = ModerationAgentGraph(self.service)

    async def moderate(self, submission: MemberSubmission) -> ModerationResult:
        if self.settings.moderation_mode == "mock":
            return self._mock_result(submission)
        api_key = self.settings.openai_api_key if self.provider == "openai" else self.settings.gemini_api_key
        if not api_key:
            key_name = "OPENAI_API_KEY" if self.provider == "openai" else "GEMINI_API_KEY"
            raise ModerationConfigurationError(
                f"{key_name} chưa được cấu hình. Hãy điền key vào file .env rồi khởi động lại server."
            )

        try:
            state = await asyncio.to_thread(self.agent_graph.invoke, submission)
            return self._graph_to_result(state)
        except (GeminiModerationError, OpenAIModerationError) as exc:
            if exc.code == "invalid_structured_output":
                return self._invalid_output_result(exc.user_message)
            if self.settings.allow_mock_fallback:
                fallback = self._mock_result(submission)
                return fallback.model_copy(
                    update={
                        "mode": "mock-fallback",
                        "model_used": "mock-fallback",
                        "fallback_used": True,
                        "fallback_reason": exc.user_message,
                    }
                )
            raise ModerationConfigurationError(exc.user_message) from exc

    def should_escalate_to_review_model(
        self, triage: GeminiStageResult, submission: MemberSubmission
    ) -> bool:
        output = triage.output
        return bool(
            output.category == "ambiguous"
            or output.action == "review"
            or output.needs_admin_review
            or output.confidence < self.settings.moderation_review_threshold
            or (submission.recent_context and output.confidence < self.settings.moderation_auto_action_threshold)
            or output.confidence < self.settings.moderation_auto_action_threshold
        )

    def _to_result(self, stage: GeminiStageResult, mode: str) -> ModerationResult:
        output = stage.output
        needs_review = (
            output.needs_admin_review
            or output.action == "review"
            or output.confidence < self.settings.moderation_auto_action_threshold
        )
        return ModerationResult(
            action="review" if needs_review else output.action,
            category=output.category,
            risk_level=output.risk_level,
            policy_id=output.policy_id,
            reason=output.reason,
            confidence=output.confidence,
            needs_admin_review=needs_review,
            evidence=output.evidence,
            model_used=stage.model_used,
            mode=mode,
            fallback_used=False,
        )

    def _graph_to_result(self, state: dict[str, object]) -> ModerationResult:
        output = state["decision"]
        needs_review = bool(
            output.needs_admin_review
            or output.action == "review"
            or output.confidence < self.settings.moderation_auto_action_threshold
        )
        return ModerationResult(
            action="review" if needs_review else output.action,
            category=output.category,
            risk_level=output.risk_level,
            policy_id=output.policy_id,
            reason=output.reason,
            confidence=output.confidence,
            needs_admin_review=needs_review,
            evidence=output.evidence,
            model_used=str(state.get("model_used") or self._active_model),
            mode=self.provider,
            fallback_used=False,
            agent_trace=list(state.get("trace") or []),
        )

    def _invalid_output_result(self, reason: str) -> ModerationResult:
        logger.warning("Gemini returned invalid structured moderation output")
        return ModerationResult(
            action="review",
            category="ambiguous",
            risk_level="medium",
            policy_id=None,
            reason="Gemini trả về kết quả không hợp lệ; nội dung được chuyển cho Admin xem xét.",
            confidence=0.0,
            needs_admin_review=True,
            evidence=[],
            model_used=self._active_model,
            mode=self.provider,
            fallback_used=False,
            fallback_reason=reason,
            agent_trace=["Agent Graph", "Invalid Output Guardrail"],
        )

    @property
    def _active_model(self) -> str:
        return self.settings.openai_moderation_model if self.provider == "openai" else self.settings.gemini_review_model

    def _mock_result(self, submission: MemberSubmission) -> ModerationResult:
        text = submission.text.strip().casefold()
        context = " ".join(submission.recent_context).casefold()
        if any(term in text for term in ("bấm vào link", "nhận tiền miễn phí", "chỉ còn 5 phút", "click link")):
            return self._mock("hide", "spam", "high", "P01", "Dấu hiệu spam hoặc lừa đảo rõ ràng.", 0.95, [submission.text])
        if any(term in text for term in ("mày ngu", "đồ ngu", "nghỉ khỏi nhóm", "cút khỏi")):
            return self._mock("warn", "harassment", "high", "P02", "Nội dung có công kích cá nhân rõ ràng.", 0.93, [submission.text])
        if any(term in text for term in ("giết mày", "đánh chết", "đâm mày")):
            return self._mock("hide", "violence", "critical", "P03", "Nội dung đe dọa bạo lực rõ ràng.", 0.91, [submission.text])
        if any(term in text for term in ("tự tử", "tự làm hại", "muốn chết")):
            return self._mock("review", "self_harm", "high", "P04", "Nội dung nhạy cảm cần Admin xem xét.", 0.68, [submission.text])
        if any(term in text for term in ("ra đường gặp tao", "nghỉ luôn đi", "làm ăn kiểu này")) or ("đùa" in context and "gặp tao" in text):
            return self._mock("review", "ambiguous", "medium", "P05", "Ngữ cảnh chưa đủ rõ để tự động xử lý an toàn.", 0.62, [submission.text])
        return self._mock("allow", "safe", "low", "P00", "Không phát hiện dấu hiệu vi phạm rõ ràng.", 0.91, [])

    @staticmethod
    def _mock(action: str, category: str, risk_level: str, policy_id: str, reason: str, confidence: float, evidence: list[str]) -> ModerationResult:
        needs_review = action == "review" or confidence < 0.80
        return ModerationResult(
            action="review" if needs_review else action,
            category=category,
            risk_level=risk_level,
            policy_id=policy_id,
            reason=reason,
            confidence=confidence,
            needs_admin_review=needs_review,
            evidence=evidence,
            model_used="mock",
            mode="mock",
            fallback_used=False,
            agent_trace=["Mock Policy Agent", "Deterministic Guardrail"],
        )
