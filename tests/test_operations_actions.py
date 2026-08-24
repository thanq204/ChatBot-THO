from types import SimpleNamespace
from unittest.mock import Mock

from backend.api import operations_routes
from backend.models.operations import AdminPlatformActionRequest, AdminPlatformActionResponse


def test_incident_action_accepts_postgres_json_dict(monkeypatch) -> None:
    store = Mock()
    store.get_incident.return_value = SimpleNamespace(
        platform="telegram",
        community_id="-100123",
        channel_id="-100123",
    )
    store.get_incident_message.return_value = {
        "message_id": "telegram--100123-42",
        "author_id": "member-1",
        "raw_json": {"message_id": 42, "from": {"first_name": "Simon"}},
    }
    service = Mock()
    service.execute.return_value = AdminPlatformActionResponse(
        action="delete_message",
        platform="telegram",
        target_user_id="member-1",
        target_message_id="42",
        completed=True,
        detail="Deleted",
    )
    service.send_telegram_action_notice.return_value = "Đã gửi thông báo lên nhóm."
    monkeypatch.setattr(operations_routes, "get_operations_store", lambda: store)
    monkeypatch.setattr(operations_routes, "PlatformModerationService", lambda: service)

    result = operations_routes.execute_incident_action(
        "INC-1",
        AdminPlatformActionRequest(
            action="delete_message",
            message_id="telegram--100123-42",
            confirmed=True,
        ),
        reviewer=SimpleNamespace(display_name="Mod Lan", email="lan@example.com", role="mod"),
    )

    assert result.completed is True
    service.execute.assert_called_once_with(
        platform="telegram",
        community_id="-100123",
        channel_id="-100123",
        user_id="member-1",
        message_id="42",
        action="delete_message",
        text="",
        duration_minutes=None,
    )
    service.send_telegram_action_notice.assert_called_once_with(
        chat_id="-100123",
        user_id="member-1",
        target_name="Simon",
        action="delete_message",
        duration_minutes=None,
        actor_name="Mod Lan",
        actor_role="mod",
    )


def test_platform_pull_returns_zero_result_when_realtime_listener_consumed_updates(monkeypatch) -> None:
    connectors = Mock()
    connectors.pull.return_value = []
    monkeypatch.setattr(operations_routes, "get_connectors", lambda: connectors)

    result = operations_routes.pull_platform("telegram", limit=50)

    assert result == {"received": 0, "analyzed": 0, "items": []}
