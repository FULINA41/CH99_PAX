import argparse
import os
import sys

import psycopg

from scrape import ScrapeInput, scrape_workflow

REPORT = """
SELECT source_key, status, bytes, sha256, error, release_name, release_title, path
FROM source_fetch WHERE run_id = %s ORDER BY source_key
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch the three HTS sources.")
    parser.add_argument("--release", help="pin a specific release, e.g. 2026HTSRev17")
    parser.add_argument("--force", action="store_true", help="rewrite payloads even if unchanged")
    args = parser.parse_args()

    ref = scrape_workflow.run(
        ScrapeInput(release=args.release, force=args.force), wait_for_result=False
    )

    failure = None
    try:
        ref.result()
    except Exception as exc:  # noqa: BLE001 - a failed run still has a report to print
        failure = exc

    _report(ref.workflow_run_id)

    if failure:
        print(f"\nrun failed: {failure}", file=sys.stderr)
        raise SystemExit(1)


# This module runs on the host, where nothing sets DATABASE_URL -- the worker gets it from
# compose and parse_run never needs it, because its report comes from the workflow's own
# result. Requiring it here meant the documented way to run Part 1 ended in a KeyError after
# the scrape had already succeeded. Same fallback as api/settings.py, and the same reason: it
# is the address the dev stack publishes.
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgres://postgres:postgres@localhost:5432/chp99"
)


def _report(run_id: str) -> None:
    # Read from source_fetch rather than the task outputs, so the report is identical
    # whether the run succeeded or lost a source.
    with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cursor:
        cursor.execute(REPORT, (run_id,))
        rows = cursor.fetchall()

    if not rows:
        print(f"no source_fetch rows for run {run_id}")
        return

    _, _, _, _, _, release_name, release_title, path = rows[0]
    print(f"release  {release_name}  {release_title or ''}".rstrip())

    tally = {"fetched": 0, "unchanged": 0, "failed": 0}
    for key, status, size, sha, error, *_ in rows:
        tally[status] = tally.get(status, 0) + 1
        if status == "skipped":
            detail = "  endpoint cannot serve a past release"
        elif size:
            detail = f"{size:>12,} B  sha {sha[:8]}…"
        else:
            detail = f"  {error or ''}"
        print(f"  {key:<12} {status:<10}{detail}")

    counts = ", ".join(f"{n} {name}" for name, n in tally.items() if n)
    print(f"{counts} → {os.path.dirname(path)}/")


if __name__ == "__main__":
    main()
