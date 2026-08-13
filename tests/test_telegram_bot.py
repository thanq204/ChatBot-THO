from unittest.mock import Mock

from backend.config import Settings
from backend.models.operations import MessageDecision
from backend.services.telegram.bot import TelegramRagBot


def build_bot() -> TelegramRagBot:
    return TelegramRagBot(
        Mock(),
        Settings(telegram_bot_token="test-token", telegram_listener_enabled=True),
        pipeline=Mock(),
    )


def test_telegram_private_messages_are_questions() -> None:
    bot = build_bot()

    assert bot._question_to_answer({"chat": {"type": "private"}}, "How do I report spam?") == "How do I report spam?"


def test_telegram_group_requires_command_or_bot_mention() -> None:
    bot = build_bot()
    bot._username = "community_helper"

    assert bot._question_to_answer({"chat": {"type": "group"}}, "hello everyone") is None
    assert bot._question_to_answer({"chat": {"type": "group"}}, "/ask What is the policy?") == "What is the policy?"
    assert bot._question_to_answer({"chat": {"type": "group"}}, "@community_helper help me") == "help me"


def test_telegram_message_is_normalized_for_operations_pipeline() -> None:
    common = TelegramRagBot._common_message(
        {
            "message_id": 42,
            "date": 1_700_000_000,
            "text": "Need help",
            "chat": {"id": -100123, "type": "supergroup"},
            "from": {"id": 9001},
            "reply_to_message": {"message_id": 41},
        }
    )

    assert common.message_id == "telegram--100123-42"
    assert common.platform == "telegram"
    assert common.parent_message_id == "41"
    assert common.text == "Need help"


def test_telegram_realtime_result_passes_through_admin_alert_gate() -> None:
    bot = build_bot()
    result = MessageDecision(
        decision="warn",
        category="harassment",
        severity="medium",
        risk_score=0.76,
        confidence=0.82,
        explanation="Conflict confirmed after three gates.",
        model_used="test-gates",
        send_to_admin=True,
    )
    bot.pipeline.analyze.return_value = result
    bot.telegram_alerts = Mock()
    bot.telegram_alerts.send_alert.return_value = True
    bot.platform_moderation = Mock()
    bot.platform_moderation.send_automatic_warning.return_value = None

    bot._handle_update(
        {
            "update_id": 1,
            "message": {
                "message_id": 42,
                "date": 1_700_000_000,
                "text": "Mày ngu quá",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "is_bot": False},
            },
        }
    )

    bot.telegram_alerts.send_alert.assert_called_once()
    sent_message, sent_result = bot.telegram_alerts.send_alert.call_args.args
    assert sent_message.message_id == "telegram--100123-42"
    assert sent_result.send_to_admin is True
