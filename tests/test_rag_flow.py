from datetime import UTC, datetime
from unittest.mock import Mock

from backend.config import Settings
from backend.models.operations import FAQ, CommonMessage, KnowledgeDocument, MessageDecision
from backend.services.chat_orchestrator import ChatOrchestrator
from backend.services.operations_store import OperationsStore
from src.ai_models.contracts import RetrievalCandidate
from src.ai_models.retrieval import RelevanceGate, SemanticReranker


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
    store.record_member_question.assert_called_once()
    store.record_unanswered_question.assert_not_called()
    chat._grounded_answer.assert_not_called()


def test_relevance_gate_rejects_semantic_only_weak_candidate() -> None:
    candidate = RetrievalCandidate(
        source_id="DOC-UNRELATED",
        title="Unsupervised Learning",
        text="Học không giám sát và phân cụm dữ liệu.",
        vector_score=0.42,
    )

    ranked = SemanticReranker().rank("Cuối tuần có sự kiện gì không", [candidate])
    decision = RelevanceGate().evaluate(ranked)

    assert decision.passed is False
    assert decision.reason == "insufficient-query-evidence"


def test_lexical_fallback_abstains_without_topic_evidence(tmp_path) -> None:
    store = OperationsStore(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'app.db'}",
            knowledge_embedding_enabled=False,
            openai_api_key="",
        )
    )

    assert store.search_knowledge_ranked("Cuối tuần có sự kiện gì không") == []

    relevant = store.search_knowledge_ranked("Trong sự kiện trực tiếp nên làm gì?")
    assert relevant
    assert relevant[0][1].document_id == "KN-003"


def test_missing_faq_and_knowledge_returns_no_source_and_records_question() -> None:
    store = Mock()
    store.find_faq.return_value = None
    store.search_knowledge_ranked.return_value = []
    pipeline = Mock()
    pipeline.analyze.return_value = _allowed()
    chat = ChatOrchestrator(store, Settings(discord_rag_llm_enabled=True), pipeline)
    chat._general_llm_answer = Mock()

    message = _message("missing-event", "Cuối tuần có sự kiện gì không")
    outcome = chat.reply(message)

    assert outcome.answer.startswith("[Không đủ nguồn]\n")
    assert outcome.stage == "rag"
    assert outcome.model_used == "relevance-gate"
    assert outcome.relevance_passed is False
    store.record_member_question.assert_called_once_with(message, outcome_stage="rag")
    store.record_unanswered_question.assert_not_called()
    chat._general_llm_answer.assert_not_called()


def test_casual_message_uses_llm_without_entering_faq_analytics() -> None:
    store = Mock()
    pipeline = Mock()
    pipeline.analyze.return_value = _allowed()
    chat = ChatOrchestrator(store, Settings(discord_rag_llm_enabled=True), pipeline)
    chat._general_llm_answer = Mock(return_value=("Cảm ơn bạn nha!", "test-llm"))

    outcome = chat.reply(_message("casual-compliment", "giỏi anh iu nha"))

    assert outcome.stage == "llm"
    assert outcome.answer == "[LLM]\nCảm ơn bạn nha!"
    store.record_member_question.assert_not_called()
    store.find_faq.assert_not_called()
    store.search_knowledge_ranked.assert_not_called()


def test_general_question_falls_back_to_llm_after_rag_miss() -> None:
    store = Mock()
    store.find_faq.return_value = None
    store.search_knowledge_ranked.return_value = []
    pipeline = Mock()
    pipeline.analyze.return_value = _allowed()
    chat = ChatOrchestrator(store, Settings(discord_rag_llm_enabled=True), pipeline)
    chat._general_llm_answer = Mock(return_value=("Hãy chia nhỏ mục tiêu học tập.", "test-llm"))

    message = _message("general-rag-miss", "Làm sao để học Python hiệu quả")
    outcome = chat.reply(message)

    assert outcome.stage == "llm"
    assert outcome.answer.startswith("[LLM]\n")
    store.record_member_question.assert_called_once_with(message, outcome_stage="llm")
    store.search_knowledge_ranked.assert_called_once()


def test_store_refuses_to_persist_non_question_even_if_called_directly(tmp_path) -> None:
    store = OperationsStore(Settings(database_url=f"sqlite:///{tmp_path / 'app.db'}"))

    suggestion = store.record_member_question(_message("not-a-question", "giỏi anh iu nha"))

    assert suggestion is None
    assert store.list_faq_suggestions() == []


