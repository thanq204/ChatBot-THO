"""Small provider ports kept outside web/backend integration code."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class EmbeddingProvider(Protocol):
    model_name: str

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one vector for every input, preserving input order."""


class OpenAIEmbeddingProvider:
    """Optional adapter; callers provide the key instead of reading global env."""

    def __init__(self, api_key: str, model_name: str = "text-embedding-3-small") -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self.model_name = model_name
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        values = list(texts)
        if not values:
            return []
        response = self._client.embeddings.create(model=self.model_name, input=values)
        by_index = {int(item.index): list(item.embedding) for item in response.data}
        if len(by_index) != len(values):
            raise RuntimeError("Embedding provider returned an incomplete batch")
        return [by_index[index] for index in range(len(values))]
