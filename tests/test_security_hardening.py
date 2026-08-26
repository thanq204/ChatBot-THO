from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from backend.main import MAX_API_REQUEST_BYTES, app
from backend.models.auth import UserPublic
from backend.models.operations import CommonMessage
from backend.services.auth_service import current_user
from backend.services.operations_pipeline import OperationsPipeline
from backend.services.rate_limit import SlidingWindowRateLimiter
from src.ai_models.answering import AnswerComposer


def _message(message_id: str, *, text: str = "Nội dung", **updates) -> CommonMessage:
    values = {
        "message_id": message_id,
        "platform": "discord",
        "community_id": "111111111111111111",
        "channel_id": "222222222222222222",
        "author_id": "333333333333333333",
        "text": text,
        "timestamp": datetime.now(UTC),
    }
    values.update(updates)
    return CommonMessage(**values)


def test_common_message_rejects_unsafe_url_and_oversized_raw_payload() -> None:
    with pytest.raises(ValidationError, match="http/https"):
        _message("unsafe-url", source_url="javascript:alert(1)")

    with pytest.raises(ValidationError, match="50.000"):
        _message("large-raw", raw={"body": "x" * 50_001})


def test_answer_composer_drops_unsafe_source_links() -> None:
    assert AnswerComposer._source_url({"source_url": "javascript:alert(1)"}) is None
    assert AnswerComposer._source_url({"source_url": "https://user:secret@example.com/a"}) is None
    assert AnswerComposer._source_url({"source_url": "https://example.com/a"}) == "https://example.com/a"


def test_context_only_accepts_prior_human_messages_from_same_channel() -> None:
    now = datetime.now(UTC)
    current = _message("current", timestamp=now)
    valid = _message("valid", timestamp=now - timedelta(seconds=2))
    bot = _message(
        "bot",
        timestamp=now - timedelta(seconds=1),
        raw={"author_is_bot": True},
    )
    other_channel = _message(
        "other-channel",
        channel_id="999999999999999999",
        timestamp=now - timedelta(seconds=1),
    )
    future = _message("future", timestamp=now + timedelta(seconds=1))
    pipeline = OperationsPipeline(store=object())

    assert pipeline._sanitized_context(current, [bot, other_channel, future, valid]) == [valid]


def test_sliding_window_rate_limiter_rejects_excess_calls() -> None:
    limiter = SlidingWindowRateLimiter()

    assert limiter.check("test", "member", limit=2, window_seconds=60) == 0
    assert limiter.check("test", "member", limit=2, window_seconds=60) == 0
    assert limiter.check("test", "member", limit=2, window_seconds=60) >= 1


@pytest.mark.asyncio
async def test_request_safety_rejects_oversized_api_content_length(client) -> None:
    response = await client.post(
        "/api/v1/messages/analyze",
        content=b"{}",
        headers={"Content-Length": str(MAX_API_REQUEST_BYTES + 1)},
    )

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_security_headers_are_attached(client) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"


@pytest.mark.asyncio
async def test_mod_cannot_call_admin_only_knowledge_endpoint(client) -> None:
    moderator = UserPublic(
        user_id=UUID("00000000-0000-0000-0000-000000000002"),
        email="mod@test.local",
        display_name="Test Mod",
        role="mod",
        is_root_admin=False,
        is_active=True,
        created_at=datetime.now(UTC),
    )
    app.dependency_overrides[current_user] = lambda: moderator

    response = await client.get("/api/v1/faqs")

    assert response.status_code == 403
