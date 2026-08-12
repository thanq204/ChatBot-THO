"""Reranking, relevance gating and cost-aware answer routing."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .contracts import (
    GenerationDecision,
    GenerationMode,
    RankedCandidate,
    RelevanceDecision,
    RetrievalCandidate,
)
from .similarity import distinctive_title_match, phrase_score, query_coverage


@dataclass(frozen=True, slots=True)
class RerankConfig:
    vector_weight: float = 0.58
    lexical_weight: float = 0.30
    phrase_weight: float = 0.12
    top_k: int = 4

    def __post_init__(self) -> None:
        total = self.vector_weight + self.lexical_weight + self.phrase_weight
        if abs(total - 1.0) > 1e-9:
            raise ValueError("Rerank weights must sum to 1.0")
        if self.top_k < 1:
            raise ValueError("top_k must be positive")


class SemanticReranker:
    def __init__(self, config: RerankConfig | None = None) -> None:
        self.config = config or RerankConfig()

    def rank(self, question: str, candidates: Iterable[RetrievalCandidate]) -> tuple[RankedCandidate, ...]:
        ranked: list[RankedCandidate] = []
        for candidate in candidates:
            combined_text = f"{candidate.title}\n{candidate.text}"
            lexical = query_coverage(question, combined_text)
            phrase = phrase_score(question, combined_text)
            title_match = distinctive_title_match(question, candidate.title)
            vector = max(0.0, min(1.0, candidate.vector_score))
            score = (
                self.config.vector_weight * vector
                + self.config.lexical_weight * lexical
                + self.config.phrase_weight * phrase
                + 0.25 * title_match
            )
            ranked.append(RankedCandidate(candidate, lexical, phrase, min(1.0, score)))
        ranked.sort(key=lambda item: (item.rerank_score, item.candidate.vector_score), reverse=True)
        return tuple(ranked[: self.config.top_k])


@dataclass(frozen=True, slots=True)
class RelevanceConfig:
    minimum_rerank_score: float = 0.52
    minimum_vector_score: float = 0.38
    minimum_query_coverage: float = 0.24
    minimum_margin: float = 0.025


class RelevanceGate:
    """Reject weak or ambiguous retrieval before any LLM call."""

    def __init__(self, config: RelevanceConfig | None = None) -> None:
        self.config = config or RelevanceConfig()

    def evaluate(self, ranked: tuple[RankedCandidate, ...]) -> RelevanceDecision:
        if not ranked:
            return RelevanceDecision(False, 0.0, self.config.minimum_rerank_score, 0.0, "no-candidate")

        best = ranked[0]
        runner_up = ranked[1].rerank_score if len(ranked) > 1 else 0.0
        margin = best.rerank_score - runner_up
        if best.rerank_score < self.config.minimum_rerank_score:
            reason = "rerank-score-below-threshold"
        elif (
            best.candidate.vector_score < self.config.minimum_vector_score
            and best.lexical_score < self.config.minimum_query_coverage
        ):
            reason = "insufficient-semantic-and-lexical-evidence"
        elif len(ranked) > 1 and margin < self.config.minimum_margin and best.rerank_score < 0.78:
            reason = "ambiguous-top-candidates"
        else:
            return RelevanceDecision(True, best.rerank_score, self.config.minimum_rerank_score, margin, "relevant")
        return RelevanceDecision(False, best.rerank_score, self.config.minimum_rerank_score, margin, reason)


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    extractive_score: float = 0.84
    extractive_coverage: float = 0.72


class GenerationRouter:
    """Use the cheapest safe answer path and reserve LLM for grounded synthesis."""

    def __init__(self, config: GenerationConfig | None = None) -> None:
        self.config = config or GenerationConfig()

    def decide(
        self,
        relevance: RelevanceDecision,
        ranked: tuple[RankedCandidate, ...],
        *,
        llm_enabled: bool,
    ) -> GenerationDecision:
        if not relevance.passed or not ranked:
            return GenerationDecision(GenerationMode.ABSTAIN, False, relevance.reason)
        best = ranked[0]
        if best.rerank_score >= self.config.extractive_score and best.lexical_score >= self.config.extractive_coverage:
            return GenerationDecision(GenerationMode.EXTRACTIVE, False, "high-confidence-source-can-answer-directly")
        if llm_enabled:
            return GenerationDecision(GenerationMode.GROUNDED_LLM, True, "relevant-context-needs-grounded-synthesis")
        return GenerationDecision(GenerationMode.EXTRACTIVE, False, "llm-disabled-use-source-excerpt")
