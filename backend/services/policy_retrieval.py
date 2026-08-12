"""Optional policy retrieval seam; disabled by default for this local MVP."""

from __future__ import annotations

from backend.config import Settings


class PolicyRetriever:
    def __init__(self, settings: Settings) -> None:
        self.enabled = settings.enable_policy_retrieval

    def retrieve(self, text: str, limit: int = 3) -> list[dict[str, str]]:
        if not self.enabled:
            return []
        # TODO: connect normalized policy documents and Gemini embeddings here.
        return []
