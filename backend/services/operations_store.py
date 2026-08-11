"""SQLite persistence for the multi-platform Community Operations Copilot."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import sqlite3
import unicodedata
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from backend.config import Settings, get_settings
from backend.models.operations import (
    CommonMessage,
    Incident,
    KnowledgeDocument,
    KnowledgeDocumentRequest,
    KnowledgeImportRecord,
    KnowledgeImportResponse,
    MessageDecision,
    OperationsSummary,
    Policy,
    PolicyUpsertRequest,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


logger = logging.getLogger(__name__)


def _fold_search_text(value: str) -> str:
    """Make Vietnamese and English search terms comparable without an LLM."""
    value = value.lower().replace("đ", "d").replace("Đ", "d")
    value = unicodedata.normalize("NFD", value)
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


# Query-intent bridges are deliberately small and explicit. They solve the
# Vietnamese -> English wording gap (for example "đẩy lẻ" -> "Split Push")
# before the optional answer LLM is called, so the LLM cannot choose a source.
_KNOWLEDGE_CONCEPTS = (
    (("xa thu", "adc", "marksman", "bot lane"), ("xa thu", "adc", "marksman", "bot lane"), 30),
    (("duong tren", "top lane", "top"), ("duong tren", "top lane", "top", "nguoi choi duong tren"), 30),
    (("di rung", "jungle", "jungler", "nguoi di rung"), ("di rung", "jungle", "jungler", "nguoi di rung"), 30),
    (("duong giua", "mid lane", "mid", "mid lane"), ("duong giua", "mid lane", "mid", "nguoi choi duong giua"), 30),
    (("ho tro", "support", "supporter", "tuong ho tro"), ("ho tro", "support", "supporter", "tuong ho tro"), 30),
    (("day le", "day duong", "split push", "push le"), ("split push", "split", "day le", "day duong", "push le"), 28),
    (("giao tranh tong", "giao tranh", "team fight", "teamfight", "combat"), ("team fight", "teamfight", "giao tranh", "combat"), 16),
    (("cuoi game", "cuoi tran", "manh cuoi", "tang tien", "late game", "scaling"), ("late game", "scaling", "cuoi tran", "cuoi game", "tang tien"), 18),
    (("dau game", "dau tran", "manh dau", "early game"), ("early game", "dau tran", "dau game", "manh dau"), 14),
    (("bao ve xa thu", "bao ke xa thu", "bao ve chu luc", "protect adc", "protecting adc"), ("protect adc", "protecting adc", "bao ve xa thu", "bao ke xa thu", "bao ve chu luc"), 16),
    (("chong lao vao", "anti dive", "counter dive"), ("anti dive", "counter dive", "chong lao vao"), 16),
)


class OperationsStore:
    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        self.settings = settings
        url = settings.database_url
        if not url.startswith("sqlite:///"):
            raise ValueError("Operations MVP currently supports SQLite only.")
        self.path = Path(url.removeprefix("sqlite:///"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._create_tables()
        self.seed_defaults()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def _create_tables(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS operations_messages (
                    message_id TEXT PRIMARY KEY, platform TEXT NOT NULL, community_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL, thread_key TEXT, parent_message_id TEXT, author_id TEXT NOT NULL,
                    text TEXT NOT NULL, timestamp TEXT NOT NULL, source_url TEXT, raw_json TEXT NOT NULL DEFAULT '{}',
                    decision TEXT, category TEXT, severity TEXT, risk_score REAL, confidence REAL,
                    explanation TEXT, model_used TEXT, incident_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_ops_messages_platform ON operations_messages(platform);
                CREATE INDEX IF NOT EXISTS idx_ops_messages_incident ON operations_messages(incident_id);
                CREATE TABLE IF NOT EXISTS operations_gate_runs (
                    run_id TEXT PRIMARY KEY, message_id TEXT NOT NULL, gate TEXT NOT NULL, passed INTEGER NOT NULL,
                    label TEXT NOT NULL, category TEXT NOT NULL, risk_score REAL NOT NULL, evidence_json TEXT NOT NULL,
                    explanation TEXT NOT NULL, model_used TEXT NOT NULL, duration_ms INTEGER NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS operations_incidents (
                    incident_id TEXT PRIMARY KEY, platform TEXT NOT NULL, community_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL, thread_key TEXT, status TEXT NOT NULL, severity TEXT NOT NULL,
                    risk_score REAL NOT NULL, title TEXT NOT NULL, summary TEXT NOT NULL, categories_json TEXT NOT NULL,
                    message_ids_json TEXT NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
                    assigned_to TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_ops_incidents_status ON operations_incidents(status);
                CREATE TABLE IF NOT EXISTS operations_audit (
                    audit_id TEXT PRIMARY KEY, incident_id TEXT, message_id TEXT, event_type TEXT NOT NULL,
                    actor TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS operations_policies (
                    policy_id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL, category TEXT NOT NULL,
                    action TEXT NOT NULL, trigger_terms_json TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
                    version INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS operations_knowledge (
                    document_id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL, tags_json TEXT NOT NULL,
                    dataset TEXT NOT NULL DEFAULT 'general', active INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS operations_knowledge_embeddings (
                    document_id TEXT PRIMARY KEY, text_hash TEXT NOT NULL, model TEXT NOT NULL,
                    vector_json TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS operations_knowledge_imports (
                    import_id TEXT PRIMARY KEY, filename TEXT NOT NULL, format TEXT NOT NULL,
                    target TEXT NOT NULL, normalized_count INTEGER NOT NULL, skipped_count INTEGER NOT NULL,
                    warnings_json TEXT NOT NULL, normalized_by TEXT NOT NULL, created_at TEXT NOT NULL
                );
                """
            )
            columns = {row[1] for row in db.execute("PRAGMA table_info(operations_knowledge)").fetchall()}
            if "dataset" not in columns:
                db.execute("ALTER TABLE operations_knowledge ADD COLUMN dataset TEXT NOT NULL DEFAULT 'general'")

    def seed_defaults(self) -> None:
        with self._connect() as db:
            if not db.execute("SELECT 1 FROM operations_policies LIMIT 1").fetchone():
                defaults = [
                    ("POL-SPAM-001", "Spam and scam", "Repeated promotion, phishing or suspicious money links.", "spam", "hide", ["free money", "click link", "giveaway", "nhận tiền"]),
                    ("POL-HAR-001", "Personal attack", "Insults or direct humiliation of another participant.", "harassment", "warn", ["ngu", "đần", "vô dụng", "im đi"]),
                    ("POL-THREAT-001", "Threat or doxxing", "Direct or indirect threat of physical harm or exposure.", "violence", "hold_for_review", ["giết", "đánh", "tìm ra mày", "dox"]),
                ]
                db.executemany(
                    "INSERT INTO operations_policies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [(pid, name, desc, cat, action, _json(terms), 1, 1, _now()) for pid, name, desc, cat, action, terms in defaults],
                )
            if not db.execute("SELECT 1 FROM operations_knowledge LIMIT 1").fetchone():
                docs = [
                    ("KN-001", "Community rules", "Tập trung vào ý kiến, không công kích con người. Khi tranh luận, dẫn nguồn và giữ ngôn ngữ tôn trọng.", ["rules", "tone"]),
                    ("KN-002", "Escalation playbook", "Spam rõ ràng có thể hide. Công kích nhẹ có thể warn. Đe doạ hoặc chưa rõ ngữ cảnh phải hold for review.", ["moderation", "escalation"]),
                    ("KN-003", "Event policy", "Trong sự kiện trực tiếp, ưu tiên ask for clarification và public de-escalation trước khi khóa thread.", ["event", "mediation"]),
                ]
                db.executemany(
                    "INSERT INTO operations_knowledge (document_id, title, body, tags_json, dataset, active, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [(did, title, body, _json(tags), "community_rules", 1, _now()) for did, title, body, tags in docs],
                )

    def purge_demo_data(self) -> int:
        """Remove seeded/demo and synthetic test records, never live Discord IDs."""
        with self._connect() as db:
            rows = db.execute(
                """SELECT message_id, incident_id FROM operations_messages
                WHERE platform='demo'
                   OR (platform='discord' AND channel_id='general')
                   OR message_id LIKE 'test-%'
                   OR message_id='api-check'"""
            ).fetchall()
            message_ids = [row["message_id"] for row in rows]
            incident_ids = {row["incident_id"] for row in rows if row["incident_id"]}
            incident_ids.update(row["incident_id"] for row in db.execute("SELECT incident_id FROM operations_incidents WHERE platform='demo' OR (platform='discord' AND channel_id='general')").fetchall())
            if not message_ids and not incident_ids:
                return 0
            message_marks = ",".join("?" for _ in message_ids) or "NULL"
            incident_marks = ",".join("?" for _ in incident_ids) or "NULL"
            if message_ids:
                db.execute(f"DELETE FROM operations_gate_runs WHERE message_id IN ({message_marks})", message_ids)
            if incident_ids:
                db.execute(f"DELETE FROM operations_audit WHERE incident_id IN ({incident_marks})", list(incident_ids))
            if message_ids:
                db.execute(f"DELETE FROM operations_messages WHERE message_id IN ({message_marks})", message_ids)
            if incident_ids:
                db.execute(f"DELETE FROM operations_incidents WHERE incident_id IN ({incident_marks})", list(incident_ids))
            return len(message_ids)

    def deduplicate_open_incidents(self) -> int:
        """Merge repeated open incidents created by rescanning identical messages."""
        merged = 0
        with self._connect() as db:
            rows = db.execute("SELECT * FROM operations_incidents WHERE status IN ('open','monitoring') ORDER BY updated_at ASC").fetchall()
            groups: dict[tuple[str, str, str, str, str], list[sqlite3.Row]] = {}
            for row in rows:
                key = (row["platform"], row["community_id"], row["channel_id"], row["title"], row["summary"])
                groups.setdefault(key, []).append(row)
            for duplicates in groups.values():
                if len(duplicates) < 2:
                    continue
                winner = duplicates[0]
                message_ids = list(json.loads(winner["message_ids_json"]))
                categories = list(json.loads(winner["categories_json"]))
                for duplicate in duplicates[1:]:
                    message_ids.extend(json.loads(duplicate["message_ids_json"]))
                    categories.extend(json.loads(duplicate["categories_json"]))
                    db.execute("UPDATE operations_messages SET incident_id=? WHERE incident_id=?", (winner["incident_id"], duplicate["incident_id"]))
                    db.execute("UPDATE operations_audit SET incident_id=? WHERE incident_id=?", (winner["incident_id"], duplicate["incident_id"]))
                    db.execute("DELETE FROM operations_incidents WHERE incident_id=?", (duplicate["incident_id"],))
                    merged += 1
                db.execute("UPDATE operations_incidents SET message_ids_json=?, categories_json=?, risk_score=?, updated_at=? WHERE incident_id=?", (_json(list(dict.fromkeys(message_ids))), _json(list(dict.fromkeys(categories))), max(row["risk_score"] for row in duplicates), _now(), winner["incident_id"]))
        return merged

    def save_message(self, message: CommonMessage, result: MessageDecision, incident_id: str | None) -> None:
        now = _now()
        with self._connect() as db:
            db.execute(
                """INSERT INTO operations_messages
                (message_id, platform, community_id, channel_id, thread_key, parent_message_id, author_id, text,
                 timestamp, source_url, raw_json, decision, category, severity, risk_score, confidence, explanation,
                 model_used, incident_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_id) DO UPDATE SET decision=excluded.decision, category=excluded.category,
                severity=excluded.severity, risk_score=excluded.risk_score, confidence=excluded.confidence,
                explanation=excluded.explanation, model_used=excluded.model_used, incident_id=excluded.incident_id,
                updated_at=excluded.updated_at""",
                (message.message_id, message.platform, message.community_id, message.channel_id, message.thread_key,
                 message.parent_message_id, message.author_id, message.text, message.timestamp.isoformat(), message.source_url,
                 _json(message.raw), result.decision, result.category, result.severity, result.risk_score, result.confidence,
                 result.explanation, result.model_used, incident_id, now, now),
            )
            db.executemany(
                """INSERT INTO operations_gate_runs
                (run_id, message_id, gate, passed, label, category, risk_score, evidence_json, explanation, model_used, duration_ms, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [(f"GATE-{uuid.uuid4().hex[:10].upper()}", message.message_id, gate.gate, int(gate.passed), gate.label,
                  gate.category, gate.risk_score, _json(gate.evidence), gate.explanation, gate.model_used, gate.duration_ms, now)
                 for gate in result.gates],
            )

    def find_open_incident(self, message: CommonMessage) -> Incident | None:
        with self._connect() as db:
            row = db.execute(
                """SELECT * FROM operations_incidents WHERE platform=? AND community_id=? AND channel_id=?
                AND status IN ('open','monitoring') AND ((thread_key IS NULL AND ? IS NULL) OR thread_key=?)
                ORDER BY updated_at DESC LIMIT 1""",
                (message.platform, message.community_id, message.channel_id, message.thread_key, message.thread_key),
            ).fetchone()
            if not row:
                # A repeated identical message in the same channel should not
                # create a new visible incident on every connector scan.
                row = db.execute(
                    """SELECT i.* FROM operations_incidents i
                    JOIN operations_messages m ON m.incident_id=i.incident_id
                    WHERE i.platform=? AND i.community_id=? AND i.channel_id=?
                      AND i.status IN ('open','monitoring')
                      AND lower(trim(m.text))=lower(trim(?))
                      AND i.last_seen >= ?
                    ORDER BY i.updated_at DESC LIMIT 1""",
                    (message.platform, message.community_id, message.channel_id, message.text, (datetime.now(UTC) - timedelta(hours=24)).replace(microsecond=0).isoformat()),
                ).fetchone()
        return self._incident(row) if row else None

    def upsert_incident(self, message: CommonMessage, result: MessageDecision) -> Incident:
        existing = self.find_open_incident(message)
        now = datetime.now(UTC)
        if existing:
            ids = list(dict.fromkeys([*existing.message_ids, message.message_id]))
            categories = list(dict.fromkeys([*existing.categories, result.category]))
            severity = max((existing.severity, result.severity), key=lambda value: ["low", "medium", "high", "critical"].index(value))
            with self._connect() as db:
                db.execute(
                    """UPDATE operations_incidents SET severity=?, risk_score=?, categories_json=?, message_ids_json=?,
                    summary=?, last_seen=?, updated_at=? WHERE incident_id=?""",
                    (severity, max(existing.risk_score, result.risk_score), _json(categories), _json(ids), result.explanation, now.isoformat(), now.isoformat(), existing.incident_id),
                )
            self.add_audit(existing.incident_id, message.message_id, "message_grouped", "system", {"decision": result.decision})
            return self.get_incident(existing.incident_id)  # type: ignore[return-value]
        incident_id = f"INC-{uuid.uuid4().hex[:10].upper()}"
        with self._connect() as db:
            db.execute(
                """INSERT INTO operations_incidents
                (incident_id, platform, community_id, channel_id, thread_key, status, severity, risk_score, title, summary,
                 categories_json, message_ids_json, first_seen, last_seen, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (incident_id, message.platform, message.community_id, message.channel_id, message.thread_key, result.severity,
                 result.risk_score, f"{result.category.title()} in {message.platform}/{message.channel_id}", result.explanation,
                 _json([result.category]), _json([message.message_id]), message.timestamp.isoformat(), message.timestamp.isoformat(), now.isoformat(), now.isoformat()),
            )
        self.add_audit(incident_id, message.message_id, "incident_created", "system", {"decision": result.decision, "evidence": result.evidence})
        return self.get_incident(incident_id)  # type: ignore[return-value]

    def get_incident(self, incident_id: str) -> Incident | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM operations_incidents WHERE incident_id=?", (incident_id,)).fetchone()
        return self._incident(row) if row else None

    def list_incidents(self, status: str | None = None, platform: str | None = None) -> list[Incident]:
        clauses, values = [], []
        if status:
            clauses.append("status=?")
            values.append(status)
        if platform:
            clauses.append("platform=?")
            values.append(platform)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connect() as db:
            rows = db.execute(f"SELECT * FROM operations_incidents{where} ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END, updated_at DESC", values).fetchall()
        return [self._incident(row) for row in rows]

    def list_incident_messages(self, incident_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM operations_messages WHERE incident_id=? ORDER BY timestamp", (incident_id,)).fetchall()
        return [dict(row) for row in rows]

    def update_incident(self, incident_id: str, status: str | None, assigned_to: str | None, note: str) -> Incident | None:
        with self._connect() as db:
            db.execute("UPDATE operations_incidents SET status=COALESCE(?,status), assigned_to=COALESCE(?,assigned_to), updated_at=? WHERE incident_id=?", (status, assigned_to, _now(), incident_id))
        if note or status:
            self.add_audit(incident_id, None, "incident_updated", assigned_to or "Admin", {"status": status, "note": note})
        return self.get_incident(incident_id)

    def add_audit(self, incident_id: str | None, message_id: str | None, event_type: str, actor: str, payload: dict[str, Any]) -> None:
        with self._connect() as db:
            db.execute("INSERT INTO operations_audit VALUES (?, ?, ?, ?, ?, ?, ?)", (f"AUD-{uuid.uuid4().hex[:10].upper()}", incident_id, message_id, event_type, actor, _json(payload), _now()))

    def audit(self, incident_id: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM operations_audit WHERE (? IS NULL OR incident_id=?) ORDER BY created_at DESC", (incident_id, incident_id)).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]

    def list_policies(self) -> list[Policy]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM operations_policies ORDER BY policy_id").fetchall()
        return [Policy(policy_id=r["policy_id"], name=r["name"], description=r["description"], category=r["category"], action=r["action"], trigger_terms=json.loads(r["trigger_terms_json"]), active=bool(r["active"]), version=r["version"], updated_at=datetime.fromisoformat(r["updated_at"])) for r in rows]

    def upsert_policy(self, policy_id: str, request: PolicyUpsertRequest) -> Policy:
        now = _now()
        with self._connect() as db:
            old = db.execute("SELECT version FROM operations_policies WHERE policy_id=?", (policy_id,)).fetchone()
            version = int(old["version"]) + 1 if old else 1
            db.execute("""INSERT INTO operations_policies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(policy_id) DO UPDATE SET name=excluded.name, description=excluded.description, category=excluded.category, action=excluded.action, trigger_terms_json=excluded.trigger_terms_json, active=excluded.active, version=excluded.version, updated_at=excluded.updated_at""", (policy_id, request.name, request.description, request.category, request.action, _json(request.trigger_terms), int(request.active), version, now))
        return next(item for item in self.list_policies() if item.policy_id == policy_id)

    def delete_policy(self, policy_id: str) -> bool:
        with self._connect() as db:
            cursor = db.execute("DELETE FROM operations_policies WHERE policy_id=?", (policy_id,))
        return cursor.rowcount > 0

    def list_knowledge(self, dataset: str | None = None) -> list[KnowledgeDocument]:
        with self._connect() as db:
            if dataset:
                rows = db.execute("SELECT * FROM operations_knowledge WHERE dataset=? ORDER BY updated_at DESC", (dataset,)).fetchall()
            else:
                rows = db.execute("SELECT * FROM operations_knowledge ORDER BY updated_at DESC").fetchall()
        return [KnowledgeDocument(document_id=r["document_id"], title=r["title"], body=r["body"], tags=json.loads(r["tags_json"]), dataset=r["dataset"] or "general", active=bool(r["active"]), updated_at=datetime.fromisoformat(r["updated_at"])) for r in rows]

    def upsert_knowledge(self, document_id: str, request: KnowledgeDocumentRequest) -> KnowledgeDocument:
        now = _now()
        with self._connect() as db:
            db.execute("""INSERT INTO operations_knowledge (document_id, title, body, tags_json, dataset, active, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(document_id) DO UPDATE SET title=excluded.title, body=excluded.body, tags_json=excluded.tags_json, dataset=excluded.dataset, active=excluded.active, updated_at=excluded.updated_at""", (document_id, request.title, request.body, _json(request.tags), request.dataset, int(request.active), now))
        return next(item for item in self.list_knowledge() if item.document_id == document_id)

    def delete_knowledge(self, document_id: str) -> bool:
        with self._connect() as db:
            cursor = db.execute("DELETE FROM operations_knowledge WHERE document_id=?", (document_id,))
            db.execute("DELETE FROM operations_knowledge_embeddings WHERE document_id=?", (document_id,))
        return cursor.rowcount > 0

    def record_import(self, response: KnowledgeImportResponse) -> KnowledgeImportResponse:
        with self._connect() as db:
            db.execute(
                "INSERT INTO operations_knowledge_imports VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (response.import_id, response.filename, response.format, response.target, response.normalized_count,
                 response.skipped_count, _json(response.warnings), response.normalized_by, response.created_at.isoformat()),
            )
        return response

    def list_imports(self) -> list[KnowledgeImportRecord]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM operations_knowledge_imports ORDER BY created_at DESC LIMIT 50").fetchall()
        return [KnowledgeImportRecord(import_id=row["import_id"], filename=row["filename"], format=row["format"], target=row["target"], normalized_count=row["normalized_count"], skipped_count=row["skipped_count"], warnings=json.loads(row["warnings_json"] or "[]"), normalized_by=row["normalized_by"], created_at=datetime.fromisoformat(row["created_at"])) for row in rows]

    @staticmethod
    def _knowledge_embedding_text(document: KnowledgeDocument) -> str:
        return (
            f"Title: {document.title}\n"
            f"Dataset: {document.dataset}\n"
            f"Tags: {', '.join(document.tags)}\n"
            f"Content: {document.body}"
        )

    @staticmethod
    def _embedding_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if not left_norm or not right_norm:
            return 0.0
        return dot / (left_norm * right_norm)

    def _semantic_knowledge_search(
        self,
        question: str,
        documents: list[KnowledgeDocument],
        limit: int,
    ) -> list[KnowledgeDocument] | None:
        """Retrieve knowledge by opt-in OpenAI embeddings persisted in SQLite."""
        if not self.settings.knowledge_embedding_enabled or not self.settings.openai_api_key or not documents:
            return None
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.settings.openai_api_key)
            model = self.settings.openai_embedding_model
            records: dict[str, list[float]] = {}
            document_texts = {document.document_id: self._knowledge_embedding_text(document) for document in documents}
            document_hashes = {document_id: self._embedding_hash(text) for document_id, text in document_texts.items()}
            placeholders = ",".join("?" for _ in documents)
            with self._connect() as db:
                cached_rows = db.execute(
                    f"SELECT document_id, text_hash, model, vector_json FROM operations_knowledge_embeddings WHERE document_id IN ({placeholders})",
                    [document.document_id for document in documents],
                ).fetchall()
            for row in cached_rows:
                if row["text_hash"] == document_hashes.get(row["document_id"]) and row["model"] == model:
                    records[row["document_id"]] = json.loads(row["vector_json"])
            pending = [
                (document, document_texts[document.document_id], document_hashes[document.document_id])
                for document in documents if document.document_id not in records
            ]
            batch_size = self.settings.knowledge_embedding_batch_size
            for start in range(0, len(pending), batch_size):
                batch = pending[start:start + batch_size]
                response = client.embeddings.create(model=model, input=[item[1] for item in batch])
                vectors_by_index = {int(item.index): list(item.embedding) for item in response.data}
                if len(vectors_by_index) != len(batch):
                    raise ValueError("Embedding response was incomplete.")
                rows_to_save = []
                for index, (document, _text, text_hash) in enumerate(batch):
                    vector = vectors_by_index[index]
                    records[document.document_id] = vector
                    rows_to_save.append((document.document_id, text_hash, model, _json(vector), _now()))
                with self._connect() as db:
                    db.executemany(
                        "INSERT INTO operations_knowledge_embeddings (document_id, text_hash, model, vector_json, updated_at) VALUES (?, ?, ?, ?, ?) "
                        "ON CONFLICT(document_id) DO UPDATE SET text_hash=excluded.text_hash, model=excluded.model, vector_json=excluded.vector_json, updated_at=excluded.updated_at",
                        rows_to_save,
                    )
            query_response = client.embeddings.create(model=model, input=[question])
            query_vector = list(query_response.data[0].embedding)
            scored = sorted(
                ((self._cosine_similarity(query_vector, records[document.document_id]), document) for document in documents),
                key=lambda item: item[0],
                reverse=True,
            )
            if not scored or scored[0][0] < self.settings.knowledge_embedding_min_score:
                return []
            relevance_floor = max(self.settings.knowledge_embedding_min_score, scored[0][0] - 0.08)
            return [document for score, document in scored[:limit] if score >= relevance_floor]
        except Exception:
            logger.warning("Knowledge embedding retrieval unavailable; using deterministic fallback.", exc_info=True)
            return None

    def search_knowledge(self, question: str, limit: int = 3, dataset: str | None = None) -> list[KnowledgeDocument]:
        documents = self.list_knowledge(dataset)
        semantic_results = self._semantic_knowledge_search(question, documents, limit)
        if semantic_results is not None:
            return semantic_results
        question_text = _fold_search_text(question)
        question_tokens = re.findall(r"[a-z0-9]{2,}", question_text)
        stopwords = {
            "muon", "choi", "chien", "thuat", "nen", "pick", "team", "nhu", "nao", "cach", "vi", "tri", "phu", "hop", "loi", "danh",
            "doi", "hinh", "trong", "mot", "cac", "cho", "va", "la", "cua", "voi",
            "theo", "thong", "tin", "ve", "gi", "the", "co", "toi", "can", "khi",
            "lien", "minh", "huyen", "thoai", "vai", "tro", "nhiem", "vu", "lam",
        }
        words = {word for word in question_tokens if word not in stopwords}
        active_concepts = [concept for concept in _KNOWLEDGE_CONCEPTS if any(alias in question_text for alias in concept[0])]
        composition_request = bool(re.search(r"\b(doi hinh|cac tuong|tuong nao|pick|phu hop|loi danh)\b", question_text))

        def longest_common_run(left: list[str], right: list[str]) -> int:
            longest = 0
            for start in range(len(left)):
                for end in range(start + 2, len(left) + 1):
                    candidate = left[start:end]
                    if any(right[index:index + len(candidate)] == candidate for index in range(len(right))):
                        longest = max(longest, len(candidate))
            return longest

        scored = []
        for doc in self.list_knowledge(dataset):
            title_text = _fold_search_text(doc.title)
            title_tokens = re.findall(r"[a-z0-9]{2,}", title_text)
            haystack = _fold_search_text(f"{doc.title} {doc.body} {' '.join(doc.tags)}")
            content_tokens = set(re.findall(r"[a-z0-9]{2,}", haystack))
            title_matches = sum(1 for word in words if word in title_tokens)
            content_matches = sum(1 for word in words if word in content_tokens)
            phrase_matches = longest_common_run(question_tokens, title_tokens)
            # An exact multi-word title match is much more meaningful than
            # generic words such as "Liên Minh" shared by many documents.
            score = content_matches + (title_matches * 3) + (phrase_matches * 6)
            # Bridge common Vietnamese wording to English titles in imported
            # game guides, especially "yếu đầu game -> mạnh cuối trận".
            if "late game" in title_text and re.search(r"(cuối game|cuối trận|mạnh cuối|tăng tiến|late game|scaling)", question.lower()):
                score += 12
            if "early game" in title_text and re.search(r"(đầu game|đầu trận|mạnh đầu|early game)", question.lower()):
                score += 6
            semantic_hits = 0
            for query_aliases, document_aliases, boost in _KNOWLEDGE_CONCEPTS:
                if any(alias in question_text for alias in query_aliases):
                    matching_aliases = [alias for alias in document_aliases if alias in haystack]
                    if matching_aliases:
                        score += boost
                        if any(alias in title_text for alias in matching_aliases):
                            score += 8
                        semantic_hits += 1
            # Distinguish "which team/champions should I pick?" from a
            # glossary question about the same topic. Imported composition
            # playbooks expose this intent through their metadata instead of
            # requiring a document-specific title rule.
            if composition_request:
                metadata_text = _fold_search_text(f"{doc.title} {' '.join(doc.tags)}")
                if "composition" in metadata_text or "doi hinh" in metadata_text:
                    score += 24
            # Once the query contains a known topic (for example "xạ thủ"),
            # a document that never mentions that topic is not allowed to win
            # merely because it shares generic words such as "vai trò".
            if active_concepts and semantic_hits == 0:
                score = 0
            scored.append((score, semantic_hits, doc))
        # Never return an unrelated document just to give the LLM some
        # context. An empty result must stay empty so the caller can say that
        # the knowledge hub has no answer instead of hallucinating.
        ranked = sorted(scored, key=lambda item: (item[0], item[1]), reverse=True)
        if not ranked or ranked[0][0] <= 0:
            return []
        best_score = ranked[0][0]
        relevance_floor = max(2, best_score * 0.35)
        return [doc for score, _semantic_hits, doc in ranked[:limit] if score >= relevance_floor]

    def summary(self) -> OperationsSummary:
        with self._connect() as db:
            messages = int(db.execute("SELECT COUNT(*) FROM operations_messages").fetchone()[0])
            open_count = int(db.execute("SELECT COUNT(*) FROM operations_incidents WHERE status IN ('open','monitoring')").fetchone()[0])
            critical = int(db.execute("SELECT COUNT(*) FROM operations_incidents WHERE severity='critical' AND status IN ('open','monitoring')").fetchone()[0])
            platform_rows = db.execute("SELECT platform, COUNT(*) count FROM operations_messages GROUP BY platform").fetchall()
            decision_rows = db.execute("SELECT COALESCE(decision,'unknown') decision, COUNT(*) count FROM operations_messages GROUP BY decision").fetchall()
            category_rows = db.execute("SELECT COALESCE(category,'unknown') category, COUNT(*) count FROM operations_messages GROUP BY category").fetchall()
        return OperationsSummary(messages_analyzed=messages, open_incidents=open_count, critical_incidents=critical, by_platform={r["platform"]: r["count"] for r in platform_rows}, by_decision={r["decision"]: r["count"] for r in decision_rows}, by_category={r["category"]: r["count"] for r in category_rows})

    @staticmethod
    def _incident(row: sqlite3.Row) -> Incident:
        return Incident(incident_id=row["incident_id"], platform=row["platform"], community_id=row["community_id"], channel_id=row["channel_id"], thread_key=row["thread_key"], status=row["status"], severity=row["severity"], risk_score=row["risk_score"], title=row["title"], summary=row["summary"], categories=json.loads(row["categories_json"]), message_ids=json.loads(row["message_ids_json"]), message_count=len(json.loads(row["message_ids_json"])), first_seen=datetime.fromisoformat(row["first_seen"]), last_seen=datetime.fromisoformat(row["last_seen"]), assigned_to=row["assigned_to"], created_at=datetime.fromisoformat(row["created_at"]), updated_at=datetime.fromisoformat(row["updated_at"]))
