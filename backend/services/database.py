"""Small DB-API compatibility layer for Supabase/PostgreSQL runtime storage."""

from __future__ import annotations

import re
from typing import Any, Iterable, Sequence

import psycopg2
import psycopg2.extras


def _postgres_sql(sql: str) -> str:
    """Translate the simple qmark placeholders used by the legacy store."""
    return re.sub(r"\?", "%s", sql)


class PostgresConnection:
    """Expose SQLite-like execute helpers while retaining PostgreSQL transactions."""

    def __init__(self, dsn: str) -> None:
        self._connection = psycopg2.connect(dsn)

    def __enter__(self) -> "PostgresConnection":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        try:
            if exc_type is None:
                self._connection.commit()
            else:
                self._connection.rollback()
        finally:
            self._connection.close()

    def execute(self, sql: str, parameters: Sequence[object] | None = None):
        cursor = self._connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        values = tuple(parameters or ())
        if values:
            cursor.execute(_postgres_sql(sql), values)
        else:
            # Passing an empty tuple makes psycopg2 parse literal `%` signs as
            # pyformat placeholders. Queries such as LIKE 'test-%' must be
            # executed without a parameters argument.
            cursor.execute(sql)
        return cursor

    def executemany(self, sql: str, parameters: Iterable[Sequence[object]]):
        cursor = self._connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.executemany(_postgres_sql(sql), list(parameters))
        return cursor

    def executescript(self, sql: str) -> None:
        cursor = self._connection.cursor()
        cursor.execute(sql)


def postgres_connection(dsn: str) -> PostgresConnection:
    if not dsn:
        raise RuntimeError("FAQ_PG_DSN is required for Supabase runtime storage.")
    return PostgresConnection(dsn)


def json_value(value: Any, default: Any) -> Any:
    """Read either native PostgreSQL jsonb values or SQLite JSON strings."""
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list, int, float, bool)):
        return value
    import json

    try:
        return json.loads(str(value))
    except (TypeError, ValueError):
        return default


def timestamp_value(value: Any):
    """Normalize PostgreSQL datetime objects and SQLite ISO strings."""
    from datetime import datetime

    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))
