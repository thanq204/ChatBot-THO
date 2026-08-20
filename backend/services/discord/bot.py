"""Discord Gateway listener for mention -> local RAG replies."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import tempfile
import threading
import time
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.config import Settings, get_settings
from backend.models.operations import RESERVED_BOT_COMMANDS, CommonMessage
from backend.services.chat_orchestrator import ChatOrchestrator
from backend.services.operations_pipeline import OperationsPipeline
from backend.services.operations_store import OperationsStore
from backend.services.question_intent import is_reusable_faq_question
from backend.services.link_safety import extract_urls
from backend.services.telegram.alerts import TelegramAlertSender
from backend.services.platform_moderation import PlatformModerationService

logger = logging.getLogger(__name__)

# The one Discord listener running in this process, if any. The admin API
# uses this to ask a live bot to re-register slash commands right after an
# Admin adds/edits/deletes one, instead of waiting for the next restart.
_active_bot: "DiscordRagBot | None" = None


def notify_commands_changed() -> None:
    """Best-effort: re-sync Discord slash commands after a command-content write.

    No-ops quietly if no Discord listener is running in this process (e.g.
    the token isn't configured, or we're in a worker that only serves HTTP).
    """
    if _active_bot is not None:
        _active_bot.resync_commands()


class DiscordRagBot:
    """Run a small, opt-in Discord listener outside FastAPI's event loop.

    The bot receives and moderates every message in channels where it has
    permission. It only writes a visible RAG reply when a user mentions the
    bot; mention is not required for realtime moderation or Telegram alerts.
    The configured default channel remains the target for historical sync only.
    It uses the same Supabase knowledge hub as the web RAG endpoint, so
    document imports and policy edits are available to Discord replies.
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
        self.platform_moderation = PlatformModerationService(self.settings)
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client: Any = None
        self._tree: Any = None
        self._run_command_async: Any = None
        self._dynamic_command_names: set[str] = set()
        self._lock_handle: Any = None
        self._seen_message_ids: set[str] = set()
        self._background_tasks: set[Any] = set()

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
        global _active_bot
        _active_bot = self

    def stop(self) -> None:
        global _active_bot
        if _active_bot is self:
            _active_bot = None
        if self._client and self._loop and not self._loop.is_closed():
            future = asyncio.run_coroutine_threadsafe(self._client.close(), self._loop)
            try:
                future.result(timeout=5)
            except Exception:
                logger.debug("Discord RAG listener close did not finish cleanly.", exc_info=True)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._release_process_lock()

    def resync_commands(self) -> None:
        """Ask the running bot to re-register custom slash commands.

        Called from the FastAPI request thread after an Admin add/edit/delete;
        schedules the actual Discord API work on the bot's own event loop and
        returns immediately without waiting on it.
        """
        if not self._client or not self._loop or self._loop.is_closed():
            return
        try:
            asyncio.run_coroutine_threadsafe(self._resync_commands_async(), self._loop)
        except RuntimeError:
            logger.debug("Discord command resync skipped; listener loop not ready.", exc_info=True)

    def _register_dynamic_commands(self) -> set[str]:
        """Register a slash command for every Admin-created command that isn't
        already covered by the decorators below (event/daily/weekly/... and
        the reserved built-ins) and is scoped to Discord."""
        if self._tree is None or self._run_command_async is None:
            return set()
        registered: set[str] = set()
        try:
            entries = self.store.list_command_content()
        except Exception:
            logger.exception("Could not load command content for Discord slash-command sync.")
            return registered
        for entry in entries:
            if entry.command in RESERVED_BOT_COMMANDS or "discord" not in entry.platforms:
                continue
            handler = self._make_dynamic_handler(entry.command)
            description = (entry.description or f"Lệnh /{entry.command}").strip()[:100] or f"Lệnh /{entry.command}"
            self._tree.command(name=entry.command, description=description)(handler)
            registered.add(entry.command)
        return registered

    def _make_dynamic_handler(self, command_name: str):
        async def _handler(interaction: Any) -> None:
            await self._run_command_async(interaction, command_name)

        _handler.__name__ = f"dynamic_{command_name}"
        return _handler

    async def _sync_tree(self) -> list[Any]:
        """Push the command tree to Discord: the normal global sync, plus an
        instant guild-scoped copy for every server the bot is already in.
        Global propagation alone can take Discord up to an hour."""
        synced = await self._tree.sync()
        for guild in self._client.guilds:
            self._tree.copy_global_to(guild=guild)
            await self._tree.sync(guild=guild)
        return synced

    async def _resync_commands_async(self) -> None:
        if self._tree is None or self._client is None:
            return
        try:
            for name in list(self._dynamic_command_names):
                self._tree.remove_command(name)
            self._dynamic_command_names = self._register_dynamic_commands()
            await self._sync_tree()
            print(f"[Discord] Slash commands re-synced after Admin update ({len(self._dynamic_command_names)} custom).", flush=True)
        except Exception:
            logger.exception("Discord slash command resync failed.")
            print("[Discord] Slash command resync failed; retry from the dashboard or restart the bot.", flush=True)

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
        intents.reactions = True
        intents.guild_reactions = True
        client = discord.Client(intents=intents)
        tree = discord.app_commands.CommandTree(client)
        self._client = client
        self._tree = tree
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

        # Exposed so resync_commands() can reuse this handler for commands
        # created from the dashboard after the bot has already started.
        self._run_command_async = run_command

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

        # Anything an Admin created from the dashboard beyond the fixed set
        # above (e.g. /gioithieu), scoped to Discord in its platform list.
        self._dynamic_command_names = self._register_dynamic_commands()

        @client.event
        async def on_ready() -> None:
            await asyncio.to_thread(
                self.store.mark_platform_bot,
                "discord",
                str(client.user.id),
                getattr(client.user, "display_name", None) or getattr(client.user, "name", None),
            )
            try:
                synced = await self._sync_tree()
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
            if not self._is_member_message(message, client.user):
                return
            print(f"[Discord] Member message in channel {getattr(message.channel, 'id', 'unknown')}", flush=True)
            message_id = str(getattr(message, "id", ""))
            if message_id and message_id in self._seen_message_ids:
                return
            if message_id:
                self._seen_message_ids.add(message_id)

            common_message = self._common_message(message)
            blocked_links = await asyncio.to_thread(self.store.find_blocked_links, common_message.text)
            if blocked_links:
                deleted = False
                try:
                    await message.delete(reason="Known community-blocked link")
                    deleted = True
                except Exception:
                    logger.warning(
                        "Discord could not delete blocked-link message %s; check Manage Messages permission.",
                        message_id,
                        exc_info=True,
                    )

                async def process_blocked_link() -> None:
                    result = None
                    try:
                        result = await asyncio.to_thread(self.pipeline.analyze, common_message)
                        await asyncio.to_thread(
                            self.store.add_audit,
                            result.incident_id,
                            common_message.message_id,
                            "known_blocked_link_seen",
                            "system",
                            {
                                "canonical_url": blocked_links[0].canonical_url,
                                "author_id": common_message.author_id,
                                "deleted": deleted,
                            },
                        )
                    except Exception:
                        logger.exception("Blocked-link persistence failed for Discord message %s", message_id)
                    await asyncio.to_thread(
                        self.telegram_alerts.send_blocked_link_alert,
                        common_message,
                        blocked_links[0].canonical_url,
                        deleted=deleted,
                    )
                    if result:
                        await asyncio.to_thread(
                            self.platform_moderation.send_automatic_warning,
                            common_message,
                            result,
                            self.store,
                        )

                task = asyncio.create_task(process_blocked_link())
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)
                return

            mentioned = client.user in message.mentions or bool(re.search(fr"<@!?{client.user.id}>", message.content or ""))
            started = time.perf_counter()
            outcome = None
            result = None
            tracking_message = None
            try:
                if mentioned:
                    question = re.sub(r"<@!?\d+>", "", message.content or "").strip()
                    # The mention is routing metadata, not user intent. Pass
                    # only the actual command/question through every chat
                    # level so e.g. "@bot /help" reaches the Rule router.
                    chat_message = common_message.model_copy(update={"text": question or " "})
                    outcome = await asyncio.to_thread(
                        self.chat.reply,
                        chat_message,
                        None,
                        track_question=False,
                    )
                    result = outcome.moderation
                    if outcome.stage in {"rag", "llm"} and is_reusable_faq_question(chat_message.text):
                        tracking_message = chat_message
                else:
                    result = await asyncio.to_thread(self.pipeline.analyze, common_message)
            except Exception:
                logger.exception("Realtime moderation failed for Discord message %s", message_id)
                print(f"[Discord] Moderation failed for message {message_id}; listener continues.", flush=True)
                return

            if mentioned:
                logger.info("Discord mention received in channel %s", message.channel.id)
                print(f"[Discord] Mention received in channel {message.channel.id}", flush=True)
                try:
                    await message.reply(
                        outcome.answer[: self.settings.discord_reply_max_chars],
                        mention_author=False,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    logger.info(
                        "Discord reply sent in channel %s with stage=%s latency_ms=%s",
                        message.channel.id,
                        outcome.stage,
                        latency_ms,
                    )
                    print(
                        f"[Discord] Reply sent in channel {message.channel.id} "
                        f"stage={outcome.stage} latency_ms={latency_ms}",
                        flush=True,
                    )
                except Exception:
                    logger.exception("Discord reply failed.")
                    print("[Discord] Reply failed; check channel permissions.", flush=True)

            async def post_process() -> None:
                try:
                    if result and await asyncio.to_thread(self.telegram_alerts.send_alert, common_message, result):
                        logger.info("Telegram alert sent for Discord message %s", message_id)
                        print(f"[Telegram] Alert sent for Discord message {message_id}", flush=True)
                    if result:
                        warning = await asyncio.to_thread(
                            self.platform_moderation.send_automatic_warning,
                            common_message,
                            result,
                            self.store,
                        )
                        if warning:
                            logger.info("Automatic Discord warning DM for %s completed=%s", message_id, warning.completed)
                    if tracking_message is not None:
                        await asyncio.to_thread(
                            self.store.record_member_question,
                            tracking_message,
                            outcome_stage=outcome.stage,
                        )
                except Exception:
                    logger.exception("Discord post-processing failed for message %s", message_id)

            task = asyncio.create_task(post_process())
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

        @client.event
        async def on_raw_reaction_add(payload: Any) -> None:
            emoji = str(getattr(payload, "emoji", ""))
            if emoji not in {"✅", "❌"} or getattr(payload, "guild_id", None) is None:
                return
            try:
                channel = client.get_channel(payload.channel_id) or await client.fetch_channel(payload.channel_id)
                message = await channel.fetch_message(payload.message_id)
                if not self._is_member_message(message, client.user):
                    return
                target_reaction = next((item for item in message.reactions if str(item.emoji) == emoji), None)
                if target_reaction is None:
                    return
                reactor_ids: set[int] = set()
                async for user in target_reaction.users(limit=None):
                    if not getattr(user, "bot", False) and user.id != message.author.id:
                        reactor_ids.add(user.id)
                reaction_count = len(reactor_ids)
                common_message = self._common_message(message)
                if emoji == "✅" and reaction_count >= self.settings.reputation_helpful_reaction_threshold:
                    await asyncio.to_thread(self.store.award_helpful_reputation, common_message, reaction_count)
                elif emoji == "❌" and reaction_count >= self.settings.reputation_block_link_reaction_threshold:
                    urls = extract_urls(common_message.text)
                    if urls:
                        await asyncio.to_thread(
                            self.store.flag_links_from_reactions,
                            common_message,
                            urls,
                            reaction_count,
                        )
            except Exception:
                logger.exception(
                    "Discord reaction reputation processing failed for message %s",
                    getattr(payload, "message_id", "unknown"),
                )

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
            author_name=getattr(author, "display_name", None) or getattr(author, "global_name", None) or getattr(author, "name", None),
            text=(getattr(message, "content", "") or "").strip() or "[attachment]",
            timestamp=created_at,
            source_url=source_url,
            raw={
                "guild_name": getattr(guild, "name", None),
                "channel_name": getattr(channel, "name", None),
                "author_is_bot": bool(getattr(author, "bot", False)),
                "webhook_id": str(getattr(message, "webhook_id", "") or "") or None,
                "application_id": str(getattr(message, "application_id", "") or "") or None,
            },
        )

    @staticmethod
    def _is_member_message(message: Any, client_user: Any) -> bool:
        """Accept human member inputs only; reject bot/webhook/application/system output."""
        author = getattr(message, "author", None)
        if author is None or client_user is None or getattr(author, "bot", False):
            return False
        if str(getattr(author, "id", "")) == str(getattr(client_user, "id", "")):
            return False
        if getattr(message, "webhook_id", None) is not None or getattr(message, "application_id", None) is not None:
            return False
        is_system = getattr(message, "is_system", None)
        if callable(is_system) and is_system():
            return False
        return True

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
