from unittest.mock import Mock, patch

import pytest

from backend.config import Settings
from backend.services.platform_moderation import PlatformModerationError, PlatformModerationService


def _response(status_code: int = 200, payload: dict | None = None) -> Mock:
    response = Mock(status_code=status_code, ok=status_code < 400)
    response.json.return_value = payload or {"ok": True}
    return response


def test_discord_delete_uses_case_channel_and_message() -> None:
    service = PlatformModerationService(Settings(discord_bot_token="token"))
    with patch("backend.services.platform_moderation.requests.delete", return_value=_response()) as delete:
        result = service.execute(platform="discord", community_id="guild-1", channel_id="channel-1", user_id="member-1", message_id="message-1", action="delete_message", text="", duration_minutes=None)

    assert result.completed is True
    assert "/channels/channel-1/messages/message-1" in delete.call_args.args[0]


def test_telegram_dm_uses_member_id_not_group_chat() -> None:
    service = PlatformModerationService(Settings(telegram_bot_token="token"))
    with patch("backend.services.platform_moderation.requests.post", return_value=_response()) as post:
        result = service.execute(platform="telegram", community_id="group", channel_id="-10099", user_id="12345", message_id=None, action="dm", text="Please follow the rules.", duration_minutes=None)

    assert result.completed is True
    assert post.call_args.kwargs["json"]["chat_id"] == "12345"


def test_timeout_requires_duration() -> None:
    service = PlatformModerationService(Settings(discord_bot_token="token"))
    with pytest.raises(PlatformModerationError, match="duration_minutes"):
        service.execute(platform="discord", community_id="guild", channel_id="channel", user_id="member", message_id=None, action="timeout", text="", duration_minutes=None)
