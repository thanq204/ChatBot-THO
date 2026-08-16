"""Small connector layer with real read APIs for Discord and Telegram.

The normalizer is shared by every platform. Zalo and Messenger are exposed as
planned connectors until their business/app credentials are supplied.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import requests

from backend.config import Settings, get_settings
from backend.models.operations import CommonMessage, DiscordChannelOption, PlatformStatus

# Discord channel types that can hold readable text history via the REST API.
_TEXT_CHANNEL_TYPES = {0, 5}  # GUILD_TEXT, GUILD_ANNOUNCEMENT


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
            if channel_id:
                return self._discord(limit, channel_id)
            return self._discord_all_channels(limit)
        if platform == "telegram":
            return self._telegram(limit)
        raise ConnectorError(f"Connector {platform} chưa có live read; hãy dùng /messages/ingest với common schema hoặc demo seed.")

    def list_discord_channels(self) -> list[DiscordChannelOption]:
        if not self.settings.discord_bot_token:
            raise ConnectorError("Thiếu DISCORD_BOT_TOKEN.")
        headers = {"Authorization": f"Bot {self.settings.discord_bot_token}"}
        guilds_response = requests.get("https://discord.com/api/v10/users/@me/guilds", headers=headers, timeout=20)
        if guilds_response.status_code >= 400:
            raise ConnectorError(f"Discord API trả về HTTP {guilds_response.status_code} khi lấy danh sách server.")
        options: list[DiscordChannelOption] = []
        for guild in guilds_response.json():
            channels_response = requests.get(
                f"https://discord.com/api/v10/guilds/{guild['id']}/channels", headers=headers, timeout=20
            )
            if channels_response.status_code >= 400:
                continue
            for channel in channels_response.json():
                if channel.get("type") not in _TEXT_CHANNEL_TYPES:
                    continue
                options.append(
                    DiscordChannelOption(
                        guild_id=str(guild["id"]),
                        guild_name=guild.get("name") or guild["id"],
                        channel_id=str(channel["id"]),
                        channel_name=channel.get("name") or channel["id"],
                    )
                )
        return options

    def _discord_all_channels(self, limit: int) -> list[CommonMessage]:
        channels = self.list_discord_channels()
        if not channels:
            if self.settings.discord_default_channel_id:
                return self._discord(limit, self.settings.discord_default_channel_id)
            raise ConnectorError("Bot chưa tham gia server Discord nào có kênh để quét.")
        collected: list[CommonMessage] = []
        for channel in channels:
            try:
                collected.extend(self._discord(limit, channel.channel_id))
            except ConnectorError:
                continue
        return collected

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
        return [CommonMessage(message_id=item["id"], platform="discord", community_id=str(item.get("guild_id") or "discord"), channel_id=channel_id, thread_key=str(item.get("message_reference", {}).get("message_id") or item["id"]), parent_message_id=(item.get("message_reference") or {}).get("message_id"), author_id=str((item.get("author") or {}).get("id") or "anonymous"), author_name=(item.get("author") or {}).get("global_name") or (item.get("author") or {}).get("username"), text=item.get("content") or "[non-text message]", timestamp=self._date(item.get("timestamp")), source_url=f"https://discord.com/channels/{item.get('guild_id','@me')}/{channel_id}/{item['id']}", raw=item) for item in collected if item.get("content")]

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
            sender = item.get("from") or {}
            display_name = sender.get("username") or " ".join(filter(None, [sender.get("first_name"), sender.get("last_name")])) or None
            messages.append(CommonMessage(message_id=f"tg-{item.get('chat', {}).get('id')}-{item.get('message_id')}", platform="telegram", community_id=str(chat.get("id") or "telegram"), channel_id=str(chat.get("id") or "general"), thread_key=str(item.get("reply_to_message", {}).get("message_id") or item.get("message_id")), parent_message_id=(item.get("reply_to_message") or {}).get("message_id"), author_id=str(sender.get("id") or "anonymous"), author_name=display_name, text=item["text"], timestamp=datetime.fromtimestamp(item.get("date", 0), UTC), source_url=self._telegram_message_link(chat, item.get("message_id")), raw=update))
        return messages

    @staticmethod
    def _telegram_message_link(chat: dict[str, Any], message_id: Any) -> str | None:
        """Best-effort deep link so Admin can jump straight to the message.

        Public chats resolve with their @username. Private supergroups/channels
        still work via the /c/ scheme using their internal id (chat id minus
        the -100 prefix); it only opens for members already in the chat.
        Legacy basic groups (not yet upgraded to a supergroup) have no working
        link format, so this returns None for those.
        """
        username = chat.get("username")
        if username:
            return f"https://t.me/{username}/{message_id}"
        chat_id = str(chat.get("id") or "")
        if chat_id.startswith("-100"):
            return f"https://t.me/c/{chat_id[4:]}/{message_id}"
        return None

    @staticmethod
    def _date(value: Any) -> datetime:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value else datetime.now(UTC)
