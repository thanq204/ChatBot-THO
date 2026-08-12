from datetime import UTC, datetime
from unittest.mock import Mock

from backend.config import Settings
from backend.models.operations import CommonMessage, KnowledgeDocument, MessageDecision
from backend.services.chat_orchestrator import ChatOrchestrator


def _message(message_id: str, text: str) -> CommonMessage:
    return CommonMessage(message_id=message_id, platform="telegram", author_id="member-1", text=text, timestamp=datetime.now(UTC))


def _allowed() -> MessageDecision:
    return MessageDecision(decision="allow", category="safe", severity="low", risk_score=0.0, confidence=1.0, explanation="safe", model_used="test")


def test_rag_reranks_then_allows_grounded_answer() -> None:
    document = KnowledgeDocument(document_id="DOC-1", title="Python schedule", body="Python class is on Tuesday evening.", updated_at=datetime.now(UTC))
    store = Mock()
    store.find_faq.return_value = None
    store.search_knowledge_ranked.return_value = [(0.82, document)]
    pipeline = Mock()
    pipeline.analyze.return_value = _allowed()
    chat = ChatOrchestrator(store, Settings(discord_rag_llm_enabled=False), pipeline)
    chat._grounded_answer = Mock(return_value=("Grounded answer", "test-llm"))

    outcome = chat.reply(_message("rag-pass", "When is the Python class schedule?"))

    assert outcome.stage == "rag"
    assert outcome.answer.startswith("[RAG]\nPython class is on Tuesday evening.")
    assert outcome.answer.endswith("Trích từ tài liệu: Python schedule (DOC-1)")
    assert outcome.answer.count("Python class is on Tuesday evening.") == 1
    assert outcome.relevance_passed is True
    assert outcome.retrieval_score and outcome.retrieval_score >= 0.30
    chat._grounded_answer.assert_not_called()


def test_relevance_gate_blocks_weak_candidate_before_llm() -> None:
    document = KnowledgeDocument(document_id="DOC-2", title="Club registration", body="Fill in the club registration form.", updated_at=datetime.now(UTC))
    store = Mock()
    store.find_faq.return_value = None
    store.search_knowledge_ranked.return_value = [(0.05, document)]
    pipeline = Mock()
    pipeline.analyze.return_value = _allowed()
    chat = ChatOrchestrator(store, Settings(discord_rag_llm_enabled=False), pipeline)
    chat._grounded_answer = Mock()

    outcome = chat.reply(_message("rag-gate", "How do I solve a derivative problem?"))

    assert outcome.model_used == "relevance-gate"
    assert outcome.relevance_passed is False
    store.record_unanswered_question.assert_called_once()
    chat._grounded_answer.assert_not_called()


def test_bot_identity_question_uses_standalone_llm_not_rag() -> None:
    store = Mock()
    store.find_faq.return_value = None
    pipeline = Mock()
    pipeline.analyze.return_value = _allowed()
    chat = ChatOrchestrator(store, Settings(discord_rag_llm_enabled=True), pipeline)
    chat._general_llm_answer = Mock(return_value=("Mình tên là CHAT-10.", "test-llm"))

    outcome = chat.reply(_message("llm-name", "bạn tên là gì"))

    assert outcome.stage == "llm"
    assert outcome.answer == "[LLM]\nMình tên là CHAT-10."
    assert outcome.model_used == "test-llm"
    store.search_knowledge_ranked.assert_not_called()
    store.record_unanswered_question.assert_not_called()


def test_current_date_question_uses_llm_with_system_context() -> None:
    store = Mock()
    store.find_faq.return_value = None
    pipeline = Mock()
    pipeline.analyze.return_value = _allowed()
    chat = ChatOrchestrator(store, Settings(discord_rag_llm_enabled=True), pipeline)
    chat._general_llm_answer = Mock(return_value=("Hôm nay là ngày 13/08/2026.", "test-llm"))

    outcome = chat.reply(_message("llm-date", "hôm nay ngày bao nhiêu"))

    assert outcome.stage == "llm"
    assert outcome.answer.startswith("[LLM]\nHôm nay là ngày")
    store.search_knowledge_ranked.assert_not_called()


def test_general_question_labels_deterministic_fallback_honestly() -> None:
    store = Mock()
    store.find_faq.return_value = None
    pipeline = Mock()
    pipeline.analyze.return_value = _allowed()
    chat = ChatOrchestrator(store, Settings(discord_rag_llm_enabled=False), pipeline)

    outcome = chat.reply(_message("fallback-name", "bạn tên là gì"))

    assert outcome.answer == "[Hệ thống]\nMình tên là CHAT-10, trợ lý cộng đồng học tập."
    assert outcome.model_used == "system-fallback"
