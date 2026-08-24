"""Platform moderation actions for Discord and Telegram.

The API actions are always Admin-confirmed. The only automated operation is an
opt-in private warning for a non-allow decision from a live bot listener.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import requests

from backend.config import Settings, get_settings
from backend.models.operations import AdminPlatformActionResponse, CommonMessage, MessageDecision
from backend.services.operations_store import OperationsStore


class PlatformModerationError(ValueError):
    pass


class PlatformModerationService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @staticmethod
    def _result(action: str, platform: str, user_id: str, message_id: str | None, completed: bool, detail: str) -> AdminPlatformActionResponse:
        return AdminPlatformActionResponse(action=action, platform=platform, target_user_id=user_id, target_message_id=message_id, completed=completed, detail=detail)

    def execute(self, *, platform: str, community_id: str, channel_id: str, user_id: str, message_id: str | None, action: str, text: str, duration_minutes: int | None) -> AdminPlatformActionResponse:
        if platform == "discord":
            return self._discord(community_id, channel_id, user_id, message_id, action, text, duration_minutes)
        if platform == "telegram":
            return self._telegram(channel_id, user_id, message_id, action, text, duration_minutes)
        raise PlatformModerationError("Nền tảng này chưa hỗ trợ hành động quản trị trực tiếp.")

    def send_automatic_warning(self, message: CommonMessage, decision: MessageDecision, store: OperationsStore) -> AdminPlatformActionResponse | None:
        """DM a member only when the same three gates allow an Admin alert."""
        if (
            not self.settings.moderation_auto_warn_dm_enabled
            or not decision.send_to_member
            or decision.decision not in {"warn", "hide", "hold_for_review"}
        ):
            return None
        if message.platform not in {"discord", "telegram"} or message.author_id == "anonymous":
            return None
        status = decision.banner or {
            "warn": "Tin nhắn của bạn đã bị cảnh báo theo nội quy cộng đồng.",
            "hide": "Tin nhắn của bạn được đề xuất ẩn và đang chờ Admin/Mod xem xét.",
            "hold_for_review": "Tin nhắn của bạn đang chờ Admin/Mod xem xét theo nội quy cộng đồng.",
        }[decision.decision]
        text = (
            f"{status} "
            f"Lý do: {decision.explanation[:500]}\n"
            "Vui lòng điều chỉnh nội dung. Nếu bạn cho rằng đây là nhầm lẫn, hãy liên hệ Admin/Mod."
        )
        result = self.execute(
            platform=message.platform,
            community_id=message.community_id,
            channel_id=message.channel_id,
            user_id=message.author_id,
            message_id=None,
            action="dm",
            text=text,
            duration_minutes=None,
        )
        store.add_audit(
            decision.incident_id,
            message.message_id,
            "automatic_moderation_dm",
            "system",
            {"decision": decision.decision, "completed": result.completed, "detail": result.detail, "target_user_id": message.author_id},
        )
        return result

    def _discord(self, guild_id: str, channel_id: str, user_id: str, message_id: str | None, action: str, text: str, duration: int | None) -> AdminPlatformActionResponse:
        if not self.settings.discord_bot_token:
            raise PlatformModerationError("DISCORD_BOT_TOKEN chưa được cấu hình.")
        headers = {"Authorization": f"Bot {self.settings.discord_bot_token}"}
        base = "https://discord.com/api/v10"
        try:
            if action == "dm":
                if not text.strip():
                    raise PlatformModerationError("Hành động DM cần nội dung message.")
                dm = requests.post(f"{base}/users/@me/channels", headers=headers, json={"recipient_id": user_id}, timeout=20)
                dm.raise_for_status()
                response = requests.post(f"{base}/channels/{dm.json()['id']}/messages", headers=headers, json={"content": text}, timeout=20)
            elif action == "delete_message":
                if not message_id:
                    raise PlatformModerationError("Xóa tin nhắn cần message_id.")
                response = requests.delete(f"{base}/channels/{channel_id}/messages/{message_id}", headers=headers, timeout=20)
            elif action == "timeout":
                if not duration:
                    raise PlatformModerationError("Timeout cần duration_minutes.")
                until = (datetime.now(UTC) + timedelta(minutes=duration)).isoformat().replace("+00:00", "Z")
                response = requests.patch(f"{base}/guilds/{guild_id}/members/{user_id}", headers=headers, json={"communication_disabled_until": until}, timeout=20)
            elif action == "kick":
                response = requests.delete(f"{base}/guilds/{guild_id}/members/{user_id}", headers=headers, timeout=20)
            elif action == "ban":
                response = requests.put(f"{base}/guilds/{guild_id}/bans/{user_id}", headers=headers, json={"delete_message_seconds": 0}, timeout=20)
            else:
                raise PlatformModerationError("Hành động không hợp lệ.")
            if response.status_code >= 400:
                hint = " Bot có thể thiếu quyền (Manage Messages/Timeout Members/Kick Members/Ban Members)." if response.status_code == 403 else ""
                return self._result(action, "discord", user_id, message_id, False, f"Discord API trả HTTP {response.status_code}: {response.text[:200]}{hint}")
            return self._result(action, "discord", user_id, message_id, True, "Đã thực hiện hành động trên Discord.")
        except requests.RequestException as exc:
            return self._result(action, "discord", user_id, message_id, False, f"Không thể gọi Discord ({type(exc).__name__}).")

    def _telegram(self, chat_id: str, user_id: str, message_id: str | None, action: str, text: str, duration: int | None) -> AdminPlatformActionResponse:
        if not self.settings.telegram_bot_token:
            raise PlatformModerationError("TELEGRAM_BOT_TOKEN chưa được cấu hình.")
        base = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}"
        try:
            if action == "dm":
                if not text.strip():
                    raise PlatformModerationError("Hành động DM cần nội dung message.")
                response = requests.post(f"{base}/sendMessage", json={"chat_id": user_id, "text": text}, timeout=20)
            elif action == "delete_message":
                if not message_id:
                    raise PlatformModerationError("Xóa tin nhắn cần message_id.")
                response = requests.post(f"{base}/deleteMessage", json={"chat_id": chat_id, "message_id": message_id}, timeout=20)
            elif action == "timeout":
                if not duration:
                    raise PlatformModerationError("Timeout cần duration_minutes.")
                response = requests.post(f"{base}/restrictChatMember", json={"chat_id": chat_id, "user_id": user_id, "permissions": {"can_send_messages": False}, "until_date": int((datetime.now(UTC) + timedelta(minutes=duration)).timestamp())}, timeout=20)
            elif action == "kick":
                response = requests.post(f"{base}/banChatMember", json={"chat_id": chat_id, "user_id": user_id}, timeout=20)
                if response.ok and response.json().get("ok"):
                    response = requests.post(f"{base}/unbanChatMember", json={"chat_id": chat_id, "user_id": user_id, "only_if_banned": True}, timeout=20)
            elif action == "ban":
                response = requests.post(f"{base}/banChatMember", json={"chat_id": chat_id, "user_id": user_id}, timeout=20)
            else:
                raise PlatformModerationError("Hành động không hợp lệ.")
            if response.status_code >= 400 or not response.json().get("ok"):
                description = response.json().get("description", "") if response.headers.get("content-type", "").startswith("application/json") else ""
                return self._result(action, "telegram", user_id, message_id, False, f"Telegram API từ chối hành động: {description or response.text[:200]}. Kiểm tra bot có phải Admin của nhóm với đủ quyền không.")
            return self._result(action, "telegram", user_id, message_id, True, "Đã thực hiện hành động trên Telegram.")
        except requests.RequestException as exc:
            return self._result(action, "telegram", user_id, message_id, False, f"Không thể gọi Telegram ({type(exc).__name__}).")
