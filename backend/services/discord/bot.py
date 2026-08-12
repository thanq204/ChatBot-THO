"""Discord Gateway listener for mention -> local RAG replies."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import tempfile
import threading
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.config import Settings, get_settings
from backend.models.operations import CommonMessage
from backend.services.chat_orchestrator import ChatOrchestrator
from backend.services.operations_pipeline import OperationsPipeline
from backend.services.operations_store import OperationsStore
from backend.services.telegram.alerts import TelegramAlertSender

logger = logging.getLogger(__name__)


class DiscordRagBot:
    """Run a small, opt-in Discord listener outside FastAPI's event loop.

    The bot receives and moderates every message in channels where it has
    permission. It only writes a visible RAG reply when a user mentions the
    bot; mention is not required for realtime moderation or Telegram alerts.
    The configured default channel remains the target for historical sync only.
    It uses the same SQLite knowledge hub as the web RAG endpoint, so document
    imports and policy edits are immediately available to Discord replies.
    """

    def __init__(
        self,
        store: OperationsStore,
        settings: Settings | None = None,
        pipeline: OperationsPipeline | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.store = store
        self.pipeline = pipeline or OperationsPipeline(store=self.store, settings=self.settings)
        self.chat = ChatOrchestrator(self.store, self.settings, self.pipeline)
        self.telegram_alerts = TelegramAlertSender(self.settings)
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client: Any = None
        self._lock_handle: Any = None
        self._seen_message_ids: set[str] = set()

    def _acquire_process_lock(self) -> bool:
        token_hash = hashlib.sha256(self.settings.discord_bot_token.encode("utf-8")).hexdigest()[:16]
        lock_path = Path(tempfile.gettempdir()) / f"ai20k-discord-listener-{token_hash}.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = lock_path.open("a+")
        try:
            handle.seek(0)
            handle.write("0")
            handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, ImportError):
            handle.close()
            return False
        self._lock_handle = handle
        return True

    def _release_process_lock(self) -> None:
        if not self._lock_handle:
            return
        try:
            if os.name == "nt":
                import msvcrt
                self._lock_handle.seek(0)
                msvcrt.locking(self._lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_UN)
        except (OSError, ImportError):
            pass
        finally:
            self._lock_handle.close()
            self._lock_handle = None

    def start(self) -> None:
        if not self.settings.discord_listener_enabled:
            logger.info("Discord RAG listener disabled by DISCORD_LISTENER_ENABLED.")
            return
        if not self.settings.discord_bot_token:
            logger.warning("Discord RAG listener skipped: DISCORD_BOT_TOKEN is missing.")
            return
        if self._thread and self._thread.is_alive():
            return
        if not self._acquire_process_lock():
            logger.warning("Discord RAG listener skipped: another listener process is already active.")
            print("[Discord] Listener already active; skipped duplicate connection.", flush=True)
            return
        print("[Discord] Starting realtime RAG listener...", flush=True)
        self._thread = threading.Thread(target=self._run, name="discord-rag-listener", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._client and self._loop and not self._loop.is_closed():
            future = asyncio.run_coroutine_threadsafe(self._client.close(), self._loop)
            try:
                future.result(timeout=5)
            except Exception:
                logger.debug("Discord RAG listener close did not finish cleanly.", exc_info=True)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._release_process_lock()

    def _run(self) -> None:
        try:
            import discord
        except ImportError:
            logger.error("Discord listener unavailable. Install dependencies with: pip install -r requirements.txt")
            return

        intents = discord.Intents.default()
        intents.guilds = True
        intents.messages = True
        intents.guild_messages = True
        intents.dm_messages = True
        intents.message_content = True
        client = discord.Client(intents=intents)
        tree = discord.app_commands.CommandTree(client)
        self._client = client
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        async def run_command(interaction: Any, command: str, argument: str = "") -> None:
            common = CommonMessage(
                message_id=f"discord-command-{interaction.id}", platform="discord",
                community_id=str(getattr(getattr(interaction, "guild", None), "id", "discord")),
                channel_id=str(getattr(getattr(interaction, "channel", None), "id", "general")),
                author_id=str(interaction.user.id), text=f"/{command}" + (f" {argument}" if argument else " "),
                timestamp=datetime.now(UTC), raw={"interaction_id": str(interaction.id)},
            )
            outcome = await asyncio.to_thread(self.chat.reply, common, [])
            await interaction.response.send_message(outcome.answer[: self.settings.discord_reply_max_chars], ephemeral=False)

        @tree.command(name="help", description="Xem danh sách lệnh")
        async def help_command(interaction: Any) -> None:
            await run_command(interaction, "help")

        @tree.command(name="start", description="Giới thiệu bot và cách dùng")
        async def start_command(interaction: Any) -> None:
            await run_command(interaction, "start")

        @tree.command(name="rule", description="Xem nội quy nhóm học tập")
        async def rule_command(interaction: Any) -> None:
            await run_command(interaction, "rule")

        @tree.command(name="event", description="Xem sự kiện hoặc lịch học")
        async def event_command(interaction: Any) -> None:
            await run_command(interaction, "event")

        @tree.command(name="daily", description="Xem việc cần làm hôm nay")
        async def daily_command(interaction: Any) -> None:
            await run_command(interaction, "daily")

        @tree.command(name="weekly", description="Xem kế hoạch tuần")
        async def weekly_command(interaction: Any) -> None:
            await run_command(interaction, "weekly")

        @tree.command(name="faq", description="Xem hướng dẫn FAQ")
        async def faq_command(interaction: Any) -> None:
            await run_command(interaction, "faq")

        @tree.command(name="resources", description="Xem tài liệu học tập")
        async def resources_command(interaction: Any) -> None:
            await run_command(interaction, "resources")

        @tree.command(name="admin", description="Cách liên hệ Admin hoặc Mod")
        async def admin_command(interaction: Any) -> None:
            await run_command(interaction, "admin")

        @tree.command(name="report", description="Báo cáo spam hoặc vi phạm")
        async def report_command(interaction: Any, details: str) -> None:
            await run_command(interaction, "report", details)

        @tree.command(name="settings", description="Bật hoặc tắt thông báo daily/weekly")
        async def settings_command(interaction: Any, kind: str, enabled: bool) -> None:
            await run_command(interaction, "settings", f"{kind} {'on' if enabled else 'off'}")

        @client.event
        async def on_ready() -> None:
            try:
                synced = await tree.sync()
                print(f"[Discord] Slash commands synced: {', '.join(command.name for command in synced)}", flush=True)
            except Exception as exc:
                logger.exception("Discord application command registration failed.")
                print(f"[Discord] Slash command sync failed: {type(exc).__name__}. Reinvite the app with applications.commands scope.", flush=True)
            logger.info("Discord RAG listener ready as %s", client.user)
            print(f"[Discord] RAG listener ready as {client.user}", flush=True)
            telegram_status = "configured" if self.telegram_alerts.configured else "not configured"
            print(f"[Telegram] Realtime alerts {telegram_status} (token/chat ID hidden)", flush=True)

        @client.event
        async def on_message(message: Any) -> None:
            print(f"[Discord] Message event in channel {getattr(message.channel, 'id', 'unknown')}", flush=True)
            if message.author.bot or client.user is None:
                return
            message_id = str(getattr(message, "id", ""))
            if message_id and message_id in self._seen_message_ids:
                return
            if message_id:
                self._seen_message_ids.add(message_id)

            common_message = self._common_message(message)
            mentioned = client.user in message.mentions or bool(re.search(fr"<@!?{client.user.id}>", message.content or ""))
            try:
                if mentioned:
                    question = re.sub(r"<@!?\d+>", "", message.content or "").strip()
                    # The mention is routing metadata, not user intent. Pass
                    # only the actual command/question through every chat
                    # level so e.g. "@bot /help" reaches the Rule router.
                    chat_message = common_message.model_copy(update={"text": question or " "})
                    outcome = await asyncio.to_thread(self.chat.reply, chat_message, [])
                    result = outcome.moderation
                else:
                    result = await asyncio.to_thread(self.pipeline.analyze, common_message, [])
                    outcome = None
                if result and await asyncio.to_thread(self.telegram_alerts.send_alert, common_message, result):
                    logger.info("Telegram alert sent for Discord message %s", message_id)
                    print(f"[Telegram] Alert sent for Discord message {message_id}", flush=True)
            except Exception:
                logger.exception("Realtime moderation failed for Discord message %s", message_id)
                print(f"[Discord] Moderation failed for message {message_id}; listener continues.", flush=True)

            if not mentioned:
                return
            logger.info("Discord mention received in channel %s", message.channel.id)
            print(f"[Discord] Mention received in channel {message.channel.id}", flush=True)
            answer = outcome.answer if outcome else self._answer(question)
            try:
                await message.reply(
                    answer[: self.settings.discord_reply_max_chars],
                    mention_author=False,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                logger.info("Discord RAG reply sent in channel %s", message.channel.id)
                print(f"[Discord] RAG reply sent in channel {message.channel.id}", flush=True)
            except Exception:
                logger.exception("Discord RAG reply failed.")
                print("[Discord] RAG reply failed; check channel permissions.", flush=True)

        try:
            self._loop.run_until_complete(client.start(self.settings.discord_bot_token))
        except Exception:
            logger.exception("Discord RAG listener stopped.")
            print("[Discord] Listener stopped; check token, intents and permissions.", flush=True)
        finally:
            self._client = None
            if self._loop and not self._loop.is_closed():
                self._loop.close()

    @staticmethod
    def _common_message(message: Any) -> CommonMessage:
        guild = getattr(message, "guild", None)
        channel = getattr(message, "channel", None)
        author = getattr(message, "author", None)
        reference = getattr(message, "reference", None)
        created_at = getattr(message, "created_at", None) or datetime.now(UTC)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        message_id = str(getattr(message, "id", "discord-message"))
        channel_id = str(getattr(channel, "id", "general"))
        parent_id = getattr(reference, "message_id", None)
        guild_id = str(getattr(guild, "id", "discord"))
        source_url = getattr(message, "jump_url", None)
        return CommonMessage(
            message_id=f"discord-{message_id}",
            platform="discord",
            community_id=guild_id,
            channel_id=channel_id,
            thread_key=str(parent_id or message_id),
            parent_message_id=str(parent_id) if parent_id else None,
            author_id=str(getattr(author, "id", "anonymous")),
            text=(getattr(message, "content", "") or "").strip() or "[attachment]",
            timestamp=created_at,
            source_url=source_url,
            raw={"guild_name": getattr(guild, "name", None), "channel_name": getattr(channel, "name", None)},
        )

    def _answer(self, question: str) -> str:
        if not question:
            return "Bạn hãy tag mình kèm câu hỏi, ví dụ: @CHAT-10 Khi nào nên hold for review?"
        if self._is_small_talk(question):
            return self._small_talk_answer(question)
        # Use the single best source. Passing several loosely related docs to
        # the LLM makes it blend facts from different guides.
        sources = self.store.search_knowledge(question, limit=1)
        if not sources:
            return "Mình chưa tìm thấy thông tin phù hợp trong knowledge hub. Bạn hãy hỏi Admin hoặc bổ sung tài liệu nhé."
        context = "\n\n".join(f"[{source.title}]\n{source.body}" for source in sources)
        if self.settings.discord_rag_llm_enabled and self.settings.openai_api_key:
            try:
                from langchain_openai import ChatOpenAI

                llm = ChatOpenAI(
                    model=self.settings.discord_rag_model,
                    api_key=self.settings.openai_api_key,
                    temperature=self.settings.discord_rag_temperature,
                    max_tokens=500,
                )
                response = llm.invoke([
                    (
                        "system",
                        "Bạn là CHAT-10, trợ lý cộng đồng. Chỉ được trả lời dựa trên CONTEXT được cung cấp. "
                        "Không được bịa, không suy đoán và không dùng kiến thức ngoài tài liệu. "
                        "Nếu context không đủ, nói rõ là chưa có thông tin và hướng người dùng hỏi Admin. "
                        "Trả lời trực tiếp câu hỏi bằng tiếng Việt tự nhiên, ngắn gọn 2-5 câu. "
                        "Không chèn tên tài liệu, không chèn phần trích dẫn và không nhắc đến CONTEXT; hệ thống sẽ tự thêm bằng chứng nguyên văn sau câu trả lời.",
                    ),
                    ("human", f"QUESTION:\n{question}\n\nCONTEXT:\n{context}"),
                ])
                content = response.content if isinstance(response.content, str) else "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part) for part in response.content
                )
                if content.strip() and self._is_grounded(content, context):
                    return self._format_source_answer(content.strip(), sources[0], question)
                logger.warning("Discord RAG answer rejected because it added unsupported facts.")
            except Exception:
                logger.exception("Discord RAG LLM failed; using grounded retrieval fallback.")
        source = sources[0]
        fallback = f"Theo tài liệu, câu trả lời nằm ở hướng dẫn về {source.title}."
        return self._format_source_answer(fallback, source, question)

    @staticmethod
    def _source_excerpt(source: Any, question: str = "") -> str:
        """Return a short verbatim evidence passage from the selected source."""
        body = str(getattr(source, "body", "") or "").strip()
        if not body:
            return "Không có đoạn nội dung để trích xuất."
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", body) if part.strip()]
        excerpt = " ".join(sentences[:2]) if sentences else body
        return excerpt[:700].rstrip()

    def _format_source_answer(self, answer: str, source: Any, question: str = "") -> str:
        excerpt = self._source_excerpt(source, question)
        return f'{answer.strip()}\n\nTrích xuất từ "{source.title}":\n“{excerpt}”'

    @staticmethod
    def _terms(text: str) -> set[str]:
        stopwords = {
            "mình", "bạn", "của", "cho", "trong", "một", "những", "được", "làm",
            "phải", "thì", "với", "này", "đó", "theo", "thông", "tin", "tài", "liệu",
            "liên", "minh", "huyền", "thoại", "gì", "nào", "hãy", "cần", "có",
        }
        normalized = unicodedata.normalize("NFC", text.lower())
        return {term for term in re.findall(r"[^\W_]{3,}", normalized, flags=re.UNICODE) if term not in stopwords}

    @classmethod
    def _is_grounded(cls, answer: str, context: str) -> bool:
        answer_terms = cls._terms(answer)
        context_terms = cls._terms(context)
        if not answer_terms:
            return True
        coverage = sum(term in context_terms for term in answer_terms) / len(answer_terms)
        return coverage >= 0.78

    @staticmethod
    def _is_small_talk(question: str) -> bool:
        normalized = unicodedata.normalize("NFC", question.lower()).strip()
        return bool(re.fullmatch(
            r"(?:hi+|hello+|hey+|alo+|chào(?: bạn)?|xin chào|bạn khỏe không|có ai không|test)[!?.,\s]*",
            normalized,
        ))

    def _small_talk_answer(self, question: str) -> str:
        if self.settings.discord_rag_llm_enabled and self.settings.openai_api_key:
            try:
                from langchain_openai import ChatOpenAI

                llm = ChatOpenAI(
                    model=self.settings.discord_rag_model,
                    api_key=self.settings.openai_api_key,
                    temperature=self.settings.discord_rag_temperature,
                    max_tokens=100,
                )
                response = llm.invoke([
                    ("system", "Bạn là CHAT-10. Trả lời lời chào ngắn gọn bằng tiếng Việt, không bịa thông tin và không cần knowledge hub."),
                    ("human", question),
                ])
                content = response.content if isinstance(response.content, str) else "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part) for part in response.content
                )
                if content.strip():
                    return content.strip()
            except Exception:
                logger.debug("Small-talk LLM failed; using local greeting fallback.", exc_info=True)
        return "Chào bạn! Mình đang sẵn sàng hỗ trợ."
