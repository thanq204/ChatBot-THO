"""Local reviewed-case memory using persisted embeddings.

The vector table deliberately lives beside the existing SQLite data so the MVP
does not require a hosted vector database. Embeddings are created only when a
review is saved or when there is at least one reviewed vector to search.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.config import Settings, get_settings
from src.models.community import ConversationThread


def _normalise(text: str) -> str:
    return " ".join(text.lower().split())


def thread_text(thread: ConversationThread) -> str:
    return "\n".join(
        f"{'reply' if message.parent_message_id else 'comment'}: {message.text}"
        for message in thread.messages
    )[:12000]


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


class EmbeddingMemory:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        url = self.settings.database_url
        if not url.startswith("sqlite:///"):
            raise ValueError("The local MVP supports SQLite embedding memory only.")
        self.path = Path(url.removeprefix("sqlite:///"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._create_table()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _create_table(self) -> None:
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS reviewed_case_embeddings (
                    embedding_id TEXT PRIMARY KEY,
                    intervention_id TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    text_hash TEXT NOT NULL,
                    source_text TEXT NOT NULL,
                    vector_json TEXT NOT NULL,
                    admin_action TEXT NOT NULL,
                    category TEXT,
                    risk_level TEXT,
                    reviewer TEXT,
                    created_at TEXT NOT NULL
                )"""
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_reviewed_embedding_hash ON reviewed_case_embeddings(text_hash)")

    def _embed(self, text: str) -> list[float] | None:
        if not self.settings.openai_api_key:
            return None
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.settings.openai_api_key)
            response = client.embeddings.create(
                model=self.settings.openai_embedding_model,
                input=text,
            )
            return list(response.data[0].embedding)
        except Exception:
            # A failed embedding call must never block an Admin decision.
            return None

    def count(self) -> int:
        with self._connect() as db:
            return int(db.execute("SELECT COUNT(*) FROM reviewed_case_embeddings").fetchone()[0])

    def remember_review(
        self,
        thread: ConversationThread,
        intervention_id: str,
        admin_action: str,
        reviewer: str,
    ) -> str | None:
        text = thread_text(thread)
        vector = self._embed(text)
        if not vector:
            return None
        embedding_id = f"EMB-{uuid.uuid4().hex[:10].upper()}"
        analysis = thread.analysis
        with self._connect() as db:
            db.execute(
                """INSERT INTO reviewed_case_embeddings
                (embedding_id, intervention_id, thread_id, text_hash, source_text, vector_json,
                 admin_action, category, risk_level, reviewer, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    embedding_id,
                    intervention_id,
                    thread.thread_id,
                    hashlib.sha256(_normalise(text).encode("utf-8")).hexdigest(),
                    text,
                    json.dumps(vector),
                    admin_action,
                    analysis.category if analysis else None,
                    analysis.risk_level if analysis else None,
                    reviewer,
                    datetime.now(UTC).isoformat(),
                ),
            )
        return embedding_id

    def search(self, thread: ConversationThread, limit: int = 5) -> list[dict[str, Any]]:
        if self.count() == 0:
            return []
        text = thread_text(thread)
        normalised_hash = hashlib.sha256(_normalise(text).encode("utf-8")).hexdigest()
        vector = self._embed(text)
        if not vector:
            return []
        with self._connect() as db:
            rows = db.execute("SELECT * FROM reviewed_case_embeddings").fetchall()
        matches = []
        for row in rows:
            stored_vector = json.loads(row["vector_json"])
            score = 1.0 if row["text_hash"] == normalised_hash else _cosine(vector, stored_vector)
            matches.append({
                "embedding_id": row["embedding_id"],
                "intervention_id": row["intervention_id"],
                "thread_id": row["thread_id"],
                "score": round(score, 4),
                "source_text": row["source_text"],
                "admin_action": row["admin_action"],
                "category": row["category"],
                "risk_level": row["risk_level"],
                "reviewer": row["reviewer"],
            })
        return sorted(matches, key=lambda item: item["score"], reverse=True)[:limit]
