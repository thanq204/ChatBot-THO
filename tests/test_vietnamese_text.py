from backend.services.vietnamese_text import (
    concise_moderation_evidence,
    vietnamese_language_label,
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


def test_long_full_message_is_not_used_as_evidence():
    source = "xin chào, tôi muốn đánh nhau với con chó kia"

    assert concise_moderation_evidence([source, "đánh nhau với con chó"], source) == [
        "đánh nhau với con chó"
    ]


def test_repeated_input_becomes_a_specific_explanation():
    source = "お前は馬鹿だ、消えろ。"
    result = vietnamese_moderation_explanation(
        source,
        "harassment",
        evidence=["馬鹿", "消えろ"],
        source_text=source,
        normalized_meaning="Mày là đồ ngu, biến đi.",
    )

    assert "“馬鹿”" in result
    assert "“消えろ”" in result
    assert "Mày là đồ ngu, biến đi" in result
    assert "nguy cơ gây xung đột" in result


def test_untranslated_japanese_reason_becomes_vietnamese_explanation():
    result = vietnamese_moderation_explanation(
        "これは侮辱的なメッセージです。",
        "harassment",
        evidence=["馬鹿"],
        source_text="お前は馬鹿だ。",
        normalized_meaning="Mày là đồ ngu.",
    )

    assert "Cụm “馬鹿”" in result
    assert "thể hiện ý “Mày là đồ ngu." in result


def test_language_code_is_shown_as_a_vietnamese_label():
    assert vietnamese_language_label("ja") == "Tiếng Nhật"
    assert vietnamese_language_label("en-US") == "Tiếng Anh"
    assert vietnamese_language_label("mixed") == "Đa ngôn ngữ"
