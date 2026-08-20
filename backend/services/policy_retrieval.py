"""Semantic retrieval for active Admin/Mod moderation policies."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from backend.config import Settings

if TYPE_CHECKING:
    from backend.services.operations_store import OperationsStore


class PolicyRetriever:
    def __init__(self, settings: Settings, store: OperationsStore) -> None:
        self.settings = settings
        self.store = store
        self.enabled = settings.enable_policy_retrieval

    def retrieve(self, text: str, limit: int = 3) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        return [
            {
                "policy_id": policy.policy_id,
                "name": policy.name,
                "category": policy.category,
                "action": policy.action,
                "version": policy.version,
                "similarity": similarity,
            }
            for similarity, policy in self.store.retrieve_policy_candidates(text, limit)
            if similarity >= self.settings.moderation_policy_semantic_threshold
        ]
