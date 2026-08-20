"""Supabase persistence for the multi-platform Community Operations Copilot.

SQLite remains available only when a test explicitly supplies a sqlite URL.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import sqlite3
import threading
import unicodedata
import uuid
import urllib.request
from collections import OrderedDict
import psycopg2
import psycopg2.extras
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.config import Settings, get_settings
from backend.services.database import json_value, postgres_connection, timestamp_value
from backend.services.question_intent import is_reusable_faq_question
from backend.models.operations import (
    FAQ,
    CommandContent,
    CommandContentRequest,
    CommonMessage,
    ActivityTimeline,
    CommunityHealth,
    FAQSuggestion,
    FAQTopic,
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


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(str(value) for value in vector) + "]"


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
    (
        ("cuoi tuan", "lich hoc", "su kien gi", "su kien nao", "su kien sap toi"),
        ("cuoi tuan", "lich hoc", "su kien sap toi", "upcoming event", "event schedule"),
        30,
    ),
    (("hoc bang du an", "project based learning", "pbl"), ("hoc bang du an", "project based learning", "pbl"), 30),
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
        self._openai_client: Any | None = None
        self._openai_client_lock = threading.Lock()
        self._embedding_cache: OrderedDict[str, tuple[str, tuple[float, ...]]] = OrderedDict()
        self._embedding_cache_lock = threading.Lock()
        self._knowledge_columns: set[str] | None = None
        self._knowledge_columns_lock = threading.Lock()
        url = settings.database_url
        # Runtime uses Supabase. An explicitly isolated SQLite path remains
        # available to unit tests without ever becoming a production fallback.
        runtime_sqlite_urls = {"sqlite:///./data/app.db", "sqlite:///./data/community_channel.db"}
        self.is_postgres = bool(settings.faq_pg_dsn) and url in runtime_sqlite_urls
        self.path: Path | None = None
        if not self.is_postgres:
            if not url.startswith("sqlite:///"):
                raise RuntimeError("FAQ_PG_DSN is required outside explicit SQLite tests.")
            self.path = Path(url.removeprefix("sqlite:///"))
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._create_tables()
        if not self.is_postgres or self.settings.operations_seed_defaults:
            self.seed_defaults()

    def _connect(self):
        if self.is_postgres:
            return postgres_connection(
                self.settings.faq_pg_dsn,
                self.settings.postgres_pool_min_size,
                self.settings.postgres_pool_max_size,
            )
        db = sqlite3.connect(self.path)  # type: ignore[arg-type]
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

    def _openai(self):
        if self._openai_client is None:
            with self._openai_client_lock:
                if self._openai_client is None:
                    from openai import OpenAI

                    self._openai_client = OpenAI(api_key=self.settings.openai_api_key)
        return self._openai_client

    def _provider_embedding(self, text: str, model: str) -> tuple[str, list[float]]:
        cache_size = self.settings.semantic_embedding_cache_size
        dimensions = self.settings.openai_embedding_dimensions
        key = f"{model}:{dimensions}\0{text.strip()}"
        if cache_size:
            with self._embedding_cache_lock:
                cached = self._embedding_cache.get(key)
                if cached is not None:
                    self._embedding_cache.move_to_end(key)
                    return cached[0], list(cached[1])

        request: dict[str, Any] = {"model": model, "input": [text]}
        if model.startswith("text-embedding-3"):
            request["dimensions"] = dimensions
        response = self._openai().embeddings.create(**request)
        vector = tuple(float(value) for value in response.data[0].embedding)
        if cache_size:
            with self._embedding_cache_lock:
                self._embedding_cache[key] = (model, vector)
                self._embedding_cache.move_to_end(key)
                while len(self._embedding_cache) > cache_size:
                    self._embedding_cache.popitem(last=False)
        return model, list(vector)

    def _create_tables(self) -> None:
        if self.is_postgres:
            migration = Path(__file__).parents[2] / "supabase" / "migrations" / "20260819_runtime_data_model.sql"
            with self._connect() as db:
                db.executescript(migration.read_text(encoding="utf-8"))
            return
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
                    """INSERT INTO operations_policies
                    (policy_id, name, description, category, action, trigger_terms_json, active, version, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [(pid, name, desc, cat, action, _json(terms), True, 1, _now()) for pid, name, desc, cat, action, terms in defaults],
                )
            if not self.is_postgres and not db.execute("SELECT 1 FROM operations_knowledge LIMIT 1").fetchone():
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
                db.executemany(
                    """INSERT INTO operations_faqs
                    (faq_id, question, answer, tags_json, active, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    [(faq_id, question, answer, _json(tags), True, _now()) for faq_id, question, answer, tags in faqs],
                )
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
                message_ids = list(json_value(winner["message_ids_json"], []))
                categories = list(json_value(winner["categories_json"], []))
                for duplicate in duplicates[1:]:
                    message_ids.extend(json_value(duplicate["message_ids_json"], []))
                    categories.extend(json_value(duplicate["categories_json"], []))
                    db.execute("UPDATE operations_messages SET incident_id=? WHERE incident_id=?", (winner["incident_id"], duplicate["incident_id"]))
                    db.execute("UPDATE operations_audit SET incident_id=? WHERE incident_id=?", (winner["incident_id"], duplicate["incident_id"]))
                    db.execute("DELETE FROM operations_incidents WHERE incident_id=?", (duplicate["incident_id"],))
                    merged += 1
                db.execute("UPDATE operations_incidents SET message_ids_json=?, categories_json=?, risk_score=?, updated_at=? WHERE incident_id=?", (_json(list(dict.fromkeys(message_ids))), _json(list(dict.fromkeys(categories))), max(row["risk_score"] for row in duplicates), _now(), winner["incident_id"]))
        return merged

    def _upsert_member(self, message: CommonMessage) -> str | None:
        if not self.is_postgres:
            return None
        member_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"p232:{message.platform}:{message.community_id}:{message.author_id}",
            )
        )
        with self._connect() as db:
            db.execute(
                """INSERT INTO community_members
                (member_id, platform, community_id, platform_user_id, display_name, first_seen_at, last_seen_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform, community_id, platform_user_id) DO UPDATE SET
                display_name=COALESCE(excluded.display_name, community_members.display_name),
                last_seen_at=excluded.last_seen_at""",
                (
                    member_id,
                    message.platform,
                    message.community_id,
                    message.author_id,
                    message.author_name,
                    message.timestamp.isoformat(),
                    message.timestamp.isoformat(),
                    _json({"source": message.platform}),
                ),
            )
        return member_id

    def save_message(self, message: CommonMessage, result: MessageDecision, incident_id: str | None) -> None:
        now = _now()
        author_member_id = self._upsert_member(message)
        with self._connect() as db:
            if self.is_postgres:
                db.execute(
                    """INSERT INTO operations_messages
                    (message_id, platform, community_id, channel_id, thread_key, parent_message_id, author_id,
                     author_member_id, text, timestamp, source_url, raw_json, decision, category, severity,
                     risk_score, confidence, explanation, model_used, incident_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(message_id) DO UPDATE SET decision=excluded.decision, category=excluded.category,
                    severity=excluded.severity, risk_score=excluded.risk_score, confidence=excluded.confidence,
                    explanation=excluded.explanation, model_used=excluded.model_used, incident_id=excluded.incident_id,
                    author_member_id=excluded.author_member_id, updated_at=excluded.updated_at""",
                    (
                        message.message_id, message.platform, message.community_id, message.channel_id,
                        message.thread_key, message.parent_message_id, message.author_id, author_member_id,
                        message.text, message.timestamp.isoformat(), message.source_url, _json(message.raw),
                        result.decision, result.category, result.severity, result.risk_score, result.confidence,
                        result.explanation, result.model_used, incident_id, now, now,
                    ),
                )
            else:
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
                [(f"GATE-{uuid.uuid4().hex[:10].upper()}", message.message_id, gate.gate, bool(gate.passed), gate.label,
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
                timestamp=timestamp_value(row["timestamp"]),
                source_url=row["source_url"],
                raw=json_value(row["raw_json"], {}),
            )
            for row in reversed(rows)
        ]
        return context

    def link_message_incident(self, message_id: str, incident_id: str) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE operations_messages SET incident_id=?, updated_at=? WHERE message_id=?",
                (incident_id, _now(), message_id),
            )

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
    def _local_moderation_embedding(text: str, dimensions: int = 1536) -> list[float]:
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
                return self._provider_embedding(text, model)
            except Exception:
                logger.warning("Moderation embedding provider unavailable; using local fallback.", exc_info=True)
        return local_model, self._local_moderation_embedding(text)

    def _semantic_embedding(self, text: str) -> tuple[str, list[float]]:
        model = self.settings.openai_embedding_model
        if self.settings.openai_api_key:
            try:
                return self._provider_embedding(text, model)
            except Exception:
                logger.warning("Semantic embedding provider unavailable; using deterministic fallback.", exc_info=True)
        return "local-hash-embedding-v1", self._local_moderation_embedding(text)

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
            created_at = timestamp_value(old["created_at"]).isoformat() if old else now
            db.execute(
                """INSERT INTO operations_moderation_marks
                (mark_id, incident_id, message_id, text, normalized_text, category, decision, reason,
                 marked_by, marked_at, source_url, active, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, TRUE, ?, ?, ?)
                ON CONFLICT(mark_id) DO UPDATE SET message_id=excluded.message_id, text=excluded.text,
                normalized_text=excluded.normalized_text, category=excluded.category,
                decision=excluded.decision, reason=excluded.reason, marked_by=excluded.marked_by,
                marked_at=excluded.marked_at, source_url=excluded.source_url, active=TRUE,
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
            if self.is_postgres:
                db.execute(
                    """INSERT INTO operations_moderation_embeddings
                    (mark_id, text_hash, model, vector_json, dimensions, embedding_version, updated_at)
                    VALUES (?, ?, ?, ?::vector, ?, 1, ?)
                    ON CONFLICT(mark_id) DO UPDATE SET text_hash=excluded.text_hash, model=excluded.model,
                    vector_json=excluded.vector_json, dimensions=excluded.dimensions,
                    embedding_version=excluded.embedding_version, updated_at=excluded.updated_at""",
                    (mark_id, self._embedding_hash(text), model, _vector_literal(vector), len(vector), now),
                )
            else:
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
        query_vectors: dict[str, list[float]] = {}
        if self.is_postgres:
            query_model, query_vector = self._moderation_embedding(text)
            query_vectors[query_model] = query_vector
            with self._connect() as db:
                rows = db.execute(
                    """SELECT m.*, e.model embedding_model, e.vector_json
                    FROM operations_moderation_marks m
                    JOIN operations_moderation_embeddings e ON e.mark_id=m.mark_id
                    WHERE m.active=TRUE AND m.category=? AND e.model=? AND e.dimensions=?
                    ORDER BY e.vector_json <=> ?::vector LIMIT ?""",
                    (
                        category,
                        query_model,
                        len(query_vector),
                        _vector_literal(query_vector),
                        self.settings.similar_case_limit,
                    ),
                ).fetchall()
        else:
            with self._connect() as db:
                rows = db.execute(
                    """SELECT m.*, e.model embedding_model, e.vector_json
                    FROM operations_moderation_marks m
                    JOIN operations_moderation_embeddings e ON e.mark_id=m.mark_id
                    WHERE m.active=TRUE AND m.category=? ORDER BY m.updated_at DESC LIMIT ?""",
                    (category, self.settings.similar_case_limit),
                ).fetchall()
        if not rows:
            return ModerationMemoryMatch(False, 0.0, True, False)
        matches: list[tuple[Any, Any]] = []
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
                marked_at=timestamp_value(row["marked_at"]),
                embedding=tuple(self._parse_vector(row["vector_json"])),
                source_url=row["source_url"],
                active=bool(row["active"]),
                version=int(row["version"]),
            )
            matches.append(
                (
                    ModerationMemoryIndex([mark], config).match(
                    text,
                    tuple(query_vectors[model]),
                    category=category,
                    ),
                    mark,
                )
            )
        best, best_mark = max(matches, key=lambda item: item[0].similarity)
        if best.matched:
            return best
        if (
            self.settings.moderation_memory_llm_verify_enabled
            and best.similarity >= self.settings.moderation_memory_llm_candidate_threshold
            and self._moderation_llm_equivalent(text, best_mark)
        ):
            timestamp = best_mark.marked_at.isoformat().replace("+00:00", "Z")
            return ModerationMemoryMatch(
                matched=True,
                similarity=best.similarity,
                send_to_admin=False,
                can_expand=True,
                banner=f"(Đã được đánh dấu: {best_mark.reason} bởi: {best_mark.marked_by} vào lúc: {timestamp})",
                mark=best_mark,
            )
        return best

    def _moderation_llm_equivalent(self, text: str, mark: Any) -> bool:
        if not self.settings.openai_api_key:
            return False
        prompt = (
            "So sánh hai tin nhắn moderation. Chỉ trả JSON {\"equivalent_case\": boolean}. "
            "True khi chúng có cùng ý định gây hại, cùng mục tiêu hành vi và có thể áp dụng chính xác "
            "quyết định Admin/Mod trước đó; false nếu chỉ chung từ khóa, là trích dẫn, đùa vô hại, "
            "hoặc khác mức độ/mục tiêu.\n"
            + json.dumps(
                {
                    "new_message": text,
                    "reviewed_message": mark.text,
                    "category": mark.category,
                    "reviewed_decision": mark.decision,
                    "reviewed_reason": mark.reason,
                },
                ensure_ascii=False,
            )
        )
        try:
            response = self._openai().chat.completions.create(
                model=self.settings.moderation_memory_llm_model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": prompt}],
            )
            payload = json.loads(response.choices[0].message.content or "{}")
            return bool(payload.get("equivalent_case"))
        except Exception:
            logger.warning("Moderation memory LLM verification unavailable.", exc_info=True)
            return False

    @staticmethod
    def _parse_vector(value: Any) -> list[float]:
        if isinstance(value, list):
            return [float(item) for item in value]
        text = str(value or "").strip().strip("[]")
        return [float(item) for item in text.split(",") if item.strip()]

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
        return [{**dict(row), "payload": json_value(row["payload_json"], {})} for row in rows]

    def list_policies(self) -> list[Policy]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM operations_policies ORDER BY policy_id").fetchall()
        return [Policy(policy_id=r["policy_id"], name=r["name"], description=r["description"], category=r["category"], action=r["action"], trigger_terms=json_value(r["trigger_terms_json"], []), active=bool(r["active"]), version=r["version"], updated_at=timestamp_value(r["updated_at"])) for r in rows]

    def upsert_policy(self, policy_id: str, request: PolicyUpsertRequest) -> Policy:
        now = _now()
        with self._connect() as db:
            old = db.execute("SELECT version FROM operations_policies WHERE policy_id=?", (policy_id,)).fetchone()
            version = int(old["version"]) + 1 if old else 1
            db.execute("""INSERT INTO operations_policies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(policy_id) DO UPDATE SET name=excluded.name, description=excluded.description, category=excluded.category, action=excluded.action, trigger_terms_json=excluded.trigger_terms_json, active=excluded.active, version=excluded.version, updated_at=excluded.updated_at""", (policy_id, request.name, request.description, request.category, request.action, _json(request.trigger_terms), bool(request.active), version, now))
        policy = next(item for item in self.list_policies() if item.policy_id == policy_id)
        if (
            self.is_postgres
            and self.settings.enable_policy_retrieval
            and self.settings.openai_api_key
        ):
            policy_text = "\n".join(
                [policy.name, policy.description, policy.category, *policy.trigger_terms]
            )
            model, vector = self._semantic_embedding(policy_text)
            with self._connect() as db:
                db.execute(
                    """INSERT INTO operations_policy_embeddings
                    (policy_id, text_hash, model, embedding, dimensions, embedding_version, updated_at)
                    VALUES (?, ?, ?, ?::vector, ?, 1, ?)
                    ON CONFLICT(policy_id) DO UPDATE SET text_hash=excluded.text_hash,
                    model=excluded.model, embedding=excluded.embedding,
                    dimensions=excluded.dimensions, embedding_version=excluded.embedding_version,
                    updated_at=excluded.updated_at""",
                    (
                        policy_id,
                        self._embedding_hash(policy_text),
                        model,
                        _vector_literal(vector),
                        len(vector),
                        now,
                    ),
                )
        return policy

    def retrieve_policy_candidates(self, text: str, limit: int = 3) -> list[tuple[float, Policy]]:
        """Return active policies nearest to a message in the current vector space."""
        if (
            not self.is_postgres
            or not self.settings.enable_policy_retrieval
            or not self.settings.openai_api_key
        ):
            return []
        model, vector = self._semantic_embedding(text)
        literal = _vector_literal(vector)
        with self._connect() as db:
            rows = db.execute(
                """SELECT p.*, 1 - (e.embedding <=> ?::vector) AS similarity
                FROM operations_policy_embeddings e
                JOIN operations_policies p ON p.policy_id=e.policy_id
                WHERE p.active=TRUE AND p.action<>'allow' AND e.model=? AND e.dimensions=?
                ORDER BY e.embedding <=> ?::vector LIMIT ?""",
                (literal, model, len(vector), literal, limit),
            ).fetchall()
        return [
            (
                float(row["similarity"]),
                Policy(
                    policy_id=row["policy_id"],
                    name=row["name"],
                    description=row["description"],
                    category=row["category"],
                    action=row["action"],
                    trigger_terms=json_value(row["trigger_terms_json"], []),
                    active=bool(row["active"]),
                    version=int(row["version"]),
                    updated_at=timestamp_value(row["updated_at"]),
                ),
            )
            for row in rows
        ]

    def delete_policy(self, policy_id: str) -> bool:
        with self._connect() as db:
            cursor = db.execute("DELETE FROM operations_policies WHERE policy_id=?", (policy_id,))
        return cursor.rowcount > 0

    def _list_knowledge_sqlite(self, dataset: str | None = None) -> list[KnowledgeDocument]:
        with self._connect() as db:
            if dataset:
                rows = db.execute(
                    "SELECT * FROM operations_knowledge WHERE dataset=? ORDER BY updated_at DESC",
                    (dataset,),
                ).fetchall()
            else:
                rows = db.execute("SELECT * FROM operations_knowledge ORDER BY updated_at DESC").fetchall()
        return [
            KnowledgeDocument(
                document_id=row["document_id"],
                title=row["title"],
                body=row["body"],
                tags=json_value(row["tags_json"], []),
                dataset=row["dataset"] or "general",
                active=bool(row["active"]),
                updated_at=timestamp_value(row["updated_at"]),
            )
            for row in rows
        ]

    @staticmethod
    def _postgres_knowledge(row: Any) -> KnowledgeDocument:
        values = dict(row)
        raw_tags = values.get("tags") or []
        if isinstance(raw_tags, str):
            try:
                raw_tags = json.loads(raw_tags)
            except json.JSONDecodeError:
                raw_tags = [tag.strip() for tag in raw_tags.split(",") if tag.strip()]
        return KnowledgeDocument(
            document_id=values["document_id"],
            title=values["title"],
            body=values["body"],
            tags=raw_tags if isinstance(raw_tags, list) else [],
            dataset=values.get("dataset") or "general",
            active=bool(values.get("active", True)),
            updated_at=values.get("updated_at") or datetime.now(timezone.utc),
        )

    def list_knowledge(self, dataset: str | None = None) -> list[KnowledgeDocument]:
        if not self.is_postgres:
            return self._list_knowledge_sqlite(dataset)

        try:
            if self._knowledge_columns is None:
                with self._knowledge_columns_lock:
                    if self._knowledge_columns is None:
                        with self._connect() as db:
                            rows = db.execute(
                                "SELECT column_name FROM information_schema.columns "
                                "WHERE table_schema='public' AND table_name='knowledge_documents'"
                            ).fetchall()
                        self._knowledge_columns = {str(row[0]) for row in rows}
            columns = self._knowledge_columns
            if not {"document_id", "title", "body"}.issubset(columns):
                raise ValueError("knowledge_documents is missing required columns")

            with self._connect() as db:
                selected = ["document_id", "title", "body"]
                selected.extend(name for name in ("tags", "dataset", "active", "updated_at") if name in columns)
                query = f"SELECT {', '.join(selected)} FROM knowledge_documents"
                params: tuple[object, ...] = ()
                if dataset and "dataset" in columns:
                    query += " WHERE dataset=?"
                    params = (dataset,)
                query += " ORDER BY updated_at DESC" if "updated_at" in columns else " ORDER BY document_id"
                rows = db.execute(query, params).fetchall()
            documents = [self._postgres_knowledge(row) for row in rows]
            if dataset and "dataset" not in columns and dataset != "general":
                return []
            return documents
        except Exception:
            logger.error("Supabase knowledge is unavailable; refusing stale local fallback.", exc_info=True)
            raise

    def upsert_knowledge(
        self,
        document_id: str,
        request: KnowledgeDocumentRequest,
        import_id: str | None = None,
        source_file: str | None = None,
    ) -> KnowledgeDocument:
        import psycopg2
        
        now = _now()
        
        # 1. Chunking
        chunks = []
        text = request.title + "\n\n" + request.body
        paragraphs = []
        for paragraph in (part.strip() for part in text.split("\n\n") if part.strip()):
            paragraphs.extend(paragraph[index:index + 1400] for index in range(0, len(paragraph), 1400))
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
            
        # 2. Embeddings are explicit. Documents and chunks are still stored
        # when the provider is disabled so lexical retrieval remains usable.
        embeddings: list[list[float] | None] = [None] * len(chunks)
        if self.settings.knowledge_embedding_enabled and self.settings.openai_api_key:
            request: dict[str, Any] = {
                "model": self.settings.openai_embedding_model,
                "input": chunks,
            }
            if self.settings.openai_embedding_model.startswith("text-embedding-3"):
                request["dimensions"] = self.settings.openai_embedding_dimensions
            response = self._openai().embeddings.create(**request)
            embeddings = [list(item.embedding) for item in response.data]
        
        # 3. Upsert into PostgreSQL
        try:
            conn = self._connect_pg()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO knowledge_documents
                    (document_id, title, body, tags, dataset, active, import_id, source_file,
                     content_hash, normalization_version, pipeline_version, updated_at, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, 'supabase-v1', %s, %s)
                    ON CONFLICT(document_id) DO UPDATE SET 
                        title=EXCLUDED.title, body=EXCLUDED.body, tags=EXCLUDED.tags, 
                        dataset=EXCLUDED.dataset, active=EXCLUDED.active,
                        import_id=COALESCE(EXCLUDED.import_id, knowledge_documents.import_id),
                        source_file=COALESCE(EXCLUDED.source_file, knowledge_documents.source_file),
                        content_hash=EXCLUDED.content_hash, pipeline_version=EXCLUDED.pipeline_version,
                        updated_at=EXCLUDED.updated_at
                """, (document_id, request.title, request.body, json.dumps(request.tags), request.dataset,
                        bool(request.active), import_id, source_file, self._embedding_hash(request.body), now, now))
                
                cur.execute("DELETE FROM knowledge_sections WHERE document_id=%s", (document_id,))
                
                for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
                    chunk_id = f"{document_id}-{i}"
                    cur.execute("""
                        INSERT INTO knowledge_sections (chunk_id, document_id, chunk_index, content, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (chunk_id, document_id, i, chunk_text, now))
                    
                    if embedding is not None:
                        vector_str = "[" + ",".join(str(f) for f in embedding) + "]"
                        cur.execute("""
                            INSERT INTO knowledge_section_embeddings
                            (chunk_id, embedding, model, text_hash, dimensions, embedding_version, updated_at)
                            VALUES (%s, %s::vector, %s, %s, %s, 1, %s)
                        """, (
                            chunk_id,
                            vector_str,
                            self.settings.openai_embedding_model,
                            self._embedding_hash(chunk_text),
                            len(embedding),
                            now,
                        ))
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
            platforms=json_value(row["platforms_json"], ["telegram", "discord"]),
            updated_at=timestamp_value(row["updated_at"]),
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
        return [MemberReport(report_id=row["report_id"], platform=row["platform"], reporter_id=row["reporter_id"], channel_id=row["channel_id"], details=row["details"], status=row["status"], created_at=timestamp_value(row["created_at"])) for row in rows]

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
            db.execute("INSERT INTO operations_notification_preferences (platform, member_id, daily_enabled, weekly_enabled, updated_at) VALUES (?, ?, ?, ?, ?) ON CONFLICT(platform, member_id) DO NOTHING", (platform, member_id, True, True, now))
            db.execute(f"UPDATE operations_notification_preferences SET {column}=?, updated_at=? WHERE platform=? AND member_id=?", (bool(enabled), now, platform, member_id))

    @staticmethod
    def _faq(row: sqlite3.Row) -> FAQ:
        return FAQ(faq_id=row["faq_id"], question=row["question"], answer=row["answer"], tags=json_value(row["tags_json"], []), active=bool(row["active"]), updated_at=timestamp_value(row["updated_at"]))

    @staticmethod
    def _similarity(left: str, right: str) -> float:
        left_terms, right_terms = set(_fold_search_text(left).split()), set(_fold_search_text(right).split())
        return len(left_terms & right_terms) / len(left_terms | right_terms) if left_terms and right_terms else 0.0

    def list_faqs(self, active_only: bool = False) -> list[FAQ]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM operations_faqs WHERE (?=FALSE OR active=TRUE) ORDER BY updated_at DESC", (bool(active_only),)).fetchall()
        return [self._faq(row) for row in rows]

    def find_faq(self, question: str, threshold: float = 0.72) -> FAQ | None:
        if self.is_postgres and self.settings.faq_semantic_clustering_enabled:
            try:
                model, vector = self._semantic_embedding(question)
                with self._connect() as db:
                    row = db.execute(
                        """SELECT f.*, 1 - (e.embedding <=> ?::vector) AS similarity
                        FROM operations_faq_embeddings e
                        JOIN operations_faqs f ON f.faq_id=e.faq_id
                        WHERE f.active=TRUE AND e.model=?
                        ORDER BY e.embedding <=> ?::vector LIMIT 1""",
                        (_vector_literal(vector), model, _vector_literal(vector)),
                    ).fetchone()
                if row and float(row["similarity"]) >= self.settings.faq_semantic_match_threshold:
                    return self._faq(row)
            except Exception:
                logger.warning("Semantic FAQ lookup failed; using lexical fallback.", exc_info=True)
        candidates = [(self._similarity(question, faq.question), faq) for faq in self.list_faqs(active_only=True)]
        best = max(candidates, default=(0.0, None), key=lambda item: item[0])
        return best[1] if best[0] >= threshold else None

    def upsert_faq(self, faq_id: str, request: FAQUpsertRequest, duplicate_threshold: float = 0.82) -> tuple[FAQ, list[FAQ]]:
        similar = [faq for faq in self.list_faqs(active_only=True) if faq.faq_id != faq_id and self._similarity(request.question, faq.question) >= duplicate_threshold]
        now = _now()
        with self._connect() as db:
            db.execute("""INSERT INTO operations_faqs
            (faq_id, question, answer, tags_json, active, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(faq_id) DO UPDATE SET question=excluded.question, answer=excluded.answer,
            tags_json=excluded.tags_json, active=excluded.active, updated_at=excluded.updated_at""",
            (faq_id, request.question, request.answer, _json(request.tags), bool(request.active), now))
        if self.is_postgres:
            model, vector = self._semantic_embedding(request.question)
            with self._connect() as db:
                db.execute(
                    """INSERT INTO operations_faq_embeddings
                    (faq_id, text_hash, model, embedding, dimensions, embedding_version, updated_at)
                    VALUES (?, ?, ?, ?::vector, ?, 1, ?)
                    ON CONFLICT(faq_id) DO UPDATE SET text_hash=excluded.text_hash, model=excluded.model,
                    embedding=excluded.embedding, dimensions=excluded.dimensions,
                    embedding_version=excluded.embedding_version, updated_at=excluded.updated_at""",
                    (faq_id, self._embedding_hash(request.question), model, _vector_literal(vector), len(vector), now),
                )
        return next(faq for faq in self.list_faqs() if faq.faq_id == faq_id), similar

    def delete_faq(self, faq_id: str) -> bool:
        with self._connect() as db:
            cursor = db.execute("DELETE FROM operations_faqs WHERE faq_id=?", (faq_id,))
        return cursor.rowcount > 0

    def record_unanswered_question(self, message: CommonMessage, minimum_questions: int = 3) -> FAQSuggestion | None:
        if not is_reusable_faq_question(message.text):
            return None
        if self.is_postgres:
            return self.record_member_question(message, minimum_questions)
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
                samples = list(dict.fromkeys([*json_value(match["samples_json"], []), message.text]))[-5:]
                count = int(match["question_count"]) + 1
                db.execute("UPDATE operations_faq_suggestions SET question_count=?, samples_json=?, updated_at=? WHERE suggestion_id=?", (count, _json(samples), now, match["suggestion_id"]))
                row = db.execute("SELECT * FROM operations_faq_suggestions WHERE suggestion_id=?", (match["suggestion_id"],)).fetchone()
            else:
                suggestion_id = f"FAQS-{uuid.uuid4().hex[:10].upper()}"
                db.execute("INSERT INTO operations_faq_suggestions VALUES (?, ?, ?, ?, ?, 'open', ?, ?)", (suggestion_id, message.text[:500], normalized, 1, _json([message.text]), now, now))
                row = db.execute("SELECT * FROM operations_faq_suggestions WHERE suggestion_id=?", (suggestion_id,)).fetchone()
        suggestion = self._suggestion(row)
        return suggestion if suggestion.question_count >= minimum_questions else None

    def record_member_question(
        self,
        message: CommonMessage,
        minimum_questions: int = 3,
        *,
        outcome_stage: str = "unanswered",
    ) -> FAQSuggestion | None:
        """Persist only reusable questions that did not match an approved FAQ."""
        if not is_reusable_faq_question(message.text):
            return None
        if not self.is_postgres:
            return self.record_unanswered_question(message, minimum_questions)
        normalized = _fold_search_text(message.text)
        if not normalized:
            return None
        question_id = f"FQQ-{uuid.uuid4().hex[:12].upper()}"
        now = _now()
        with self._connect() as db:
            row = db.execute(
                """INSERT INTO operations_faq_questions
                (question_id, message_id, question, normalized_question, platform, community_id,
                 channel_id, author_id, outcome_stage, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_id) DO UPDATE SET outcome_stage=excluded.outcome_stage
                RETURNING question_id""",
                (
                    question_id,
                    message.message_id,
                    message.text[:2000],
                    normalized,
                    message.platform,
                    message.community_id,
                    message.channel_id,
                    message.author_id,
                    outcome_stage[:30],
                    now,
                ),
            ).fetchone()
            if row is None:
                existing = db.execute(
                    "SELECT question_id FROM operations_faq_questions WHERE message_id=?",
                    (message.message_id,),
                ).fetchone()
                return self._suggestion_for_question(existing["question_id"]) if existing else None
            question_id = str(row["question_id"])

        model, vector = self._semantic_embedding(message.text)
        with self._connect() as db:
            db.execute(
                """INSERT INTO faq_question_embeddings
                (question_id, text_hash, model, embedding, dimensions, embedding_version, created_at)
                VALUES (?, ?, ?, ?::vector, ?, 1, ?)
                ON CONFLICT(question_id) DO UPDATE SET text_hash=excluded.text_hash,
                model=excluded.model, embedding=excluded.embedding,
                dimensions=excluded.dimensions, embedding_version=excluded.embedding_version""",
                (question_id, self._embedding_hash(message.text), model, _vector_literal(vector), len(vector), now),
            )
        cluster_id = self._cluster_member_question(question_id, message.text, normalized, model, vector)
        suggestion = self._suggestion_for_cluster(cluster_id)
        return suggestion if suggestion and suggestion.question_count >= minimum_questions else None

    def _faq_llm_decision(
        self,
        question: str,
        candidate_label: str | None = None,
        candidate_samples: list[str] | None = None,
    ) -> tuple[bool, str]:
        """Verify intent equivalence and produce one concise Vietnamese topic label."""
        fallback_label = question.strip()[:500]
        if not self.settings.openai_api_key:
            return False, fallback_label
        payload = {
            "question": question,
            "candidate_topic": candidate_label,
            "candidate_examples": candidate_samples or [],
        }
        prompt = (
            "Phân tích ý định câu hỏi của thành viên. Trả JSON có đúng hai trường: "
            "same_intent (boolean) và topic_label (một câu tiếng Việt ngắn mô tả nội dung chung, "
            "không trả lời câu hỏi). same_intent chỉ true khi câu mới và candidate thực sự cần cùng một câu trả lời FAQ.\n"
            + json.dumps(payload, ensure_ascii=False)
        )
        try:
            response = self._openai().chat.completions.create(
                model=self.settings.faq_clustering_model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": prompt}],
            )
            data = json.loads(response.choices[0].message.content or "{}")
            label = str(data.get("topic_label") or fallback_label).strip()[:500]
            return bool(data.get("same_intent")) if candidate_label else False, label
        except Exception:
            logger.warning("FAQ intent LLM unavailable; using embedding-only clustering.", exc_info=True)
            return False, fallback_label

    def _cluster_member_question(
        self,
        question_id: str,
        question: str,
        normalized: str,
        model: str,
        vector: list[float],
    ) -> str:
        vector_literal = _vector_literal(vector)
        with self._connect() as db:
            candidates = db.execute(
                """SELECT *, 1 - (centroid_embedding <=> ?::vector) AS similarity
                FROM faq_topic_clusters WHERE status='open' AND embedding_model=?
                ORDER BY centroid_embedding <=> ?::vector LIMIT 5""",
                (vector_literal, model, vector_literal),
            ).fetchall()

        selected = None
        llm_verified = False
        topic_label = question.strip()[:500]
        for candidate in candidates:
            score = float(candidate["similarity"])
            if score >= self.settings.faq_cluster_auto_merge_threshold:
                selected = candidate
                topic_label = str(candidate["topic_label"])
                break
            if score >= self.settings.faq_cluster_candidate_threshold:
                same_intent, label = self._faq_llm_decision(
                    question,
                    str(candidate["topic_label"]),
                    json_value(candidate["sample_questions"], []),
                )
                if same_intent:
                    selected = candidate
                    llm_verified = True
                    topic_label = label
                    break

        now = _now()
        if selected is None:
            _same, topic_label = self._faq_llm_decision(question)
            cluster_id = f"FAQC-{uuid.uuid4().hex[:10].upper()}"
            with self._connect() as db:
                db.execute(
                    """INSERT INTO faq_topic_clusters
                    (cluster_id, topic_label, normalized_label, representative_question, question_count,
                     sample_questions, centroid_embedding, embedding_model, embedding_dimensions,
                     embedding_version, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 1, ?, ?::vector, ?, ?, 1, 'open', ?, ?)""",
                    (
                        cluster_id,
                        topic_label,
                        _fold_search_text(topic_label),
                        question[:500],
                        _json([question]),
                        vector_literal,
                        model,
                        len(vector),
                        now,
                        now,
                    ),
                )
        else:
            cluster_id = str(selected["cluster_id"])
            old_count = int(selected["question_count"])
            old_vector = self._parse_vector(selected["centroid_embedding"])
            centroid = [
                ((old_vector[index] * old_count) + vector[index]) / (old_count + 1)
                for index in range(min(len(old_vector), len(vector)))
            ]
            samples = list(dict.fromkeys([*json_value(selected["sample_questions"], []), question]))[-10:]
            with self._connect() as db:
                db.execute(
                    """UPDATE faq_topic_clusters SET topic_label=?, normalized_label=?,
                    question_count=question_count+1, sample_questions=?, centroid_embedding=?::vector,
                    updated_at=? WHERE cluster_id=?""",
                    (topic_label, _fold_search_text(topic_label), _json(samples), _vector_literal(centroid), now, cluster_id),
                )

        similarity = 1.0 if selected is None else float(selected["similarity"])
        with self._connect() as db:
            db.execute(
                """INSERT INTO faq_topic_members
                (cluster_id, question_id, similarity_score, llm_verified, created_at)
                VALUES (?, ?, ?, ?, ?) ON CONFLICT(cluster_id, question_id) DO NOTHING""",
                (cluster_id, question_id, similarity, llm_verified, now),
            )
            cluster = db.execute("SELECT * FROM faq_topic_clusters WHERE cluster_id=?", (cluster_id,)).fetchone()
            db.execute(
                """INSERT INTO operations_faq_suggestions
                (suggestion_id, representative_question, normalized_question, question_count,
                 samples_json, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(suggestion_id) DO UPDATE SET representative_question=excluded.representative_question,
                normalized_question=excluded.normalized_question, question_count=excluded.question_count,
                samples_json=excluded.samples_json, status=excluded.status, updated_at=excluded.updated_at""",
                (
                    cluster_id,
                    cluster["representative_question"],
                    cluster["normalized_label"],
                    cluster["question_count"],
                    _json(json_value(cluster["sample_questions"], [])),
                    cluster["status"],
                    cluster["created_at"],
                    cluster["updated_at"],
                ),
            )
        return cluster_id

    def _suggestion_for_question(self, question_id: str) -> FAQSuggestion | None:
        with self._connect() as db:
            row = db.execute(
                """SELECT c.* FROM faq_topic_clusters c
                JOIN faq_topic_members m ON m.cluster_id=c.cluster_id
                WHERE m.question_id=? ORDER BY m.created_at DESC LIMIT 1""",
                (question_id,),
            ).fetchone()
        return self._cluster_suggestion(row) if row else None

    def _suggestion_for_cluster(self, cluster_id: str) -> FAQSuggestion | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM faq_topic_clusters WHERE cluster_id=?", (cluster_id,)).fetchone()
        return self._cluster_suggestion(row) if row else None

    @staticmethod
    def _cluster_suggestion(row: Any) -> FAQSuggestion:
        return FAQSuggestion(
            suggestion_id=row["cluster_id"],
            representative_question=row["representative_question"],
            question_count=int(row["question_count"]),
            status=row["status"],
            sample_questions=json_value(row["sample_questions"], []),
            created_at=timestamp_value(row["created_at"]),
            updated_at=timestamp_value(row["updated_at"]),
        )

    @staticmethod
    def _suggestion(row: sqlite3.Row) -> FAQSuggestion:
        return FAQSuggestion(suggestion_id=row["suggestion_id"], representative_question=row["representative_question"], question_count=row["question_count"], status=row["status"], sample_questions=json_value(row["samples_json"], []), created_at=timestamp_value(row["created_at"]), updated_at=timestamp_value(row["updated_at"]))

    def list_faq_suggestions(self, status: str = "open") -> list[FAQSuggestion]:
        if self.is_postgres:
            clauses = "WHERE status=?" if status else ""
            parameters: tuple[object, ...] = (status,) if status else ()
            with self._connect() as db:
                rows = db.execute(
                    f"SELECT * FROM faq_topic_clusters {clauses} ORDER BY question_count DESC, updated_at DESC",
                    parameters,
                ).fetchall()
            return [self._cluster_suggestion(row) for row in rows]
        with self._connect() as db:
            rows = db.execute("SELECT * FROM operations_faq_suggestions WHERE (?='' OR status=?) ORDER BY question_count DESC, updated_at DESC", (status, status)).fetchall()
        return [self._suggestion(row) for row in rows]

    def set_faq_suggestion_status(self, suggestion_id: str, status: str) -> FAQSuggestion | None:
        if self.is_postgres:
            with self._connect() as db:
                cursor = db.execute(
                    "UPDATE faq_topic_clusters SET status=?, updated_at=? WHERE cluster_id=?",
                    (status, _now(), suggestion_id),
                )
                if not cursor.rowcount:
                    return None
                db.execute(
                    "UPDATE operations_faq_suggestions SET status=?, updated_at=? WHERE suggestion_id=?",
                    (status, _now(), suggestion_id),
                )
                row = db.execute("SELECT * FROM faq_topic_clusters WHERE cluster_id=?", (suggestion_id,)).fetchone()
            return self._cluster_suggestion(row)
        with self._connect() as db:
            cursor = db.execute("UPDATE operations_faq_suggestions SET status=?, updated_at=? WHERE suggestion_id=?", (status, _now(), suggestion_id))
            if not cursor.rowcount:
                return None
            row = db.execute("SELECT * FROM operations_faq_suggestions WHERE suggestion_id=?", (suggestion_id,)).fetchone()
        return self._suggestion(row)

    def link_faq_topic(self, cluster_id: str, faq_id: str) -> None:
        if not self.is_postgres:
            return
        with self._connect() as db:
            db.execute(
                "UPDATE faq_topic_clusters SET approved_faq_id=?, status='approved', updated_at=? WHERE cluster_id=?",
                (faq_id, _now(), cluster_id),
            )
            db.execute(
                "UPDATE operations_faqs SET source_cluster_id=?, updated_at=? WHERE faq_id=?",
                (cluster_id, _now(), faq_id),
            )

    def list_faq_top_topics(self, limit: int = 10) -> list[FAQTopic]:
        if not self.is_postgres:
            return [
                FAQTopic(
                    cluster_id=item.suggestion_id,
                    topic_label=item.representative_question,
                    representative_question=item.representative_question,
                    question_count=item.question_count,
                    sample_questions=item.sample_questions,
                    status=item.status,
                    updated_at=item.updated_at,
                )
                for item in self.list_faq_suggestions("open")[:limit]
            ]
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM faq_top_10_topics LIMIT ?",
                (min(limit, self.settings.faq_top_limit),),
            ).fetchall()
        return [
            FAQTopic(
                cluster_id=row["cluster_id"],
                topic_label=row["topic_label"],
                representative_question=row["representative_question"],
                question_count=int(row["question_count"]),
                sample_questions=json_value(row["sample_questions"], []),
                status=row["status"],
                approved_faq_id=row["approved_faq_id"],
                updated_at=timestamp_value(row["updated_at"]),
            )
            for row in rows
        ]

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

    def record_import(self, response: KnowledgeImportResponse, source_hash: str | None = None, status: str = "completed") -> KnowledgeImportResponse:
        with self._connect() as db:
            if not self.is_postgres:
                db.execute(
                    "INSERT INTO operations_knowledge_imports VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (response.import_id, response.filename, response.format, response.target, response.normalized_count,
                     response.skipped_count, _json(response.warnings), response.normalized_by, response.created_at.isoformat()),
                )
                return response
            db.execute(
                """INSERT INTO operations_knowledge_imports
                (import_id, filename, format, target, normalized_count, skipped_count,
                 warnings_json, normalized_by, source_hash, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(import_id) DO UPDATE SET normalized_count=excluded.normalized_count,
                skipped_count=excluded.skipped_count, warnings_json=excluded.warnings_json,
                normalized_by=excluded.normalized_by,
                source_hash=COALESCE(excluded.source_hash, operations_knowledge_imports.source_hash),
                status=excluded.status, created_at=excluded.created_at""",
                (response.import_id, response.filename, response.format, response.target, response.normalized_count,
                 response.skipped_count, _json(response.warnings), response.normalized_by,
                 source_hash, status, response.created_at.isoformat()),
            )
        return response

    def archive_import(self, import_id: str, filename: str, content: bytes, content_type: str | None = None) -> None:
        if not self.is_postgres:
            return
        digest = hashlib.sha256(content).hexdigest()
        with self._connect() as db:
            db.execute(
                """INSERT INTO knowledge_import_raw
                (import_id, filename, content_type, source_hash, content, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(import_id) DO UPDATE SET filename=excluded.filename,
                content_type=excluded.content_type, source_hash=excluded.source_hash, content=excluded.content""",
                (import_id, filename, content_type, digest, psycopg2.Binary(content), _now()),
            )

    def record_normalized_item(
        self,
        import_id: str,
        record_index: int,
        record_type: str,
        item: dict[str, object],
        document_id: str | None = None,
        policy_id: str | None = None,
    ) -> None:
        if not self.is_postgres:
            return
        with self._connect() as db:
            db.execute(
                """INSERT INTO knowledge_normalized_records
                (import_id, record_index, record_type, document_id, policy_id, canonical_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(import_id, record_index) DO UPDATE SET record_type=excluded.record_type,
                document_id=excluded.document_id, policy_id=excluded.policy_id,
                canonical_json=excluded.canonical_json""",
                (import_id, record_index, record_type, document_id, policy_id, _json(item), _now()),
            )

    def list_imports(self) -> list[KnowledgeImportRecord]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM operations_knowledge_imports ORDER BY created_at DESC LIMIT 50").fetchall()
        return [KnowledgeImportRecord(import_id=row["import_id"], filename=row["filename"], format=row["format"], target=row["target"], normalized_count=row["normalized_count"], skipped_count=row["skipped_count"], warnings=json_value(row["warnings_json"], []), normalized_by=row["normalized_by"], created_at=timestamp_value(row["created_at"])) for row in rows]

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
            model = self.settings.openai_embedding_model
            _model, query_vector = self._provider_embedding(question, model)
            vector_str = _vector_literal(query_vector)

            with self._connect() as db:
                query = """
                    WITH ranked_chunks AS (
                        SELECT 
                            s.document_id,
                            1 - (e.embedding <=> ?::vector) AS similarity_score
                        FROM knowledge_section_embeddings e
                        JOIN knowledge_sections s ON e.chunk_id = s.chunk_id
                        WHERE e.model=? AND e.dimensions=?
                        ORDER BY e.embedding <=> ?::vector
                        LIMIT 50
                    ),
                    best_per_doc AS (
                        SELECT document_id, MAX(similarity_score) AS max_score
                        FROM ranked_chunks
                        GROUP BY document_id
                        ORDER BY max_score DESC
                        LIMIT ?
                    )
                    SELECT 
                        d.document_id, d.title, d.body, d.tags, d.dataset, d.active, d.updated_at,
                        b.max_score AS similarity_score
                    FROM best_per_doc b
                    JOIN knowledge_documents d ON b.document_id = d.document_id
                    WHERE d.active=TRUE
                    ORDER BY b.max_score DESC;
                """
                rows = db.execute(
                    query,
                    (
                        vector_str,
                        model,
                        len(query_vector),
                        vector_str,
                        limit,
                    ),
                ).fetchall()
            
            scored = []
            for row in rows:
                score = row["similarity_score"]
                if score < self.settings.knowledge_embedding_min_score:
                    continue
                doc = KnowledgeDocument(
                    document_id=row["document_id"],
                    title=row["title"],
                    body=row["body"],
                    tags=row["tags"] if isinstance(row["tags"], list) else json_value(row["tags"], []),
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
            "khong", "hoc", "dang", "tham", "gia", "nay", "thi", "bang", "phuong", "phap",
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
            # A fallback candidate must contain topic evidence, not merely a
            # generic word shared with unrelated documents. This prevents a
            # question such as "cuối tuần có sự kiện gì không" from selecting
            # an arbitrary learning document when no event source exists.
            has_specific_evidence = (
                title_matches > 0
                or phrase_matches >= 2
                or content_matches >= 3
                or semantic_hits > 0
            )
            if not has_specific_evidence:
                score = 0
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
        if not ranked or ranked[0][0] < 3:
            return []
        best_score = ranked[0][0]
        relevance_floor = max(3, best_score * 0.35)
        selected = [item for item in ranked[:limit] if item[0] >= relevance_floor]
        # Keep an absolute confidence signal. Normalizing by best_score made
        # every weak query look like a perfect retrieval match.
        return [(min(0.95, score / (score + 2.0)), doc) for score, _semantic_hits, doc in selected]

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
        message_ids = json_value(row["message_ids_json"], [])
        return Incident(incident_id=row["incident_id"], platform=row["platform"], community_id=row["community_id"], channel_id=row["channel_id"], thread_key=row["thread_key"], status=row["status"], severity=row["severity"], risk_score=row["risk_score"], title=row["title"], summary=row["summary"], categories=json_value(row["categories_json"], []), message_ids=message_ids, message_count=len(message_ids), first_seen=timestamp_value(row["first_seen"]), last_seen=timestamp_value(row["last_seen"]), assigned_to=row["assigned_to"], created_at=timestamp_value(row["created_at"]), updated_at=timestamp_value(row["updated_at"]), source_url=row["source_url"])
