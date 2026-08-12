"""Embedding-first FAQ matching with ambiguity protection."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .contracts import FAQEntry, FAQMatch, Vector
from .similarity import cosine_similarity, normalize_text, query_coverage


@dataclass(frozen=True, slots=True)
class FAQMatchConfig:
    minimum_score: float = 0.86
    minimum_margin: float = 0.035
    semantic_weight: float = 0.90
    lexical_weight: float = 0.10


class SemanticFAQMatcher:
    def __init__(self, config: FAQMatchConfig | None = None) -> None:
        self.config = config or FAQMatchConfig()

    def match(self, question: str, query_embedding: Vector, entries: Iterable[FAQEntry]) -> FAQMatch | None:
        scored: list[tuple[float, FAQEntry]] = []
        normalized_question = normalize_text(question)
        for entry in entries:
            if not entry.active:
                continue
            if normalized_question == normalize_text(entry.question):
                score = 1.0
            else:
                semantic = max(0.0, cosine_similarity(query_embedding, entry.embedding))
                lexical = query_coverage(question, entry.question)
                score = self.config.semantic_weight * semantic + self.config.lexical_weight * lexical
            scored.append((score, entry))
        scored.sort(key=lambda item: item[0], reverse=True)
        if not scored or scored[0][0] < self.config.minimum_score:
            return None
        runner_up = scored[1][0] if len(scored) > 1 else 0.0
        margin = scored[0][0] - runner_up
        if len(scored) > 1 and margin < self.config.minimum_margin and scored[0][0] < 0.97:
            return None
        return FAQMatch(scored[0][1], scored[0][0], margin)
