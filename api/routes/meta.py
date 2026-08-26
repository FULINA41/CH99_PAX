from fastapi import APIRouter

from db import one, rows

router = APIRouter(tags=["meta"])

RELEASE = """
SELECT release_name, release_title, max(fetched_at) AS fetched_at, count(*) AS sources
FROM source_fetch GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 1
"""

COUNTS = """
SELECT 'hts_base' AS relation, count(*) FROM hts_base
UNION ALL SELECT 'rule', count(*) FROM rule
UNION ALL SELECT 'note', count(*) FROM note
UNION ALL SELECT 'trade_programme', count(*) FROM trade_programme
UNION ALL SELECT 'parse_issue', count(*) FROM parse_issue
ORDER BY 1
"""

ISSUES = """
SELECT stage, issue_kind, count(*) FROM parse_issue GROUP BY 1, 2 ORDER BY 3 DESC
"""


@router.get("/meta")
def read_meta() -> dict:
    """Describe the data behind every other endpoint.

    The HTSUS is revised several times a year, so which revision an answer came from is part
    of the answer. The parse issues are here for the same reason: a reader is entitled to
    know what the parser could not read before trusting what it could.

    Returns:
        The release the rows were parsed from, row counts per table, and the parse issues
        grouped by the stage that raised them.
    """
    return {
        "release": one(RELEASE),
        "counts": {row["relation"]: row["count"] for row in rows(COUNTS)},
        "parse_issues": rows(ISSUES),
    }
