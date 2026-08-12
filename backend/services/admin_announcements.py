"""Explicit Admin-only broadcast delivery for configured community channels."""

from __future__ import annotations

from backend.config import Settings, get_settings
from backend.models.operations import AnnouncementDelivery


class AdminAnnouncementSender:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def send(self, message: str, target: str) -> AnnouncementDelivery:
        if target == "discord":
            return self._discord(message)
        if target == "telegram":
            return self._telegram(message)
        raise ValueError(f"Unsupported announcement target: {target}")

    def _discord(self, message: str) -> AnnouncementDelivery:
        if not self.settings.discord_bot_token or not self.settings.discord_default_channel_id:
            return AnnouncementDelivery(platform="discord", delivered=False, detail="DISCORD_BOT_TOKEN hoặc DISCORD_DEFAULT_CHANNEL_ID chưa được cấu hình.")
        try:
            import requests

            response = requests.post(
                f"https://discord.com/api/v10/channels/{self.settings.discord_default_channel_id}/messages",
                headers={"Authorization": f"Bot {self.settings.discord_bot_token}"},
                json={"content": message}, timeout=20,
            )
            if response.status_code >= 400:
                return AnnouncementDelivery(platform="discord", delivered=False, detail=f"Discord API trả HTTP {response.status_code}.")
            return AnnouncementDelivery(platform="discord", delivered=True, detail="Đã gửi thông báo.")
        except Exception as exc:
            return AnnouncementDelivery(platform="discord", delivered=False, detail=f"Không thể gửi Discord ({type(exc).__name__}).")

    def _telegram(self, message: str) -> AnnouncementDelivery:
        if not self.settings.telegram_bot_token or not self.settings.telegram_default_chat_id:
            return AnnouncementDelivery(platform="telegram", delivered=False, detail="TELEGRAM_BOT_TOKEN hoặc TELEGRAM_DEFAULT_CHAT_ID chưa được cấu hình.")
        try:
            import requests

            response = requests.post(
                f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage",
                json={"chat_id": self.settings.telegram_default_chat_id, "text": message}, timeout=20,
            )
            if response.status_code >= 400 or not response.json().get("ok"):
                return AnnouncementDelivery(platform="telegram", delivered=False, detail="Telegram API từ chối gửi thông báo.")
            return AnnouncementDelivery(platform="telegram", delivered=True, detail="Đã gửi thông báo.")
        except Exception as exc:
            return AnnouncementDelivery(platform="telegram", delivered=False, detail=f"Không thể gửi Telegram ({type(exc).__name__}).")
