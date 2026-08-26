from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest

from backend.config import Settings
from backend.models.operations import AdminPlatformActionResponse, CommonMessage, MessageDecision
from backend.services.platform_moderation import PlatformModerationError, PlatformModerationService


def _response(status_code: int = 200, payload: dict | None = None) -> Mock:
    response = Mock(status_code=status_code, ok=status_code < 400)
    response.json.return_value = payload or {"ok": True}
    return response


def test_discord_delete_uses_case_channel_and_message() -> None:
    service = PlatformModerationService(Settings(discord_bot_token="token"))
    with patch("backend.services.platform_moderation.requests.delete", return_value=_response()) as delete:
        result = service.execute(
            platform="discord",
            community_id="111111111111111111",
            channel_id="222222222222222222",
            user_id="333333333333333333",
            message_id="444444444444444444",
            action="delete_message",
            text="",
            duration_minutes=None,
        )

    assert result.completed is True
    assert "/channels/222222222222222222/messages/444444444444444444" in delete.call_args.args[0]


def test_telegram_dm_uses_member_id_not_group_chat() -> None:
    service = PlatformModerationService(Settings(telegram_bot_token="token"))
    with patch("backend.services.platform_moderation.requests.post", return_value=_response()) as post:
        result = service.execute(platform="telegram", community_id="group", channel_id="-10099", user_id="12345", message_id=None, action="dm", text="Please follow the rules.", duration_minutes=None)

    assert result.completed is True
    assert post.call_args.kwargs["json"]["chat_id"] == "12345"


def test_timeout_requires_duration() -> None:
    service = PlatformModerationService(Settings(discord_bot_token="token"))
    with pytest.raises(PlatformModerationError, match="duration_minutes"):
        service.execute(
            platform="discord",
            community_id="111111111111111111",
            channel_id="222222222222222222",
            user_id="333333333333333333",
            message_id=None,
            action="timeout",
            text="",
            duration_minutes=None,
        )


def test_discord_action_rejects_path_injection_ids() -> None:
    service = PlatformModerationService(Settings(discord_bot_token="token"))

    with pytest.raises(PlatformModerationError, match="không hợp lệ"):
        service.execute(
            platform="discord",
            community_id="111111111111111111",
            channel_id="../users/@me",
            user_id="333333333333333333",
            message_id="444444444444444444",
            action="delete_message",
            text="",
            duration_minutes=None,
        )


def test_telegram_permanent_ban_is_not_available() -> None:
    service = PlatformModerationService(Settings(telegram_bot_token="token"))
    with pytest.raises(PlatformModerationError, match="permanent-ban"):
        service.execute(
            platform="telegram",
            community_id="group",
            channel_id="-10099",
            user_id="12345",
            message_id=None,
            action="ban",
            text="",
            duration_minutes=None,
        )


def test_telegram_confirmed_action_notifies_member_and_group_with_reviewer() -> None:
    service = PlatformModerationService(Settings(telegram_bot_token="token"))
    with patch("backend.services.platform_moderation.requests.post", return_value=_response()) as post:
        detail = service.send_telegram_action_notice(
            chat_id="-10099",
            user_id="12345",
            target_name="Ngọc",
            action="timeout",
            duration_minutes=60,
            actor_name="Minh",
            actor_role="mod",
        )

    assert "riêng" in detail and "nhóm" in detail
    assert [call.kwargs["json"]["chat_id"] for call in post.call_args_list] == ["12345", "-10099"]
    assert "bởi Mod Minh" in post.call_args_list[0].kwargs["json"]["text"]


def test_automatic_warning_only_sends_dm_for_warn_decision() -> None:
    service = PlatformModerationService(Settings(moderation_auto_warn_dm_enabled=True))
    service.execute = Mock(return_value=AdminPlatformActionResponse(action="dm", platform="telegram", target_user_id="member", completed=True, detail="sent"))
    store = Mock()
    message = CommonMessage(message_id="telegram-1", platform="telegram", community_id="group", channel_id="group", author_id="member", text="bad words", timestamp=datetime.now(UTC))
    decision = MessageDecision(decision="warn", category="harassment", severity="medium", risk_score=0.7, confidence=0.8, explanation="Personal attack", model_used="test", incident_id="INC-1")

    result = service.send_automatic_warning(message, decision, store)

    assert result and result.completed is True
    assert service.execute.call_args.kwargs["action"] == "dm"
    store.add_audit.assert_called_once()


def test_automatic_warning_sends_dm_for_hide_and_review() -> None:
    service = PlatformModerationService(Settings(moderation_auto_warn_dm_enabled=True))
    service.execute = Mock(return_value=AdminPlatformActionResponse(action="dm", platform="telegram", target_user_id="member", completed=True, detail="sent"))
    store = Mock()
    message = CommonMessage(message_id="telegram-1", platform="telegram", author_id="member", text="spam", timestamp=datetime.now(UTC))
    decision = MessageDecision(decision="hide", category="spam", severity="high", risk_score=0.9, confidence=0.9, explanation="Spam", model_used="test")

    assert service.send_automatic_warning(message, decision, store).completed is True
    review = decision.model_copy(update={"decision": "hold_for_review"})
    assert service.send_automatic_warning(message, review, store).completed is True
    assert service.execute.call_count == 2
    assert store.add_audit.call_count == 2


def test_discord_dm_is_suppressed_when_three_gates_reject_notification() -> None:
    service = PlatformModerationService(Settings(moderation_auto_warn_dm_enabled=True))
    service.execute = Mock()
    store = Mock()
    message = CommonMessage(
        message_id="discord-duplicate",
        platform="discord",
        community_id="guild",
        channel_id="channel",
        author_id="member",
        text="repeated case",
        timestamp=datetime.now(UTC),
    )
    decision = MessageDecision(
        decision="hold_for_review",
        category="violence",
        severity="critical",
        risk_score=0.9,
        confidence=0.9,
        explanation="Case đã được Gate 3 chặn thông báo lặp.",
        model_used="test",
        send_to_admin=False,
        send_to_member=False,
        already_marked=True,
    )

    result = service.send_automatic_warning(message, decision, store)

    assert result is None
    service.execute.assert_not_called()
    store.add_audit.assert_not_called()
