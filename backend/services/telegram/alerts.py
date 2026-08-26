"""Outbound Telegram moderation alerts."""

from __future__ import annotations

import logging

import requests

from backend.config import Settings, get_settings
from backend.models.operations import CommonMessage, MessageDecision

logger = logging.getLogger(__name__)


class TelegramAlertSender:
    """Send concise moderation alerts through a Telegram Bot API token.

    This intentionally uses a bot token and chat ID, never a personal Telegram
    login/session. Alerts are disabled until explicitly enabled in ``.env``.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def configured(self) -> bool:
        return bool(
            self.settings.telegram_alerts_enabled
            and self.settings.telegram_bot_token.strip()
            and self.settings.telegram_admin_chat_id.strip()
        )

    @staticmethod
    def should_alert(result: MessageDecision, threshold: float) -> bool:
        return result.send_to_admin and (result.decision != "allow" or result.risk_score >= threshold)

    def send_alert(
        self,
        message: CommonMessage,
        result: MessageDecision,
    ) -> bool:
        if not self.should_alert(result, self.settings.telegram_alert_risk_threshold):
            return False
        if not self.configured:
            logger.debug(
                "Telegram alert skipped: disabled or TELEGRAM_BOT_TOKEN/"
                "TELEGRAM_ADMIN_CHAT_ID is missing."
            )
            return False

        return self._send_text(message.message_id, self._format_alert(message, result))

    def send_blocked_link_alert(
        self,
        message: CommonMessage,
        canonical_url: str,
        *,
        deleted: bool,
    ) -> bool:
        """Always alert on a known blocked link, independent of duplicate-case suppression."""
        if not self.configured:
            return False
        content = " ".join(message.text.split())
        if len(content) > 1800:
            content = content[:1797] + "..."
        lines = [
            "🚨 LINK ĐÃ BỊ CỘNG ĐỒNG CHẶN XUẤT HIỆN LẠI",
            f"Nền tảng: {message.platform.upper()} · Kênh: {message.channel_id}",
            f"Mã thành viên: {message.author_id}",
            f"Nội dung đầy đủ: {content}",
            f"Link chuẩn hóa: {canonical_url}",
            f"Xóa khỏi Discord: {'thành công' if deleted else 'không thành công - cần Admin xử lý'}",
        ]
        if message.source_url:
            lines.append(f"Mở tin nhắn: {message.source_url}")
        return self._send_text(message.message_id, "\n".join(lines)[:3900])

    def _send_text(self, message_id: str, text: str) -> bool:
        endpoint = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        try:
            response = requests.post(
                endpoint,
                json={
                    "chat_id": self.settings.telegram_admin_chat_id,
                    "text": text,
                    "disable_web_page_preview": True,
                },
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            if not payload.get("ok"):
                raise RuntimeError(payload.get("description", "Telegram API returned ok=false"))
            logger.info("Telegram moderation alert sent for message %s", message_id)
            return True
        except requests.RequestException as exc:
            # Do not log the endpoint: it contains the bot token.
            logger.error(
                "Telegram moderation alert failed for message %s (%s)",
                message_id,
                type(exc).__name__,
            )
            return False
        except Exception as exc:
            # The moderation pipeline must continue even if Telegram is down.
            logger.error(
                "Telegram moderation alert failed for message %s (%s)",
                message_id,
                type(exc).__name__,
            )
            return False

    @staticmethod
    def _format_alert(message: CommonMessage, result: MessageDecision) -> str:
        decision = result.decision.replace("_", " ").upper()
        content = " ".join(message.text.split())
        if len(content) > 900:
            content = content[:897] + "..."
        evidence = ", ".join(f'"{item}"' for item in result.evidence[:4]) or "không có cụm từ nổi bật"
        lines = [
            "🚨 CẢNH BÁO COMMUNITY",
            f"Nền tảng: {message.platform.upper()} · Kênh: {message.channel_id}",
            f"Quyết định AI: {decision}",
            f"Nhóm: {result.category} · Risk: {result.risk_score:.0%} · Severity: {result.severity}",
            f"Tác giả: {message.author_id}",
            f"Nội dung: {content}",
            f"Bằng chứng: {evidence}",
            f"Lý do: {result.explanation}",
        ]
        if result.incident_id:
            lines.append(f"Incident: {result.incident_id}")
        if message.source_url:
            lines.append(f"Mở tin nhắn: {message.source_url}")
        return "\n".join(lines)[:3900]
