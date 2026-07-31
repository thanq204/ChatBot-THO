import pytest

from src.config import Settings
from src.models.moderation import GeminiModerationOutput, MemberSubmission
from src.services.gemini_moderation import GeminiModerationError, GeminiStageResult
from src.services.moderation import ModerationConfigurationError, ModerationEngine


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "context", "action", "category"),
    [
        ("Cảm ơn mọi người đã hỗ trợ mình hoàn thành bài.", [], "allow", "safe"),
        ("Bấm vào link này để nhận tiền miễn phí, chỉ còn 5 phút.", [], "hide", "spam"),
        ("Mày ngu thế thì nghỉ khỏi nhóm đi.", [], "warn", "harassment"),
        ("Làm ăn kiểu này thì nghỉ luôn đi.", ["Bạn gửi lại file giúp mình nhé."], "review", "ambiguous"),
        ("Ra đường gặp tao là biết.", ["Bọn mình đang đùa với nhau về trận game tối qua."], "review", "ambiguous"),
    ],
)
async def test_mock_moderation_cases(text, context, action, category):
    engine = ModerationEngine(Settings(moderation_mode="mock", gemini_api_key=""))
    result = await engine.moderate(MemberSubmission(user_id="U001", text=text, recent_context=context))

    assert result.mode == "mock"
    assert result.action == action
    assert result.category == category
    assert result.needs_admin_review is (action == "review")


@pytest.mark.asyncio
async def test_missing_key_is_a_clear_configuration_error():
    engine = ModerationEngine(Settings(moderation_mode="gemini", gemini_api_key=""))

    with pytest.raises(ModerationConfigurationError, match="GEMINI_API_KEY"):
        await engine.moderate(MemberSubmission(user_id="U001", text="Xin chào mọi người"))


@pytest.mark.asyncio
async def test_two_stage_gemini_pipeline_uses_review_model_for_ambiguous_content(monkeypatch):
    engine = ModerationEngine(Settings(moderation_mode="gemini", gemini_api_key="configured"))
    calls = []

    def triage(submission):
        calls.append("triage")
        return GeminiStageResult(
            output=GeminiModerationOutput(
                action="review", category="ambiguous", risk_level="medium", policy_id=None,
                reason="Context is ambiguous.", confidence=0.62, needs_admin_review=True,
                evidence=[submission.text],
            ),
            model_used="gemini-3.1-flash-lite",
        )

    def review(submission, triage_result):
        calls.append("review")
        return GeminiStageResult(
            output=GeminiModerationOutput(
                action="review", category="ambiguous", risk_level="medium", policy_id=None,
                reason="Admin should decide because intent remains unclear.", confidence=0.67,
                needs_admin_review=True, evidence=[submission.text],
            ),
            model_used="gemini-3.6-flash",
        )

    monkeypatch.setattr(engine.gemini, "moderate_with_triage", triage)
    monkeypatch.setattr(engine.gemini, "review_ambiguous_content", review)

    result = await engine.moderate(MemberSubmission(user_id="U001", text="Ra đường gặp tao là biết."))

    assert calls == ["triage", "review"]
    assert result.mode == "gemini"
    assert result.model_used == "gemini-3.6-flash"
    assert result.action == "review"


@pytest.mark.asyncio
async def test_gemini_policy_id_can_be_descriptive(monkeypatch):
    engine = ModerationEngine(Settings(moderation_mode="gemini", gemini_api_key="configured"))
    monkeypatch.setattr(
        engine.gemini,
        "moderate_with_triage",
        lambda submission: GeminiStageResult(
            output=GeminiModerationOutput(
                action="warn", category="harassment", risk_level="high",
                policy_id="harassment_policy_001", reason="Personal attack.", confidence=0.95,
                needs_admin_review=False, evidence=[submission.text],
            ),
            model_used="gemini-3.1-flash-lite",
        ),
    )

    result = await engine.moderate(MemberSubmission(user_id="U001", text="You are being rude."))

    assert result.policy_id == "harassment_policy_001"
    assert result.action == "warn"


@pytest.mark.asyncio
async def test_mock_fallback_requires_explicit_flag(monkeypatch):
    engine = ModerationEngine(Settings(moderation_mode="gemini", gemini_api_key="configured", allow_mock_fallback=True))
    monkeypatch.setattr(
        engine.gemini,
        "moderate_with_triage",
        lambda submission: (_ for _ in ()).throw(GeminiModerationError("quota", "Quota exceeded.")),
    )

    result = await engine.moderate(MemberSubmission(user_id="U001", text="Xin chào mọi người"))

    assert result.mode == "mock-fallback"
    assert result.model_used == "mock-fallback"
    assert result.fallback_used is True
    assert result.fallback_reason is not None


@pytest.mark.asyncio
async def test_invalid_gemini_output_is_sent_to_review(monkeypatch):
    engine = ModerationEngine(Settings(moderation_mode="gemini", gemini_api_key="configured"))
    monkeypatch.setattr(
        engine.gemini,
        "moderate_with_triage",
        lambda submission: (_ for _ in ()).throw(
            GeminiModerationError("invalid_structured_output", "Invalid JSON")
        ),
    )

    result = await engine.moderate(MemberSubmission(user_id="U001", text="Có thể là câu nói đùa."))

    assert result.action == "review"
    assert result.category == "ambiguous"
    assert result.needs_admin_review is True
    assert result.fallback_used is False
