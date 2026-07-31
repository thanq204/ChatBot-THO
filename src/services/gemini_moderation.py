"""Two-stage Gemini moderation service with structured, validated output."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from src.config import Settings
from src.models.moderation import GeminiModerationOutput, MemberSubmission

logger = logging.getLogger(__name__)


class GeminiModerationError(RuntimeError):
    def __init__(self, code: str, user_message: str) -> None:
        super().__init__(code)
        self.code = code
        self.user_message = user_message


@dataclass(frozen=True)
class GeminiStageResult:
    output: GeminiModerationOutput
    model_used: str


class GeminiModerationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = None

    def moderate_with_triage(self, submission: MemberSubmission) -> GeminiStageResult:
        return self._generate(
            self.settings.gemini_triage_model,
            self._prompt(submission, stage="triage"),
        )

    def review_ambiguous_content(
        self, submission: MemberSubmission, triage: GeminiStageResult
    ) -> GeminiStageResult:
        return self._generate(
            self.settings.gemini_review_model,
            self._prompt(submission, stage="review", triage=triage.output),
        )

    def _generate(self, model: str, prompt: str) -> GeminiStageResult:
        client = self._get_client()
        last_error: Exception | None = None
        for attempt in range(self.settings.gemini_max_retries + 1):
            try:
                from google.genai import types

                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=self.settings.gemini_temperature,
                        max_output_tokens=self.settings.gemini_max_output_tokens,
                        response_mime_type="application/json",
                        response_schema=GeminiModerationOutput,
                    ),
                )
                output = GeminiModerationOutput.model_validate_json(response.text)
                return GeminiStageResult(output=output, model_used=model)
            except Exception as exc:  # SDK exceptions vary between versions.
                last_error = exc
                if attempt < self.settings.gemini_max_retries and self._retryable(exc):
                    time.sleep(min(2**attempt, 4))
                    continue
                break

        code, message = self._classify_error(last_error)
        logger.warning("Gemini moderation failed: code=%s model=%s", code, model)
        raise GeminiModerationError(code, message) from last_error

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from google import genai

            self._client = genai.Client(api_key=self.settings.gemini_api_key)
            return self._client
        except ImportError as exc:
            raise GeminiModerationError(
                "sdk_missing",
                "Gemini SDK chưa được cài. Hãy chạy: pip install -r requirements.txt",
            ) from exc
        except Exception as exc:
            raise GeminiModerationError(
                "client_configuration", "Không thể khởi tạo Gemini client. Hãy kiểm tra GEMINI_API_KEY."
            ) from exc

    @staticmethod
    def _prompt(
        submission: MemberSubmission, stage: str, triage: GeminiModerationOutput | None = None
    ) -> str:
        context = "\n".join(f"- {item[:500]}" for item in submission.recent_context[-5:]) or "(none)"
        triage_text = (
            f"\nTriage result to review:\n{triage.model_dump_json()}\n" if triage is not None else ""
        )
        return f"""You are a community moderation assistant. This is the {stage} stage.
Do not infer identity, gender, or personal traits. Understand Vietnamese, slang, and teencode when possible.
Judge the current text together with recent_context. Do not flag a keyword without harmful context.
Do not ignore a threat just because it is abbreviated or indirect.
When uncertain, choose action=review, category=ambiguous, and needs_admin_review=true.
Use only these policies: safe, spam, harassment, hate, violence, sexual, self_harm, ambiguous, other.
Keep reason short and useful to an Admin. Evidence must contain only the necessary excerpts, not the full text.
Confidence is the model's confidence, not a calibrated probability.

user_id: {submission.user_id}
channel: {submission.channel}
recent_context:
{context}
current_text: {submission.text[:5000]}
{triage_text}"""

    @staticmethod
    def _retryable(error: Exception) -> bool:
        text = str(error).lower()
        return any(token in text for token in ("429", "quota", "rate", "timeout", "temporar", "503", "500"))

    @staticmethod
    def _classify_error(error: Exception | None) -> tuple[str, str]:
        text = str(error).lower() if error else ""
        if "429" in text or "quota" in text or "rate" in text:
            return "quota", "Gemini API đã đạt giới hạn sử dụng. Vui lòng thử lại sau."
        if "timeout" in text:
            return "timeout", "Gemini API phản hồi quá lâu. Vui lòng thử lại."
        if "404" in text or "not found" in text or "permission" in text or "403" in text:
            return "model_or_permission", "Gemini model không tồn tại hoặc API key không có quyền truy cập."
        if "json" in text or "validation" in text:
            return "invalid_structured_output", "Gemini trả về dữ liệu không đúng cấu trúc moderation."
        return "network_or_api", "Không thể kết nối Gemini API. Vui lòng kiểm tra key và kết nối mạng."
