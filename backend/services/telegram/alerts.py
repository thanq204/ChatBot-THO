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
            and self.settings.telegram_default_chat_id.strip()
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
                "TELEGRAM_DEFAULT_CHAT_ID is missing."
            )
            return False

        text = self._format_alert(message, result)
        endpoint = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        try:
            response = requests.post(
                endpoint,
                json={
                    "chat_id": self.settings.telegram_default_chat_id,
                    "text": text,
                    "disable_web_page_preview": True,
                },
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            if not payload.get("ok"):
                raise RuntimeError(payload.get("description", "Telegram API returned ok=false"))
            logger.info("Telegram moderation alert sent for message %s", message.message_id)
            return True
        except requests.RequestException as exc:
            # Do not log the endpoint: it contains the bot token.
            logger.error(
                "Telegram moderation alert failed for message %s (%s)",
                message.message_id,
                type(exc).__name__,
            )
            return False
        except Exception as exc:
            # The moderation pipeline must continue even if Telegram is down.
            logger.error(
                "Telegram moderation alert failed for message %s (%s)",
                message.message_id,
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
            lines.append(f"Mở message: {message.source_url}")
        return "\n".join(lines)[:3900]