def test_approved_faq_answers_without_readding_question_to_top_topics() -> None:
    store = Mock()
    store.find_faq.return_value = FAQ(
        faq_id="FAQ-REPORT",
        question="Làm sao báo cáo spam?",
        answer="Dùng lệnh /report.",
        updated_at=datetime.now(UTC),
    )
    pipeline = Mock()
    pipeline.analyze.return_value = _allowed()
    chat = ChatOrchestrator(store, Settings(discord_rag_llm_enabled=False), pipeline)

    outcome = chat.reply(_message("faq-hit", "Làm sao để báo cáo spam?"))

    assert outcome.stage == "faq"
    assert outcome.faq_id == "FAQ-REPORT"
    store.record_member_question.assert_not_called()
    store.search_knowledge_ranked.assert_not_called()


def test_moderation_stops_before_faq_rag_and_question_tracking() -> None:
    store = Mock()
    pipeline = Mock()
    pipeline.analyze.return_value = MessageDecision(
        decision="warn",
        category="harassment",
        severity="high",
        risk_score=0.92,
        confidence=0.9,
        explanation="Công kích trực tiếp.",
        model_used="gate1-safety-lexicon-v1",
    )
    chat = ChatOrchestrator(store, Settings(discord_rag_llm_enabled=True), pipeline)

    outcome = chat.reply(_message("blocked-profanity", "địt cụ m"))

    assert outcome.stage == "moderation"
    assert outcome.answer.startswith("[Moderation]\n")
    store.record_member_question.assert_not_called()
    store.find_faq.assert_not_called()
    store.search_knowledge_ranked.assert_not_called()


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
    store.record_member_question.assert_not_called()
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


def test_out_of_scope_cooking_question_rejected() -> None:
    store = Mock()
    pipeline = Mock()
    pipeline.analyze.return_value = _allowed()
    chat = ChatOrchestrator(store, Settings(discord_rag_llm_enabled=True), pipeline)
    chat._general_llm_answer = Mock()

    outcome = chat.reply(_message("scope-cooking", "Cách nấu phở ngon nhất"))

    assert outcome.stage == "scope-filter"
    assert outcome.model_used == "deterministic-scope-filter"
    assert "Ngoài phạm vi" in outcome.answer
    chat._general_llm_answer.assert_not_called()
    store.search_knowledge_ranked.assert_not_called()


def test_out_of_scope_crypto_question_rejected() -> None:
    store = Mock()
    store.find_faq.return_value = None
    store.search_knowledge_ranked.return_value = []
    pipeline = Mock()
    pipeline.analyze.return_value = _allowed()
    chat = ChatOrchestrator(store, Settings(discord_rag_llm_enabled=True), pipeline)
    chat._general_llm_answer = Mock()

    outcome = chat.reply(_message("scope-crypto", "Bitcoin giá bao nhiêu"))

    assert outcome.stage == "scope-filter"
    assert "Ngoài phạm vi" in outcome.answer
    chat._general_llm_answer.assert_not_called()


def test_out_of_scope_gaming_question_rejected() -> None:
    store = Mock()
    store.find_faq.return_value = None
    store.search_knowledge_ranked.return_value = []
    pipeline = Mock()
    pipeline.analyze.return_value = _allowed()
    chat = ChatOrchestrator(store, Settings(discord_rag_llm_enabled=True), pipeline)
    chat._general_llm_answer = Mock()

    outcome = chat.reply(_message("scope-gaming", "Rank Liên Quân mùa này thế nào"))

    assert outcome.stage == "scope-filter"
    assert "Ngoài phạm vi" in outcome.answer
    chat._general_llm_answer.assert_not_called()


def test_in_scope_study_question_passes_through() -> None:
    store = Mock()
    store.find_faq.return_value = None
    store.search_knowledge_ranked.return_value = []
    pipeline = Mock()
    pipeline.analyze.return_value = _allowed()
    chat = ChatOrchestrator(store, Settings(discord_rag_llm_enabled=True), pipeline)
    chat._general_llm_answer = Mock(return_value=("Hãy chia nhỏ mục tiêu.", "test-llm"))

    outcome = chat.reply(_message("scope-study", "Làm sao để học Python hiệu quả"))

    assert outcome.stage != "scope-filter"


def test_mixed_scope_with_in_scope_keyword_passes() -> None:
    """Cross-domain like 'code Python để crawl giá Bitcoin' has in-scope keywords."""
    store = Mock()
    store.find_faq.return_value = None
    store.search_knowledge_ranked.return_value = []
    pipeline = Mock()
    pipeline.analyze.return_value = _allowed()
    chat = ChatOrchestrator(store, Settings(discord_rag_llm_enabled=True), pipeline)
    chat._general_llm_answer = Mock(return_value=("Bạn có thể dùng requests.", "test-llm"))

    outcome = chat.reply(_message("scope-mixed", "Code Python để crawl giá Bitcoin"))

    assert outcome.stage != "scope-filter"

