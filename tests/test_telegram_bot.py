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
            "from": {"id": 9001, "first_name": "Simon"},
            "reply_to_message": {"message_id": 41},
        }
    )

    assert common.message_id == "telegram--100123-42"
    assert common.platform == "telegram"
    assert common.parent_message_id == "41"
    assert common.author_name == "Simon"
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


def test_telegram_replies_to_the_message_that_asked_the_question() -> None:
    bot = build_bot()
    bot.chat = Mock()
    bot.chat.reply.return_value = Mock(answer="Hello", moderation=None, stage="rule")
    bot._send_message = Mock()

    bot._handle_update(
        {
            "message": {
                "message_id": 42,
                "date": 1_700_000_000,
                "text": "/help",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "is_bot": False},
            }
        }
    )

    bot._send_message.assert_called_once_with("-100123", "Hello", reply_to_message_id=42)


def test_telegram_custom_command_is_answered_when_scoped_to_telegram() -> None:
    bot = build_bot()
    bot.store.get_command_content.return_value = Mock(platforms=["telegram"])

    assert bot._question_to_answer({"chat": {"type": "group"}}, "/gioithieu") == "/gioithieu"


def test_telegram_deletes_a_known_blocked_link_before_answering() -> None:
    bot = build_bot()
    bot.store.find_blocked_links.return_value = [Mock(canonical_url="https://bad.example/")]
    bot._delete_message = Mock(return_value=True)
    bot.pipeline.analyze.return_value = Mock(incident_id="INC-1")
    bot.telegram_alerts = Mock()

    bot._handle_update(
        {
            "message": {
                "message_id": 42,
                "date": 1_700_000_000,
                "text": "https://bad.example/",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "is_bot": False},
            }
        }
    )

    bot._delete_message.assert_called_once_with("-100123", 42)
    bot.telegram_alerts.send_blocked_link_alert.assert_called_once()


def test_telegram_helpful_reactions_award_reputation_at_threshold() -> None:
    bot = build_bot()
    bot.settings.reputation_helpful_reaction_threshold = 1
    common = TelegramRagBot._common_message(
        {
            "message_id": 42,
            "date": 1_700_000_000,
            "text": "Useful answer",
            "chat": {"id": -100123, "type": "supergroup"},
            "from": {"id": 9001},
        }
    )
    bot._message_cache[("-100123", "42")] = common

    bot._handle_reaction_update(
        {
            "chat": {"id": -100123},
            "message_id": 42,
            "user": {"id": 9002},
            "old_reaction": [],
            "new_reaction": [{"type": "emoji", "emoji": "👍"}],
        }
    )

    bot.store.award_helpful_reputation.assert_called_once_with(common, 1, reaction_emoji="👍")


def test_telegram_anonymous_actor_reaction_awards_reputation() -> None:
    bot = build_bot()
    bot.settings.reputation_helpful_reaction_threshold = 1
    common = TelegramRagBot._common_message(
        {
            "message_id": 42,
            "date": 1_700_000_000,
            "text": "Useful answer",
            "chat": {"id": -100123, "type": "supergroup"},
            "from": {"id": 9001},
        }
    )
    bot._message_cache[("-100123", "42")] = common

    bot._handle_reaction_update(
        {
            "chat": {"id": -100123},
            "message_id": 42,
            "actor_chat": {"id": -100987},
            "old_reaction": [],
            "new_reaction": [{"type": "emoji", "emoji": "👍"}],
        }
    )

    bot.store.award_helpful_reputation.assert_called_once_with(common, 1, reaction_emoji="👍")


def test_telegram_anonymous_reaction_count_awards_reputation_at_threshold() -> None:
    bot = build_bot()
    bot.settings.reputation_helpful_reaction_threshold = 1
    common = TelegramRagBot._common_message(
        {
            "message_id": 42,
            "date": 1_700_000_000,
            "text": "Useful answer",
            "chat": {"id": -100123, "type": "supergroup"},
            "from": {"id": 9001},
        }
    )
    bot._message_cache[("-100123", "42")] = common

    bot._handle_reaction_count_update(
        {
            "chat": {"id": -100123},
            "message_id": 42,
            "reactions": [{"type": {"type": "emoji", "emoji": "👍"}, "total_count": 1}],
        }
    )

    bot.store.award_helpful_reputation.assert_called_once_with(common, 1, reaction_emoji="👍")


def test_telegram_reaction_loads_a_persisted_message_after_restart() -> None:
    bot = build_bot()
    bot.settings.reputation_helpful_reaction_threshold = 1
    common = TelegramRagBot._common_message(
        {
            "message_id": 42,
            "date": 1_700_000_000,
            "text": "Useful answer",
            "chat": {"id": -100123, "type": "supergroup"},
            "from": {"id": 9001},
        }
    )
    bot.store.get_message.return_value = common

    bot._handle_reaction_count_update(
        {
            "chat": {"id": -100123},
            "message_id": 42,
            "reactions": [{"type": {"type": "emoji", "emoji": "👍"}, "total_count": 1}],
        }
    )

    bot.store.get_message.assert_called_once_with("telegram--100123-42")
    bot.store.award_helpful_reputation.assert_called_once_with(common, 1, reaction_emoji="👍")
