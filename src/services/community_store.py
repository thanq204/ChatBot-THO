"""SQLite persistence for conversation radar, interventions, feedback and snapshots."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.config import Settings, get_settings
from src.models.community import (
    AdminInterventionRequest,
    CommunityHealth,
    ConversationAnalysis,
    ConversationMessage,
    ConversationThread,
    InterventionRecommendation,
    MediationSummary,
    SimilarCase,
)


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


class CommunityStore:
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
                CREATE TABLE IF NOT EXISTS conversations (
                    thread_id TEXT PRIMARY KEY, platform TEXT NOT NULL, community_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL, video_id TEXT, video_title TEXT, content_url TEXT,
                    source_mode TEXT NOT NULL, action_mode TEXT NOT NULL, imported_at TEXT NOT NULL,
                    expires_at TEXT, last_analyzed_at TEXT, conversation_stage TEXT, escalation_score REAL,
                    urgency TEXT, category TEXT, risk_level TEXT, main_topic TEXT, conflict_summary TEXT, root_causes TEXT NOT NULL DEFAULT '[]',
                    triggers TEXT NOT NULL DEFAULT '[]', participants TEXT NOT NULL DEFAULT '[]',
                    tone_trend TEXT, needs_intervention INTEGER NOT NULL DEFAULT 0,
                    recommended_intervention TEXT, confidence REAL, model_used TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    message_id TEXT PRIMARY KEY, thread_id TEXT NOT NULL, parent_message_id TEXT,
                    author_id TEXT NOT NULL, text TEXT NOT NULL, timestamp TEXT NOT NULL,
                    platform_status TEXT NOT NULL DEFAULT 'published', like_count INTEGER NOT NULL DEFAULT 0,
                    source_url TEXT, is_trigger INTEGER NOT NULL DEFAULT 0,
                    moderation_category TEXT, moderation_risk_level TEXT, moderation_action TEXT,
                    FOREIGN KEY(thread_id) REFERENCES conversations(thread_id)
                );
                CREATE INDEX IF NOT EXISTS idx_conversations_stage ON conversations(conversation_stage);
                CREATE INDEX IF NOT EXISTS idx_conversations_score ON conversations(escalation_score DESC);
                CREATE TABLE IF NOT EXISTS interventions (
                    intervention_id TEXT PRIMARY KEY, thread_id TEXT NOT NULL, recommended_action TEXT NOT NULL,
                    reason TEXT NOT NULL, target_users TEXT NOT NULL DEFAULT '[]', draft_message TEXT NOT NULL DEFAULT '',
                    expected_outcome TEXT NOT NULL, urgency TEXT NOT NULL, requires_admin_approval INTEGER NOT NULL DEFAULT 1,
                    internal_action TEXT, youtube_action TEXT, supported INTEGER NOT NULL DEFAULT 1,
                    support_reason TEXT, model_used TEXT NOT NULL, admin_selected_action TEXT,
                    admin_edited_message TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'recommended',
                    action_mode TEXT NOT NULL DEFAULT 'simulated', youtube_write_performed INTEGER NOT NULL DEFAULT 0,
                    youtube_reply_id TEXT, reviewer TEXT, admin_note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL, reviewed_at TEXT,
                    FOREIGN KEY(thread_id) REFERENCES conversations(thread_id)
                );
                CREATE TABLE IF NOT EXISTS mediation_sessions (
                    session_id TEXT PRIMARY KEY, thread_id TEXT NOT NULL, side_a_position TEXT NOT NULL,
                    side_b_position TEXT NOT NULL, common_ground TEXT NOT NULL DEFAULT '[]',
                    core_disagreement TEXT NOT NULL DEFAULT '[]', harmful_patterns TEXT NOT NULL DEFAULT '[]',
                    recommended_next_steps TEXT NOT NULL DEFAULT '[]', admin_editable_draft TEXT NOT NULL,
                    original_ai_draft TEXT NOT NULL, admin_edited_draft TEXT, status TEXT NOT NULL DEFAULT 'draft',
                    model_used TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    FOREIGN KEY(thread_id) REFERENCES conversations(thread_id)
                );
                CREATE TABLE IF NOT EXISTS admin_feedback (
                    feedback_id TEXT PRIMARY KEY, thread_id TEXT NOT NULL, intervention_id TEXT,
                    original_ai_stage TEXT, original_escalation_score REAL, original_recommendation TEXT,
                    admin_selected_action TEXT, admin_edited_message TEXT NOT NULL DEFAULT '',
                    admin_agreed_with_ai INTEGER, resolution_status TEXT NOT NULL DEFAULT 'unknown',
                    outcome_after_intervention TEXT NOT NULL DEFAULT 'unknown', after_intervention_score REAL,
                    admin_note TEXT NOT NULL DEFAULT '', classification_decision TEXT NOT NULL DEFAULT 'accept_ai',
                    admin_category TEXT, admin_risk_level TEXT, admin_conversation_stage TEXT,
                    similar_case_ids TEXT NOT NULL DEFAULT '[]', action_mode TEXT NOT NULL DEFAULT 'simulated',
                    created_at TEXT NOT NULL, reviewed_at TEXT,
                    FOREIGN KEY(thread_id) REFERENCES conversations(thread_id)
                );
                CREATE INDEX IF NOT EXISTS idx_feedback_stage ON admin_feedback(original_ai_stage);
                CREATE TABLE IF NOT EXISTS youtube_videos (
                    video_id TEXT PRIMARY KEY, title TEXT NOT NULL, channel_id TEXT, channel_title TEXT,
                    published_at TEXT, imported_at TEXT NOT NULL, last_synced_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS youtube_comment_threads (
                    youtube_thread_id TEXT PRIMARY KEY, video_id TEXT NOT NULL, top_level_comment_id TEXT NOT NULL,
                    total_reply_count INTEGER NOT NULL DEFAULT 0, created_at TEXT, updated_at TEXT,
                    imported_at TEXT NOT NULL, last_synced_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS youtube_comments (
                    youtube_comment_id TEXT PRIMARY KEY, youtube_thread_id TEXT NOT NULL, parent_comment_id TEXT,
                    anonymized_author_id TEXT NOT NULL, display_name TEXT, text TEXT NOT NULL,
                    like_count INTEGER NOT NULL DEFAULT 0, published_at TEXT NOT NULL, updated_at TEXT,
                    moderation_status TEXT, video_id TEXT NOT NULL, source_url TEXT, last_synced_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS youtube_connections (
                    id INTEGER PRIMARY KEY CHECK (id = 1), channel_id TEXT, channel_title TEXT,
                    encrypted_access_token TEXT, encrypted_refresh_token TEXT, token_expiry TEXT,
                    scopes TEXT NOT NULL DEFAULT '', connected_at TEXT, last_sync_at TEXT, status TEXT NOT NULL
                );
                """
            )
            columns = {row["name"] for row in db.execute("PRAGMA table_info(admin_feedback)").fetchall()}
            if "after_intervention_score" not in columns:
                db.execute("ALTER TABLE admin_feedback ADD COLUMN after_intervention_score REAL")
            for column, definition in (
                ("classification_decision", "TEXT NOT NULL DEFAULT 'accept_ai'"),
                ("admin_category", "TEXT"),
                ("admin_risk_level", "TEXT"),
                ("admin_conversation_stage", "TEXT"),
            ):
                if column not in columns:
                    db.execute(f"ALTER TABLE admin_feedback ADD COLUMN {column} {definition}")
            conversation_columns = {row["name"] for row in db.execute("PRAGMA table_info(conversations)").fetchall()}
            if "category" not in conversation_columns:
                db.execute("ALTER TABLE conversations ADD COLUMN category TEXT")
            if "risk_level" not in conversation_columns:
                db.execute("ALTER TABLE conversations ADD COLUMN risk_level TEXT")

    def upsert_thread(self, thread: ConversationThread) -> ConversationThread:
        analysis = thread.analysis
        created = thread.imported_at.isoformat()
        updated = now_iso()
        with self._connect() as db:
            db.execute(
                """INSERT INTO conversations
                (thread_id, platform, community_id, channel_id, video_id, video_title, content_url,
                 source_mode, action_mode, imported_at, expires_at, last_analyzed_at, conversation_stage,
                 escalation_score, urgency, category, risk_level, main_topic, conflict_summary, root_causes, triggers, participants,
                 tone_trend, needs_intervention, recommended_intervention, confidence, model_used, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(thread_id) DO UPDATE SET
                 video_title=excluded.video_title, content_url=excluded.content_url,
                 source_mode=excluded.source_mode, action_mode=excluded.action_mode,
                 expires_at=excluded.expires_at, last_analyzed_at=excluded.last_analyzed_at,
                 conversation_stage=excluded.conversation_stage, escalation_score=excluded.escalation_score,
                 urgency=excluded.urgency, category=excluded.category, risk_level=excluded.risk_level,
                 main_topic=excluded.main_topic, conflict_summary=excluded.conflict_summary,
                 root_causes=excluded.root_causes, triggers=excluded.triggers, participants=excluded.participants,
                 tone_trend=excluded.tone_trend, needs_intervention=excluded.needs_intervention,
                 recommended_intervention=excluded.recommended_intervention, confidence=excluded.confidence,
                 model_used=excluded.model_used, updated_at=excluded.updated_at""",
                (
                    thread.thread_id, thread.platform, thread.community_id, thread.channel_id, thread.video_id,
                    thread.video_title, thread.content_url, thread.source_mode, thread.action_mode, created,
                    thread.expires_at.isoformat() if thread.expires_at else None,
                    thread.last_analyzed_at.isoformat() if thread.last_analyzed_at else None,
                    analysis.conversation_stage if analysis else None, analysis.escalation_score if analysis else None,
                    analysis.urgency if analysis else None, analysis.category if analysis else None,
                    analysis.risk_level if analysis else None, analysis.main_topic if analysis else None,
                    analysis.conflict_summary if analysis else None, dumps(analysis.root_causes if analysis else []),
                    dumps([item.model_dump() for item in analysis.triggers] if analysis else []),
                    dumps(analysis.participants_in_conflict if analysis else []), analysis.tone_trend if analysis else None,
                    int(analysis.needs_intervention) if analysis else 0,
                    analysis.recommended_intervention if analysis else None, analysis.confidence if analysis else None,
                    analysis.model_used if analysis else None, created, updated,
                ),
            )
            for message in thread.messages:
                db.execute(
                    """INSERT INTO conversation_messages
                    (message_id, thread_id, parent_message_id, author_id, text, timestamp, platform_status,
                     like_count, source_url, is_trigger, moderation_category, moderation_risk_level, moderation_action)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(message_id) DO UPDATE SET text=excluded.text,
                     platform_status=excluded.platform_status, like_count=excluded.like_count,
                     is_trigger=excluded.is_trigger, moderation_category=excluded.moderation_category,
                     moderation_risk_level=excluded.moderation_risk_level, moderation_action=excluded.moderation_action""",
                    (
                        message.message_id, thread.thread_id, message.parent_message_id, message.author_id,
                        message.text, message.timestamp.isoformat(), message.platform_status, message.like_count,
                        message.source_url, int(message.is_trigger), message.moderation_category,
                        message.moderation_risk_level, message.moderation_action,
                    ),
                )
        return self.get_thread(thread.thread_id) or thread

    def get_thread(self, thread_id: str) -> ConversationThread | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM conversations WHERE thread_id = ?", (thread_id,)).fetchone()
            if row is None:
                return None
            messages = db.execute(
                "SELECT * FROM conversation_messages WHERE thread_id = ? ORDER BY timestamp ASC",
                (thread_id,),
            ).fetchall()
        return self._thread_from_rows(row, messages)

    def save_youtube_snapshot(self, video_id: str, title: str, threads: list[ConversationThread]) -> None:
        """Persist normalized YouTube rows alongside the conversation projection."""
        synced = now_iso()
        with self._connect() as db:
            db.execute(
                """INSERT INTO youtube_videos (video_id, title, imported_at, last_synced_at)
                VALUES (?, ?, ?, ?) ON CONFLICT(video_id) DO UPDATE SET title=excluded.title, last_synced_at=excluded.last_synced_at""",
                (video_id, title, synced, synced),
            )
            for thread in threads:
                top = thread.messages[0] if thread.messages else None
                if top is None:
                    continue
                db.execute(
                    """INSERT INTO youtube_comment_threads
                    (youtube_thread_id, video_id, top_level_comment_id, total_reply_count, imported_at, last_synced_at)
                    VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(youtube_thread_id) DO UPDATE SET
                    total_reply_count=excluded.total_reply_count, last_synced_at=excluded.last_synced_at""",
                    (thread.thread_id, video_id, top.message_id, max(0, len(thread.messages) - 1), synced, synced),
                )
                for message in thread.messages:
                    db.execute(
                        """INSERT INTO youtube_comments
                        (youtube_comment_id, youtube_thread_id, parent_comment_id, anonymized_author_id,
                         text, like_count, published_at, moderation_status, video_id, source_url, last_synced_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(youtube_comment_id) DO UPDATE SET
                        text=excluded.text, like_count=excluded.like_count, last_synced_at=excluded.last_synced_at""",
                        (message.message_id, thread.thread_id, message.parent_message_id, message.author_id,
                         message.text, message.like_count, message.timestamp.isoformat(), message.platform_status,
                         video_id, message.source_url, synced),
                    )

    def list_threads(self, stage: str | None = None, source_mode: str | None = None, video_id: str | None = None) -> list[ConversationThread]:
        clauses, values = [], []
        if stage:
            clauses.append("conversation_stage = ?")
            values.append(stage)
        if source_mode:
            clauses.append("source_mode = ?")
            values.append(source_mode)
        if video_id:
            clauses.append("video_id = ?")
            values.append(video_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as db:
            rows = db.execute(
                f"SELECT * FROM conversations {where} ORDER BY CASE conversation_stage WHEN 'critical' THEN 1 WHEN 'escalating' THEN 2 WHEN 'tense' THEN 3 WHEN 'disagreement' THEN 4 ELSE 5 END, escalation_score DESC, updated_at DESC",
                values,
            ).fetchall()
            messages_by_thread: dict[str, list[sqlite3.Row]] = {}
            for row in rows:
                messages_by_thread[row["thread_id"]] = db.execute(
                    "SELECT * FROM conversation_messages WHERE thread_id = ? ORDER BY timestamp ASC",
                    (row["thread_id"],),
                ).fetchall()
        return [self._thread_from_rows(row, messages_by_thread[row["thread_id"]]) for row in rows]

    def save_intervention(self, thread_id: str, rec: InterventionRecommendation) -> dict[str, Any]:
        intervention_id = f"INT-{uuid.uuid4().hex[:10].upper()}"
        with self._connect() as db:
            db.execute(
                """INSERT INTO interventions
                (intervention_id, thread_id, recommended_action, reason, target_users, draft_message,
                 expected_outcome, urgency, requires_admin_approval, internal_action, youtube_action,
                 supported, support_reason, model_used, action_mode, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    intervention_id, thread_id, rec.recommended_action, rec.reason, dumps(rec.target_users),
                    rec.draft_message, rec.expected_outcome, rec.urgency, int(rec.requires_admin_approval),
                    rec.internal_action, rec.youtube_action, int(rec.supported), rec.support_reason,
                    rec.model_used, "simulated", now_iso(),
                ),
            )
        return self.get_intervention(intervention_id)

    def get_intervention(self, intervention_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT * FROM interventions WHERE intervention_id = ?", (intervention_id,)).fetchone()
        if row is None:
            raise KeyError(intervention_id)
        return self._intervention_from_row(row)

    def latest_intervention(self, thread_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM interventions WHERE thread_id = ? ORDER BY created_at DESC LIMIT 1", (thread_id,)
            ).fetchone()
        return self._intervention_from_row(row) if row else None

    def save_mediation(self, thread_id: str, summary: MediationSummary) -> dict[str, Any]:
        session_id = f"MED-{uuid.uuid4().hex[:10].upper()}"
        created = now_iso()
        with self._connect() as db:
            db.execute(
                """INSERT INTO mediation_sessions
                (session_id, thread_id, side_a_position, side_b_position, common_ground, core_disagreement,
                 harmful_patterns, recommended_next_steps, admin_editable_draft, original_ai_draft, model_used,
                 created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id, thread_id, summary.side_a_position, summary.side_b_position, dumps(summary.common_ground),
                    dumps(summary.core_disagreement), dumps(summary.harmful_patterns), dumps(summary.recommended_next_steps),
                    summary.admin_editable_draft, summary.admin_editable_draft, summary.model_used, created, created,
                ),
            )
        return self.get_mediation(session_id)

    def get_mediation(self, session_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT * FROM mediation_sessions WHERE session_id = ?", (session_id,)).fetchone()
        if row is None:
            raise KeyError(session_id)
        data = dict(row)
        for key in ("common_ground", "core_disagreement", "harmful_patterns", "recommended_next_steps"):
            data[key] = json.loads(data[key] or "[]")
        return data

    def decide_intervention(self, thread_id: str, request: AdminInterventionRequest) -> dict[str, Any]:
        intervention = self.latest_intervention(thread_id)
        if not intervention:
            raise KeyError(thread_id)
        thread = self.get_thread(thread_id)
        reviewed = now_iso()
        with self._connect() as db:
            db.execute(
                """UPDATE interventions SET admin_selected_action = ?, admin_edited_message = ?, status = ?,
                reviewer = ?, admin_note = ?, reviewed_at = ? WHERE intervention_id = ?""",
                (
                    request.selected_action, request.admin_edited_message, "approved" if request.confirm else "selected",
                    request.reviewer, request.admin_note, reviewed, intervention["intervention_id"],
                ),
            )
            if thread and thread.analysis and request.classification_decision == "correct_ai":
                db.execute(
                    """UPDATE conversations SET category = COALESCE(?, category), risk_level = COALESCE(?, risk_level),
                    conversation_stage = COALESCE(?, conversation_stage), updated_at = ? WHERE thread_id = ?""",
                    (
                        request.admin_category, request.admin_risk_level, request.admin_conversation_stage,
                        reviewed, thread_id,
                    ),
                )
        refreshed = self.get_intervention(intervention["intervention_id"])
        self._create_feedback(thread_id, refreshed, request)
        refreshed["classification_decision"] = request.classification_decision
        refreshed["admin_category"] = request.admin_category
        refreshed["admin_risk_level"] = request.admin_risk_level
        refreshed["admin_conversation_stage"] = request.admin_conversation_stage
        return refreshed

    def save_outcome(self, thread_id: str, outcome: str, after_score: float | None, note: str) -> dict[str, Any]:
        intervention = self.latest_intervention(thread_id)
        if not intervention:
            raise KeyError(thread_id)
        with self._connect() as db:
            db.execute(
                "UPDATE interventions SET admin_note = ? WHERE intervention_id = ?",
                (f"Outcome: {outcome}. {note}".strip(), intervention["intervention_id"]),
            )
            db.execute(
                "UPDATE admin_feedback SET outcome_after_intervention = ?, resolution_status = ?, after_intervention_score = ?, admin_note = ?, reviewed_at = ? WHERE intervention_id = ?",
                (outcome, outcome, after_score, note, now_iso(), intervention["intervention_id"]),
            )
        result = self.get_intervention(intervention["intervention_id"])
        result["after_intervention_score"] = after_score
        return result

    def list_feedback(self, source_mode: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as db:
            if source_mode:
                rows = db.execute(
                    """SELECT f.* FROM admin_feedback f
                    JOIN conversations c ON c.thread_id = f.thread_id
                    WHERE c.source_mode = ? ORDER BY f.reviewed_at DESC, f.created_at DESC""",
                    (source_mode,),
                ).fetchall()
            else:
                rows = db.execute("SELECT * FROM admin_feedback ORDER BY reviewed_at DESC, created_at DESC").fetchall()
        return [self._feedback_from_row(row) for row in rows]

    def similar_cases(self, thread: ConversationThread, limit: int) -> list[SimilarCase]:
        if not thread.analysis:
            return []
        with self._connect() as db:
            rows = db.execute(
                """SELECT * FROM admin_feedback WHERE admin_selected_action IS NOT NULL
                ORDER BY ABS(COALESCE(original_escalation_score, 0) - ?) ASC, reviewed_at DESC LIMIT ?""",
                (thread.analysis.escalation_score, limit),
            ).fetchall()
        return [
            SimilarCase(
                feedback_id=row["feedback_id"], thread_id=row["thread_id"], stage=row["original_ai_stage"] or "unknown",
                escalation_score=float(row["original_escalation_score"] or 0),
                admin_selected_action=row["admin_selected_action"], admin_note=row["admin_note"],
                similarity_reason="Matched by escalation score and conversation stage.",
                reviewed_at=datetime.fromisoformat(row["reviewed_at"] or row["created_at"]),
            )
            for row in rows
        ]

    def health(self, source_mode: str | None = None) -> CommunityHealth:
        with self._connect() as db:
            scope = " WHERE source_mode = ?" if source_mode else ""
            scope_values = (source_mode,) if source_mode else ()
            total = int(db.execute(f"SELECT COUNT(*) FROM conversations{scope}", scope_values).fetchone()[0])
            stage_rows = db.execute(f"SELECT COALESCE(conversation_stage, 'unknown') stage, COUNT(*) count FROM conversations{scope} GROUP BY stage", scope_values).fetchall()
            if source_mode:
                interventions = int(db.execute("""SELECT COUNT(*) FROM interventions i JOIN conversations c ON c.thread_id = i.thread_id
                    WHERE c.source_mode = ? AND i.admin_selected_action IS NOT NULL""", (source_mode,)).fetchone()[0])
                feedback = db.execute("""SELECT f.* FROM admin_feedback f JOIN conversations c ON c.thread_id = f.thread_id
                    WHERE c.source_mode = ?""", (source_mode,)).fetchall()
            else:
                interventions = int(db.execute("SELECT COUNT(*) FROM interventions WHERE admin_selected_action IS NOT NULL").fetchone()[0])
                feedback = db.execute("SELECT * FROM admin_feedback").fetchall()
            avg = float(db.execute(f"SELECT COALESCE(AVG(escalation_score), 0) FROM conversations{scope}", scope_values).fetchone()[0])
            category_rows = db.execute(f"SELECT COALESCE(category, 'unknown') category, COUNT(*) count FROM conversations{scope} GROUP BY category ORDER BY count DESC LIMIT 5", scope_values).fetchall()
            channel_rows = db.execute(f"SELECT channel_id channel, COUNT(*) count FROM conversations{scope} GROUP BY channel_id ORDER BY count DESC LIMIT 5", scope_values).fetchall()
        accepted = sum(1 for row in feedback if row["admin_agreed_with_ai"] == 1)
        edited = sum(1 for row in feedback if row["admin_edited_message"])
        rejected = sum(1 for row in feedback if row["admin_selected_action"] in {"observe", "reject"})
        denominator = len(feedback) or 1
        improved = sum(1 for row in feedback if row["outcome_after_intervention"] in {"improved", "resolved"})
        return CommunityHealth(
            total_conversations=total,
            stage_counts={row["stage"]: int(row["count"]) for row in stage_rows},
            intervention_count=interventions,
            admin_agreement_rate=accepted / denominator,
            admin_edit_rate=edited / denominator,
            admin_rejection_rate=rejected / denominator,
            improved_or_resolved=improved,
            average_escalation_score=round(avg, 3),
            override_rate=1 - (accepted / denominator),
            top_categories=[{"category": row["category"], "count": int(row["count"])} for row in category_rows],
            top_channels=[{"channel": row["channel"], "count": int(row["count"])} for row in channel_rows],
        )

    def save_youtube_connection(self, data: dict[str, Any]) -> None:
        with self._connect() as db:
            db.execute(
                """INSERT INTO youtube_connections (id, channel_id, channel_title, encrypted_access_token,
                encrypted_refresh_token, token_expiry, scopes, connected_at, last_sync_at, status)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET channel_id=excluded.channel_id, channel_title=excluded.channel_title,
                encrypted_access_token=excluded.encrypted_access_token, encrypted_refresh_token=excluded.encrypted_refresh_token,
                token_expiry=excluded.token_expiry, scopes=excluded.scopes, connected_at=excluded.connected_at,
                last_sync_at=excluded.last_sync_at, status=excluded.status""",
                tuple(data.get(key) for key in ("channel_id", "channel_title", "encrypted_access_token", "encrypted_refresh_token", "token_expiry", "scopes", "connected_at", "last_sync_at", "status")),
            )

    def get_youtube_connection(self) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM youtube_connections WHERE id = 1").fetchone()
        return dict(row) if row else None

    def disconnect_youtube(self) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM youtube_connections WHERE id = 1")

    def _create_feedback(self, thread_id: str, intervention: dict[str, Any], request: AdminInterventionRequest) -> None:
        thread = self.get_thread(thread_id)
        analysis = thread.analysis if thread else None
        if not analysis:
            return
        with self._connect() as db:
            db.execute(
                """INSERT INTO admin_feedback
                (feedback_id, thread_id, intervention_id, original_ai_stage, original_escalation_score,
                 original_recommendation, admin_selected_action, admin_edited_message, admin_agreed_with_ai,
                 resolution_status, outcome_after_intervention, admin_note, classification_decision,
                 admin_category, admin_risk_level, admin_conversation_stage, action_mode, created_at, reviewed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unknown', 'unknown', ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"FB-{uuid.uuid4().hex[:10].upper()}", thread_id, intervention["intervention_id"],
                    analysis.conversation_stage, analysis.escalation_score, analysis.recommended_intervention,
                    request.selected_action, request.admin_edited_message,
                    int(request.selected_action == analysis.recommended_intervention), request.admin_note,
                    request.classification_decision, request.admin_category, request.admin_risk_level,
                    request.admin_conversation_stage, thread.action_mode, now_iso(), now_iso(),
                ),
            )

    @staticmethod
    def _thread_from_rows(row: sqlite3.Row, messages: list[sqlite3.Row]) -> ConversationThread:
        analysis = None
        if row["conversation_stage"]:
            analysis = ConversationAnalysis(
                conversation_stage=row["conversation_stage"], escalation_score=row["escalation_score"],
                urgency=row["urgency"], category=row["category"] or "other", risk_level=row["risk_level"] or "low",
                main_topic=row["main_topic"], conflict_summary=row["conflict_summary"],
                root_causes=json.loads(row["root_causes"] or "[]"), triggers=json.loads(row["triggers"] or "[]"),
                participants_in_conflict=json.loads(row["participants"] or "[]"), tone_trend=row["tone_trend"],
                needs_intervention=bool(row["needs_intervention"]), recommended_intervention=row["recommended_intervention"],
                confidence=row["confidence"], model_used=row["model_used"] or "unknown",
            )
        return ConversationThread(
            thread_id=row["thread_id"], platform=row["platform"], community_id=row["community_id"],
            channel_id=row["channel_id"], video_id=row["video_id"], video_title=row["video_title"],
            content_url=row["content_url"], messages=[ConversationMessage(**{**dict(item), "is_trigger": bool(item["is_trigger"])}) for item in messages],
            analysis=analysis, source_mode=row["source_mode"], action_mode=row["action_mode"],
            imported_at=datetime.fromisoformat(row["imported_at"]),
            expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
            last_analyzed_at=datetime.fromisoformat(row["last_analyzed_at"]) if row["last_analyzed_at"] else None,
        )

    @staticmethod
    def _intervention_from_row(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["target_users"] = json.loads(data.get("target_users") or "[]")
        for key in ("requires_admin_approval", "supported", "youtube_write_performed"):
            data[key] = bool(data.get(key, 0))
        return data

    @staticmethod
    def _feedback_from_row(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["similar_case_ids"] = json.loads(data.get("similar_case_ids") or "[]")
        data["admin_agreed_with_ai"] = bool(data.get("admin_agreed_with_ai"))
        return data
