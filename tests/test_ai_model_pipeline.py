from datetime import UTC, datetime

import pytest

from src.ai_models import (
    CommunityAIPipeline,
    FAQEntry,
    FlowName,
    GenerationMode,
    ModerationMark,
    ModerationMemoryIndex,
    RetrievalCandidate,
)


def test_four_flow_router_keeps_qa_out_of_realtime_messages() -> None:
    pipeline = CommunityAIPipeline()

    command = pipeline.route_input("/help", bot_mentioned=False)
    realtime = pipeline.route_input("Mọi người học đến đâu rồi?", bot_mentioned=False)
    tagged = pipeline.route_input("@chatbot lịch học Python khi nào?", bot_mentioned=True, bot_username="chatbot")

    assert command.stages == (FlowName.RULE,)
    assert realtime.stages == (FlowName.MODERATION,)
    assert tagged.stages == (FlowName.MODERATION, FlowName.FAQ, FlowName.LLM_RAG)
    assert tagged.question == "lịch học Python khi nào?"


def test_approved_faq_match_avoids_rag_and_llm() -> None:
    pipeline = CommunityAIPipeline()
    faq = FAQEntry(
        faq_id="FAQ-SCHEDULE",
        question="Lịch học Python vào thứ mấy?",
        answer="Lớp học vào tối thứ ba.",
        embedding=(1.0, 0.0, 0.0),
    )

    decision = pipeline.decide_question(
        "Python học ngày nào?",
        (0.999, 0.02, 0.0),
        [faq],
        [],
        llm_enabled=True,
    )

    assert decision.flow is FlowName.FAQ
    assert decision.faq_match and decision.faq_match.faq.faq_id == "FAQ-SCHEDULE"
    assert decision.generation.mode is GenerationMode.FAQ
    assert decision.generation.use_llm is False


def test_rerank_and_relevance_select_grounded_source() -> None:
    pipeline = CommunityAIPipeline()
    candidates = [
        RetrievalCandidate("KN-WRONG", "Đăng ký câu lạc bộ", "Điền biểu mẫu tham gia.", 0.88),
        RetrievalCandidate("KN-RIGHT", "Lịch học Python", "Lớp Python học vào tối thứ ba.", 0.82),
    ]

    decision = pipeline.decide_question(
        "Lịch học Python vào thứ mấy?",
        (0.0, 1.0),
        [],
        candidates,
        llm_enabled=True,
    )

    assert decision.ranked_candidates[0].candidate.source_id == "KN-RIGHT"
    assert decision.relevance and decision.relevance.passed is True
    assert decision.generation.mode in {GenerationMode.EXTRACTIVE, GenerationMode.GROUNDED_LLM}


def test_project_learning_query_beats_generic_feynman_candidate() -> None:
    pipeline = CommunityAIPipeline()
    candidates = [
        RetrievalCandidate(
            "KN-FEYNMAN",
            "Feynman Technique",
            "Phương pháp Feynman yêu cầu người học giải thích một khái niệm bằng ngôn ngữ đơn giản như đang dạy cho người chưa biết chủ đề đó.",
            1.0,
        ),
        RetrievalCandidate(
            "KN-PROJECT",
            "Project-Based Learning",
            "Học bằng dự án giúp kết hợp nhiều kiến thức vào một sản phẩm thực tế, đặc biệt phù hợp với lập trình, dữ liệu và trí tuệ nhân tạo.",
            0.8,
        ),
    ]

    decision = pipeline.decide_question(
        "tôi đang tham gia 1 dự án, muốn học bằng dự án thì phương pháp này như nào",
        (0.0, 1.0),
        [],
        candidates,
        llm_enabled=True,
    )

    assert decision.ranked_candidates[0].candidate.source_id == "KN-PROJECT"
    assert decision.relevance and decision.relevance.passed is True


@pytest.mark.parametrize(
    ("question", "expected_source", "candidates"),
    [
        (
            "Tôi nên áp dụng Pomodoro như thế nào để học hiệu quả?",
            "KN-POMODORO",
            [
                RetrievalCandidate("KN-MATH", "Learning Mathematics", "Khi học Toán, hãy hiểu công thức và tự giải bài.", 0.833),
                RetrievalCandidate("KN-POMODORO", "Pomodoro Technique", "Pomodoro chia việc học thành các phiên tập trung ngắn xen kẽ thời gian nghỉ.", 1.0),
            ],
        ),
        (
            "Quy trình học RAG gồm những bước nào?",
            "KN-RAG",
            [
                RetrievalCandidate("KN-LOL", "Công trình trong Liên Minh Huyền Thoại", "Phá công trình phòng thủ theo từng bước.", 1.0),
                RetrievalCandidate("KN-RAG", "Learning RAG", "Tài liệu được chia chunk, tạo embedding, lưu kho vector rồi truy xuất ngữ cảnh.", 0.833),
            ],
        ),
    ],
)
def test_distinctive_title_term_beats_generic_overlap(
    question: str,
    expected_source: str,
    candidates: list[RetrievalCandidate],
) -> None:
    decision = CommunityAIPipeline().decide_question(
        question,
        (),
        [],
        candidates,
        llm_enabled=False,
    )

    assert decision.ranked_candidates[0].candidate.source_id == expected_source
    assert decision.relevance and decision.relevance.passed is True


def test_relevance_gate_abstains_before_llm_for_weak_context() -> None:
    pipeline = CommunityAIPipeline()
    candidates = [RetrievalCandidate("KN-CLUB", "Câu lạc bộ", "Điền biểu mẫu tham gia.", 0.20)]

    decision = pipeline.decide_question(
        "Cách tính đạo hàm hàm hợp?",
        (0.0, 1.0),
        [],
        candidates,
        llm_enabled=True,
    )

    assert decision.relevance and decision.relevance.passed is False
    assert decision.generation.mode is GenerationMode.ABSTAIN
    assert decision.generation.use_llm is False
    assert decision.should_record_unanswered is True


