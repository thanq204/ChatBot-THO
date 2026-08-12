"""Framework-neutral contracts for the community AI decision pipeline."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

Vector = Sequence[float]


class FlowName(StrEnum):
    RULE = "rule"
    MODERATION = "moderation"
    FAQ = "faq"
    LLM_RAG = "llm_rag"


class GenerationMode(StrEnum):
    FAQ = "faq"
    EXTRACTIVE = "extractive"
    GROUNDED_LLM = "grounded_llm"
    ABSTAIN = "abstain"


@dataclass(frozen=True, slots=True)
class RoutingPlan:
    stages: tuple[FlowName, ...]
    question: str
    is_qa_request: bool
    reason: str


@dataclass(frozen=True, slots=True)
class RetrievalCandidate:
    source_id: str
    title: str
    text: str
    vector_score: float
    source_type: str = "knowledge"
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    candidate: RetrievalCandidate
    lexical_score: float
    phrase_score: float
    rerank_score: float


@dataclass(frozen=True, slots=True)
class RelevanceDecision:
    passed: bool
    score: float
    threshold: float
    margin: float
    reason: str


@dataclass(frozen=True, slots=True)
class FAQEntry:
    faq_id: str
    question: str
    answer: str
    embedding: Vector
    active: bool = True


@dataclass(frozen=True, slots=True)
class FAQMatch:
    faq: FAQEntry
    score: float
    margin: float


@dataclass(frozen=True, slots=True)
class GenerationDecision:
    mode: GenerationMode
    use_llm: bool
    reason: str


@dataclass(frozen=True, slots=True)
class QuestionDecision:
    flow: FlowName
    generation: GenerationDecision
    faq_match: FAQMatch | None = None
    ranked_candidates: tuple[RankedCandidate, ...] = ()
    relevance: RelevanceDecision | None = None
    should_record_unanswered: bool = False


@dataclass(frozen=True, slots=True)
class Citation:
    source_id: str
    title: str
    excerpt: str
    source_type: str
    source_url: str | None = None


@dataclass(frozen=True, slots=True)
class AnswerEnvelope:
    answer: str
    display_text: str
    answer_mode: GenerationMode
    model_used: str
    citations: tuple[Citation, ...] = ()


@dataclass(frozen=True, slots=True)
class ModerationMark:
    mark_id: str
    message_id: str
    text: str
    category: str
    decision: str
    reason: str
    marked_by: str
    marked_at: datetime
    embedding: Vector
    source_url: str | None = None
    active: bool = True
    version: int = 1


@dataclass(frozen=True, slots=True)
class ModerationMemoryMatch:
    matched: bool
    similarity: float
    send_to_admin: bool
    can_expand: bool
    banner: str | None = None
    mark: ModerationMark | None = None
