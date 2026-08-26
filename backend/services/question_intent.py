"""Deterministic intent checks shared by chat routing and FAQ analytics."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


def normalize_intent_text(text: str) -> str:
    folded = unicodedata.normalize(
        "NFD",
        text.casefold().replace("\N{LATIN SMALL LETTER D WITH STROKE}", "d"),
    )
    folded = "".join(character for character in folded if unicodedata.category(character) != "Mn")
    return re.sub(r"\s+", " ", folded).strip()


@dataclass(frozen=True, slots=True)
class QuestionIntentDecision:
    is_question: bool
    faq_eligible: bool
    reason: str


_QUESTION_START = re.compile(
    r"^(?:ai|gi|cai gi|dieu gi|nao|cai nao|tai sao|vi sao|sao|khi nao|bao gio|"
    r"bao nhieu|may|o dau|dau|the nao|nhu nao|lam sao|what|which|who|whose|"
    r"why|when|where|how)\b",
    re.I,
)
_QUESTION_END = re.compile(
    r"\b(?:ai|gi|nao|sao|dau|khong|chua|a|ha|may|bao nhieu|the nao|nhu nao)"
    r"[.!\s]*$",
    re.I,
)
_REQUEST = re.compile(
    r"^(?:cho\s+(?:toi|minh|em)\s+(?:hoi|biet)|cho\s+hoi|xin\s+hoi|hay\s+cho\s+biet|"
    r"giai\s+thich|huong\s+dan|giup\s+(?:toi|minh|em)|chi\s+(?:toi|minh|em)|"
    r"hay\s+(?:giai\s+thich|huong\s+dan|chi|tim)|tim\s+giup|tra\s+cuu\s+giup|"
    r"tell\s+me|explain|show\s+me|help\s+me|can\s+you|could\s+you|would\s+you)\b",
    re.I,
)
_QUESTION_PAIR = re.compile(
    r"\b(?:co|can|nen|phai|muon|dung|xai|hoc|lam|tim|lay|biet|nho|hieu|la)\b"
    r".{0,100}\b(?:gi|ai|nao|khong|chua|o dau|khi nao|bao gio|bao nhieu|the nao|nhu nao)\b",
    re.I,
)
_ENGLISH_AUXILIARY = re.compile(
    r"^(?:is|are|am|was|were|do|does|did|can|could|should|would|will|have|has)\b",
    re.I,
)

# These messages can contain question-like particles, but their purpose is
# social interaction rather than asking the bot for reusable information.
_SOCIAL_OR_ACTIVITY = re.compile(
    r"^(?:(?:xin )?chao|hello|hi|hey|alo|test)\b"
    r"|\b(?:gioi|hay qua|tuyet|cam on|thanks?|yeu|thuong|anh iu)\b"
    r"|\b(?:danh|choi|vao|lam)\s+(?:lien quan|game|rank|mot tran|tran)\b"
    r"|\b(?:anh em|ae)\s+(?:danh|choi|vao)\b",
    re.I,
)

# A real question is not necessarily reusable FAQ training data. Volatile
# answers, bot metadata and personal small-talk always stay in the LLM lane.
_NON_REUSABLE_QUESTION = re.compile(
    r"\b(?:hom nay|bay gio|hien tai)\b.*\b(?:ngay|thu|gio|thoi tiet|nhiet do)\b"
    r"|\b(?:thoi tiet|nhiet do)\b"
    r"|\b(?:ban|chatbot|chat-10|tho|bot)\b.*\b(?:ten|la ai|model|mo hinh|llm|lam duoc gi)\b"
    r"|\b(?:khi nao|luc nao|tai sao)\b.*\b(?:ban|chatbot|chat-10|tho|bot)\b.*\b(?:llm|rag|model|mo hinh)\b"
    r"|\bban\b.*\b(?:khoe|thich|yeu|cam thay)\b",
    re.I,
)


def classify_question_intent(text: str) -> QuestionIntentDecision:
    """Classify routing intent separately from FAQ analytics eligibility."""
    stripped = text.strip()
    if not stripped:
        return QuestionIntentDecision(False, False, "empty")

    normalized = normalize_intent_text(stripped)
    if _SOCIAL_OR_ACTIVITY.search(normalized):
        return QuestionIntentDecision(False, False, "social-or-activity")

    is_question = "?" in stripped or any(
        pattern.search(normalized)
        for pattern in (_QUESTION_START, _QUESTION_END, _REQUEST, _QUESTION_PAIR, _ENGLISH_AUXILIARY)
    )
    if not is_question:
        return QuestionIntentDecision(False, False, "not-a-question")
    if _NON_REUSABLE_QUESTION.search(normalized):
        return QuestionIntentDecision(True, False, "volatile-or-bot-meta")
    return QuestionIntentDecision(True, True, "reusable-question")


def has_question_intent(text: str) -> bool:
    """Return True only when the member is asking for information or help."""
    return classify_question_intent(text).is_question


def is_reusable_faq_question(text: str) -> bool:
    """Return True only for intentional questions suitable for FAQ grouping."""
    return classify_question_intent(text).faq_eligible
