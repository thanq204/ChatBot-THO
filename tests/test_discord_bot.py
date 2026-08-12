from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

from backend.config import Settings
from backend.services.discord.bot import DiscordRagBot


def test_discord_mention_is_removed_before_chat_routing() -> None:
    bot = DiscordRagBot(Mock(), Settings(discord_rag_llm_enabled=False), pipeline=Mock())
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