def test_high_confidence_source_uses_extractive_answer_without_llm() -> None:
    pipeline = CommunityAIPipeline()
    candidate = RetrievalCandidate(
        "KN-PYTHON",
        "Lịch học Python vào thứ mấy?",
        "Lịch học Python vào thứ mấy? Lớp học vào tối thứ ba.",
        0.95,
    )

    decision = pipeline.decide_question(
        "Lịch học Python vào thứ mấy?",
        (0.0, 1.0),
        [],
        [candidate],
        llm_enabled=True,
    )

    assert decision.generation.mode is GenerationMode.EXTRACTIVE
    assert decision.generation.use_llm is False


def test_relevant_source_that_needs_synthesis_uses_grounded_llm() -> None:
    pipeline = CommunityAIPipeline()
    candidate = RetrievalCandidate(
        "KN-PYTHON",
        "Python schedule",
        "The class meets on Tuesday evening in room C204.",
        0.92,
    )

    decision = pipeline.decide_question(
        "When should I attend the Python lesson?",
        (0.0, 1.0),
        [],
        [candidate],
        llm_enabled=True,
    )

    assert decision.relevance and decision.relevance.passed is True
    assert decision.generation.mode is GenerationMode.GROUNDED_LLM
    assert decision.generation.use_llm is True


def test_rag_answer_is_labeled_and_always_contains_source_excerpt() -> None:
    pipeline = CommunityAIPipeline()
    candidate = RetrievalCandidate(
        "KN-PROJECT",
        "Project-Based Learning",
        "Học bằng dự án giúp kết hợp nhiều kiến thức vào một sản phẩm thực tế.",
        0.92,
        metadata={"source_url": "https://example.invalid/knowledge/project"},
    )
    decision = pipeline.decide_question(
        "Học bằng dự án là gì?",
        (0.0, 1.0),
        [],
        [candidate],
        llm_enabled=True,
    )

    envelope = pipeline.compose_answer(
        "Bạn học thông qua việc tạo một sản phẩm thực tế.",
        decision,
        model_used="test-model",
    )

    assert envelope.display_text.startswith("[RAG]")
    assert "Trích từ tài liệu: Project-Based Learning (KN-PROJECT)" in envelope.display_text
    assert envelope.display_text.count("Bạn học thông qua việc tạo một sản phẩm thực tế.") == 1
    assert "Học bằng dự án giúp kết hợp nhiều kiến thức" not in envelope.display_text
    assert envelope.citations[0].excerpt.startswith("Học bằng dự án giúp kết hợp nhiều kiến thức")
    assert envelope.citations[0].source_url == "https://example.invalid/knowledge/project"


def test_faq_answer_has_a_distinct_approved_label() -> None:
    pipeline = CommunityAIPipeline()
    faq = FAQEntry("FAQ-001", "Lịch học khi nào?", "Tối thứ ba.", (1.0, 0.0))
    decision = pipeline.decide_question(
        "Lịch học khi nào?",
        (1.0, 0.0),
        [faq],
        [],
        llm_enabled=True,
    )

    envelope = pipeline.compose_answer(faq.answer, decision, model_used="admin-faq")

    assert envelope.answer_mode is GenerationMode.FAQ
    assert envelope.display_text.startswith("[FAQ đã duyệt]")
    assert "FAQ-001" in envelope.display_text


def test_moderation_memory_suppresses_duplicate_admin_ticket() -> None:
    mark = ModerationMark(
        mark_id="MM-001",
        message_id="MSG-001",
        text="Mày ngu quá, biến khỏi nhóm đi",
        category="harassment",
        decision="warn",
        reason="công kích cá nhân",
        marked_by="mod-lan",
        marked_at=datetime(2026, 8, 12, 10, 30, tzinfo=UTC),
        embedding=(1.0, 0.0, 0.0),
        source_url="https://example.invalid/messages/001",
    )
    pipeline = CommunityAIPipeline(moderation_memory=ModerationMemoryIndex([mark]))

    match = pipeline.check_moderation_memory(
        "Ngu quá, biến khỏi nhóm đi",
        (0.999, 0.01, 0.0),
        category="harassment",
    )

    assert match.matched is True
    assert match.send_to_admin is False
    assert match.can_expand is True
    assert match.banner == "(Đã được đánh dấu: công kích cá nhân bởi: mod-lan vào lúc: 2026-08-12T10:30:00Z)"


def test_moderation_memory_does_not_reuse_a_different_category() -> None:
    mark = ModerationMark(
        mark_id="MM-001",
        message_id="MSG-001",
        text="Nhận tiền miễn phí tại link này",
        category="spam",
        decision="hide",
        reason="spam",
        marked_by="Admin",
        marked_at=datetime.now(UTC),
        embedding=(1.0, 0.0),
    )
    pipeline = CommunityAIPipeline(moderation_memory=ModerationMemoryIndex([mark]))

    match = pipeline.check_moderation_memory("Tao sẽ đánh mày", (1.0, 0.0), category="violence")

    assert match.matched is False
    assert match.send_to_admin is True


def test_invalid_rerank_weights_fail_fast() -> None:
    from src.ai_models import RerankConfig

    with pytest.raises(ValueError, match="sum to 1.0"):
        RerankConfig(vector_weight=0.5, lexical_weight=0.5, phrase_weight=0.5)
