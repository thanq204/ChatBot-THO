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

_CATEGORY_EXPLANATION_TEMPLATES = {
    "spam": "cụm này thúc giục hoặc dẫn dụ người đọc thực hiện hành động đáng ngờ, nên có dấu hiệu spam/lừa đảo",
    "harassment": "cụm này hạ nhục, xua đuổi, công kích hoặc thể hiện ý gây gổ trực tiếp với một đối tượng, nên có nguy cơ gây xung đột",
    "hate": "cụm này công kích một nhóm người dựa trên đặc điểm của họ, nên có dấu hiệu ngôn từ thù ghét",
    "violence": "cụm này mô tả ý định tấn công, đe dọa hoặc gây tổn hại tới một đối tượng, nên thuộc nhóm bạo lực/đe dọa",
    "sexual": "cụm này mang nội dung tình dục hoặc quấy rối tình dục không phù hợp, nên cần được kiểm tra",
    "self_harm": "cụm này thể hiện nguy cơ tự gây hại, nên cần được chuyển cho Admin/Mod xem xét thận trọng",
    "ambiguous": "ý nghĩa hoặc đối tượng bị nhắm tới chưa đủ rõ, nên hệ thống chưa tự động kết luận",
}
_NON_LATIN_LANGUAGE_SCRIPT = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")
_VIETNAMESE_EXPLANATION_MARKERS = (
    "cụm",
    "được hiểu",
    "nội dung",
    "nghĩa",
    "vì",
    "nên",
    "dấu hiệu",
    "xúc phạm",
    "đe dọa",
    "công kích",
)
_LANGUAGE_LABELS = {
    "vi": "Tiếng Việt",
    "vietnamese": "Tiếng Việt",
    "en": "Tiếng Anh",
    "english": "Tiếng Anh",
    "ja": "Tiếng Nhật",
    "jp": "Tiếng Nhật",
    "japanese": "Tiếng Nhật",
    "zh": "Tiếng Trung",
    "chinese": "Tiếng Trung",
    "ko": "Tiếng Hàn",
    "korean": "Tiếng Hàn",
    "mixed": "Đa ngôn ngữ",
    "mixed language": "Đa ngôn ngữ",
    "multilingual": "Đa ngôn ngữ",
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


def appears_to_be_untranslated_non_vietnamese(text: str | None) -> bool:
    """Catch CJK/Korean prose while allowing quoted source spans in Vietnamese prose."""
    cleaned = (text or "").strip()
    if not _NON_LATIN_LANGUAGE_SCRIPT.search(cleaned):
        return False
    folded = cleaned.casefold()
    return not any(marker in folded for marker in _VIETNAMESE_EXPLANATION_MARKERS)


def concise_moderation_evidence(values: list[str], source_text: str = "") -> list[str]:
    """Keep short harmful spans and discard evidence that merely repeats a long input."""
    source = " ".join(source_text.split()).strip()
    source_folded = source.casefold()
    normalized_values = [" ".join(str(value).split()).strip().strip('"“”') for value in values]
    has_specific_span = any(
        item
        and source_folded
        and item.casefold() != source_folded
        and item.casefold() in source_folded
        for item in normalized_values
    )
    result: list[str] = []
    for item in normalized_values:
        if not item:
            continue
        is_full_input = bool(source_folded and item.casefold() == source_folded)
        if is_full_input and (has_specific_span or len(item) > 48 or len(item.split()) > 8):
            continue
        if len(item) > 140 or len(item.split()) > 18:
            continue
        if item not in result:
            result.append(item)
    return result[:5]


def _is_plain_restatement(reason: str, source_text: str) -> bool:
    if not reason or not source_text:
        return False

    def normalize(value: str) -> str:
        return re.sub(r"[^\w]+", " ", value.casefold(), flags=re.UNICODE).strip()

    reason_key = normalize(reason)
    source_key = normalize(source_text)
    return bool(
        source_key
        and (reason_key == source_key or (source_key in reason_key and len(reason_key) <= len(source_key) + 24))
    )


def _specific_explanation(
    category: str,
    evidence: list[str],
    normalized_meaning: str | None,
) -> str:
    detail = _CATEGORY_EXPLANATION_TEMPLATES.get(category)
    if not detail:
        return _CATEGORY_REASONS.get(category, _CATEGORY_REASONS["other"])
    phrase = evidence[0] if evidence else ""
    meaning = (normalized_meaning or "").strip()
    if meaning.casefold() in {"", "chưa xác định được nghĩa.", "chưa xác định được nghĩa"}:
        meaning = ""
    quoted_evidence = ", ".join(f"“{item}”" for item in evidence[:3])
    subject = f"Cụm {quoted_evidence}" if len(evidence) == 1 else f"Các cụm {quoted_evidence}"
    if phrase and meaning:
        verb = "thể hiện ý" if len(evidence) == 1 else "cùng thể hiện ý"
        result = f"{subject} {verb} “{meaning}”; {detail}."
    elif phrase:
        result = f"{subject} là tín hiệu chính: {detail}."
    elif meaning:
        result = f"Nội dung được hiểu là “{meaning}”; {detail}."
    else:
        result = _CATEGORY_REASONS.get(category, _CATEGORY_REASONS["other"])
    return result[:500]


def vietnamese_moderation_explanation(
    text: str | None,
    category: str,
    *,
    evidence: list[str] | None = None,
    source_text: str = "",
    normalized_meaning: str | None = None,
) -> str:
    """Return a Vietnamese explanation rather than a translation/repetition of input."""
    cleaned = (text or "").strip()
    evidence_values = evidence or []
    evidence_is_explained = not evidence_values or any(
        item.casefold() in cleaned.casefold() for item in evidence_values
    )
    if (
        cleaned
        and not appears_to_be_english(cleaned)
        and not appears_to_be_untranslated_non_vietnamese(cleaned)
        and not _is_plain_restatement(cleaned, source_text)
        and (category not in _CATEGORY_EXPLANATION_TEMPLATES or evidence_is_explained)
    ):
        return cleaned
    return _specific_explanation(category, evidence_values, normalized_meaning)


def vietnamese_response_or_fallback(text: str | None, fallback: str) -> str:
    cleaned = (text or "").strip()
    if (
        cleaned
        and not appears_to_be_english(cleaned)
        and not appears_to_be_untranslated_non_vietnamese(cleaned)
    ):
        return cleaned
    return fallback


def vietnamese_category_label(category: str) -> str:
    return _CATEGORY_LABELS.get(category, "Nội dung cần xem xét")


def vietnamese_language_label(language: str | None) -> str | None:
    cleaned = (language or "").strip()
    if not cleaned:
        return None
    normalized = cleaned.casefold().replace("_", "-")
    code = normalized.split("-", 1)[0]
    return _LANGUAGE_LABELS.get(normalized) or _LANGUAGE_LABELS.get(code) or cleaned
