from datetime import UTC, datetime
from unittest.mock import Mock, patch

from backend.config import Settings
from backend.models.operations import CommonMessage, MessageDecision
from backend.services.telegram.alerts import TelegramAlertSender


def _message() -> CommonMessage:
    return CommonMessage(
        message_id="telegram--100123-42",
        platform="telegram",
        community_id="-100123",
        channel_id="-100123",
        author_id="user-1",
        text="Nội dung cần xem xét",
        timestamp=datetime.now(UTC),
    )


def _decision() -> MessageDecision:
    return MessageDecision(
        decision="hold_for_review",
        category="violence",
        severity="critical",
        risk_score=0.9,
        confidence=0.9,
        explanation="Cần Admin xem xét.",
        model_used="test",
        send_to_admin=True,
    )


def test_moderation_alert_is_sent_to_private_admin_chat_not_group() -> None:
    sender = TelegramAlertSender(
        Settings(
            telegram_alerts_enabled=True,
            telegram_bot_token="token",
            telegram_default_chat_id="-100123",
            telegram_admin_chat_id="998877",
        )
    )
    response = Mock()
    response.json.return_value = {"ok": True}
    response.raise_for_status.return_value = None

    with patch("backend.services.telegram.alerts.requests.post", return_value=response) as post:
        assert sender.send_alert(_message(), _decision()) is True

    assert post.call_args.kwargs["json"]["chat_id"] == "998877"
    assert post.call_args.kwargs["json"]["chat_id"] != "-100123"


def test_moderation_alert_is_disabled_without_private_admin_chat() -> None:
    sender = TelegramAlertSender(
        Settings(
            telegram_alerts_enabled=True,
            telegram_bot_token="token",
            telegram_default_chat_id="-100123",
            telegram_admin_chat_id="",
        )
    )

    assert sender.configured is False
