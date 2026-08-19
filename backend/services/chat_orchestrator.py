"""Shared Rule -> Moderation -> FAQ -> RAG/LLM conversation flow."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from backend.config import Settings, get_settings
from backend.models.operations import ChatOutcome, CommonMessage
from backend.services.operations_pipeline import OperationsPipeline
from backend.services.operations_store import OperationsStore
from src.ai_models import CommunityAIPipeline, RetrievalCandidate

logger = logging.getLogger(__name__)
VIETNAM_TIMEZONE = timezone(timedelta(hours=7))


class ChatOrchestrator:
    _GENERAL_LLM_PATTERNS = (
        r"\b(bạn|ban)\s+(tên|ten)\s+(là|la)\s+(gì|gi)\b",
        r"\b(tên|ten)\s+(bạn|ban)\b",
        r"\b(bạn|ban)\s+(là|la)\s+ai\b",
        r"\b(hôm nay|hom nay)\s+(là|la)?\s*(ngày|ngay)\s+(bao nhiêu|bao nhieu|mấy|may)\b",
        r"\b(hôm nay|hom nay)\s+(là|la)\s+(thứ|thu)\s+(mấy|may)\b",
        r"\b(bây giờ|bay gio|hiện tại|hien tai)\s+(là|la)?\s*(mấy giờ|may gio)\b",
        r"\b(bạn|ban)\s+(có thể|co the|làm được|lam duoc)\s+(gì|gi)\b",
    )
    STUDY_GROUP_RULES = """Nội quy nhóm học tập:
1. Trao đổi đúng chủ đề học tập và nêu rõ môn/chương khi cần.
2. Tôn trọng người khác; không công kích, chế giễu hoặc spam.
3. Không chia sẻ đáp án thi, làm hộ bài kiểm tra hoặc tài liệu bị hạn chế.
4. Khi trả lời kiến thức, ưu tiên nêu nguồn hoặc cách kiểm chứng.
5. Không đăng thông tin cá nhân, link lừa đảo hoặc quảng cáo không liên quan.
6. Báo Admin khi thấy nội dung vi phạm hoặc cần hoà giải."""

    def __init__(self, store: OperationsStore, settings: Settings | None = None, pipeline: OperationsPipeline | None = None) -> None:
        self.settings = settings or get_settings()
        self.store = store
        self.pipeline = pipeline or OperationsPipeline(store=store, settings=self.settings)
        self.ai_pipeline = CommunityAIPipeline()

    def _help_text(self, platform: str) -> str:
        """Built fresh every time so a command Admin just added/removed from
        the dashboard shows up immediately, without a code change or deploy."""
        lines = [
            "Các lệnh có thể dùng:",
            "/start — Giới thiệu bot và cách dùng",
            "/help — Xem danh sách lệnh",
            "/rule — Xem nội quy nhóm học tập",
        ]
        for entry in self.store.list_command_content():
            if platform not in entry.platforms:
                continue
            note = entry.description.strip() or f"Lệnh /{entry.command}"
            lines.append(f"/{entry.command} — {note}")
        lines += [
            "/faq — Hướng dẫn FAQ",
            "/report <link/message ID và mô tả> — Báo cáo vi phạm",
            "/settings daily|weekly on|off — Bật/tắt thông báo trong chat riêng",
        ]
        return "\n".join(lines)

    def _rule_answer(self, message: CommonMessage) -> str | None:
        cleaned = message.text.strip().lower()
        if not cleaned:
            return "Bạn hãy nhập câu hỏi hoặc dùng /help."
        if cleaned.startswith("/"):
            command, _, argument = cleaned.partition(" ")
            command = command.split("@", 1)[0]
            if command == "/start":
                return "Chào bạn! Mình là trợ lý nhóm học tập. Dùng /help để xem các lệnh và gửi câu hỏi học tập bất kỳ để được hỗ trợ."
            if command == "/help":
                return self._help_text(message.platform)
            if command in {"/rule", "/rules"}:
                return self.STUDY_GROUP_RULES
            if command == "/faq":
                return "FAQ là các câu trả lời do Admin/Mod duyệt. Nếu nhiều người hỏi một vấn đề chưa có FAQ, hệ thống sẽ đề xuất Admin tạo FAQ mới."
            if command == "/report":
                if not argument.strip():
                    return "Hãy gửi /report kèm link hoặc message ID và mô tả ngắn. Ví dụ: /report 123456 - spam link lừa đảo."
                report = self.store.create_member_report(message, argument.strip())
                return f"Đã tạo báo cáo {report.report_id}. Admin/Mod sẽ xem xét sớm nhất có thể."
            if command == "/settings":
                parts = argument.split()
                if len(parts) != 2 or parts[0] not in {"daily", "weekly"} or parts[1] not in {"on", "off"}:
                    return "Dùng /settings daily on|off hoặc /settings weekly on|off. Lệnh này chỉ áp dụng trong chat riêng."
                if message.platform == "telegram" and message.channel_id != message.author_id:
                    return "Hãy dùng /settings trong chat riêng với bot để bảo vệ lựa chọn thông báo của bạn."
                self.store.set_notification_preference(message.platform, message.author_id, parts[0], parts[1] == "on")
                return f"Đã {'bật' if parts[1] == 'on' else 'tắt'} thông báo {parts[0]} cho bạn."
            # Everything else falls back to Admin-managed content: the seeded
            # built-ins (/event, /daily, ...) and any command created later
            # from the dashboard, without needing a code change per command.
            # A command scoped to only one platform stays "unrecognized" on
            # the other, matching what a member there actually experiences.
            content = self.store.get_command_content(command[1:])
            if content and message.platform in content.platforms:
                return content.body
            return "Không nhận ra lệnh. Dùng /help để xem các lệnh."
        if cleaned in {"nội quy", "noi quy", "quy định nhóm", "quy dinh nhom"}:
            return self.STUDY_GROUP_RULES
        if re.fullmatch(r"(?:hi+|hello+|hey+|alo+|chào(?: bạn)?|xin chào|test)[!?.,\s]*", cleaned):
            return "Chào bạn! Bạn có thể dùng /help hoặc hỏi về quy định, tài liệu và hoạt động học tập."
        if len(message.text.strip()) > 8_000:
            return "Tin nhắn quá dài. Hãy rút gọn câu hỏi dưới 8.000 ký tự để mình hỗ trợ chính xác hơn."
        return None

    def reply(self, message: CommonMessage, context: list[CommonMessage] | None = None) -> ChatOutcome:
        rule_answer = self._rule_answer(message)
        if rule_answer:
            return ChatOutcome(answer=rule_answer, stage="rule", model_used="deterministic-rules")

        moderation = self.pipeline.analyze(message, context or [])
        if moderation.decision != "allow":
            answer = moderation.banner or "Tin nhắn này cần được kiểm tra theo quy định cộng đồng trước khi mình có thể trả lời thêm."
            return ChatOutcome(answer=answer, stage="moderation", model_used=moderation.model_used, moderation=moderation)

        # Every safe member question reaching the bot is captured for semantic
        # FAQ analytics, regardless of whether FAQ, RAG, or LLM answers it.
        self.store.record_member_question(message)

        faq = self.store.find_faq(message.text)
        if faq:
            return ChatOutcome(answer=faq.answer, stage="faq", model_used="admin-faq", moderation=moderation, faq_id=faq.faq_id)

        if self._is_general_llm_question(message.text):
            answer, model = self._general_llm_answer(message.text)
            label = "LLM" if model != "system-fallback" else "Hệ thống"
            return ChatOutcome(answer=f"[{label}]\n{answer}", stage="llm", model_used=model, moderation=moderation)

        # Level 4: Vector Search -> Reranker -> Relevance Gate -> cited source.
        candidates = self.store.search_knowledge_ranked(
            message.text,
            limit=self.settings.rag_candidate_limit,
        )
        if not candidates:
            self.store.record_unanswered_question(message)
            return ChatOutcome(answer="Mình chưa tìm thấy tài liệu phù hợp. Câu hỏi của bạn đã được ghi nhận để Admin cân nhắc bổ sung FAQ hoặc tài liệu.", stage="rag", model_used="vector-search", moderation=moderation, relevance_passed=False)

        source_by_id = {str(document.document_id): document for _score, document in candidates}
        model_candidates = [
            RetrievalCandidate(
                source_id=str(document.document_id),
                title=str(document.title),
                text=str(document.body),
                vector_score=vector_score,
                source_type="knowledge",
                metadata={"source_url": getattr(document, "source_url", None)},
            )
            for vector_score, document in candidates
        ]
        rag_decision = self.ai_pipeline.decide_question(
            message.text,
            (),
            (),
            model_candidates,
            # Knowledge records are already canonical answers. Returning the
            # selected source verbatim avoids unsupported LLM elaboration.
            llm_enabled=False,
        )
        if not rag_decision.relevance or not rag_decision.relevance.passed:
            self.store.record_unanswered_question(message)
            sources = []
            if rag_decision.ranked_candidates:
                best_id = rag_decision.ranked_candidates[0].candidate.source_id
                if best_id in source_by_id:
                    sources.append(source_by_id[best_id])
            return ChatOutcome(answer="[Không đủ nguồn]\nMình chưa tìm thấy nguồn tài liệu đủ liên quan để trả lời chính xác. Câu hỏi của bạn đã được ghi nhận để Admin cân nhắc bổ sung FAQ hoặc tài liệu.", stage="rag", model_used="relevance-gate", moderation=moderation, sources=sources, retrieval_score=rag_decision.relevance.score, relevance_passed=False)

        best = rag_decision.ranked_candidates[0]
        source = source_by_id[best.candidate.source_id]
        answer, model = source.body.strip(), "rag-retrieval"
        rendered = self.ai_pipeline.compose_answer(answer, rag_decision, model_used=model)
        return ChatOutcome(answer=rendered.display_text, stage="rag", model_used=model, moderation=moderation, sources=[source], retrieval_score=rag_decision.relevance.score, relevance_passed=True)

    @classmethod
    def _is_general_llm_question(cls, question: str) -> bool:
        normalized = question.strip().casefold()
        return any(re.search(pattern, normalized) for pattern in cls._GENERAL_LLM_PATTERNS)

    def _general_llm_answer(self, question: str) -> tuple[str, str]:
        now = datetime.now(VIETNAM_TIMEZONE)
        if self.settings.discord_rag_llm_enabled and self.settings.openai_api_key:
            try:
                from langchain_openai import ChatOpenAI

                llm = ChatOpenAI(
                    model=self.settings.discord_rag_model,
                    api_key=self.settings.openai_api_key,
                    temperature=0,
                    max_tokens=160,
                )
                response = llm.invoke(
                    [
                        (
                            "system",
                            "Bạn là CHAT-10, trợ lý cộng đồng học tập. "
                            f"Thời gian hệ thống tại Việt Nam là {now:%H:%M, ngày %d/%m/%Y}. "
                            "Chỉ trả lời ngắn gọn câu hỏi hội thoại về danh tính, khả năng của bot hoặc ngày giờ. "
                            "Không được bịa thông tin cá nhân, dữ liệu dự án hoặc sự kiện hiện tại khác.",
                        ),
                        ("human", question),
                    ]
                )
                content = response.content if isinstance(response.content, str) else str(response.content)
                if content.strip():
                    return content.strip(), self.settings.discord_rag_model
            except Exception:
                logger.exception("General conversation LLM failed; using deterministic system answer.")

        return self._general_system_answer(question, now), "system-fallback"

    @staticmethod
    def _general_system_answer(question: str, now: datetime) -> str:
        normalized = question.casefold()
        if "tên" in normalized or "ten" in normalized or "là ai" in normalized or "la ai" in normalized:
            return "Mình tên là CHAT-10, trợ lý cộng đồng học tập."
        if "giờ" in normalized or "gio" in normalized:
            return f"Hiện tại là {now:%H:%M} ngày {now:%d/%m/%Y} theo giờ Việt Nam."
        if "ngày" in normalized or "ngay" in normalized or "hôm nay" in normalized or "hom nay" in normalized:
            return f"Hôm nay là ngày {now:%d/%m/%Y} theo giờ Việt Nam."
        return "Mình có thể hỗ trợ nội quy, FAQ và tra cứu tài liệu học tập khi bạn tag CHAT-10."

    @staticmethod
    def _rerank_candidates(question: str, candidates: list[tuple[float, object]]) -> list[tuple[float, object, float]]:
        """Promote the vector candidate that directly matches the question."""
        tokens = set(re.findall(r"[a-zA-ZÀ-ỹ0-9]{2,}", question.lower()))
        stopwords = {"của", "với", "và", "cho", "các", "một", "những", "là", "để", "thì", "này", "mình", "bạn", "tôi", "hỏi", "về"}
        tokens -= stopwords
        reranked = []
        for vector_score, document in candidates:
            title_tokens = set(re.findall(r"[a-zA-ZÀ-ỹ0-9]{2,}", str(getattr(document, "title", "")).lower()))
            body_tokens = set(re.findall(r"[a-zA-ZÀ-ỹ0-9]{2,}", str(getattr(document, "body", "")).lower()))
            title_overlap = len(tokens & title_tokens) / max(1, len(tokens))
            body_overlap = len(tokens & body_tokens) / max(1, len(tokens))
            score = min(1.0, (0.60 * vector_score) + (0.28 * title_overlap) + (0.12 * body_overlap))
            reranked.append((vector_score, document, score))
        return sorted(reranked, key=lambda item: (item[2], item[0]), reverse=True)

    def _grounded_answer(self, question: str, title: str, body: str, *, use_llm: bool = True) -> tuple[str, str]:
        if use_llm and self.settings.discord_rag_llm_enabled and self.settings.openai_api_key:
            try:
                from langchain_openai import ChatOpenAI

                llm = ChatOpenAI(model=self.settings.discord_rag_model, api_key=self.settings.openai_api_key, temperature=self.settings.discord_rag_temperature, max_tokens=500)
                response = llm.invoke([("system", "Trả lời ngắn gọn bằng tiếng Việt, chỉ dựa vào CONTEXT."), ("human", f"QUESTION: {question}\n\nCONTEXT ({title}):\n{body[:6000]}")])
                content = response.content if isinstance(response.content, str) else str(response.content)
                if content.strip():
                    return content.strip(), self.settings.discord_rag_model
            except Exception:
                pass
        return f'Theo tài liệu "{title}": {body[:1200]}', "local-knowledge-retrieval"
