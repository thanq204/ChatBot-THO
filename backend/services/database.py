"""Small DB-API compatibility layer for Supabase/PostgreSQL runtime storage."""

from __future__ import annotations

import re
import threading
from typing import Any, Iterable, Sequence

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool


_pools: dict[tuple[str, int, int], ThreadedConnectionPool] = {}
_pools_lock = threading.Lock()


def _pool_for(dsn: str, min_size: int, max_size: int) -> ThreadedConnectionPool:
    max_size = max(min_size, max_size)
    key = (dsn, min_size, max_size)
    with _pools_lock:
        pool = _pools.get(key)
        if pool is None:
            pool = ThreadedConnectionPool(min_size, max_size, dsn)
            _pools[key] = pool
        return pool


def _postgres_sql(sql: str) -> str:
    """Translate the simple qmark placeholders used by the legacy store."""
    return re.sub(r"\?", "%s", sql)


class PostgresConnection:
    """Expose SQLite-like execute helpers while retaining PostgreSQL transactions."""

    def __init__(self, dsn: str, min_pool_size: int = 1, max_pool_size: int = 8) -> None:
        self._pool = _pool_for(dsn, min_pool_size, max_pool_size)
        self._connection = self._pool.getconn()
        self._cursors: list[Any] = []

    def __enter__(self) -> "PostgresConnection":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        broken = bool(self._connection.closed)
        try:
            if exc_type is None and not broken:
                self._connection.commit()
            elif not broken:
                self._connection.rollback()
        except psycopg2.Error:
            broken = True
            raise
        finally:
            for cursor in self._cursors:
                try:
                    cursor.close()
                except psycopg2.Error:
                    broken = True
            self._pool.putconn(self._connection, close=broken)

    def execute(self, sql: str, parameters: Sequence[object] | None = None):
        cursor = self._connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        if hasattr(self, "_cursors"):
            self._cursors.append(cursor)
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
        if hasattr(self, "_cursors"):
            self._cursors.append(cursor)
        cursor.executemany(_postgres_sql(sql), list(parameters))
        return cursor

    def executescript(self, sql: str) -> None:
        cursor = self._connection.cursor()
        if hasattr(self, "_cursors"):
            self._cursors.append(cursor)
        cursor.execute(sql)


def postgres_connection(
    dsn: str,
    min_pool_size: int = 1,
    max_pool_size: int = 8,
) -> PostgresConnection:
    if not dsn:
        raise RuntimeError("FAQ_PG_DSN is required for Supabase runtime storage.")
    return PostgresConnection(dsn, min_pool_size, max_pool_size)


def close_postgres_pools() -> None:
    with _pools_lock:
        pools = list(_pools.values())
        _pools.clear()
    for pool in pools:
        pool.closeall()


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
