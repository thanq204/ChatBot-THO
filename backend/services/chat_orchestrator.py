"""Shared Rule -> Moderation -> FAQ -> RAG/LLM conversation flow."""

from __future__ import annotations

import re

from backend.config import Settings, get_settings
from backend.models.operations import ChatOutcome, CommonMessage
from backend.services.operations_pipeline import OperationsPipeline
from backend.services.operations_store import OperationsStore


class ChatOrchestrator:
    STUDY_GROUP_RULES = """Nội quy nhóm học tập:
1. Hỏi và trả lời đúng chủ đề học tập, ghi rõ môn/chương khi cần.
2. Tôn trọng người khác; không công kích, chế giễu hoặc spam.
3. Không chia sẻ đáp án thi, làm hộ bài kiểm tra hoặc tài liệu bị hạn chế.
4. Khi trả lời kiến thức, ưu tiên nêu nguồn hoặc cách kiểm chứng.
5. Không đăng thông tin cá nhân, link lừa đảo hay quảng cáo không liên quan.
6. Báo Admin khi thấy nội dung vi phạm hoặc cần hoà giải."""

    def __init__(self, store: OperationsStore, settings: Settings | None = None, pipeline: OperationsPipeline | None = None) -> None:
        self.settings = settings or get_settings()
        self.store = store
        self.pipeline = pipeline or OperationsPipeline(store=store, settings=self.settings)

    @staticmethod
    def _rule_answer(text: str) -> str | None:
        cleaned = text.strip().lower()
        if cleaned in {"/rules", "/rule", "nội quy", "noi quy", "quy định nhóm", "quy dinh nhom"}:
            return ChatOrchestrator.STUDY_GROUP_RULES
        if cleaned in {"/faq", "faq", "cách tạo faq", "cach tao faq"}:
            return "FAQ được Admin tạo từ câu hỏi và câu trả lời đã kiểm chứng. Nếu một câu hỏi chưa có FAQ được nhiều người hỏi, hệ thống sẽ tạo gợi ý để Admin duyệt."
        if re.fullmatch(r"(?:hi+|hello+|hey+|alo+|chào(?: bạn)?|xin chào|test)[!?.,\s]*", cleaned):
            return "Chào bạn! Bạn có thể hỏi mình về quy định, tài liệu hoặc tình huống trong cộng đồng."
        if len(text.strip()) > 8_000:
            return "Tin nhắn quá dài. Hãy rút gọn câu hỏi dưới 8.000 ký tự để mình hỗ trợ chính xác hơn."
        return None

    def reply(self, message: CommonMessage, context: list[CommonMessage] | None = None) -> ChatOutcome:
        rule_answer = self._rule_answer(message.text)
        if rule_answer:
            return ChatOutcome(answer=rule_answer, stage="rule", model_used="deterministic-rules")

        moderation = self.pipeline.analyze(message, context or [])
        if moderation.decision != "allow":
            return ChatOutcome(answer="Tin nhắn này cần được kiểm tra theo quy định cộng đồng trước khi mình có thể trả lời thêm.", stage="moderation", model_used=moderation.model_used, moderation=moderation)

        faq = self.store.find_faq(message.text)
        if faq:
            return ChatOutcome(answer=faq.answer, stage="faq", model_used="admin-faq", moderation=moderation, faq_id=faq.faq_id)

        self.store.record_unanswered_question(message)
        sources = self.store.search_knowledge(message.text, limit=1)
        if not sources:
            return ChatOutcome(answer="Mình chưa tìm thấy tài liệu phù hợp. Câu hỏi của bạn đã được ghi nhận để Admin cân nhắc bổ sung FAQ hoặc tài liệu.", stage="rag", model_used="local-knowledge-retrieval", moderation=moderation)
        answer, model = self._grounded_answer(message.text, sources[0].title, sources[0].body)
        return ChatOutcome(answer=answer, stage="rag", model_used=model, moderation=moderation, sources=sources)

    def _grounded_answer(self, question: str, title: str, body: str) -> tuple[str, str]:
        if self.settings.discord_rag_llm_enabled and self.settings.openai_api_key:
            try:
                from langchain_openai import ChatOpenAI

                llm = ChatOpenAI(model=self.settings.discord_rag_model, api_key=self.settings.openai_api_key, temperature=self.settings.discord_rag_temperature, max_tokens=500)
                response = llm.invoke([
                    ("system", "Trả lời ngắn gọn bằng tiếng Việt, chỉ dựa vào CONTEXT. Nếu thiếu thông tin, nói rõ là chưa đủ dữ liệu."),
                    ("human", f"QUESTION: {question}\n\nCONTEXT ({title}):\n{body[:6000]}"),
                ])
                content = response.content if isinstance(response.content, str) else str(response.content)
                if content.strip():
                    return content.strip(), self.settings.discord_rag_model
            except Exception:
                pass
        return f'Theo tài liệu "{title}": {body[:1200]}', "local-knowledge-retrieval"
