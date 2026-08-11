"""Opt-in Telegram polling bot for moderation and grounded RAG replies."""

from __future__ import annotations

import logging
import re
import threading
from datetime import UTC, datetime
from typing import Any

import requests

from backend.config import Settings, get_settings
from backend.models.operations import CommonMessage
from backend.services.chat_orchestrator import ChatOrchestrator
from backend.services.operations_pipeline import OperationsPipeline
from backend.services.operations_store import OperationsStore

logger = logging.getLogger(__name__)


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
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._offset: int | None = None
        self._seen_updates: set[int] = set()
        self._username = ""

    def start(self) -> None:
        if not self.settings.telegram_listener_enabled:
            logger.info("Telegram listener disabled by TELEGRAM_LISTENER_ENABLED.")
            return
        if not self.settings.telegram_bot_token:
            logger.warning("Telegram listener skipped: TELEGRAM_BOT_TOKEN is missing.")
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="telegram-rag-listener", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self.settings.telegram_polling_timeout_seconds + 5)

    @property
    def _api_base(self) -> str:
        return f"https://api.telegram.org/bot{self.settings.telegram_bot_token}"

    def _run(self) -> None:
        try:
            response = requests.get(f"{self._api_base}/getMe", timeout=15)
            response.raise_for_status()
            self._username = str(response.json().get("result", {}).get("username", "")).lower()
            logger.info("Telegram RAG listener ready as @%s", self._username or "bot")
        except requests.RequestException:
            logger.exception("Telegram listener stopped: getMe failed.")
            return

        while not self._stop.is_set():
            try:
                params: dict[str, object] = {"timeout": self.settings.telegram_polling_timeout_seconds, "allowed_updates": '["message"]'}
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
        if not text or sender.get("is_bot"):
            return
        common = self._common_message(message)
        question = self._question_to_answer(message, text)
        if question is not None:
            common = common.model_copy(update={"text": question})
            outcome = self.chat.reply(common, [])
            self._send_message(str(message["chat"]["id"]), outcome.answer)
        else:
            self.pipeline.analyze(common, [])

    def _question_to_answer(self, message: dict[str, Any], text: str) -> str | None:
        chat_type = str((message.get("chat") or {}).get("type", ""))
        command = re.match(r"^/(?:ask|start)(?:@\w+)?\s*(.*)$", text, re.I | re.S)
        if command:
            return command.group(1).strip() or "hello"
        if chat_type == "private":
            return text
        if self._username:
            mention = f"@{self._username}"
            if mention in text.lower():
                return re.sub(re.escape(mention), "", text, flags=re.I).strip() or "hello"
        return None

    def _send_message(self, chat_id: str, text: str) -> None:
        try:
            response = requests.post(f"{self._api_base}/sendMessage", json={"chat_id": chat_id, "text": text[:self.settings.telegram_reply_max_chars]}, timeout=20)
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("Telegram RAG reply failed.")

    @staticmethod
    def _common_message(message: dict[str, Any]) -> CommonMessage:
        chat = message.get("chat") or {}
        reply = message.get("reply_to_message") or {}
        date_value = int(message.get("date") or 0)
        return CommonMessage(
            message_id=f"telegram-{chat.get('id')}-{message.get('message_id')}",
            platform="telegram",
            community_id=str(chat.get("id") or "telegram"),
            channel_id=str(chat.get("id") or "general"),
            thread_key=str(reply.get("message_id") or message.get("message_id")),
            parent_message_id=str(reply["message_id"]) if reply.get("message_id") else None,
            author_id=str((message.get("from") or {}).get("id") or "anonymous"),
            text=str(message.get("text") or "").strip(),
            timestamp=datetime.fromtimestamp(date_value, UTC) if date_value else datetime.now(UTC),
            raw=message,
        )
