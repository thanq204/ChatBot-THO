"""Small connector layer with real read APIs for Discord and Telegram.

The normalizer is shared by every platform. Zalo and Messenger are exposed as
planned connectors until their business/app credentials are supplied.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import requests

from src.config import Settings, get_settings
from src.models.operations import CommonMessage, PlatformStatus


class ConnectorError(ValueError):
    pass


class PlatformConnectors:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def statuses(self) -> list[PlatformStatus]:
        return [
            PlatformStatus(platform="discord", configured=bool(self.settings.discord_bot_token), connected=bool(self.settings.discord_bot_token), mode="live-read" if self.settings.discord_bot_token else "not-configured", missing_credentials=[] if self.settings.discord_bot_token else ["DISCORD_BOT_TOKEN", "DISCORD_DEFAULT_CHANNEL_ID"], note="Bot token + channel ID để đọc message Discord."),
            PlatformStatus(platform="telegram", configured=bool(self.settings.telegram_bot_token), connected=bool(self.settings.telegram_bot_token), mode="live-read" if self.settings.telegram_bot_token else "not-configured", missing_credentials=[] if self.settings.telegram_bot_token else ["TELEGRAM_BOT_TOKEN", "TELEGRAM_DEFAULT_CHAT_ID"], note="Bot token + chat ID để đọc Telegram updates."),
            PlatformStatus(platform="zalo", configured=bool(self.settings.zalo_access_token), connected=False, mode="planned", missing_credentials=[] if self.settings.zalo_access_token else ["ZALO_ACCESS_TOKEN"], note="POC interface; cần Official Account credentials và scope phù hợp."),
            PlatformStatus(platform="messenger", configured=bool(self.settings.messenger_page_access_token), connected=False, mode="planned", missing_credentials=[] if self.settings.messenger_page_access_token else ["MESSENGER_PAGE_ACCESS_TOKEN"], note="POC interface; cần Meta Page token/webhook."),
            PlatformStatus(platform="web", configured=True, connected=True, mode="local", missing_credentials=[], note="Web ingest local luôn sẵn sàng."),
        ]

    def pull(self, platform: str, limit: int = 20, channel_id: str | None = None) -> list[CommonMessage]:
        if platform == "discord":
            return self._discord(limit, channel_id or self.settings.discord_default_channel_id)
        if platform == "telegram":
            return self._telegram(limit)
        raise ConnectorError(f"Connector {platform} chưa có live read; hãy dùng /messages/ingest với common schema hoặc demo seed.")

    def _discord(self, limit: int, channel_id: str) -> list[CommonMessage]:
        if not self.settings.discord_bot_token or not channel_id:
            raise ConnectorError("Thiếu DISCORD_BOT_TOKEN hoặc DISCORD_DEFAULT_CHANNEL_ID.")
        collected: list[dict[str, Any]] = []
        before: str | None = None
        target = min(limit, 500)
        while len(collected) < target:
            params: dict[str, Any] = {"limit": min(100, target - len(collected))}
            if before:
                params["before"] = before
            response = requests.get(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                headers={"Authorization": f"Bot {self.settings.discord_bot_token}"},
                params=params, timeout=20,
            )
            if response.status_code >= 400:
                raise ConnectorError(f"Discord API trả về HTTP {response.status_code}.")
            items = response.json()
            if not items:
                break
            collected.extend(items)
            before = items[-1].get("id")
            if len(items) < params["limit"]:
                break
        return [CommonMessage(message_id=item["id"], platform="discord", community_id=str(item.get("guild_id") or "discord"), channel_id=channel_id, thread_key=str(item.get("message_reference", {}).get("message_id") or item["id"]), parent_message_id=(item.get("message_reference") or {}).get("message_id"), author_id=str((item.get("author") or {}).get("id") or "anonymous"), text=item.get("content") or "[non-text message]", timestamp=self._date(item.get("timestamp")), source_url=f"https://discord.com/channels/{item.get('guild_id','@me')}/{channel_id}/{item['id']}", raw=item) for item in collected if item.get("content")]

    def _telegram(self, limit: int) -> list[CommonMessage]:
        if not self.settings.telegram_bot_token:
            raise ConnectorError("Thiếu TELEGRAM_BOT_TOKEN.")
        response = requests.get(f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/getUpdates", params={"limit": min(limit, 100), "allowed_updates": '["message"]'}, timeout=20)
        if response.status_code >= 400 or not response.json().get("ok"):
            raise ConnectorError("Telegram API không trả về updates hợp lệ.")
        messages = []
        for update in response.json().get("result", []):
            item = update.get("message") or {}
            if not item.get("text"):
                continue
            chat = item.get("chat") or {}
            messages.append(CommonMessage(message_id=f"tg-{item.get('chat', {}).get('id')}-{item.get('message_id')}", platform="telegram", community_id=str(chat.get("id") or "telegram"), channel_id=str(chat.get("id") or "general"), thread_key=str(item.get("reply_to_message", {}).get("message_id") or item.get("message_id")), parent_message_id=(item.get("reply_to_message") or {}).get("message_id"), author_id=str((item.get("from") or {}).get("id") or "anonymous"), text=item["text"], timestamp=datetime.fromtimestamp(item.get("date", 0), UTC), raw=update))
        return messages

    @staticmethod
    def _date(value: Any) -> datetime:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value else datetime.now(UTC)
