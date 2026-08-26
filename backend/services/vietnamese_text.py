"""Keep AI-generated, user-facing explanations in Vietnamese."""

from __future__ import annotations

import re

_ENGLISH_MARKERS = {
    "agents",
    "ambiguous",
    "attack",
    "because",
    "appears",
    "clear",
    "contains",
    "content",
    "context",
    "detected",
    "evidence",
    "harmful",
    "harassment",
    "intent",
    "language",
    "message",
    "personal",
    "policy",
    "risk",
    "safe",
    "specialist",
    "threat",
    "user",
    "violation",
    "exceeded",
    "found",
    "quota",
    "requires",
}
_KNOWN_ENGLISH_OUTPUTS = {
    "allow",
    "allowed",
    "ambiguous",
    "hide",
    "no violation",
    "review",
    "safe",
    "warn",
}

_CATEGORY_REASONS = {
    "safe": "Không phát hiện dấu hiệu vi phạm rõ ràng.",
    "spam": "Nội dung có dấu hiệu spam hoặc lừa đảo và cần được kiểm tra.",
    "harassment": "Nội dung có dấu hiệu quấy rối hoặc công kích cá nhân.",
    "hate": "Nội dung có dấu hiệu ngôn từ thù ghét.",
    "violence": "Nội dung có dấu hiệu đe dọa hoặc cổ súy bạo lực.",
    "sexual": "Nội dung có dấu hiệu nhạy cảm và cần được kiểm tra.",
    "self_harm": "Nội dung liên quan đến tự gây hại và cần Admin/Mod xem xét.",
    "ambiguous": "Ngữ cảnh chưa đủ rõ để hệ thống tự động đưa ra kết luận.",
    "benign_activity": "Đây là hoạt động thông thường, chưa thấy ý định gây hại.",
    "friendly_teasing": "Ngữ cảnh cho thấy đây có thể là lời đùa thân thiện.",
    "quoted_or_educational": "Nội dung đang được trích dẫn hoặc dùng để giải thích, chưa thấy ý định gây hại.",
    "other": "Nội dung cần được kiểm tra thêm trước khi đưa ra kết luận.",
}
_CATEGORY_LABELS = {
    "safe": "Nội dung an toàn",
    "spam": "Spam / lừa đảo",
    "harassment": "Quấy rối",
    "hate": "Ngôn từ thù ghét",
    "violence": "Bạo lực / đe dọa",
    "sexual": "Nội dung nhạy cảm",
    "self_harm": "Tự gây hại",
    "ambiguous": "Nội dung chưa rõ ràng",
    "benign_activity": "Hoạt động thông thường",
    "friendly_teasing": "Đùa giỡn thân thiện",
    "quoted_or_educational": "Trích dẫn / giáo dục",
    "other": "Nội dung khác",
}


def appears_to_be_english(text: str | None) -> bool:
    """Detect ordinary English prose without treating model names as prose."""
    cleaned = (text or "").strip()
    if not cleaned:
        return False
    folded = cleaned.casefold().strip(" .:;!?[]()")
    if folded in _KNOWN_ENGLISH_OUTPUTS:
        return True
    words = re.findall(r"[a-z]+", folded)
    marker_count = sum(word in _ENGLISH_MARKERS for word in words)
    return marker_count >= 2


def vietnamese_moderation_explanation(text: str | None, category: str) -> str:
    """Preserve Vietnamese model detail and replace leaked English prose safely."""
    cleaned = (text or "").strip()
    if cleaned and not appears_to_be_english(cleaned):
        return cleaned
    return _CATEGORY_REASONS.get(category, _CATEGORY_REASONS["other"])


def vietnamese_response_or_fallback(text: str | None, fallback: str) -> str:
    cleaned = (text or "").strip()
    if cleaned and not appears_to_be_english(cleaned):
        return cleaned
    return fallback


def vietnamese_category_label(category: str) -> str:
    return _CATEGORY_LABELS.get(category, "Nội dung cần xem xét")
