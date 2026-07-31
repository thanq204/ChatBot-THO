"""SQLite repository for the local Admin Review Queue and audit trail."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from src.config import Settings, get_settings
from src.models.moderation import AdminDecisionRequest, AuditLogEntry, MemberSubmission, ModerationResult, ReviewCase


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ReviewStore:
    def __init__(self, database_url: str | None = None, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        url = database_url or settings.database_url
        if not url.startswith("sqlite:///"):
            raise ValueError("The local MVP supports SQLite only.")
        self.path = Path(url.removeprefix("sqlite:///"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._create_tables()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _create_tables(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS reviews (
                    review_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, content TEXT NOT NULL,
                    channel TEXT NOT NULL, recent_context TEXT NOT NULL, model_action TEXT NOT NULL,
                    model_category TEXT NOT NULL, model_risk_level TEXT NOT NULL, model_reason TEXT NOT NULL,
                    model_confidence REAL NOT NULL, evidence TEXT NOT NULL DEFAULT '[]', model_used TEXT NOT NULL DEFAULT 'unknown',
                    fallback_used INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL, created_at TEXT NOT NULL,
                    reviewed_at TEXT, admin_action TEXT, admin_note TEXT, reviewer TEXT
                );
                CREATE TABLE IF NOT EXISTS audit_logs (
                    audit_id TEXT PRIMARY KEY, review_id TEXT NOT NULL, user_id TEXT NOT NULL,
                    content TEXT NOT NULL, channel TEXT NOT NULL, model_action TEXT NOT NULL,
                    model_category TEXT NOT NULL, model_risk_level TEXT NOT NULL, model_reason TEXT NOT NULL,
                    model_confidence REAL NOT NULL, evidence TEXT NOT NULL DEFAULT '[]', model_used TEXT NOT NULL DEFAULT 'unknown',
                    fallback_used INTEGER NOT NULL DEFAULT 0, admin_action TEXT NOT NULL, admin_note TEXT NOT NULL,
                    reviewer TEXT NOT NULL, created_at TEXT NOT NULL, reviewed_at TEXT NOT NULL
                );
                """
            )
            self._add_column_if_missing(db, "reviews", "evidence", "TEXT NOT NULL DEFAULT '[]'")
            self._add_column_if_missing(db, "reviews", "model_used", "TEXT NOT NULL DEFAULT 'unknown'")
            self._add_column_if_missing(db, "reviews", "fallback_used", "INTEGER NOT NULL DEFAULT 0")
            self._add_column_if_missing(db, "audit_logs", "evidence", "TEXT NOT NULL DEFAULT '[]'")
            self._add_column_if_missing(db, "audit_logs", "model_used", "TEXT NOT NULL DEFAULT 'unknown'")
            self._add_column_if_missing(db, "audit_logs", "fallback_used", "INTEGER NOT NULL DEFAULT 0")

    @staticmethod
    def _add_column_if_missing(db: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def create_review(self, submission: MemberSubmission, result: ModerationResult) -> ReviewCase:
        review_id, created_at = f"REV-{uuid.uuid4().hex[:10].upper()}", _now()
        with self._connect() as db:
            db.execute(
                """INSERT INTO reviews
                   (review_id, user_id, content, channel, recent_context, model_action, model_category,
                    model_risk_level, model_reason, model_confidence, evidence, model_used, fallback_used,
                    status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
                (
                    review_id, submission.user_id, submission.text, submission.channel,
                    json.dumps(submission.recent_context, ensure_ascii=False), result.action, result.category,
                    result.risk_level, result.reason, result.confidence, json.dumps(result.evidence, ensure_ascii=False),
                    result.model_used, int(result.fallback_used), created_at,
                ),
            )
        return self.get_review(review_id)

    def get_review(self, review_id: str) -> ReviewCase:
        with self._connect() as db:
            row = db.execute("SELECT * FROM reviews WHERE review_id = ?", (review_id,)).fetchone()
        if row is None:
            raise KeyError(review_id)
        return self._review_from_row(row)

    def list_pending(self) -> list[ReviewCase]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM reviews WHERE status = 'pending' ORDER BY created_at DESC").fetchall()
        return [self._review_from_row(row) for row in rows]

    def list_audit_logs(self) -> list[AuditLogEntry]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM audit_logs ORDER BY reviewed_at DESC").fetchall()
        entries = []
        for row in rows:
            data = dict(row)
            data["evidence"] = json.loads(data.get("evidence") or "[]")
            data["fallback_used"] = bool(data.get("fallback_used", 0))
            entries.append(AuditLogEntry.model_validate(data))
        return entries

    def decide(self, review_id: str, decision: AdminDecisionRequest) -> ReviewCase:
        reviewed_at = _now()
        with self._connect() as db:
            row = db.execute("SELECT * FROM reviews WHERE review_id = ?", (review_id,)).fetchone()
            if row is None:
                raise KeyError(review_id)
            if row["status"] != "pending":
                raise ValueError("This review has already been decided.")
            db.execute(
                """UPDATE reviews SET status = 'reviewed', reviewed_at = ?, admin_action = ?, admin_note = ?, reviewer = ?
                   WHERE review_id = ?""",
                (reviewed_at, decision.action, decision.admin_note, decision.reviewer, review_id),
            )
            db.execute(
                """INSERT INTO audit_logs
                   (audit_id, review_id, user_id, content, channel, model_action, model_category,
                    model_risk_level, model_reason, model_confidence, evidence, model_used, fallback_used,
                    admin_action, admin_note, reviewer, created_at, reviewed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"AUD-{uuid.uuid4().hex[:10].upper()}", review_id, row["user_id"], row["content"], row["channel"],
                    row["model_action"], row["model_category"], row["model_risk_level"], row["model_reason"],
                    row["model_confidence"], row["evidence"], row["model_used"], row["fallback_used"],
                    decision.action, decision.admin_note, decision.reviewer,
                    row["created_at"], reviewed_at,
                ),
            )
        return self.get_review(review_id)

    @staticmethod
    def _review_from_row(row: sqlite3.Row) -> ReviewCase:
        data = dict(row)
        data["recent_context"] = json.loads(data["recent_context"])
        data["evidence"] = json.loads(data.get("evidence") or "[]")
        data["fallback_used"] = bool(data.get("fallback_used", 0))
        return ReviewCase.model_validate(data)
