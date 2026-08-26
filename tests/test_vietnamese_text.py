from backend.services.vietnamese_text import (
    vietnamese_moderation_explanation,
    vietnamese_response_or_fallback,
)


def test_english_moderation_reason_is_replaced_by_vietnamese_category_reason():
    result = vietnamese_moderation_explanation(
        "The message contains a clear personal attack.",
        "harassment",
    )

    assert result == "Nội dung có dấu hiệu quấy rối hoặc công kích cá nhân."


def test_existing_vietnamese_reason_is_preserved():
    reason = "Đây là lời đùa trong ngữ cảnh chơi game, chưa thấy ý định gây hại."

    assert vietnamese_moderation_explanation(reason, "safe") == reason


def test_english_general_response_uses_vietnamese_fallback():
    fallback = "Mình chưa thể tạo câu trả lời phù hợp bằng tiếng Việt."

    assert vietnamese_response_or_fallback("This response contains general content.", fallback) == fallback
