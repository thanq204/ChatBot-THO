"""Shared Rule -> Moderation -> FAQ -> RAG/LLM conversation flow."""

from __future__ import annotations

import re

from backend.config import Settings, get_settings
from backend.models.operations import ChatOutcome, CommonMessage
from backend.services.operations_pipeline import OperationsPipeline
from backend.services.operations_store import OperationsStore


class ChatOrchestrator:
    STUDY_GROUP_RULES = """Nội quy nhóm học tập:
1. Trao đổi đúng chủ đề học tập và nêu rõ môn/chương khi cần.
2. Tôn trọng người khác; không công kích, chế giễu hoặc spam.
3. Không chia sẻ đáp án thi, làm hộ bài kiểm tra hoặc tài liệu bị hạn chế.
4. Khi trả lời kiến thức, ưu tiên nêu nguồn hoặc cách kiểm chứng.
5. Không đăng thông tin cá nhân, link lừa đảo hoặc quảng cáo không liên quan.
6. Báo Admin khi thấy nội dung vi phạm hoặc cần hoà giải."""

    HELP_TEXT = """Các lệnh có thể dùng:
/start — Giới thiệu bot và cách dùng
/help — Xem danh sách lệnh
/rule — Xem nội quy nhóm học tập
/event — Xem sự kiện/lịch học gần nhất
/daily — Xem việc cần làm hôm nay
/weekly — Xem kế hoạch tuần
/faq — Hướng dẫn FAQ
/report <link/message ID và mô tả> — Báo cáo vi phạm
/admin — Cách liên hệ Admin/Mod
/resources — Tài liệu học tập chính
/settings daily|weekly on|off — Bật/tắt thông báo trong chat riêng"""

    def __init__(self, store: OperationsStore, settings: Settings | None = None, pipeline: OperationsPipeline | None = None) -> None:
        self.settings = settings or get_settings()
        self.store = store
        self.pipeline = pipeline or OperationsPipeline(store=store, settings=self.settings)

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
                return self.HELP_TEXT
            if command in {"/rule", "/rules"}:
                return self.STUDY_GROUP_RULES
            if command == "/faq":
                return "FAQ là các câu trả lời do Admin/Mod duyệt. Nếu nhiều người hỏi một vấn đề chưa có FAQ, hệ thống sẽ đề xuất Admin tạo FAQ mới."
            if command in {"/event", "/daily", "/weekly", "/resources", "/admin"}:
                content = self.store.get_command_content(command[1:])
                return content.body if content else "Chưa có thông báo mới, vui lòng quay lại sau."
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
            return ChatOutcome(answer="Tin nhắn này cần được kiểm tra theo quy định cộng đồng trước khi mình có thể trả lời thêm.", stage="moderation", model_used=moderation.model_used, moderation=moderation)

        faq = self.store.find_faq(message.text)
        if faq:
            return ChatOutcome(answer=faq.answer, stage="faq", model_used="admin-faq", moderation=moderation, faq_id=faq.faq_id)

        # Level 4: Vector Search -> Reranker -> Relevance Gate -> LLM.
        candidates = self.store.search_knowledge_ranked(
            message.text,
            limit=self.settings.rag_candidate_limit,
        )
        if not candidates:
            self.store.record_unanswered_question(message)
            return ChatOutcome(answer="Mình chưa tìm thấy tài liệu phù hợp. Câu hỏi của bạn đã được ghi nhận để Admin cân nhắc bổ sung FAQ hoặc tài liệu.", stage="rag", model_used="vector-search", moderation=moderation, relevance_passed=False)

        _vector_score, source, rerank_score = self._rerank_candidates(message.text, candidates)[0]
        if rerank_score < self.settings.rag_relevance_threshold:
            self.store.record_unanswered_question(message)
            return ChatOutcome(answer="Mình chưa tìm thấy nguồn tài liệu đủ liên quan để trả lời chính xác. Câu hỏi của bạn đã được ghi nhận để Admin cân nhắc bổ sung FAQ hoặc tài liệu.", stage="rag", model_used="relevance-gate", moderation=moderation, sources=[source], retrieval_score=rerank_score, relevance_passed=False)

        answer, model = self._grounded_answer(message.text, source.title, source.body)
        return ChatOutcome(answer=answer, stage="rag", model_used=model, moderation=moderation, sources=[source], retrieval_score=rerank_score, relevance_passed=True)

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

    def _grounded_answer(self, question: str, title: str, body: str) -> tuple[str, str]:
        if self.settings.discord_rag_llm_enabled and self.settings.openai_api_key:
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
