import pytest

from backend.services.question_intent import (
    classify_question_intent,
    has_question_intent,
    is_reusable_faq_question,
)


@pytest.mark.parametrize(
    "text",
    (
        "khi nào bạn xài LLM để trả lời",
        "bạn tên là gì",
        "Cuối tuần có sự kiện gì không",
        "Làm sao để học Python hiệu quả",
        "Hãy giải thích embedding cho mình",
        "Where is the Python class?",
    ),
)
def test_detects_intentional_questions(text: str) -> None:
    assert has_question_intent(text) is True


@pytest.mark.parametrize(
    "text",
    (
        "giỏi anh iu nha",
        "xin chào",
        "mình không biết câu này",
        "FAQ chỉ lưu câu nào với chủ định hỏi thôi, mấy câu kia đâu phải câu hỏi",
        "đánh liên quân không anh em",
    ),
)
def test_rejects_casual_or_declarative_messages(text: str) -> None:
    assert has_question_intent(text) is False


@pytest.mark.parametrize(
    ("text", "eligible"),
    (
        ("Cuối tuần có sự kiện gì không?", True),
        ("Làm sao để báo cáo spam trong server?", True),
        ("Hãy giải thích embedding cho mình", True),
        ("Hôm nay là ngày bao nhiêu?", False),
        ("Bạn tên là gì?", False),
        ("Khi nào bạn dùng LLM để trả lời?", False),
        ("Đánh Liên Quân không anh em?", False),
    ),
)
def test_separates_question_detection_from_faq_eligibility(text: str, eligible: bool) -> None:
    decision = classify_question_intent(text)

    assert decision.faq_eligible is eligible
    assert is_reusable_faq_question(text) is eligible
