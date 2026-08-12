"""Outbound manual notifications, triggered from the admin UI's platform picker.

Discord and Telegram send through the bot credentials already used by the
read connectors (backend/services/platform_connectors.py). Zalo and Messenger
use the Official Account / Page Send APIs and require an access token plus a
default recipient id; until those are supplied in .env they report back as
not configured instead of failing the whole request.
"""

from __future__ import annotations

import logging

import requests

from backend.config import Settings, get_settings
from backend.models.operations import NotifyResult

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def send(self, platforms: list[str], title: str, message: str) -> list[NotifyResult]:
        text = f"{title}\n\n{message}" if title.strip() else message
        senders = {
            "discord": self._send_discord,
            "telegram": self._send_telegram,
            "zalo": self._send_zalo,
            "messenger": self._send_messenger,
        }
        results = []
        for platform in platforms:
            sender = senders.get(platform)
            if sender is None:
                results.append(NotifyResult(platform=platform, sent=False, detail="Nền tảng chưa hỗ trợ gửi thông báo."))
                continue
            results.append(sender(text))
        return results

    def _send_discord(self, text: str) -> NotifyResult:
        token = self.settings.discord_bot_token.strip()
        channel_id = self.settings.discord_default_channel_id.strip()
        if not token or not channel_id:
            return NotifyResult(platform="discord", sent=False, detail="Thiếu DISCORD_BOT_TOKEN hoặc DISCORD_DEFAULT_CHANNEL_ID.")
        try:
            response = requests.post(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                headers={"Authorization": f"Bot {token}"},
                json={"content": text[:2000]},
                timeout=15,
            )
            response.raise_for_status()
            return NotifyResult(platform="discord", sent=True, detail="Đã gửi tới kênh Discord.")
        except requests.RequestException as exc:
            logger.error("Discord notify failed (%s)", type(exc).__name__)
            return NotifyResult(platform="discord", sent=False, detail=f"Gửi Discord thất bại: {exc}")

    def _send_telegram(self, text: str) -> NotifyResult:
        token = self.settings.telegram_bot_token.strip()
        chat_id = self.settings.telegram_default_chat_id.strip()
        if not token or not chat_id:
            return NotifyResult(platform="telegram", sent=False, detail="Thiếu TELEGRAM_BOT_TOKEN hoặc TELEGRAM_DEFAULT_CHAT_ID.")
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text[:3900], "disable_web_page_preview": True},
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            if not payload.get("ok"):
                raise RuntimeError(payload.get("description", "Telegram API returned ok=false"))
            return NotifyResult(platform="telegram", sent=True, detail="Đã gửi tới Telegram.")
        except requests.RequestException as exc:
            logger.error("Telegram notify failed (%s)", type(exc).__name__)
            return NotifyResult(platform="telegram", sent=False, detail=f"Gửi Telegram thất bại: {exc}")
        except Exception as exc:
            logger.error("Telegram notify failed (%s)", type(exc).__name__)
            return NotifyResult(platform="telegram", sent=False, detail=str(exc))

    def _send_zalo(self, text: str) -> NotifyResult:
        token = self.settings.zalo_access_token.strip()
        recipient_id = self.settings.zalo_default_recipient_id.strip()
        if not token or not recipient_id:
            return NotifyResult(platform="zalo", sent=False, detail="Thiếu ZALO_ACCESS_TOKEN hoặc ZALO_DEFAULT_RECIPIENT_ID.")
        try:
            response = requests.post(
                "https://openapi.zalo.me/v3.0/oa/message/cs",
                headers={"access_token": token, "Content-Type": "application/json"},
                json={"recipient": {"user_id": recipient_id}, "message": {"text": text[:2000]}},
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("error"):
                raise RuntimeError(payload.get("message", "Zalo OA API trả về lỗi"))
            return NotifyResult(platform="zalo", sent=True, detail="Đã gửi tới Zalo OA.")
        except requests.RequestException as exc:
            logger.error("Zalo notify failed (%s)", type(exc).__name__)
            return NotifyResult(platform="zalo", sent=False, detail=f"Gửi Zalo thất bại: {exc}")
        except Exception as exc:
            logger.error("Zalo notify failed (%s)", type(exc).__name__)
            return NotifyResult(platform="zalo", sent=False, detail=str(exc))

    def _send_messenger(self, text: str) -> NotifyResult:
        token = self.settings.messenger_page_access_token.strip()
        recipient_id = self.settings.messenger_default_recipient_id.strip()
        if not token or not recipient_id:
            return NotifyResult(platform="messenger", sent=False, detail="Thiếu MESSENGER_PAGE_ACCESS_TOKEN hoặc MESSENGER_DEFAULT_RECIPIENT_ID.")
        try:
            response = requests.post(
                "https://graph.facebook.com/v20.0/me/messages",
                params={"access_token": token},
                json={"recipient": {"id": recipient_id}, "message": {"text": text[:2000]}},
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("error"):
                raise RuntimeError(payload["error"].get("message", "Messenger API trả về lỗi"))
            return NotifyResult(platform="messenger", sent=True, detail="Đã gửi tới Messenger.")
        except requests.RequestException as exc:
            logger.error("Messenger notify failed (%s)", type(exc).__name__)
            return NotifyResult(platform="messenger", sent=False, detail=f"Gửi Messenger thất bại: {exc}")
        except Exception as exc:
            logger.error("Messenger notify failed (%s)", type(exc).__name__)
            return NotifyResult(platform="messenger", sent=False, detail=str(exc))
