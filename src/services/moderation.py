"""Moderation orchestration: Gemini is primary; mock is explicit only."""

from __future__ import annotations

import asyncio
import logging

from src.config import Settings, get_settings
from src.models.moderation import MemberSubmission, ModerationResult
from src.services.gemini_moderation import GeminiModerationError, GeminiModerationService, GeminiStageResult

logger = logging.getLogger(__name__)


class ModerationConfigurationError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.user_message = message


class ModerationEngine:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.gemini = GeminiModerationService(self.settings)

    async def moderate(self, submission: MemberSubmission) -> ModerationResult:
        if self.settings.moderation_mode == "mock":
            return self._mock_result(submission)
        if not self.settings.gemini_api_key:
            raise ModerationConfigurationError(
                "Gemini API chưa được cấu hình. Hãy điền GEMINI_API_KEY vào file .env rồi khởi động lại server."
            )

        try:
            triage = await asyncio.to_thread(self.gemini.moderate_with_triage, submission)
            final = triage
            if self.should_escalate_to_review_model(triage, submission):
                final = await asyncio.to_thread(self.gemini.review_ambiguous_content, submission, triage)
            return self._to_result(final, mode="gemini")
        except GeminiModerationError as exc:
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
            model_used=self.settings.gemini_review_model,
            mode="gemini",
            fallback_used=False,
            fallback_reason=reason,
        )

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
        )
