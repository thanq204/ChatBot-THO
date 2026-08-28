"""Small connector layer with real read APIs for Discord and Telegram.

The normalizer is shared by every platform. Zalo and Messenger are exposed as
planned connectors until their business/app credentials are supplied.
"""

from __future__ import annotations

import re
import threading
import time
from datetime import UTC, datetime
from typing import Any

import requests

from backend.config import Settings, get_settings
from backend.models.operations import CommonMessage, DiscordChannelOption, PlatformStatus
from backend.services.message_filter import raw_message_is_automated
from backend.services.operations_store import OperationsStore

# Discord channel types that can hold readable text history via the REST API.
_TEXT_CHANNEL_TYPES = {0, 5}  # GUILD_TEXT, GUILD_ANNOUNCEMENT

# Listing channels costs one Discord round-trip per guild — measured at ~1.7s —
# and the dashboard asks for it on every visit to the Community page just to
# populate a filter dropdown. Channels change rarely, and the operator-triggered
# sweep forces a refresh anyway, so this can stay warm for a long while.
_CHANNEL_CACHE_TTL_S = 900.0


class ConnectorError(ValueError):
    pass


class PlatformConnectors:
    def __init__(self, settings: Settings | None = None, store: OperationsStore | None = None) -> None:
        self.settings = settings or get_settings()
        self.store = store
        self._channel_cache: tuple[float, list[DiscordChannelOption]] | None = None
        self._channel_lock = threading.Lock()

    def statuses(self) -> list[PlatformStatus]:
        return [
            PlatformStatus(platform="discord", configured=bool(self.settings.discord_bot_token), connected=bool(self.settings.discord_bot_token), mode="live-read" if self.settings.discord_bot_token else "not-configured", missing_credentials=[] if self.settings.discord_bot_token else ["DISCORD_BOT_TOKEN", "DISCORD_DEFAULT_CHANNEL_ID"], note="Token bot và mã kênh để đọc tin nhắn Discord."),
            PlatformStatus(platform="telegram", configured=bool(self.settings.telegram_bot_token), connected=bool(self.settings.telegram_bot_token), mode="live-read" if self.settings.telegram_bot_token else "not-configured", missing_credentials=[] if self.settings.telegram_bot_token else ["TELEGRAM_BOT_TOKEN", "TELEGRAM_DEFAULT_CHAT_ID"], note="Token bot và mã cuộc trò chuyện để đọc cập nhật Telegram."),
        ]

    def pull(self, platform: str, limit: int = 20, channel_id: str | None = None) -> list[CommonMessage]:
        if platform == "discord":
            if channel_id:
                return self._discord_tracked(limit, channel_id)
            return self._discord_all_channels(limit)
        if platform == "telegram":
            return self._telegram(limit)
        raise ConnectorError(f"Connector {platform} chưa có live read; hãy dùng /messages/ingest với common schema hoặc demo seed.")

    def list_discord_channels(self, refresh: bool = False) -> list[DiscordChannelOption]:
        """Text channels the bot can see, cached for `_CHANNEL_CACHE_TTL_S`.

        Pass `refresh=True` right after the operator adds or renames a channel.
        """
        if not refresh:
            cached = self._channel_cache
            if cached and time.monotonic() - cached[0] < _CHANNEL_CACHE_TTL_S:
                return cached[1]

        with self._channel_lock:
            # A second caller may have refilled the cache while we waited.
            cached = self._channel_cache
            if not refresh and cached and time.monotonic() - cached[0] < _CHANNEL_CACHE_TTL_S:
                return cached[1]
            options = self._fetch_discord_channels()
            self._channel_cache = (time.monotonic(), options)
            return options

    def _fetch_discord_channels(self) -> list[DiscordChannelOption]:
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
        # An operator-triggered sweep should see channels added since the last
        # dashboard visit, so this path pays for a fresh listing.
        channels = self.list_discord_channels(refresh=True)
        if not channels:
            if self.settings.discord_default_channel_id:
                return self._discord_tracked(limit, self.settings.discord_default_channel_id)
            raise ConnectorError("Bot chưa tham gia server Discord nào có kênh để quét.")
        collected: list[CommonMessage] = []
        for channel in channels:
            try:
                collected.extend(self._discord_tracked(limit, channel.channel_id))
            except ConnectorError:
                continue
        return collected

    def _discord_tracked(self, limit: int, channel_id: str) -> list[CommonMessage]:
        """Pull a channel and advance its scan cursor so the next scan only
        fetches messages posted after this one, instead of re-fetching (and
        re-running full AI moderation on) the same recent window every click."""
        if not re.fullmatch(r"\d{5,25}", str(channel_id)):
            raise ConnectorError("Discord channel ID không hợp lệ.")
        since = self.store.get_platform_sync_cursor("discord", channel_id) if self.store else None
        guild_id = self._guild_id_for_channel(channel_id)
        messages, newest_seen_id = self._discord(limit, channel_id, since_message_id=since, guild_id=guild_id)
        if self.store and newest_seen_id:
            self.store.set_platform_sync_cursor("discord", channel_id, newest_seen_id)
        return messages

    def _guild_id_for_channel(self, channel_id: str) -> str:
        """Discord's message-list REST endpoint never includes `guild_id` on
        its items (only Gateway events carry that), so it has to be resolved
        separately. Without a real guild id, `community_id` on every ingested
        message falls back to the literal string "discord" — which then makes
        every moderation action that targets a guild (timeout/kick/ban) call
        Discord with an invalid guild id and fail 100% of the time."""
        for option in self.list_discord_channels():
            if option.channel_id == channel_id:
                return option.guild_id
        if not self.settings.discord_bot_token:
            return "discord"
        response = requests.get(
            f"https://discord.com/api/v10/channels/{channel_id}",
            headers={"Authorization": f"Bot {self.settings.discord_bot_token}"}, timeout=20,
        )
        if response.status_code < 400:
            guild_id = response.json().get("guild_id")
            if guild_id:
                return str(guild_id)
        return "discord"

    def _discord(
        self, limit: int, channel_id: str, since_message_id: str | None = None, guild_id: str = "discord"
    ) -> tuple[list[CommonMessage], str | None]:
        """Fetch messages newer than `since_message_id`, or the newest `limit`
        on a first-ever scan of this channel. Also returns the highest raw
        message id seen on the newest page, even when every item on it was
        content-less (embeds/stickers), so the caller's cursor still advances
        past them instead of re-fetching the same page forever."""
        if not self.settings.discord_bot_token or not channel_id:
            raise ConnectorError("Thiếu DISCORD_BOT_TOKEN hoặc DISCORD_DEFAULT_CHANNEL_ID.")
        collected: list[dict[str, Any]] = []
        before: str | None = None
        target = min(limit, 500)
        since = int(since_message_id) if since_message_id else None
        newest_seen_id: str | None = None
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
            if newest_seen_id is None:
                newest_seen_id = str(items[0]["id"])
            if since is not None:
                fresh = [item for item in items if int(item["id"]) > since]
                collected.extend(fresh)
                if len(fresh) < len(items):
                    # The rest of this page (and everything older) was already
                    # synced on a previous scan; no need to page back further.
                    break
            else:
                collected.extend(items)
            before = items[-1].get("id")
            if len(items) < params["limit"]:
                break
        messages = [
            CommonMessage(
                message_id=item["id"],
                platform="discord",
                community_id=guild_id,
                channel_id=channel_id,
                thread_key=str(item.get("message_reference", {}).get("message_id") or item["id"]),
                parent_message_id=(item.get("message_reference") or {}).get("message_id"),
                author_id=str((item.get("author") or {}).get("id") or "anonymous"),
                author_name=(item.get("author") or {}).get("global_name") or (item.get("author") or {}).get("username"),
                text=item["content"],
                timestamp=self._date(item.get("timestamp")),
                source_url=f"https://discord.com/channels/{guild_id}/{channel_id}/{item['id']}",
                raw=item,
            )
            for item in collected
            if item.get("content") and not raw_message_is_automated("discord", item)
        ]
        return messages, newest_seen_id

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
            if sender.get("is_bot"):
                continue
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
