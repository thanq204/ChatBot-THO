"""Opt-in Telegram polling bot for moderation and grounded RAG replies."""

from __future__ import annotations

import logging
import re
import threading
from datetime import UTC, datetime
from time import monotonic
from typing import Any

import requests

from backend.config import Settings, get_settings
from backend.models.operations import RESERVED_BOT_COMMANDS, CommonMessage, MessageDecision
from backend.services.chat_orchestrator import ChatOrchestrator
from backend.services.operations_pipeline import OperationsPipeline
from backend.services.operations_store import OperationsStore
from backend.services.platform_moderation import PlatformModerationService
from backend.services.question_intent import is_reusable_faq_question
from backend.services.telegram.alerts import TelegramAlertSender

logger = logging.getLogger(__name__)

_active_bot: TelegramRagBot | None = None


def notify_commands_changed() -> None:
    """Refresh a live Telegram command menu after an Admin edit."""
    if _active_bot is not None:
        _active_bot.resync_commands()


class TelegramRagBot:
    """Moderate Telegram messages and answer direct/explicit bot questions.

    Long polling is intentional for local development and Docker deployments
    without a public HTTPS endpoint. The shared orchestrator keeps the same
    Rule -> Moderation -> FAQ -> RAG/LLM order as Discord.
    """

    def __init__(self, store: OperationsStore, settings: Settings | None = None, pipeline: OperationsPipeline | None = None) -> None:
        self.settings = settings or get_settings()
        self.store = store
        self.pipeline = pipeline or OperationsPipeline(store=store, settings=self.settings)
        self.chat = ChatOrchestrator(store, self.settings, self.pipeline)
        self.telegram_alerts = TelegramAlertSender(self.settings)
        self.platform_moderation = PlatformModerationService(self.settings)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._offset: int | None = None
        self._seen_updates: set[int] = set()
        self._username = ""
        self._message_cache: dict[tuple[str, str], CommonMessage] = {}
        self._reaction_users: dict[tuple[str, str, str], set[str]] = {}
        self._pending_commands: dict[tuple[str, str], tuple[str, dict[str, Any], float]] = {}
        self._telegram_users_by_username: dict[tuple[str, str], tuple[str, str | None]] = {}
        self._telegram_username_by_user_id: dict[tuple[str, str], str] = {}
        self._telegram_member_signatures: dict[tuple[str, str], tuple[str, str, str, bool]] = {}

    def start(self) -> None:
        print(f"[Telegram] start() called: listener_enabled={self.settings.telegram_listener_enabled}, token={'SET' if self.settings.telegram_bot_token else 'EMPTY'}", flush=True)
        if not self.settings.telegram_listener_enabled:
            logger.info("Telegram listener disabled by TELEGRAM_LISTENER_ENABLED.")
            print("[Telegram] Listener DISABLED by config.", flush=True)
            return
        if not self.settings.telegram_bot_token:
            logger.warning("Telegram listener skipped: TELEGRAM_BOT_TOKEN is missing.")
            print("[Telegram] Listener SKIPPED: no bot token.", flush=True)
            return
        if self._thread and self._thread.is_alive():
            print("[Telegram] Listener thread already alive, skipping.", flush=True)
            return
        self._stop.clear()
        global _active_bot
        _active_bot = self
        self._thread = threading.Thread(target=self._run, name="telegram-rag-listener", daemon=True)
        self._thread.start()
        print("[Telegram] Listener thread started.", flush=True)

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self.settings.telegram_polling_timeout_seconds + 5)
        global _active_bot
        if _active_bot is self:
            _active_bot = None

    @property
    def _api_base(self) -> str:
        return f"https://api.telegram.org/bot{self.settings.telegram_bot_token}"

    def resync_commands(self) -> None:
        self._register_commands()

    def _register_commands(self) -> None:
        """Expose Level 1 commands in Telegram's native '/' command menu."""
        commands = [
            {"command": "start", "description": "Giới thiệu bot"},
            {"command": "help", "description": "Danh sách lệnh"},
            {"command": "rule", "description": "Nội quy nhóm"},
            {"command": "event", "description": "Sự kiện và lịch học"},
            {"command": "daily", "description": "Việc cần làm hôm nay"},
            {"command": "weekly", "description": "Kế hoạch tuần"},
            {"command": "faq", "description": "Câu hỏi thường gặp"},
            {"command": "report", "description": "Báo cáo vi phạm", "is_ephemeral": True},
            {"command": "admin", "description": "Liên hệ Admin/Mod"},
            {"command": "resources", "description": "Tài liệu học tập"},
            {"command": "settings", "description": "Cài đặt thông báo"},
            {"command": "trade_open", "description": "Mở giao dịch với người bán", "is_ephemeral": True},
            {"command": "trade_confirm", "description": "Xác nhận giao dịch hoàn tất", "is_ephemeral": True},
            {"command": "trade_review", "description": "Đánh giá giao dịch đã xác nhận", "is_ephemeral": True},
            {"command": "seller_check", "description": "Yêu cầu kiểm tra người bán", "is_ephemeral": True},
        ]
        known = {item["command"] for item in commands}
        try:
            for entry in self.store.list_command_content():
                if "telegram" not in entry.platforms or entry.command in known:
                    continue
                commands.append(
                    {
                        "command": entry.command,
                        "description": (entry.description or f"Command /{entry.command}").strip()[:256],
                    }
                )
                known.add(entry.command)
        except Exception:
            logger.exception("Could not load Admin-created Telegram commands.")
        try:
            response = requests.post(f"{self._api_base}/setMyCommands", json={"commands": commands}, timeout=15)
            response.raise_for_status()
            if not response.json().get("ok"):
                raise RuntimeError("Telegram returned ok=false")
        except Exception:
            logger.warning("Telegram command menu registration failed; text commands remain available.")

    def _run(self) -> None:
        print("[Telegram] _run() entered, calling getMe...", flush=True)
        try:
            response = requests.get(f"{self._api_base}/getMe", timeout=15)
            response.raise_for_status()
            self._username = str(response.json().get("result", {}).get("username", "")).lower()
            self._register_commands()
            logger.info("Telegram RAG listener ready as @%s", self._username or "bot")
            print(f"[Telegram] RAG listener ready as @{self._username}", flush=True)
        except requests.RequestException as exc:
            logger.exception("Telegram listener stopped: getMe failed.")
            print(f"[Telegram] getMe FAILED: {exc}", flush=True)
            return

        while not self._stop.is_set():
            try:
                params: dict[str, object] = {"timeout": self.settings.telegram_polling_timeout_seconds, "allowed_updates": '["message", "message_reaction", "message_reaction_count", "chat_member"]'}
                if self._offset is not None:
                    params["offset"] = self._offset
                response = requests.get(f"{self._api_base}/getUpdates", params=params, timeout=(10, self.settings.telegram_polling_timeout_seconds + 10))
                response.raise_for_status()
                for update in response.json().get("result", []):
                    update_id = int(update.get("update_id", -1))
                    if update_id >= 0:
                        self._offset = update_id + 1
                    if update_id in self._seen_updates:
                        continue
                    self._seen_updates.add(update_id)
                    if update.get("message_reaction"):
                        self._handle_reaction_update(update["message_reaction"])
                    elif update.get("message_reaction_count"):
                        self._handle_reaction_count_update(update["message_reaction_count"])
                    elif update.get("chat_member"):
                        self._handle_chat_member_update(update["chat_member"])
                    else:
                        self._handle_update(update)
            except requests.RequestException:
                if not self._stop.is_set():
                    logger.exception("Telegram polling failed; retrying.")
                    self._stop.wait(3)
            except Exception:
                logger.exception("Telegram update handling failed; listener continues.")

    def _handle_update(self, update: dict[str, Any]) -> None:
        message = update.get("message") or {}
        text = str(message.get("text") or message.get("caption") or "").strip()
        sender = message.get("from") or {}
        chat_id = str((message.get("chat") or {}).get("id") or "")
        self._remember_telegram_user(chat_id, sender)
        left_member = message.get("left_chat_member")
        if isinstance(left_member, dict):
            self._remember_telegram_user(
                chat_id,
                left_member,
                membership_status="left",
                is_active_member=False,
                observed_at=self._telegram_update_time(message.get("date")),
            )
        if sender.get("is_bot"):
            return
        new_members = message.get("new_chat_members")
        if isinstance(new_members, list):
            for member in new_members:
                self._remember_telegram_user(
                    chat_id,
                    member,
                    membership_status="member",
                    is_active_member=True,
                    observed_at=self._telegram_update_time(message.get("date")),
                )
            self._welcome_new_members(message, new_members)
            return
        if not text:
            return
        pending_key = self._pending_command_key(message)
        if re.fullmatch(r"/cancel(?:@\w+)?", text, re.I):
            had_pending = self._pending_commands.pop(pending_key, None) is not None
            response = "Đã hủy thao tác đang chờ." if had_pending else "Không có thao tác nào đang chờ."
            self._send_message(
                str((message.get("chat") or {}).get("id") or ""),
                response,
                **self._ephemeral_reply_kwargs(message),
            )
            return
        message, text = self._resume_pending_command(message, text)
        resumed_private_command = str(message.pop("_resumed_private_command", ""))
        if (
            resumed_private_command in {"report", "trade_open", "trade_confirm", "trade_review", "seller_check"}
            and str((message.get("chat") or {}).get("type") or "") in {"group", "supergroup"}
            and message.get("ephemeral_message_id") is None
        ):
            # Some Telegram mobile clients submit ForceReply input as a normal
            # group message even when the originating command was ephemeral.
            # Remove that visible input immediately before processing it.
            if not self._delete_message(chat_id, message.get("message_id")):
                logger.warning(
                    "Could not hide visible Telegram %s input %s; grant the bot Delete messages permission.",
                    resumed_private_command,
                    message.get("message_id"),
                )
        common = self._common_message(message)
        self._message_cache[(common.channel_id, str(message.get("message_id")))] = common
        if len(self._message_cache) > 5_000:
            self._message_cache.pop(next(iter(self._message_cache)))
        if self._handle_report_command(message, text):
            return
        blocked_links = self.store.find_blocked_links(common.text)
        # Production stores return a list. Keep lightweight test/API mocks from
        # being mistaken for a blocked-link match.
        if not isinstance(blocked_links, list):
            blocked_links = []
        if blocked_links:
            deleted = self._delete_message(common.channel_id, message.get("message_id"))
            result = self.pipeline.analyze(common)
            self.store.add_audit(
                result.incident_id,
                common.message_id,
                "known_blocked_link_seen",
                "system",
                {"canonical_url": blocked_links[0].canonical_url, "author_id": common.author_id, "deleted": deleted},
            )
            self.telegram_alerts.send_blocked_link_alert(common, blocked_links[0].canonical_url, deleted=deleted)
            self._send_moderation_notice(
                common,
                result,
                reply_to_message_id=None if deleted else message.get("message_id"),
            )
            self.platform_moderation.send_automatic_warning(common, result, self.store)
            return
        if self._handle_trade_command(message, text):
            return
        question = self._question_to_answer(message, text)
        tracking_message = None
        if question is not None:
            common = common.model_copy(update={"text": question})
            outcome = self.chat.reply(common, track_question=False)
            self._send_message(str(message["chat"]["id"]), outcome.answer, reply_to_message_id=message.get("message_id"))
            result = outcome.moderation
            if outcome.stage in {"rag", "llm"} and is_reusable_faq_question(common.text):
                tracking_message = common
        else:
            result = self.pipeline.analyze(common)
        if result:
            if question is None:
                self._send_moderation_notice(
                    common,
                    result,
                    reply_to_message_id=message.get("message_id"),
                )
            if self.telegram_alerts.send_alert(common, result):
                logger.info("Admin Telegram alert sent for Telegram message %s", common.message_id)
            warning = self.platform_moderation.send_automatic_warning(common, result, self.store)
            if warning:
                logger.info("Automatic Telegram warning DM for %s completed=%s", common.message_id, warning.completed)
        if tracking_message is not None:
            try:
                self.store.record_member_question(tracking_message, outcome_stage=outcome.stage)
            except Exception:
                logger.exception("Telegram FAQ analytics failed for message %s", common.message_id)

    def _welcome_new_members(self, message: dict[str, Any], members: list[dict[str, Any]]) -> None:
        if not self.settings.telegram_welcome_new_members_enabled:
            return
        names = []
        for member in members:
            if member.get("is_bot"):
                continue
            name = " ".join(
                part for part in (member.get("first_name"), member.get("last_name")) if part
            ) or member.get("username") or "thành viên mới"
            names.append(str(name))
        if not names:
            return
        self._send_message(
            str((message.get("chat") or {}).get("id") or ""),
            f"Chào {', '.join(names)}! Mừng bạn đến với cộng đồng. Dùng /help để xem hướng dẫn và các lệnh hỗ trợ.",
            reply_to_message_id=message.get("message_id"),
        )

    @staticmethod
    def _telegram_update_time(value: Any) -> datetime | None:
        try:
            return datetime.fromtimestamp(int(value), UTC)
        except (TypeError, ValueError, OSError):
            return None

    def _handle_chat_member_update(self, member_update: dict[str, Any]) -> None:
        """Track joins, leaves and membership changes delivered by Telegram."""
        chat_id = str((member_update.get("chat") or {}).get("id") or "")
        new_member = member_update.get("new_chat_member") or {}
        user = new_member.get("user") or {}
        status = str(new_member.get("status") or "unknown").lower()
        is_active = status in {"creator", "administrator", "member"}
        if status == "restricted":
            is_active = bool(new_member.get("is_member"))
        self._remember_telegram_user(
            chat_id,
            user,
            membership_status=status,
            is_active_member=is_active,
            observed_at=self._telegram_update_time(member_update.get("date")),
        )

    def _remember_telegram_user(
        self,
        chat_id: str,
        user: dict[str, Any],
        *,
        membership_status: str = "active",
        is_active_member: bool = True,
        observed_at: datetime | None = None,
    ) -> None:
        """Keep a persistent, group-local Telegram username-to-ID directory."""
        if not chat_id or user.get("is_bot") or user.get("id") is None:
            return
        user_id = str(user["id"])
        reverse_key = (chat_id, user_id)
        previous_username = self._telegram_username_by_user_id.get(reverse_key)
        username = str(user.get("username") or "").strip().lstrip("@").lower()
        if previous_username and previous_username != username:
            self._telegram_users_by_username.pop((chat_id, previous_username), None)
        name = " ".join(
            str(part).strip()
            for part in (user.get("first_name"), user.get("last_name"))
            if part and str(part).strip()
        ) or (f"@{username}" if username else f"Telegram user {user_id}")
        if not is_active_member or not username:
            self._telegram_username_by_user_id.pop(reverse_key, None)
            if username:
                self._telegram_users_by_username.pop((chat_id, username), None)
        else:
            self._telegram_users_by_username[(chat_id, username)] = (user_id, str(name))
            self._telegram_username_by_user_id[reverse_key] = username

        signature = (username, str(name), membership_status, is_active_member)
        if self._telegram_member_signatures.get(reverse_key) == signature:
            return
        try:
            self.store.remember_telegram_member(
                chat_id,
                user_id,
                display_name=str(name),
                username=username or None,
                membership_status=membership_status,
                is_active_member=is_active_member,
                is_bot=False,
                observed_at=observed_at,
            )
            self._telegram_member_signatures[reverse_key] = signature
        except Exception:
            logger.exception("Could not persist Telegram member %s in chat %s.", user_id, chat_id)

    def _send_moderation_notice(
        self,
        message: CommonMessage,
        result: MessageDecision,
        *,
        reply_to_message_id: int | None,
    ) -> bool:
        """Notify the group only for a gated, non-allow moderation decision."""
        if not result.send_to_member or result.decision not in {"warn", "hide", "hold_for_review"}:
            return False
        fallback = {
            "warn": "Nội dung có dấu hiệu vi phạm nội quy cộng đồng.",
            "hide": "Nội dung có dấu hiệu vi phạm và được đề xuất ẩn.",
            "hold_for_review": "Nội dung đang chờ Admin/Mod xem xét.",
        }[result.decision]
        status = (result.banner or fallback).strip()
        explanation = str(result.explanation or "").strip()
        notice = f"⚠️ {status}"
        if explanation and explanation.lower() not in status.lower():
            notice += f"\nLý do: {explanation[:500]}"
        self._send_message(
            message.channel_id,
            notice,
            reply_to_message_id=reply_to_message_id,
        )
        return True

    @staticmethod
    def _pending_command_key(message: dict[str, Any]) -> tuple[str, str]:
        chat_id = str((message.get("chat") or {}).get("id") or "")
        author_id = str((message.get("from") or {}).get("id") or "anonymous")
        return chat_id, author_id

    def _begin_pending_command(self, command: str, message: dict[str, Any], prompt: str) -> None:
        self._pending_commands[self._pending_command_key(message)] = (command, dict(message), monotonic())
        placeholders = {
            "report": "Nhập nội dung cần báo cáo",
            "trade_open": "Nhập seller và mô tả món hàng",
            "trade_confirm": "Nhập mã giao dịch TRD-...",
            "trade_review": "Nhập mã giao dịch và điểm đánh giá",
            "seller_check": "Nhập seller và lý do kiểm tra",
        }
        self._send_message(
            str((message.get("chat") or {}).get("id") or ""),
            prompt + "\nGửi /cancel để hủy.",
            force_reply=True,
            force_reply_placeholder=placeholders.get(command),
            **self._ephemeral_reply_kwargs(message),
        )

    def _resume_pending_command(
        self,
        message: dict[str, Any],
        text: str,
    ) -> tuple[dict[str, Any], str]:
        key = self._pending_command_key(message)
        pending = self._pending_commands.get(key)
        if pending is None:
            command = self._command_from_replied_prompt(message)
            if command is None or text.startswith("/"):
                return message, text
            original_message = message
        else:
            command, original_message, started_at = pending
            if monotonic() - started_at > 300:
                self._pending_commands.pop(key, None)
                return message, text
        if text.startswith("/"):
            self._pending_commands.pop(key, None)
            return message, text

        self._pending_commands.pop(key, None)
        resumed_message = dict(message)
        # Preserve command context (for example, the seller selected by
        # replying to their message). A mobile ForceReply response normally
        # points at the bot prompt, which must not replace that seller context.
        if original_message.get("reply_to_message"):
            resumed_message["reply_to_message"] = original_message["reply_to_message"]
        resumed_text = f"/{command} {text}"
        resumed_message["text"] = resumed_text
        resumed_message["_resumed_private_command"] = command
        return resumed_message, resumed_text

    def _command_from_replied_prompt(self, message: dict[str, Any]) -> str | None:
        """Recover a pending flow from ForceReply after a worker restart."""
        replied = message.get("reply_to_message") or {}
        replied_sender = replied.get("from") or {}
        replied_username = str(replied_sender.get("username") or "").lower()
        if not replied_sender.get("is_bot") or (
            self._username and replied_username != self._username
        ):
            return None
        current_date = int(message.get("date") or 0)
        prompt_date = int(replied.get("date") or 0)
        if current_date and prompt_date and current_date - prompt_date > 300:
            return None
        prompt = str(replied.get("text") or "")
        prompt_commands = {
            "Hãy gửi liên kết hoặc mã tin nhắn": "report",
            "Hãy gửi <seller_id> <mô tả món hàng>": "trade_open",
            "Hãy gửi mã giao dịch cần xác nhận": "trade_confirm",
            "Hãy gửi: <trade_id>": "trade_review",
            "Hãy gửi <seller_id> [lý do]": "seller_check",
        }
        return next(
            (command for prefix, command in prompt_commands.items() if prompt.startswith(prefix)),
            None,
        )

    def _handle_report_command(self, message: dict[str, Any], text: str) -> bool:
        match = re.match(r"^/report(?:@\w+)?(?:\s+(.*))?$", text, re.I | re.S)
        if not match:
            return False
        argument = (match.group(1) or "").strip()
        if not argument:
            self._begin_pending_command(
                "report",
                message,
                "Hãy gửi liên kết hoặc mã tin nhắn kèm mô tả ngắn về nội dung cần báo cáo.",
            )
            return True

        common = self._common_message(message).model_copy(update={"text": f"/report {argument}"})
        outcome = self.chat.reply(common, track_question=False)
        self._send_message(
            common.channel_id,
            outcome.answer,
            **self._ephemeral_reply_kwargs(message),
        )
        return True

    def _handle_trade_command(self, message: dict[str, Any], text: str) -> bool:
        """Handle Telegram-native versions of the verified trade commands."""
        match = re.match(r"^/(trade_open|trade_confirm|trade_review|seller_check)(?:@\w+)?(?:\s+(.*))?$", text, re.I | re.S)
        if not match:
            return False

        command = match.group(1).lower()
        argument = (match.group(2) or "").strip()
        chat = message.get("chat") or {}
        chat_id = str(chat.get("id") or "")

        def reply(body: str) -> None:
            self._send_message(chat_id, body, **self._ephemeral_reply_kwargs(message))

        configured_chat = self.settings.telegram_trade_chat_id.strip()
        if not configured_chat:
            reply("Admin chưa cấu hình TELEGRAM_TRADE_CHAT_ID nên luồng giao dịch đang khóa.")
            return True
        if chat_id != configured_chat:
            reply("Lệnh giao dịch chỉ dùng trong nhóm Telegram giao dịch đã được Admin cấu hình.")
            return True

        common = self._common_message(message)
        if common.author_id == "anonymous":
            reply("Không xác định được tài khoản Telegram của bạn.")
            return True

        if not argument:
            prompts = {
                "trade_open": (
                    "Hãy gửi @username <mô tả món hàng>. Nếu bạn đã reply tin nhắn của seller khi bấm lệnh, "
                    "chỉ cần gửi mô tả món hàng."
                ),
                "trade_confirm": "Hãy gửi mã giao dịch cần xác nhận, ví dụ TRD-ABC123.",
                "trade_review": (
                    "Hãy gửi: <trade_id> <tổng quan 1-5> <đúng mô tả 1-5> <giao tiếp 1-5> "
                    "<hoàn tất 1-5> <có|không> [nhận xét]."
                ),
                "seller_check": (
                    "Hãy gửi @username [lý do]. Nếu bạn đã reply tin nhắn của seller khi bấm lệnh, "
                    "chỉ cần gửi lý do."
                ),
            }
            self._begin_pending_command(command, message, prompts[command])
            return True

        if command == "trade_confirm":
            if not re.fullmatch(r"TRD-[A-Z0-9]+", argument, re.I):
                reply("Cú pháp: /trade_confirm TRD-... ")
                return True
            try:
                trade = self.store.confirm_trade_case(argument.upper(), common.author_id)
            except (ValueError, PermissionError) as exc:
                reply(str(exc))
                return True
            if not trade:
                reply("Không tìm thấy mã giao dịch.")
                return True
            status = (
                "Hai bên đã xác nhận. Người mua có thể dùng /trade_review."
                if trade.status == "completed"
                else "Đã ghi nhận xác nhận của bạn; đang chờ bên còn lại."
            )
            reply(f"Giao dịch {trade.trade_id}: {status}")
            return True

        if command == "trade_review":
            parts = argument.split(maxsplit=6)
            if len(parts) < 6:
                reply(
                    "Cú pháp: /trade_review TRD-... <tổng_quan 1-5> <đúng_mô_tả 1-5> "
                    "<giao_tiếp 1-5> <hoàn_tất 1-5> <có|không> [nhận xét]"
                )
                return True
            trade_id, *review_parts = parts
            try:
                ratings = [int(value) for value in review_parts[:4]]
            except ValueError:
                ratings = []
            if len(ratings) != 4 or any(value < 1 or value > 5 for value in ratings):
                reply("Bốn điểm đánh giá phải là số từ 1 đến 5.")
                return True
            again_value = review_parts[4].lower()
            yes_values = {"có", "co", "yes", "y", "true", "1"}
            no_values = {"không", "khong", "no", "n", "false", "0"}
            if again_value not in yes_values | no_values:
                reply("Giá trị giao dịch lại phải là có/không (hoặc yes/no).")
                return True
            comment = review_parts[5] if len(review_parts) > 5 else ""
            if len(comment) > 2_000:
                reply("Nhận xét chỉ được dài tối đa 2.000 ký tự.")
                return True
            try:
                review = self.store.add_seller_review(
                    trade_id.upper(),
                    buyer_id=common.author_id,
                    overall_rating=ratings[0],
                    item_accuracy=ratings[1],
                    communication=ratings[2],
                    fulfillment=ratings[3],
                    would_trade_again=again_value in yes_values,
                    comment=comment,
                )
            except (LookupError, ValueError, PermissionError) as exc:
                reply(str(exc))
                return True
            reply(
                f"Đã lưu đánh giá {review.review_id} dưới nhãn giao dịch xác thực. "
                "Đây là trải nghiệm của người mua, không phải bảo đảm an toàn từ bot."
            )
            return True

        seller_id, seller_name, detail = self._telegram_seller_target(message, argument)
        if not seller_id:
            seller_token = argument.split(maxsplit=1)[0] if argument else ""
            if seller_token.startswith("@"):
                reply(
                    f"Không tìm thấy {seller_token} trong thành viên bot đã ghi nhận. "
                    "Seller hãy gửi một tin nhắn trong nhóm, hoặc bạn reply trực tiếp tin nhắn của seller rồi thử lại."
                )
                return True
            usage = (
                "/trade_open @username <mô tả món hàng>, hoặc reply tin nhắn seller bằng /trade_open <mô tả>"
                if command == "trade_open"
                else "/seller_check @username [lý do], hoặc reply tin nhắn seller bằng /seller_check [lý do]"
            )
            reply(f"Không xác định được seller. Cú pháp: {usage}")
            return True

        if command == "trade_open":
            if len(detail) < 3 or len(detail) > 500:
                retry_message = dict(message)
                retry_message["reply_to_message"] = {
                    "from": {
                        "id": seller_id,
                        "first_name": seller_name or f"Seller {seller_id}",
                        "is_bot": False,
                    }
                }
                self._begin_pending_command(
                    "trade_open",
                    retry_message,
                    "Mô tả món hàng phải dài từ 3 đến 500 ký tự. Hãy nhập lại mô tả món hàng; không cần nhập lại seller.",
                )
                return True
            try:
                trade = self.store.create_trade_case(
                    platform="telegram",
                    community_id=chat_id,
                    channel_id=chat_id,
                    buyer_id=common.author_id,
                    buyer_name=common.author_name,
                    seller_id=seller_id,
                    seller_name=seller_name,
                    item_summary=detail,
                    created_by=common.author_id,
                    evidence_urls=[],
                )
            except ValueError as exc:
                reply(str(exc))
                return True
            buyer_label = common.author_name or f"ID {common.author_id}"
            seller_label = seller_name or f"ID {seller_id}"
            reply(
                f"Đã mở giao dịch {trade.trade_id} giữa người mua {buyer_label} và người bán {seller_label}. "
                "Hai bên dùng /trade_confirm sau khi hoàn tất. Không gửi OTP, mật khẩu hoặc thông tin thẻ vào Telegram."
            )
            return True

        reason = detail or "Thành viên yêu cầu kiểm tra thông tin người bán."
        if len(reason) > 1_000:
            reply("Lý do kiểm tra chỉ được dài tối đa 1.000 ký tự.")
            return True
        assessment = self.store.create_seller_assessment(
            platform="telegram",
            community_id=chat_id,
            requester_id=common.author_id,
            seller_id=seller_id,
            reason=reason,
        )
        reply(
            f"Đã gửi yêu cầu {assessment.assessment_id} cho Admin/Mod. "
            "Bot không tự kết luận người bán an toàn hoặc lừa đảo."
        )
        return True

    def _telegram_seller_target(self, message: dict[str, Any], argument: str) -> tuple[str, str | None, str]:
        """Resolve a seller from a replied-to message, @username, or numeric ID."""
        replied_sender = (message.get("reply_to_message") or {}).get("from") or {}
        if replied_sender.get("id") is not None and not replied_sender.get("is_bot"):
            name = " ".join(
                part for part in (replied_sender.get("first_name"), replied_sender.get("last_name")) if part
            ) or replied_sender.get("username") or None
            return str(replied_sender["id"]), name, argument

        parts = argument.split(maxsplit=1)
        if not parts:
            return "", None, argument
        detail = parts[1].strip() if len(parts) > 1 else ""
        if parts[0].startswith("@"):
            username = parts[0][1:].lower()
            chat_id = str((message.get("chat") or {}).get("id") or "")
            seller = self._telegram_users_by_username.get((chat_id, username))
            if seller:
                return seller[0], seller[1], detail
            persisted_seller = self.store.find_telegram_member_by_username(chat_id, username)
            if isinstance(persisted_seller, tuple) and len(persisted_seller) == 2:
                self._telegram_users_by_username[(chat_id, username)] = persisted_seller
                return persisted_seller[0], persisted_seller[1], detail
            return "", None, detail
        if re.fullmatch(r"\d{1,20}", parts[0]):
            return parts[0], None, detail
        return "", None, argument

    def _question_to_answer(self, message: dict[str, Any], text: str) -> str | None:
        chat_type = str((message.get("chat") or {}).get("type", ""))
        command = re.match(r"^/(\w+)(?:@\w+)?(?:\s+(.*))?$", text, re.I | re.S)
        if command:
            name, argument = command.group(1).lower(), (command.group(2) or "").strip()
            if name == "ask":
                return argument or "hello"
            if name in {"start", "help", "rule", "rules", "event", "daily", "weekly", "faq", "report", "admin", "resources", "settings"}:
                return f"/{name}" + (f" {argument}" if argument else "")
            try:
                content = self.store.get_command_content(name)
            except Exception:
                logger.exception("Could not look up Telegram command %s", name)
                content = None
            if content and name not in RESERVED_BOT_COMMANDS and "telegram" in content.platforms:
                return f"/{name}" + (f" {argument}" if argument else "")
        if chat_type == "private":
            return text
        replied_sender = (message.get("reply_to_message") or {}).get("from") or {}
        replied_username = str(replied_sender.get("username") or "").lower()
        if replied_sender.get("is_bot") and (
            not self._username or replied_username == self._username
        ):
            return text
        if self._username:
            mention = f"@{self._username}"
            if mention in text.lower():
                return re.sub(re.escape(mention), "", text, flags=re.I).strip() or "hello"
        return None

    def _send_message(
        self,
        chat_id: str,
        text: str,
        *,
        reply_to_message_id: int | None = None,
        reply_to_ephemeral_message_id: int | None = None,
        ephemeral_user_id: int | None = None,
        force_reply: bool = False,
        force_reply_placeholder: str | None = None,
    ) -> None:
        payload: dict[str, object] = {"chat_id": chat_id, "text": text[:self.settings.telegram_reply_max_chars]}
        if ephemeral_user_id is not None:
            payload["ephemeral_message_parameters"] = {"receiver_user_id": ephemeral_user_id}
        if reply_to_ephemeral_message_id is not None:
            payload["reply_parameters"] = {"ephemeral_message_id": reply_to_ephemeral_message_id}
        elif reply_to_message_id is not None:
            payload["reply_to_message_id"] = reply_to_message_id
        if force_reply:
            reply_markup: dict[str, object] = {"force_reply": True}
            # An ephemeral prompt already has exactly one receiver. Avoid
            # selective targeting here because some mobile clients do not
            # activate ForceReply for the new ephemeral reply target.
            if ephemeral_user_id is None:
                reply_markup["selective"] = True
            if force_reply_placeholder:
                reply_markup["input_field_placeholder"] = force_reply_placeholder[:64]
            payload["reply_markup"] = reply_markup

        for attempt in range(2):
            try:
                response = requests.post(f"{self._api_base}/sendMessage", json=payload, timeout=20)
                response.raise_for_status()
                return
            except requests.ConnectionError as exc:
                # A reset during TCP/TLS setup happens before Telegram receives
                # the request, so one retry is safe. Do not retry ambiguous
                # read failures, HTTP errors, or other request exceptions.
                if attempt == 0 and self._exception_chain_contains(exc, ConnectionResetError):
                    logger.warning("Telegram send connection reset; retrying once.")
                    self._stop.wait(0.5)
                    continue
                logger.exception("Telegram RAG reply failed.")
                return
            except requests.RequestException:
                logger.exception("Telegram RAG reply failed.")
                return

    @staticmethod
    def _exception_chain_contains(exc: BaseException, expected: type[BaseException]) -> bool:
        """Inspect wrapped urllib3/request exceptions without string matching."""
        pending: list[BaseException] = [exc]
        seen: set[int] = set()
        while pending:
            current = pending.pop()
            if id(current) in seen:
                continue
            seen.add(id(current))
            if isinstance(current, expected):
                return True
            for nested in (current.__cause__, current.__context__, *current.args):
                if isinstance(nested, BaseException):
                    pending.append(nested)
        return False

    @staticmethod
    def _ephemeral_reply_kwargs(message: dict[str, Any]) -> dict[str, int]:
        """Target one group member and, when possible, reply to their ephemeral message."""
        if str((message.get("chat") or {}).get("type") or "") not in {"group", "supergroup"}:
            return {}
        user_id = (message.get("from") or {}).get("id")
        if not isinstance(user_id, int):
            return {}
        kwargs = {"ephemeral_user_id": user_id}
        ephemeral_message_id = message.get("ephemeral_message_id")
        if isinstance(ephemeral_message_id, int):
            kwargs["reply_to_ephemeral_message_id"] = ephemeral_message_id
        return kwargs

    def _delete_message(self, chat_id: str, message_id: Any) -> bool:
        if message_id is None:
            return False
        try:
            response = requests.post(
                f"{self._api_base}/deleteMessage",
                json={"chat_id": chat_id, "message_id": message_id},
                timeout=20,
            )
            return response.ok and bool(response.json().get("ok"))
        except (requests.RequestException, ValueError):
            logger.warning("Telegram could not delete known blocked-link message %s", message_id, exc_info=True)
            return False

    def _handle_reaction_update(self, reaction: dict[str, Any]) -> None:
        """Apply per-user Telegram reaction events to community rules."""
        chat_id = str((reaction.get("chat") or {}).get("id") or "")
        message_id = str(reaction.get("message_id") or "")
        message = self._reaction_message(chat_id, message_id)
        # Telegram supplies ``actor_chat`` instead of ``user`` for anonymous
        # reactions (for example, an Admin reacting anonymously). Treat that
        # chat identity as one distinct reactor rather than dropping it.
        actor_id = str((reaction.get("user") or {}).get("id") or "")
        if not actor_id:
            actor_chat_id = (reaction.get("actor_chat") or {}).get("id")
            actor_id = f"chat:{actor_chat_id}" if actor_chat_id is not None else ""
        if not message or not actor_id or actor_id == message.author_id:
            return
        old = {item.get("emoji") for item in reaction.get("old_reaction", []) if item.get("type") == "emoji"}
        new = {item.get("emoji") for item in reaction.get("new_reaction", []) if item.get("type") == "emoji"}
        # Telegram's default reaction palette always includes thumbs up/down,
        # unlike the check/cross reactions used by the Discord adapter.
        for emoji in {"👍", "👎"}:
            users = self._reaction_users.setdefault((chat_id, message_id, emoji), set())
            if emoji in old and emoji not in new:
                users.discard(actor_id)
            if emoji in new:
                users.add(actor_id)
            self._apply_reaction_count(message, emoji, len(users))

    def _handle_reaction_count_update(self, reaction: dict[str, Any]) -> None:
        """Handle aggregate/anonymous reaction counts sent by Telegram.

        Telegram emits this update instead of ``message_reaction`` when the
        reacting members are not exposed individually.  The store actions are
        idempotent, so a count refresh cannot award or flag twice.
        """
        chat_id = str((reaction.get("chat") or {}).get("id") or "")
        message_id = str(reaction.get("message_id") or "")
        message = self._reaction_message(chat_id, message_id)
        if not message:
            return
        for item in reaction.get("reactions", []):
            reaction_type = item.get("type") or {}
            if reaction_type.get("type") != "emoji":
                continue
            emoji = reaction_type.get("emoji")
            if emoji in {"👍", "👎"}:
                self._apply_reaction_count(message, emoji, int(item.get("total_count") or 0))

    def _apply_reaction_count(self, message: CommonMessage, emoji: str, count: int) -> None:
        if emoji == "👍" and count >= self.settings.reputation_helpful_reaction_threshold:
            self.store.award_helpful_reputation(message, count, reaction_emoji=emoji)
        elif emoji == "👎" and count >= self.settings.reputation_block_link_reaction_threshold:
            from backend.services.link_safety import extract_urls

            urls = extract_urls(message.text)
            if urls:
                self.store.flag_links_from_reactions(message, urls, count)

    def _reaction_message(self, chat_id: str, message_id: str) -> CommonMessage | None:
        cached = self._message_cache.get((chat_id, message_id))
        if cached:
            return cached
        try:
            return self.store.get_message(f"telegram-{chat_id}-{message_id}")
        except Exception:
            logger.exception("Could not load Telegram message %s for reaction processing", message_id)
            return None

    @staticmethod
    def _message_link(chat: dict[str, Any], message_id: Any) -> str | None:
        """Best-effort deep link so Admin can jump straight to the message.

        Public chats resolve with their @username. Private supergroups/channels
        still work via the /c/ scheme using their internal id (chat id minus
        the -100 prefix); it only opens for members already in the chat, same
        as any other Telegram internal link. Legacy basic groups (not yet
        upgraded to a supergroup) have no working link format, so this
        returns None for those.
        """
        username = chat.get("username")
        if username:
            return f"https://t.me/{username}/{message_id}"
        chat_id = str(chat.get("id") or "")
        if chat_id.startswith("-100"):
            return f"https://t.me/c/{chat_id[4:]}/{message_id}"
        return None

    @staticmethod
    def _common_message(message: dict[str, Any]) -> CommonMessage:
        chat = message.get("chat") or {}
        reply = message.get("reply_to_message") or {}
        sender = message.get("from") or {}
        date_value = int(message.get("date") or 0)
        author_name = " ".join(
            part for part in (sender.get("first_name"), sender.get("last_name")) if part
        ) or sender.get("username") or None
        platform_message_id = message.get("message_id")
        if platform_message_id is None and message.get("ephemeral_message_id") is not None:
            platform_message_id = f"ephemeral-{message['ephemeral_message_id']}"
        return CommonMessage(
            message_id=f"telegram-{chat.get('id')}-{platform_message_id}",
            platform="telegram",
            community_id=str(chat.get("id") or "telegram"),
            channel_id=str(chat.get("id") or "general"),
            thread_key=str(reply.get("message_id") or platform_message_id),
            parent_message_id=str(reply["message_id"]) if reply.get("message_id") else None,
            author_id=str(sender.get("id") or "anonymous"),
            author_name=author_name,
            text=str(message.get("text") or "").strip(),
            timestamp=datetime.fromtimestamp(date_value, UTC) if date_value else datetime.now(UTC),
            source_url=TelegramRagBot._message_link(chat, message.get("message_id")),
            raw=message,
        )
