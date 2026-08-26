import os
from typing import Any

import psycopg

LOOKUP = """
SELECT id FROM source_fetch
WHERE release_name = %(release_name)s
  AND source_key = %(source_key)s
  AND sha256 = %(sha256)s
ORDER BY fetched_at DESC
LIMIT 1
"""

# run_id is left NULL on purpose: this row describes a fetch that some earlier run made,
# reconstructed from the manifest, and pretending to know the run would be a lie.
RECONSTRUCT = """
INSERT INTO source_fetch (
    source_key, release_name, release_title, url, path, status, bytes, sha256, fetched_at
) VALUES (
    %(source_key)s, %(release_name)s, %(release_title)s, %(url)s, %(path)s,
    %(status)s, %(bytes)s, %(sha256)s, COALESCE(%(fetched_at)s::timestamptz, now())
)
RETURNING id
"""


# Every loader takes an exclusive lock -- TRUNCATE, then COPY -- and a worker killed while
# holding one leaves the connection open server-side with the lock still held. Postgres waits
# for a client that is never coming back, and every later run queues behind it: observed as a
# COPY stuck 42 minutes in wait_event_type='Client' with nine TRUNCATEs stacked behind it and
# nothing failing, anywhere. A run that cannot get the lock in ten seconds is not going to get
# it, so it should say so and go red rather than hang. D-0046.
LOCK_TIMEOUT_MS = 10_000
# The bound on a single statement. The largest is a 26,246-row COPY, which takes about 4s.
STATEMENT_TIMEOUT_MS = 300_000


def connect(dsn: str | None = None) -> psycopg.Connection:
    conn = psycopg.connect(dsn or os.environ["DATABASE_URL"])
    with conn.cursor() as cursor:
        cursor.execute(f"SET lock_timeout = {LOCK_TIMEOUT_MS}")
        cursor.execute(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}")
    return conn


def resolve_source_fetch_ids(
    release: dict[str, Any],
    sources: dict[str, dict[str, Any]],
    *,
    dsn: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Give every payload a ``source_fetch`` row to point at, creating one if needed.

    ``setup.sh`` is a schema reset and drops ``source_fetch`` along with everything
    else, so re-parsing after a reset would otherwise leave every row without
    provenance. The manifest on disk survives that and is authoritative (D-0005), so
    a missing row is rebuilt from it rather than left NULL.

    Args:
        release: The manifest's release, carrying ``name`` and ``title``.
        sources: The manifest's per-source entries, keyed by source.
        dsn: Connection string. Falls back to ``DATABASE_URL``.

    Returns:
        One entry per source: its ``source_fetch_id``, and whether that row had to be
        reconstructed rather than found.
    """
    resolved: dict[str, dict[str, Any]] = {}

    with connect(dsn) as conn, conn.cursor() as cursor:
        for key, entry in sources.items():
            row = {
                "source_key": key,
                "release_name": release.get("name"),
                "release_title": release.get("title"),
                **{field: entry.get(field) for field in
                   ("url", "path", "status", "bytes", "sha256", "fetched_at")},
            }

            cursor.execute(LOOKUP, row)
            found = cursor.fetchone()
            if found:
                resolved[key] = {"source_fetch_id": found[0], "reconstructed": False}
                continue

            cursor.execute(RECONSTRUCT, row)
            resolved[key] = {"source_fetch_id": cursor.fetchone()[0], "reconstructed": True}

    return resolved
