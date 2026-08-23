"""
One row per source per run, so a parsed row can name the fetch it came from.

Written by each fetch task as it finishes rather than in one batch at the end: a run
that dies partway should still leave a record of what it did before dying.
"""

import os
from typing import Any

import psycopg

INSERT = """
INSERT INTO source_fetch (
    run_id, source_key, release_name, release_title, url, path,
    status, http_status, bytes, sha256, duration_ms, error
) VALUES (
    %(run_id)s, %(source_key)s, %(release_name)s, %(release_title)s, %(url)s, %(path)s,
    %(status)s, %(http_status)s, %(bytes)s, %(sha256)s, %(duration_ms)s, %(error)s
)
"""


def record_fetch(
    entry: dict[str, Any],
    *,
    release: dict[str, Any],
    run_id: str | None,
    dsn: str | None = None,
) -> None:
    """Record one fetch, so a parsed row can later name where it came from.

    Args:
        entry: A fetch result from ``fetch_source``, failures included.
        release: The resolved release the fetch belongs to.
        run_id: The Hatchet run, to trace a row back to the run that wrote it.
        dsn: Connection string. Falls back to ``DATABASE_URL``.
    """
    row = {
        "run_id": run_id,
        "release_name": release.get("name"),
        "release_title": release.get("title"),
        **{key: entry.get(key) for key in
           ("source_key", "url", "path", "status", "http_status", "bytes", "sha256",
            "duration_ms", "error")},
    }

    with psycopg.connect(dsn or os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cursor:
            cursor.execute(INSERT, row)
