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
import urllib.request
import psycopg2
import psycopg2.extras
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.config import Settings, get_settings
from backend.models.operations import (
    FAQ,
    CommandContent,
    CommandContentRequest,
    CommonMessage,
    ActivityTimeline,
    CommunityHealth,
    FAQSuggestion,
    FAQUpsertRequest,
    Incident,
    KnowledgeDocument,
    KnowledgeDocumentRequest,
    KnowledgeImportRecord,
    KnowledgeImportResponse,
    MemberReport,
    MessageDecision,
    OperationsSummary,
    Policy,
    PolicyUpsertRequest,
    TimelineBucket,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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

    def _connect_pg(self):
        import psycopg2
        import psycopg2.extras
        dsn = getattr(self.settings, "faq_pg_dsn", "")
        if dsn:
            conn = psycopg2.connect(dsn)
        else:
            conn = psycopg2.connect(
                host=getattr(self.settings, "faq_pg_host", "localhost"),
                port=getattr(self.settings, "faq_pg_port", 5433),
                dbname=getattr(self.settings, "faq_pg_db", "faq_rag"),
                user=getattr(self.settings, "faq_pg_user", "faq_user"),
                password=getattr(self.settings, "faq_pg_password", "faq_pass_dev"),
            )
        return conn

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
                    assigned_to TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, source_url TEXT
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
                CREATE TABLE IF NOT EXISTS operations_moderation_marks (
                    mark_id TEXT PRIMARY KEY, incident_id TEXT NOT NULL, message_id TEXT NOT NULL,
                    text TEXT NOT NULL, normalized_text TEXT NOT NULL, category TEXT NOT NULL,
                    decision TEXT NOT NULL, reason TEXT NOT NULL, marked_by TEXT NOT NULL,
                    marked_at TEXT NOT NULL, source_url TEXT, active INTEGER NOT NULL DEFAULT 1,
                    version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_ops_moderation_marks_category
                    ON operations_moderation_marks(category, active);
                CREATE TABLE IF NOT EXISTS operations_moderation_embeddings (
                    mark_id TEXT PRIMARY KEY, text_hash TEXT NOT NULL, model TEXT NOT NULL,
                    vector_json TEXT NOT NULL, updated_at TEXT NOT NULL
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
                CREATE TABLE IF NOT EXISTS operations_faqs (
                    faq_id TEXT PRIMARY KEY, question TEXT NOT NULL, answer TEXT NOT NULL,
                    tags_json TEXT NOT NULL DEFAULT '[]', active INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS operations_faq_questions (
                    question_id TEXT PRIMARY KEY, message_id TEXT UNIQUE, question TEXT NOT NULL,
                    normalized_question TEXT NOT NULL, platform TEXT NOT NULL, author_id TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS operations_faq_suggestions (
                    suggestion_id TEXT PRIMARY KEY, representative_question TEXT NOT NULL, normalized_question TEXT NOT NULL,
                    question_count INTEGER NOT NULL DEFAULT 1, samples_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS operations_command_content (
                    command TEXT PRIMARY KEY, body TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
                    platforms_json TEXT NOT NULL DEFAULT '["telegram","discord"]', updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS operations_member_reports (
                    report_id TEXT PRIMARY KEY, platform TEXT NOT NULL, reporter_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL, details TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS operations_notification_preferences (
                    platform TEXT NOT NULL, member_id TEXT NOT NULL, daily_enabled INTEGER NOT NULL DEFAULT 1,
                    weekly_enabled INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL,
                    PRIMARY KEY (platform, member_id)
                );
                """
            )
            columns = {row[1] for row in db.execute("PRAGMA table_info(operations_knowledge)").fetchall()}
            if "dataset" not in columns:
                db.execute("ALTER TABLE operations_knowledge ADD COLUMN dataset TEXT NOT NULL DEFAULT 'general'")
            command_columns = {row[1] for row in db.execute("PRAGMA table_info(operations_command_content)").fetchall()}
            if "description" not in command_columns:
                db.execute("ALTER TABLE operations_command_content ADD COLUMN description TEXT NOT NULL DEFAULT ''")
            if "platforms_json" not in command_columns:
                db.execute("ALTER TABLE operations_command_content ADD COLUMN platforms_json TEXT NOT NULL DEFAULT '[\"telegram\",\"discord\"]'")
            incident_columns = {row[1] for row in db.execute("PRAGMA table_info(operations_incidents)").fetchall()}
            if "source_url" not in incident_columns:
                db.execute("ALTER TABLE operations_incidents ADD COLUMN source_url TEXT")

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
            if not db.execute("SELECT 1 FROM operations_faqs LIMIT 1").fetchone():
                faqs = [
                    ("FAQ-STUDY-RULES", "Nội quy nhóm học tập là gì?", "Tôn trọng mọi người, trao đổi đúng chủ đề, không spam/công kích, không chia sẻ đáp án thi hoặc làm hộ bài kiểm tra, và báo Admin khi cần hỗ trợ.", ["rules", "study-group"]),
                    ("FAQ-ACADEMIC-INTEGRITY", "Có được xin đáp án hoặc nhờ làm hộ bài kiểm tra không?", "Không. Nhóm hỗ trợ giải thích kiến thức và phương pháp làm bài, không cung cấp đáp án thi hoặc làm hộ bài kiểm tra.", ["academic-integrity", "assessment"]),
                    ("FAQ-ASK-HELP", "Làm sao để hỏi bài hiệu quả?", "Hãy nêu môn học, phần đang vướng, điều bạn đã thử và câu hỏi cụ thể. Đừng đăng thông tin cá nhân hoặc toàn bộ đề thi đang diễn ra.", ["study", "help"]),
                ]
                db.executemany("INSERT INTO operations_faqs VALUES (?, ?, ?, ?, ?, ?)", [(faq_id, question, answer, _json(tags), 1, _now()) for faq_id, question, answer, tags in faqs])
            if not db.execute("SELECT 1 FROM operations_command_content LIMIT 1").fetchone():
                command_defaults = {
                    "event": ("Chưa có thông báo mới về sự kiện hoặc lịch học.", "Sự kiện và lịch học sắp tới"),
                    "daily": ("Chưa có thông báo mới cho hôm nay.", "Việc cần làm hôm nay"),
                    "weekly": ("Chưa có thông báo mới cho tuần này.", "Kế hoạch tuần"),
                    "resources": ("Chưa có tài liệu học tập chính được Admin cập nhật.", "Tài liệu học tập chính"),
                    "admin": ("Liên hệ Admin/Mod trong kênh quản trị hoặc dùng /report để báo nội dung cần xem xét.", "Cách liên hệ Admin/Mod"),
                }
                db.executemany(
                    "INSERT INTO operations_command_content (command, body, description, platforms_json, updated_at) VALUES (?, ?, ?, ?, ?)",
                    [(command, body, description, _json(["telegram", "discord"]), _now()) for command, (body, description) in command_defaults.items()],
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

    def recent_context(self, message: CommonMessage) -> list[CommonMessage]:
        """Load nearby messages from the same live conversation for Gate 2."""
        since = message.timestamp - timedelta(minutes=self.settings.moderation_context_window_minutes)
        with self._connect() as db:
            rows = db.execute(
                """SELECT * FROM operations_messages
                WHERE platform=? AND community_id=? AND channel_id=? AND message_id<>?
                  AND timestamp>=? AND timestamp<=?
                  AND (? IS NULL OR thread_key=? OR parent_message_id=?)
                ORDER BY timestamp DESC LIMIT ?""",
                (
                    message.platform,
                    message.community_id,
                    message.channel_id,
                    message.message_id,
                    since.isoformat(),
                    message.timestamp.isoformat(),
                    message.thread_key,
                    message.thread_key,
                    message.parent_message_id,
                    self.settings.moderation_context_message_limit,
                ),
            ).fetchall()
        context = [
            CommonMessage(
                message_id=row["message_id"],
                platform=row["platform"],
                community_id=row["community_id"],
                channel_id=row["channel_id"],
                thread_key=row["thread_key"],
                parent_message_id=row["parent_message_id"],
                author_id=row["author_id"],
                text=row["text"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                source_url=row["source_url"],
                raw=json.loads(row["raw_json"] or "{}"),
            )
            for row in reversed(rows)
        ]
        return context

    def find_recent_equivalent_incident_id(self, message: CommonMessage, category: str) -> str | None:
        """Find an identical recent alert so connectors do not notify twice."""
        since = message.timestamp - timedelta(minutes=self.settings.moderation_context_window_minutes)
        with self._connect() as db:
            rows = db.execute(
                """SELECT text, incident_id FROM operations_messages
                WHERE platform=? AND community_id=? AND channel_id=? AND category=?
                  AND incident_id IS NOT NULL AND timestamp>=? AND timestamp<=?
                ORDER BY timestamp DESC LIMIT 30""",
                (
                    message.platform,
                    message.community_id,
                    message.channel_id,
                    category,
                    since.isoformat(),
                    message.timestamp.isoformat(),
                ),
            ).fetchall()
        normalized = _fold_search_text(message.text)
        match = next((row for row in rows if _fold_search_text(row["text"]) == normalized), None)
        return str(match["incident_id"]) if match else None

    @staticmethod
    def _local_moderation_embedding(text: str, dimensions: int = 256) -> list[float]:
        """Deterministic fallback embedding used when no provider is available."""
        tokens = _fold_search_text(text).split()
        features = [*tokens, *(f"{left}_{right}" for left, right in zip(tokens, tokens[1:]))]
        vector = [0.0] * dimensions
        for feature in features:
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % dimensions
            vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector

    def _moderation_embedding(self, text: str, preferred_model: str | None = None) -> tuple[str, list[float]]:
        local_model = "local-hash-embedding-v1"
        model = preferred_model or self.settings.openai_embedding_model
        can_use_provider = (
            model != local_model
            and self.settings.moderation_memory_embedding_enabled
            and bool(self.settings.openai_api_key)
        )
        if can_use_provider:
            try:
                from openai import OpenAI

                response = OpenAI(api_key=self.settings.openai_api_key).embeddings.create(model=model, input=[text])
                return model, list(response.data[0].embedding)
            except Exception:
                logger.warning("Moderation embedding provider unavailable; using local fallback.", exc_info=True)
        return local_model, self._local_moderation_embedding(text)

    def remember_incident(self, incident_id: str, marked_by: str, reason: str = "") -> str | None:
        """Persist one human-reviewed case and its separate embedding chunk."""
        incident = self.get_incident(incident_id)
        message = self.get_incident_message(incident_id)
        if not incident or not message:
            return None
        now = _now()
        mark_id = f"MM-{incident_id.removeprefix('INC-')}"
        text = str(message["text"])
        model, vector = self._moderation_embedding(text)
        with self._connect() as db:
            old = db.execute(
                "SELECT version, created_at FROM operations_moderation_marks WHERE mark_id=?",
                (mark_id,),
            ).fetchone()
            version = int(old["version"]) + 1 if old else 1
            created_at = str(old["created_at"]) if old else now
            db.execute(
                """INSERT INTO operations_moderation_marks
                (mark_id, incident_id, message_id, text, normalized_text, category, decision, reason,
                 marked_by, marked_at, source_url, active, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                ON CONFLICT(mark_id) DO UPDATE SET message_id=excluded.message_id, text=excluded.text,
                normalized_text=excluded.normalized_text, category=excluded.category,
                decision=excluded.decision, reason=excluded.reason, marked_by=excluded.marked_by,
                marked_at=excluded.marked_at, source_url=excluded.source_url, active=1,
                version=excluded.version, updated_at=excluded.updated_at""",
                (
                    mark_id,
                    incident_id,
                    message["message_id"],
                    text,
                    _fold_search_text(text),
                    str(message.get("category") or incident.categories[0]),
                    str(message.get("decision") or "hold_for_review"),
                    reason.strip() or incident.summary,
                    marked_by.strip() or "Admin",
                    now,
                    message.get("source_url"),
                    version,
                    created_at,
                    now,
                ),
            )
            db.execute(
                """INSERT INTO operations_moderation_embeddings
                (mark_id, text_hash, model, vector_json, updated_at) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(mark_id) DO UPDATE SET text_hash=excluded.text_hash, model=excluded.model,
                vector_json=excluded.vector_json, updated_at=excluded.updated_at""",
                (mark_id, self._embedding_hash(text), model, _json(vector), now),
            )
        self.add_audit(
            incident_id,
            str(message["message_id"]),
            "moderation_memory_updated",
            marked_by.strip() or "Admin",
            {"mark_id": mark_id, "category": str(message.get("category") or incident.categories[0]), "version": version},
        )
        return mark_id

    def match_reviewed_case(self, text: str, category: str):
        """Return the closest human-reviewed case using semantic + lexical score."""
        from src.ai_models.contracts import ModerationMark, ModerationMemoryMatch
        from src.ai_models.moderation_memory import ModerationMemoryConfig, ModerationMemoryIndex

        if not self.settings.enable_case_based_learning:
            return ModerationMemoryMatch(False, 0.0, True, False)
        with self._connect() as db:
            rows = db.execute(
                """SELECT m.*, e.model embedding_model, e.vector_json
                FROM operations_moderation_marks m
                JOIN operations_moderation_embeddings e ON e.mark_id=m.mark_id
                WHERE m.active=1 AND m.category=? ORDER BY m.updated_at DESC LIMIT ?""",
                (category, self.settings.similar_case_limit),
            ).fetchall()
        if not rows:
            return ModerationMemoryMatch(False, 0.0, True, False)
        query_vectors: dict[str, list[float]] = {}
        matches = []
        config = ModerationMemoryConfig(minimum_score=self.settings.moderation_memory_similarity_threshold)
        for row in rows:
            model = str(row["embedding_model"])
            if model not in query_vectors:
                returned_model, query_vector = self._moderation_embedding(text, preferred_model=model)
                query_vectors[model] = query_vector if returned_model == model else []
            mark = ModerationMark(
                mark_id=row["mark_id"],
                message_id=row["message_id"],
                text=row["text"],
                category=row["category"],
                decision=row["decision"],
                reason=row["reason"],
                marked_by=row["marked_by"],
                marked_at=datetime.fromisoformat(row["marked_at"]),
                embedding=tuple(json.loads(row["vector_json"])),
                source_url=row["source_url"],
                active=bool(row["active"]),
                version=int(row["version"]),
            )
            matches.append(
                ModerationMemoryIndex([mark], config).match(
                    text,
                    tuple(query_vectors[model]),
                    category=category,
                )
            )
        return max(matches, key=lambda item: item.similarity)

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
                 categories_json, message_ids_json, first_seen, last_seen, created_at, updated_at, source_url)
                VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (incident_id, message.platform, message.community_id, message.channel_id, message.thread_key, result.severity,
                 result.risk_score, f"{result.category.title()} từ {message.author_name or message.author_id}", result.explanation,
                 _json([result.category]), _json([message.message_id]), message.timestamp.isoformat(), message.timestamp.isoformat(), now.isoformat(), now.isoformat(), message.source_url),
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

    def get_incident_message(self, incident_id: str, message_id: str | None = None) -> dict[str, Any] | None:
        """Get the explicitly selected message, or the latest case message."""
        with self._connect() as db:
            if message_id:
                row = db.execute("SELECT * FROM operations_messages WHERE incident_id=? AND message_id=?", (incident_id, message_id)).fetchone()
            else:
                row = db.execute("SELECT * FROM operations_messages WHERE incident_id=? ORDER BY timestamp DESC LIMIT 1", (incident_id,)).fetchone()
        return dict(row) if row else None

    def update_incident(self, incident_id: str, status: str | None, assigned_to: str | None, note: str) -> Incident | None:
        with self._connect() as db:
            db.execute("UPDATE operations_incidents SET status=COALESCE(?,status), assigned_to=COALESCE(?,assigned_to), updated_at=? WHERE incident_id=?", (status, assigned_to, _now(), incident_id))
        if note or status:
            self.add_audit(incident_id, None, "incident_updated", assigned_to or "Admin", {"status": status, "note": note})
        if status == "resolved":
            self.remember_incident(incident_id, assigned_to or "Admin", note)
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
        try:
            conn = self._connect_pg()
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                if dataset:
                    cur.execute("SELECT * FROM knowledge_documents WHERE dataset=%s ORDER BY updated_at DESC", (dataset,))
                else:
                    cur.execute("SELECT * FROM knowledge_documents ORDER BY updated_at DESC")
                rows = cur.fetchall()
            conn.close()
            return [KnowledgeDocument(
                document_id=r["document_id"], 
                title=r["title"], 
                body=r["body"], 
                tags=r["tags"] if isinstance(r["tags"], list) else json.loads(r["tags"]), 
                dataset=r["dataset"] or "general", 
                active=bool(r["active"]), 
                updated_at=r["updated_at"]
            ) for r in rows]
        except Exception:
            logger.error("Failed to list knowledge from PostgreSQL", exc_info=True)
            return []

    def upsert_knowledge(self, document_id: str, request: KnowledgeDocumentRequest) -> KnowledgeDocument:
        import psycopg2
        from openai import OpenAI
        
        now = _now()
        
        # 1. Chunking
        chunks = []
        text = request.title + "\n\n" + request.body
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        current_chunk = ""
        for p in paragraphs:
            if len(current_chunk) + len(p) < 1500:
                current_chunk += p + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = p + "\n\n"
        if current_chunk:
            chunks.append(current_chunk.strip())
        if not chunks:
            chunks = [text[:1500]]
            
        # 2. Get embeddings
        client = OpenAI(api_key=self.settings.openai_api_key)
        response = client.embeddings.create(model=self.settings.openai_embedding_model, input=chunks)
        embeddings = [list(item.embedding) for item in response.data]
        
        # 3. Upsert into PostgreSQL
        try:
            conn = self._connect_pg()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO knowledge_documents (document_id, title, body, tags, dataset, active, updated_at, created_at) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(document_id) DO UPDATE SET 
                        title=EXCLUDED.title, body=EXCLUDED.body, tags=EXCLUDED.tags, 
                        dataset=EXCLUDED.dataset, active=EXCLUDED.active, updated_at=EXCLUDED.updated_at
                """, (document_id, request.title, request.body, json.dumps(request.tags), request.dataset, bool(request.active), now, now))
                
                cur.execute("DELETE FROM knowledge_sections WHERE document_id=%s", (document_id,))
                
                for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
                    chunk_id = f"{document_id}-{i}"
                    cur.execute("""
                        INSERT INTO knowledge_sections (chunk_id, document_id, chunk_index, content, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (chunk_id, document_id, i, chunk_text, now))
                    
                    vector_str = "[" + ",".join(str(f) for f in embedding) + "]"
                    cur.execute("""
                        INSERT INTO knowledge_section_embeddings (chunk_id, embedding, updated_at)
                        VALUES (%s, %s::vector, %s)
                    """, (chunk_id, vector_str, now))
            conn.commit()
            conn.close()
        except Exception:
            logger.error("Failed to upsert knowledge to PostgreSQL", exc_info=True)
            raise
            
        return next(item for item in self.list_knowledge() if item.document_id == document_id)

    def delete_knowledge(self, document_id: str) -> bool:
        try:
            conn = self._connect_pg()
            with conn.cursor() as cur:
                cur.execute("DELETE FROM knowledge_documents WHERE document_id=%s", (document_id,))
                rowcount = cur.rowcount
            conn.commit()
            conn.close()
            return rowcount > 0
        except Exception:
            logger.error("Failed to delete knowledge from PostgreSQL", exc_info=True)
            return False

    @staticmethod
    def _command_content(row: sqlite3.Row) -> CommandContent:
        return CommandContent(
            command=row["command"],
            body=row["body"],
            description=row["description"] or "",
            platforms=json.loads(row["platforms_json"] or "null") or ["telegram", "discord"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def get_command_content(self, command: str) -> CommandContent | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM operations_command_content WHERE command=?", (command,)).fetchone()
        return self._command_content(row) if row else None

    def list_command_content(self) -> list[CommandContent]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM operations_command_content ORDER BY command").fetchall()
        return [self._command_content(row) for row in rows]

    def upsert_command_content(self, command: str, request: CommandContentRequest) -> CommandContent:
        command = command.strip().lower().lstrip("/")
        now = _now()
        with self._connect() as db:
            db.execute(
                """INSERT INTO operations_command_content (command, body, description, platforms_json, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(command) DO UPDATE SET body=excluded.body, description=excluded.description,
                platforms_json=excluded.platforms_json, updated_at=excluded.updated_at""",
                (command, request.body, request.description.strip(), _json(request.platforms), now),
            )
        return self.get_command_content(command)  # type: ignore[return-value]

    def delete_command_content(self, command: str) -> bool:
        with self._connect() as db:
            cursor = db.execute("DELETE FROM operations_command_content WHERE command=?", (command,))
        return cursor.rowcount > 0

    def create_member_report(self, message: CommonMessage, details: str) -> MemberReport:
        report = MemberReport(report_id=f"REP-{uuid.uuid4().hex[:10].upper()}", platform=message.platform, reporter_id=message.author_id, channel_id=message.channel_id, details=details[:4000], created_at=datetime.now(UTC))
        with self._connect() as db:
            db.execute("INSERT INTO operations_member_reports VALUES (?, ?, ?, ?, ?, 'open', ?)", (report.report_id, report.platform, report.reporter_id, report.channel_id, report.details, report.created_at.isoformat()))
        self.add_audit(None, message.message_id, "member_report_created", message.author_id, {"report_id": report.report_id, "details": report.details})
        return report

    def list_member_reports(self) -> list[MemberReport]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM operations_member_reports ORDER BY created_at DESC").fetchall()
        return [MemberReport(report_id=row["report_id"], platform=row["platform"], reporter_id=row["reporter_id"], channel_id=row["channel_id"], details=row["details"], status=row["status"], created_at=datetime.fromisoformat(row["created_at"])) for row in rows]

    def set_member_report_status(self, report_id: str, status: str, actor: str = "Admin") -> MemberReport | None:
        """Close out a /report submission. Returns None when the id is unknown."""
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE operations_member_reports SET status=? WHERE report_id=?", (status, report_id)
            )
            if cursor.rowcount == 0:
                return None
        self.add_audit(None, None, "member_report_reviewed", actor, {"report_id": report_id, "status": status})
        return next((item for item in self.list_member_reports() if item.report_id == report_id), None)

    def set_notification_preference(self, platform: str, member_id: str, kind: str, enabled: bool) -> None:
        column = "daily_enabled" if kind == "daily" else "weekly_enabled"
        now = _now()
        with self._connect() as db:
            db.execute("INSERT INTO operations_notification_preferences (platform, member_id, daily_enabled, weekly_enabled, updated_at) VALUES (?, ?, 1, 1, ?) ON CONFLICT(platform, member_id) DO NOTHING", (platform, member_id, now))
            db.execute(f"UPDATE operations_notification_preferences SET {column}=?, updated_at=? WHERE platform=? AND member_id=?", (int(enabled), now, platform, member_id))

    @staticmethod
    def _faq(row: sqlite3.Row) -> FAQ:
        return FAQ(faq_id=row["faq_id"], question=row["question"], answer=row["answer"], tags=json.loads(row["tags_json"]), active=bool(row["active"]), updated_at=datetime.fromisoformat(row["updated_at"]))

    @staticmethod
    def _similarity(left: str, right: str) -> float:
        left_terms, right_terms = set(_fold_search_text(left).split()), set(_fold_search_text(right).split())
        return len(left_terms & right_terms) / len(left_terms | right_terms) if left_terms and right_terms else 0.0

    def list_faqs(self, active_only: bool = False) -> list[FAQ]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM operations_faqs WHERE (?=0 OR active=1) ORDER BY updated_at DESC", (int(active_only),)).fetchall()
        return [self._faq(row) for row in rows]

    def find_faq(self, question: str, threshold: float = 0.72) -> FAQ | None:
        candidates = [(self._similarity(question, faq.question), faq) for faq in self.list_faqs(active_only=True)]
        best = max(candidates, default=(0.0, None), key=lambda item: item[0])
        return best[1] if best[0] >= threshold else None

    def upsert_faq(self, faq_id: str, request: FAQUpsertRequest, duplicate_threshold: float = 0.82) -> tuple[FAQ, list[FAQ]]:
        similar = [faq for faq in self.list_faqs(active_only=True) if faq.faq_id != faq_id and self._similarity(request.question, faq.question) >= duplicate_threshold]
        now = _now()
        with self._connect() as db:
            db.execute("""INSERT INTO operations_faqs VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(faq_id) DO UPDATE SET question=excluded.question, answer=excluded.answer, tags_json=excluded.tags_json, active=excluded.active, updated_at=excluded.updated_at""", (faq_id, request.question, request.answer, _json(request.tags), int(request.active), now))
        return next(faq for faq in self.list_faqs() if faq.faq_id == faq_id), similar

    def delete_faq(self, faq_id: str) -> bool:
        with self._connect() as db:
            cursor = db.execute("DELETE FROM operations_faqs WHERE faq_id=?", (faq_id,))
        return cursor.rowcount > 0

    def record_unanswered_question(self, message: CommonMessage, minimum_questions: int = 3) -> FAQSuggestion | None:
        normalized = _fold_search_text(message.text)
        if not normalized:
            return None
        now = _now()
        with self._connect() as db:
            try:
                db.execute("INSERT INTO operations_faq_questions VALUES (?, ?, ?, ?, ?, ?, ?)", (f"FQQ-{uuid.uuid4().hex[:12].upper()}", message.message_id, message.text[:2000], normalized, message.platform, message.author_id, now))
            except sqlite3.IntegrityError:
                return None
            rows = db.execute("SELECT * FROM operations_faq_suggestions WHERE status='open'").fetchall()
            match = next((row for row in rows if self._similarity(normalized, row["normalized_question"]) >= 0.72), None)
            if match:
                samples = list(dict.fromkeys([*json.loads(match["samples_json"]), message.text]))[-5:]
                count = int(match["question_count"]) + 1
                db.execute("UPDATE operations_faq_suggestions SET question_count=?, samples_json=?, updated_at=? WHERE suggestion_id=?", (count, _json(samples), now, match["suggestion_id"]))
                row = db.execute("SELECT * FROM operations_faq_suggestions WHERE suggestion_id=?", (match["suggestion_id"],)).fetchone()
            else:
                suggestion_id = f"FAQS-{uuid.uuid4().hex[:10].upper()}"
                db.execute("INSERT INTO operations_faq_suggestions VALUES (?, ?, ?, ?, ?, 'open', ?, ?)", (suggestion_id, message.text[:500], normalized, 1, _json([message.text]), now, now))
                row = db.execute("SELECT * FROM operations_faq_suggestions WHERE suggestion_id=?", (suggestion_id,)).fetchone()
        suggestion = self._suggestion(row)
        return suggestion if suggestion.question_count >= minimum_questions else None

    @staticmethod
    def _suggestion(row: sqlite3.Row) -> FAQSuggestion:
        return FAQSuggestion(suggestion_id=row["suggestion_id"], representative_question=row["representative_question"], question_count=row["question_count"], status=row["status"], sample_questions=json.loads(row["samples_json"]), created_at=datetime.fromisoformat(row["created_at"]), updated_at=datetime.fromisoformat(row["updated_at"]))

    def list_faq_suggestions(self, status: str = "open") -> list[FAQSuggestion]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM operations_faq_suggestions WHERE (?='' OR status=?) ORDER BY question_count DESC, updated_at DESC", (status, status)).fetchall()
        return [self._suggestion(row) for row in rows]

    def set_faq_suggestion_status(self, suggestion_id: str, status: str) -> FAQSuggestion | None:
        with self._connect() as db:
            cursor = db.execute("UPDATE operations_faq_suggestions SET status=?, updated_at=? WHERE suggestion_id=?", (status, _now(), suggestion_id))
            if not cursor.rowcount:
                return None
            row = db.execute("SELECT * FROM operations_faq_suggestions WHERE suggestion_id=?", (suggestion_id,)).fetchone()
        return self._suggestion(row)

    def community_health(self, window_hours: int = 24) -> CommunityHealth:
        since = (datetime.now(UTC) - timedelta(hours=window_hours)).isoformat()
        with self._connect() as db:
            rows = db.execute("SELECT text, category, decision, author_id FROM operations_messages WHERE timestamp>=?", (since,)).fetchall()
            first_seen = db.execute("SELECT author_id, MIN(timestamp) first_seen FROM operations_messages GROUP BY author_id").fetchall()
            open_suggestions = int(db.execute("SELECT COUNT(*) FROM operations_faq_suggestions WHERE status='open'").fetchone()[0])
        categories = [str(row["category"] or "") for row in rows]
        terms: dict[str, int] = {}
        for row in rows:
            # Numeric tokens are Discord/Telegram snowflake ids, never topics.
            for term in set(
                term
                for term in _fold_search_text(row["text"]).split()
                if len(term) >= 4 and not term.isdigit()
            ):
                terms[term] = terms.get(term, 0) + 1
        return CommunityHealth(window_hours=window_hours, messages_total=len(rows), spam_count=categories.count("spam"), toxic_count=sum(item in {"harassment", "hate", "violence"} for item in categories), risky_count=sum(str(row["decision"] or "allow") != "allow" for row in rows), unique_members=len({row["author_id"] for row in rows}), new_members=sum(str(row["first_seen"]) >= since for row in first_seen), top_topics=sorted(terms.items(), key=lambda item: (-item[1], item[0]))[:10], open_faq_suggestions=open_suggestions, generated_at=datetime.now(UTC))

    @staticmethod
    def _as_utc(value: object) -> datetime | None:
        """Rows written by different connectors mix naive and aware stamps."""
        try:
            stamp = datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None
        return stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)

    def activity_timeline(self, window_hours: int = 48, bucket_hours: int = 1) -> ActivityTimeline:
        """Scanned messages and violations bucketed into a fixed grid of slots.

        Empty slots are emitted too. A gap in the chart has to read as "nothing
        happened here", which only works if the slot exists with a zero.
        """
        bucket = timedelta(hours=bucket_hours)
        slots = max(1, math.ceil(window_hours / bucket_hours))

        # Align the newest slot to a bucket boundary so labels land on round hours.
        newest = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        newest -= timedelta(hours=newest.hour % bucket_hours)
        start = newest - bucket * (slots - 1)

        with self._connect() as db:
            rows = db.execute(
                "SELECT timestamp, COALESCE(decision,'allow') decision FROM operations_messages WHERE timestamp>=?",
                (start.isoformat(),),
            ).fetchall()

        scanned = [0] * slots
        violations = [0] * slots
        for row in rows:
            stamp = self._as_utc(row["timestamp"])
            if stamp is None:
                continue
            index = int((stamp - start) // bucket)
            if not 0 <= index < slots:
                continue
            scanned[index] += 1
            if str(row["decision"]) != "allow":
                violations[index] += 1

        return ActivityTimeline(
            window_hours=window_hours,
            bucket_hours=bucket_hours,
            scanned_total=sum(scanned),
            violations_total=sum(violations),
            buckets=[
                TimelineBucket(start=start + bucket * index, scanned=scanned[index], violations=violations[index])
                for index in range(slots)
            ],
            generated_at=datetime.now(UTC),
        )

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
    ) -> list[tuple[float, KnowledgeDocument]] | None:
        """Retrieve knowledge by opt-in OpenAI embeddings persisted in PostgreSQL pgvector."""
        if not self.settings.knowledge_embedding_enabled or not self.settings.openai_api_key:
            return None
        try:
            from openai import OpenAI
            import psycopg2
            import psycopg2.extras
            
            client = OpenAI(api_key=self.settings.openai_api_key)
            model = self.settings.openai_embedding_model
            
            query_response = client.embeddings.create(model=model, input=[question])
            query_vector = list(query_response.data[0].embedding)
            
            conn = psycopg2.connect(
                host=getattr(self.settings, "faq_pg_host", "localhost"),
                port=getattr(self.settings, "faq_pg_port", 5433),
                dbname=getattr(self.settings, "faq_pg_db", "faq_rag"),
                user=getattr(self.settings, "faq_pg_user", "faq_user"),
                password=getattr(self.settings, "faq_pg_password", "faq_pass_dev"),
            )
            
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                vector_str = "[" + ",".join(str(f) for f in query_vector) + "]"
                
                query = """
                    WITH ranked_chunks AS (
                        SELECT 
                            s.document_id,
                            1 - (e.embedding <=> %s::vector) AS similarity_score
                        FROM knowledge_section_embeddings e
                        JOIN knowledge_sections s ON e.chunk_id = s.chunk_id
                        ORDER BY e.embedding <=> %s::vector
                        LIMIT 50
                    ),
                    best_per_doc AS (
                        SELECT document_id, MAX(similarity_score) AS max_score
                        FROM ranked_chunks
                        GROUP BY document_id
                        ORDER BY max_score DESC
                        LIMIT %s
                    )
                    SELECT 
                        d.document_id, d.title, d.body, d.tags, d.dataset, d.active, d.updated_at,
                        b.max_score AS similarity_score
                    FROM best_per_doc b
                    JOIN knowledge_documents d ON b.document_id = d.document_id
                    ORDER BY b.max_score DESC;
                """
                cur.execute(query, (vector_str, vector_str, limit))
                rows = cur.fetchall()
                
            conn.close()
            
            scored = []
            for row in rows:
                score = row["similarity_score"]
                if score < self.settings.knowledge_embedding_min_score:
                    continue
                doc = KnowledgeDocument(
                    document_id=row["document_id"],
                    title=row["title"],
                    body=row["body"],
                    tags=row["tags"] if isinstance(row["tags"], list) else json.loads(row["tags"]),
                    dataset=row["dataset"],
                    active=row["active"],
                    updated_at=row["updated_at"]
                )
                scored.append((score, doc))
                
            if not scored:
                return []
            
            relevance_floor = max(self.settings.knowledge_embedding_min_score, scored[0][0] - 0.08)
            return [(score, document) for score, document in scored if score >= relevance_floor]
            
        except Exception:
            logger.warning("PostgreSQL pgvector retrieval unavailable; using deterministic fallback.", exc_info=True)
            return None

    def search_knowledge(self, question: str, limit: int = 3, dataset: str | None = None) -> list[KnowledgeDocument]:
        return [document for _score, document in self.search_knowledge_ranked(question, limit, dataset)]

    def search_knowledge_ranked(
        self,
        question: str,
        limit: int = 3,
        dataset: str | None = None,
    ) -> list[tuple[float, KnowledgeDocument]]:
        """Return vector-search candidates and normalized retrieval scores.

        Embeddings are opt-in; the deterministic local index is the fallback
        when an embedding provider is unavailable.
        """
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
        selected = [item for item in ranked[:limit] if item[0] >= relevance_floor]
        return [(min(1.0, score / best_score), doc) for score, _semantic_hits, doc in selected]

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
        return Incident(incident_id=row["incident_id"], platform=row["platform"], community_id=row["community_id"], channel_id=row["channel_id"], thread_key=row["thread_key"], status=row["status"], severity=row["severity"], risk_score=row["risk_score"], title=row["title"], summary=row["summary"], categories=json.loads(row["categories_json"]), message_ids=json.loads(row["message_ids_json"]), message_count=len(json.loads(row["message_ids_json"])), first_seen=datetime.fromisoformat(row["first_seen"]), last_seen=datetime.fromisoformat(row["last_seen"]), assigned_to=row["assigned_to"], created_at=datetime.fromisoformat(row["created_at"]), updated_at=datetime.fromisoformat(row["updated_at"]), source_url=row["source_url"])
