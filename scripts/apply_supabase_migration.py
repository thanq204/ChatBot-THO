"""Apply the idempotent P-232 Supabase schema with an in-database backup."""

from __future__ import annotations

import re
from pathlib import Path

import psycopg2
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260819_runtime_data_model.sql"
BACKUP_SCHEMA = "p232_backup_20260819_before_runtime_v2"


def main() -> int:
    load_dotenv(ROOT / ".env")
    from os import getenv

    dsn = getenv("FAQ_PG_DSN", "").strip()
    if not dsn:
        raise RuntimeError("FAQ_PG_DSN is required")
    if not re.fullmatch(r"[a-zA-Z0-9_]+", BACKUP_SCHEMA):
        raise RuntimeError("Unsafe backup schema name")

    connection = psycopg2.connect(dsn, connect_timeout=15)
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {BACKUP_SCHEMA}")
            cursor.execute(
                """SELECT table_name FROM information_schema.tables
                WHERE table_schema='public' AND table_type='BASE TABLE'
                ORDER BY table_name"""
            )
            tables = [row[0] for row in cursor.fetchall()]
            for table in tables:
                if not re.fullmatch(r"[a-zA-Z0-9_]+", table):
                    continue
                cursor.execute(
                    "SELECT 1 FROM information_schema.tables WHERE table_schema=%s AND table_name=%s",
                    (BACKUP_SCHEMA, table),
                )
                if cursor.fetchone():
                    continue
                cursor.execute(f"CREATE TABLE {BACKUP_SCHEMA}.{table} AS TABLE public.{table}")
            cursor.execute(MIGRATION.read_text(encoding="utf-8"))
        connection.commit()
        print(f"Supabase migration applied; backup schema: {BACKUP_SCHEMA}")
        return 0
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
