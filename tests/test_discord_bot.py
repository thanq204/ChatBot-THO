from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

from backend.config import Settings
from backend.services.discord.bot import DiscordRagBot


def test_discord_mention_is_removed_before_chat_routing() -> None:
    store = Mock()
    store.list_command_content.return_value = [
        Mock(command="daily", description="Daily task", platforms=["discord"])
    ]
    bot = DiscordRagBot(store, Settings(discord_rag_llm_enabled=False), pipeline=Mock())
    message = SimpleNamespace(
        id=1,
        guild=SimpleNamespace(id=2),
        channel=SimpleNamespace(id=3),
        author=SimpleNamespace(id=4),
        reference=None,
        created_at=datetime.now(UTC),
        jump_url=None,
        content="<@123> /help",
    )

    common = bot._common_message(message)
    routed = common.model_copy(update={"text": "/help"})
    outcome = bot.chat.reply(routed)

    assert outcome.stage == "rule"
    assert "/daily" in outcome.answer


def test_empty_discord_mention_returns_input_prompt() -> None:
    bot = DiscordRagBot(Mock(), Settings(discord_rag_llm_enabled=False), pipeline=Mock())
    message = SimpleNamespace(
        id=2, guild=SimpleNamespace(id=2), channel=SimpleNamespace(id=3),
        author=SimpleNamespace(id=4), reference=None, created_at=datetime.now(UTC),
        jump_url=None, content="<@123>",
    )

    outcome = bot.chat.reply(bot._common_message(message).model_copy(update={"text": " "}))

    assert outcome.stage == "rule"
    assert "nhập câu hỏi" in outcome.answer


def test_realtime_listener_accepts_human_member_only() -> None:
    client_user = SimpleNamespace(id=99)
    human = SimpleNamespace(
        author=SimpleNamespace(id=4, bot=False),
        webhook_id=None,
        application_id=None,
        is_system=lambda: False,
    )
    bot_output = SimpleNamespace(
        author=SimpleNamespace(id=99, bot=True),
        webhook_id=None,
        application_id=None,
        is_system=lambda: False,
    )
    webhook = SimpleNamespace(
        author=SimpleNamespace(id=5, bot=False),
        webhook_id=123,
        application_id=None,
        is_system=lambda: False,
    )
    application = SimpleNamespace(
        author=SimpleNamespace(id=6, bot=False),
        webhook_id=None,
        application_id=456,
        is_system=lambda: False,
    )
    system = SimpleNamespace(
        author=SimpleNamespace(id=7, bot=False),
        webhook_id=None,
        application_id=None,
        is_system=lambda: True,
    )

    assert DiscordRagBot._is_member_message(human, client_user) is True
    assert DiscordRagBot._is_member_message(bot_output, client_user) is False
    assert DiscordRagBot._is_member_message(webhook, client_user) is False
    assert DiscordRagBot._is_member_message(application, client_user) is False
    assert DiscordRagBot._is_member_message(system, client_user) is False
