"""Repair known legacy orphan references and validate Supabase foreign keys."""

from __future__ import annotations

from pathlib import Path

import psycopg2
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    load_dotenv(ROOT / ".env")
    from os import getenv

    connection = psycopg2.connect(getenv("FAQ_PG_DSN", ""), connect_timeout=15)
    constraints = {
        "fk_operations_messages_incident": "operations_messages",
        "fk_gate_runs_message": "operations_gate_runs",
        "fk_operations_audit_incident": "operations_audit",
        "fk_operations_audit_message": "operations_audit",
        "fk_moderation_marks_incident": "operations_moderation_marks",
        "fk_moderation_marks_message": "operations_moderation_marks",
        "fk_moderation_embedding_mark": "operations_moderation_embeddings",
        "fk_faq_question_message": "operations_faq_questions",
        "fk_faq_source_cluster": "operations_faqs",
    }
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE operations_messages message SET incident_id=NULL, updated_at=NOW()
                WHERE incident_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM operations_incidents incident
                    WHERE incident.incident_id=message.incident_id
                )"""
            )
            repaired_messages = cursor.rowcount
            cursor.execute(
                """UPDATE operations_audit audit
                SET payload_json=COALESCE(payload_json, '{}'::jsonb)
                    || jsonb_build_object('legacy_orphan_message_id', message_id),
                    message_id=NULL
                WHERE message_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM operations_messages message
                    WHERE message.message_id=audit.message_id
                )"""
            )
            repaired_audits = cursor.rowcount
            for name, table in constraints.items():
                cursor.execute(f"ALTER TABLE {table} VALIDATE CONSTRAINT {name}")
        connection.commit()
        print(f"repaired_message_links={repaired_messages}")
        print(f"repaired_audit_links={repaired_audits}")
        print(f"foreign_keys_validated={len(constraints)}")
        return 0
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
