from datetime import UTC, datetime
from unittest.mock import Mock

from backend.config import Settings
from backend.models.operations import CommonMessage
from backend.services.message_filter import message_is_automated
from backend.services.operations_pipeline import OperationsPipeline
from backend.services.platform_connectors import PlatformConnectors


class _Response:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def _discord_item(message_id: str, *, bot: bool = False, **extra):
    return {
        "id": message_id,
        "content": "nội dung kiểm thử",
        "timestamp": "2026-08-25T10:00:00+00:00",
        "type": 0,
        "author": {"id": f"user-{message_id}", "username": "member", "bot": bot},
        **extra,
    }


def test_discord_rest_pull_keeps_human_messages_only(monkeypatch) -> None:
    payload = [
        _discord_item("104", bot=True),
        _discord_item("103", webhook_id="webhook-1"),
        _discord_item("102", type=7),
        _discord_item("101"),
    ]
    monkeypatch.setattr(
        "backend.services.platform_connectors.requests.get",
        lambda *args, **kwargs: _Response(payload),
    )
    connector = PlatformConnectors(Settings(discord_bot_token="token"))

    messages, newest = connector._discord(20, "channel-1", guild_id="guild-1")

    assert newest == "104"
    assert [message.message_id for message in messages] == ["101"]


def test_telegram_rest_pull_keeps_human_messages_only(monkeypatch) -> None:
    payload = {
        "ok": True,
        "result": [
            {
                "message": {
                    "message_id": 1,
                    "date": 1,
                    "text": "bot output",
                    "chat": {"id": -1001},
                    "from": {"id": 11, "is_bot": True},
                }
            },
            {
                "message": {
                    "message_id": 2,
                    "date": 2,
                    "text": "human input",
                    "chat": {"id": -1001},
                    "from": {"id": 12, "is_bot": False, "first_name": "Lan"},
                }
            },
        ],
    }
    monkeypatch.setattr(
        "backend.services.platform_connectors.requests.get",
        lambda *args, **kwargs: _Response(payload),
    )
    connector = PlatformConnectors(Settings(telegram_bot_token="token"))

    messages = connector._telegram(20)

    assert [message.author_id for message in messages] == ["12"]


def test_pipeline_never_persists_or_alerts_for_automated_output() -> None:
    message = CommonMessage(
        message_id="bot-1",
        platform="discord",
        community_id="guild-1",
        channel_id="channel-1",
        author_id="bot-user",
        text="automated response",
        timestamp=datetime.now(UTC),
        raw={"type": 0, "author": {"id": "bot-user", "bot": True}},
    )
    store = Mock()
    pipeline = OperationsPipeline(store=store, settings=Settings())

    result = pipeline.analyze(message)

    assert message_is_automated(message) is True
    assert result.decision == "allow"
    assert result.send_to_admin is False
    assert result.send_to_member is False
    assert result.model_used == "human-message-filter"
    store.save_message.assert_not_called()
    store.upsert_incident.assert_not_called()


def test_string_false_bot_flag_is_not_treated_as_automated() -> None:
    message = CommonMessage(
        message_id="human-string-flag",
        platform="discord",
        community_id="guild-1",
        channel_id="channel-1",
        author_id="member-1",
        text="human input",
        timestamp=datetime.now(UTC),
        raw={"author_is_bot": "false", "author": {"bot": "false"}},
    )

    assert message_is_automated(message) is False
