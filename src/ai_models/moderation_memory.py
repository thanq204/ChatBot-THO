"""Semantic memory for human-confirmed moderation decisions."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass

from .contracts import ModerationMark, ModerationMemoryMatch, Vector
from .similarity import cosine_similarity, normalize_text, query_coverage


@dataclass(frozen=True, slots=True)
class ModerationMemoryConfig:
    minimum_score: float = 0.90
    semantic_weight: float = 0.92
    lexical_weight: float = 0.08
    require_same_category: bool = True


class ModerationMemoryIndex:
    """Look up prior human decisions before creating another Admin ticket."""

    def __init__(
        self,
        marks: Iterable[ModerationMark] = (),
        config: ModerationMemoryConfig | None = None,
    ) -> None:
        self.config = config or ModerationMemoryConfig()
        self._marks: dict[str, ModerationMark] = {mark.mark_id: mark for mark in marks}

    def add(self, mark: ModerationMark) -> None:
        self._marks[mark.mark_id] = mark

    def match(self, text: str, embedding: Vector, *, category: str | None = None) -> ModerationMemoryMatch:
        normalized = normalize_text(text)
        exact_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        scored: list[tuple[float, ModerationMark]] = []
        for mark in self._marks.values():
            if not mark.active:
                continue
            if self.config.require_same_category and category and mark.category != category:
                continue
            mark_normalized = normalize_text(mark.text)
            if hashlib.sha256(mark_normalized.encode("utf-8")).hexdigest() == exact_hash:
                score = 1.0
            else:
                semantic = max(0.0, cosine_similarity(embedding, mark.embedding))
                lexical = query_coverage(text, mark.text)
                score = self.config.semantic_weight * semantic + self.config.lexical_weight * lexical
            scored.append((score, mark))
        if not scored:
            return ModerationMemoryMatch(False, 0.0, True, False)
        score, mark = max(scored, key=lambda item: item[0])
        if score < self.config.minimum_score:
            return ModerationMemoryMatch(False, score, True, False)
        timestamp = mark.marked_at.isoformat().replace("+00:00", "Z")
        banner = f"(Đã được đánh dấu: {mark.reason} bởi: {mark.marked_by} vào lúc: {timestamp})"
        return ModerationMemoryMatch(
            matched=True,
            similarity=score,
            send_to_admin=False,
            can_expand=True,
            banner=banner,
            mark=mark,
        )
