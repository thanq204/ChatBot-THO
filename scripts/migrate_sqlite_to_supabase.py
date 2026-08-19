"""One-time, idempotent migration from the legacy SQLite runtime to Supabase."""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
SQLITE_PATH = ROOT / "data" / "app.db"


def rows(db: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return [dict(row) for row in db.execute(f"SELECT * FROM {table}").fetchall()] if exists else []


def json_text(value: Any, default: str) -> str:
    if value is None or value == "":
        return default
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def upsert_many(
    cursor,
    table: str,
    columns: list[str],
    records: list[tuple[Any, ...]],
    key: str,
    update_exclude: set[str] | None = None,
) -> None:
    if not records:
        return
    excluded = {key, *(update_exclude or set())}
    assignments = ", ".join(f"{column}=EXCLUDED.{column}" for column in columns if column not in excluded)
    placeholders = ", ".join(["%s"] * len(columns))
    query = (
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT({key}) DO UPDATE SET {assignments}"
    )
    psycopg2.extras.execute_batch(cursor, query, records, page_size=500)


def main() -> int:
    load_dotenv(ROOT / ".env")
    from os import getenv

    dsn = getenv("FAQ_PG_DSN", "").strip()
    if not dsn:
        raise RuntimeError("FAQ_PG_DSN is required")
    source = sqlite3.connect(SQLITE_PATH)
    source.row_factory = sqlite3.Row
    target = psycopg2.connect(dsn, connect_timeout=15)
    try:
        with target.cursor() as cursor:
            incident_rows = rows(source, "operations_incidents")
            incident_columns = [
                "incident_id", "platform", "community_id", "channel_id", "thread_key", "status",
                "severity", "risk_score", "title", "summary", "categories_json", "message_ids_json",
                "first_seen", "last_seen", "assigned_to", "created_at", "updated_at", "source_url",
            ]
            upsert_many(
                cursor,
                "operations_incidents",
                incident_columns,
                [tuple(json_text(row[column], "[]") if column in {"categories_json", "message_ids_json"} else row.get(column) for column in incident_columns) for row in incident_rows],
                "incident_id",
            )

            message_rows = rows(source, "operations_messages")
            member_records: dict[tuple[str, str, str], tuple[Any, ...]] = {}
            for row in message_rows:
                key = (row["platform"], row["community_id"], row["author_id"])
                member_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"p232:{key[0]}:{key[1]}:{key[2]}"))
                member_records[key] = (
                    member_id, key[0], key[1], key[2], None, row["timestamp"], row["timestamp"], "{}",
                )
            upsert_many(
                cursor,
                "community_members",
                ["member_id", "platform", "community_id", "platform_user_id", "display_name", "first_seen_at", "last_seen_at", "metadata"],
                list(member_records.values()),
                "member_id",
            )
            message_columns = [
                "message_id", "platform", "community_id", "channel_id", "thread_key", "parent_message_id",
                "author_id", "author_member_id", "text", "timestamp", "source_url", "raw_json", "decision",
                "category", "severity", "risk_score", "confidence", "explanation", "model_used", "incident_id",
                "created_at", "updated_at",
            ]
            message_records = []
            for row in message_rows:
                key = (row["platform"], row["community_id"], row["author_id"])
                member_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"p232:{key[0]}:{key[1]}:{key[2]}"))
                values = {**row, "author_member_id": member_id, "raw_json": json_text(row.get("raw_json"), "{}")}
                message_records.append(tuple(values.get(column) for column in message_columns))
            upsert_many(cursor, "operations_messages", message_columns, message_records, "message_id")

            gate_columns = [
                "run_id", "message_id", "gate", "passed", "label", "category", "risk_score",
                "evidence_json", "explanation", "model_used", "duration_ms", "created_at",
            ]
            gate_records = []
            for row in rows(source, "operations_gate_runs"):
                row["passed"] = bool(row["passed"])
                row["evidence_json"] = json_text(row.get("evidence_json"), "[]")
                gate_records.append(tuple(row.get(column) for column in gate_columns))
            upsert_many(cursor, "operations_gate_runs", gate_columns, gate_records, "run_id")

            message_ids = {row["message_id"] for row in message_rows}
            incident_ids = {row["incident_id"] for row in incident_rows}
            audit_columns = ["audit_id", "incident_id", "message_id", "event_type", "actor", "payload_json", "created_at"]
            audit_records = []
            for row in rows(source, "operations_audit"):
                row["incident_id"] = row["incident_id"] if row["incident_id"] in incident_ids else None
                row["message_id"] = row["message_id"] if row["message_id"] in message_ids else None
                row["payload_json"] = json_text(row.get("payload_json"), "{}")
                audit_records.append(tuple(row.get(column) for column in audit_columns))
            upsert_many(cursor, "operations_audit", audit_columns, audit_records, "audit_id")

            policy_columns = ["policy_id", "name", "description", "category", "action", "trigger_terms_json", "active", "version", "updated_at"]
            policy_records = []
            for row in rows(source, "operations_policies"):
                row["active"] = bool(row["active"])
                row["trigger_terms_json"] = json_text(row.get("trigger_terms_json"), "[]")
                policy_records.append(tuple(row.get(column) for column in policy_columns))
            upsert_many(cursor, "operations_policies", policy_columns, policy_records, "policy_id")

            mark_columns = [
                "mark_id", "incident_id", "message_id", "text", "normalized_text", "category", "decision",
                "reason", "marked_by", "marked_at", "source_url", "active", "version", "created_at", "updated_at",
            ]
            mark_records = []
            for row in rows(source, "operations_moderation_marks"):
                if row["incident_id"] not in incident_ids or row["message_id"] not in message_ids:
                    continue
                row["active"] = bool(row["active"])
                mark_records.append(tuple(row.get(column) for column in mark_columns))
            upsert_many(cursor, "operations_moderation_marks", mark_columns, mark_records, "mark_id")

            import_columns = [
                "import_id", "filename", "format", "target", "normalized_count", "skipped_count",
                "warnings_json", "normalized_by", "status", "created_at",
            ]
            import_records = []
            for row in rows(source, "operations_knowledge_imports"):
                row["warnings_json"] = json_text(row.get("warnings_json"), "[]")
                row["status"] = "completed"
                import_records.append(tuple(row.get(column) for column in import_columns))
            upsert_many(cursor, "operations_knowledge_imports", import_columns, import_records, "import_id")

            faq_columns = ["faq_id", "question", "answer", "tags_json", "active", "updated_at"]
            faq_records = []
            for row in rows(source, "operations_faqs"):
                row["active"] = bool(row["active"])
                row["tags_json"] = json_text(row.get("tags_json"), "[]")
                faq_records.append(tuple(row.get(column) for column in faq_columns))
            upsert_many(cursor, "operations_faqs", faq_columns, faq_records, "faq_id")

            question_columns = [
                "question_id", "message_id", "question", "normalized_question", "platform",
                "community_id", "channel_id", "author_id", "created_at",
            ]
            question_records = []
            for row in rows(source, "operations_faq_questions"):
                message = next((item for item in message_rows if item["message_id"] == row["message_id"]), None)
                row["community_id"] = message["community_id"] if message else "community-001"
                row["channel_id"] = message["channel_id"] if message else "general"
                row["message_id"] = row["message_id"] if row["message_id"] in message_ids else None
                question_records.append(tuple(row.get(column) for column in question_columns))
            upsert_many(
                cursor,
                "operations_faq_questions",
                question_columns,
                question_records,
                "message_id",
                update_exclude={"question_id"},
            )

            command_columns = ["command", "body", "description", "platforms_json", "updated_at"]
            command_records = []
            for row in rows(source, "operations_command_content"):
                row["platforms_json"] = json_text(row.get("platforms_json"), '["telegram","discord"]')
                command_records.append(tuple(row.get(column) for column in command_columns))
            upsert_many(cursor, "operations_command_content", command_columns, command_records, "command")

            report_columns = ["report_id", "platform", "reporter_id", "channel_id", "details", "status", "created_at"]
            upsert_many(cursor, "operations_member_reports", report_columns, [tuple(row.get(column) for column in report_columns) for row in rows(source, "operations_member_reports")], "report_id")

        target.commit()
    except Exception:
        target.rollback()
        raise
    finally:
        source.close()
        target.close()

    print("SQLite operational data migrated to Supabase")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
