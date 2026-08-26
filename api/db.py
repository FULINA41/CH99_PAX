from contextlib import asynccontextmanager
from typing import Any, Iterator

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

import settings

_pool: ConnectionPool | None = None


@asynccontextmanager
async def lifespan(app):
    """Hold one connection pool for the process, opened before the first request."""
    global _pool
    _pool = ConnectionPool(settings.DATABASE_URL, min_size=settings.POOL_MIN,
                           max_size=settings.POOL_MAX, open=True, kwargs={"autocommit": True})
    try:
        yield
    finally:
        _pool.close()
        _pool = None


def rows(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Run one read and return its rows as dicts.

    Every query this API makes is a read against tables the parser owns, so there is no
    transaction to manage and no write path to guard -- the pool runs autocommit and the
    role would fail on a write anyway.

    Args:
        sql: The statement.
        params: Named parameters, ``%(name)s`` style.

    Returns:
        One dict per row, column names as keys. Empty when nothing matched.
    """
    with _pool.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(sql, params or {})
        return cursor.fetchall()


def one(sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    found = rows(sql, params)
    return found[0] if found else None
