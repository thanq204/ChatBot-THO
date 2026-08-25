"""Shared checks that keep automated platform output out of human moderation."""

from __future__ import annotations

from typing import Any

from backend.models.operations import CommonMessage


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return False


def raw_message_is_automated(platform: str, raw: dict[str, Any] | None) -> bool:
    payload = _mapping(raw)
    if _truthy(payload.get("author_is_bot")):
        return True

    if platform == "discord":
        message = _mapping(payload.get("message")) or payload
        author = _mapping(message.get("author"))
        if _truthy(author.get("bot")):
            return True
        if message.get("webhook_id") or message.get("application_id"):
            return True
        message_type = message.get("type")
        if message_type is not None:
            try:
                if int(message_type) not in {0, 19}:
                    return True
            except (TypeError, ValueError):
                return True

    if platform == "telegram":
        message = (
            _mapping(payload.get("message"))
            or _mapping(payload.get("edited_message"))
            or payload
        )
        if _truthy(_mapping(message.get("from")).get("is_bot")):
            return True

    return False


def message_is_automated(message: CommonMessage) -> bool:
    return raw_message_is_automated(message.platform, message.raw)
