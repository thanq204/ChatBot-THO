"""Opt-in Telegram polling bot for moderation and grounded RAG replies."""

from __future__ import annotations

import logging
import re
import threading
from datetime import UTC, datetime
from typing import Any

import requests

from backend.config import Settings, get_settings
from backend.models.operations import RESERVED_BOT_COMMANDS, CommonMessage
from backend.services.chat_orchestrator import ChatOrchestrator
from backend.services.operations_pipeline import OperationsPipeline
from backend.services.operations_store import OperationsStore
from backend.services.question_intent import is_reusable_faq_question
from backend.services.platform_moderation import PlatformModerationService
from backend.services.telegram.alerts import TelegramAlertSender

logger = logging.getLogger(__name__)

_active_bot: "TelegramRagBot | None" = None


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
            {"command": "report", "description": "Báo cáo vi phạm"},
            {"command": "admin", "description": "Liên hệ Admin/Mod"},
            {"command": "resources", "description": "Tài liệu học tập"},
            {"command": "settings", "description": "Cài đặt thông báo"},
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
                params: dict[str, object] = {"timeout": self.settings.telegram_polling_timeout_seconds, "allowed_updates": '["message", "message_reaction", "message_reaction_count"]'}
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
        text = str(message.get("text") or "").strip()
        sender = message.get("from") or {}
        if sender.get("is_bot"):
            return
        if not text:
            self._send_message(str((message.get("chat") or {}).get("id")), "Bạn hãy nhập câu hỏi hoặc dùng /help.")
            return
        common = self._common_message(message)
        self._message_cache[(common.channel_id, str(message.get("message_id")))] = common
        if len(self._message_cache) > 5_000:
            self._message_cache.pop(next(iter(self._message_cache)))
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
            self.platform_moderation.send_automatic_warning(common, result, self.store)
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
        if self._username:
            mention = f"@{self._username}"
            if mention in text.lower():
                return re.sub(re.escape(mention), "", text, flags=re.I).strip() or "hello"
        return None

    def _send_message(self, chat_id: str, text: str, *, reply_to_message_id: int | None = None) -> None:
        try:
            payload: dict[str, object] = {"chat_id": chat_id, "text": text[:self.settings.telegram_reply_max_chars]}
            if reply_to_message_id is not None:
                payload["reply_to_message_id"] = reply_to_message_id
            response = requests.post(f"{self._api_base}/sendMessage", json=payload, timeout=20)
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("Telegram RAG reply failed.")

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
        return CommonMessage(
            message_id=f"telegram-{chat.get('id')}-{message.get('message_id')}",
            platform="telegram",
            community_id=str(chat.get("id") or "telegram"),
            channel_id=str(chat.get("id") or "general"),
            thread_key=str(reply.get("message_id") or message.get("message_id")),
            parent_message_id=str(reply["message_id"]) if reply.get("message_id") else None,
            author_id=str(sender.get("id") or "anonymous"),
            author_name=author_name,
            text=str(message.get("text") or "").strip(),
            timestamp=datetime.fromtimestamp(date_value, UTC) if date_value else datetime.now(UTC),
            source_url=TelegramRagBot._message_link(chat, message.get("message_id")),
            raw=message,
        )
