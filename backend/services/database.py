"""Small DB-API compatibility layer for Supabase/PostgreSQL runtime storage."""

from __future__ import annotations

import re
import threading
from collections.abc import Generator, Iterable, Sequence
from contextlib import contextmanager
from typing import Any

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

# Callers that outnumber the pool wait this long for a free connection before
# giving up. Opening a fresh link to a remote Supabase costs ~500ms, so queuing
# briefly is always cheaper than bypassing the pool.
_ACQUIRE_TIMEOUT_S = 30.0


class _PoolHandle:
    """A connection pool plus a gate that makes over-subscription wait, not fail.

    `ThreadedConnectionPool.getconn()` raises as soon as every connection is
    checked out. Requests run on a threadpool that is far larger than the pool,
    so without this gate a burst of traffic would surface as `PoolError` instead
    of simply taking slightly longer.
    """

    def __init__(self, dsn: str, min_size: int, max_size: int) -> None:
        self._pool = ThreadedConnectionPool(min_size, max_size, dsn)
        self._slots = threading.Semaphore(max_size)

    def acquire(self):
        if not self._slots.acquire(timeout=_ACQUIRE_TIMEOUT_S):
            raise RuntimeError("Timed out waiting for a free PostgreSQL connection.")
        try:
            return self._pool.getconn()
        except BaseException:
            self._slots.release()
            raise

    def release(self, connection, close: bool = False) -> None:
        try:
            self._pool.putconn(connection, close=close)
        finally:
            self._slots.release()

    def closeall(self) -> None:
        self._pool.closeall()


_pools: dict[tuple[str, int, int], _PoolHandle] = {}
_pools_lock = threading.Lock()


def _pool_for(dsn: str, min_size: int, max_size: int) -> _PoolHandle:
    max_size = max(min_size, max_size)
    key = (dsn, min_size, max_size)
    with _pools_lock:
        pool = _pools.get(key)
        if pool is None:
            pool = _PoolHandle(dsn, min_size, max_size)
            _pools[key] = pool
        return pool


def _postgres_sql(sql: str) -> str:
    """Translate the simple qmark placeholders used by the legacy store."""
    return re.sub(r"\?", "%s", sql)


class PostgresConnection:
    """Expose SQLite-like execute helpers while retaining PostgreSQL transactions."""

    def __init__(
        self,
        dsn: str,
        min_pool_size: int = 1,
        max_pool_size: int = 8,
        readonly: bool = False,
    ) -> None:
        self._pool = _pool_for(dsn, min_pool_size, max_pool_size)
        self._connection = self._pool.acquire()
        self._cursors: list[Any] = []
        # See `pooled_connection`: skips the BEGIN/COMMIT round-trip pair that a
        # read-only block would otherwise pay for. Writes must not set this.
        self._readonly = readonly
        if readonly:
            self._connection.autocommit = True

    def __enter__(self) -> PostgresConnection:
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
            if self._readonly and not self._connection.closed:
                self._connection.autocommit = False
            self._pool.release(self._connection, close=broken)

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
    readonly: bool = False,
) -> PostgresConnection:
    if not dsn:
        raise RuntimeError("FAQ_PG_DSN is required for Supabase runtime storage.")
    return PostgresConnection(dsn, min_pool_size, max_pool_size, readonly)


@contextmanager
def pooled_connection(
    dsn: str,
    min_pool_size: int = 1,
    max_pool_size: int = 8,
    readonly: bool = False,
) -> Generator[Any, None, None]:
    """Lend out a raw psycopg2 connection from the shared pool.

    `postgres_connection` wraps the connection in a SQLite-flavoured facade.
    Callers that want the psycopg2 API directly — `conn.cursor(cursor_factory=...)`
    — use this instead, and still avoid paying for a new connection per call.

    `readonly=True` drops the implicit transaction psycopg2 would otherwise wrap
    the block in. Against a remote database that BEGIN/COMMIT pair is two extra
    round-trips, which triples the cost of a block that only reads. Toggling
    `autocommit` is client-side, so buying that back costs nothing. Only pass it
    for blocks that issue no writes.
    """
    if not dsn:
        raise RuntimeError("FAQ_PG_DSN is required for Supabase runtime storage.")
    pool = _pool_for(dsn, min_pool_size, max_pool_size)
    connection = pool.acquire()
    broken = False
    try:
        if readonly:
            connection.autocommit = True
        yield connection
    except BaseException:
        broken = _close_transaction(connection, commit=False)
        raise
    else:
        broken = _close_transaction(connection, commit=True)
    finally:
        if readonly and not connection.closed:
            # Never hand an autocommit connection to the next borrower.
            connection.autocommit = False
        pool.release(connection, close=broken)


def _close_transaction(connection, commit: bool) -> bool:
    """End the transaction. Returns True when the connection is no longer usable."""
    if connection.closed:
        return True
    try:
        if commit:
            connection.commit()
        else:
            connection.rollback()
    except psycopg2.Error:
        return True
    return False


def warm_postgres_pool(dsn: str, min_pool_size: int = 1, max_pool_size: int = 8) -> None:
    """Open the pool's baseline connections at startup rather than on a request.

    `ThreadedConnectionPool` creates connections under a single lock, so a cold
    pool turns the first burst of concurrent requests into a queue of ~500ms
    handshakes. Paying for them during boot keeps that off the first page load.
    """
    if not dsn:
        return
    try:
        _pool_for(dsn, min_pool_size, max_pool_size)
    except psycopg2.Error:
        # A database that is not reachable yet must not stop the app from booting;
        # the pool will be built on first use instead.
        pass


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
