import re

from fastapi import APIRouter, Query

from db import rows
from duty import queries

router = APIRouter(tags=["search"])

# '7208.51.00.30', '7208.51', '7208515' -- what someone pastes from an invoice rather than
# types as a description.
LOOKS_LIKE_A_CODE = re.compile(r"^\d{4}(\.\d{2}){0,3}$")


@router.get("/search")
def search(
    q: str = Query(min_length=2, description="Words from the schedule's description of a good"),
    limit: int = Query(default=40, ge=1, le=100),
) -> dict:
    """Find candidate base-schedule codes by the schedule's own wording.

    Two passes: full text first, then trigram similarity if it finds nothing. Neither is
    classification -- the schedule describes a laptop bag as "Trunks, suitcases ... with outer
    surface of textile materials", and matching prose is not the same as deciding what a
    product is.

    Args:
        q: Search words, or a code pasted straight in.
        limit: How many candidates to return.

    Returns:
        The candidates, which pass matched them, and whether the input looked like a code.
    """
    cleaned = q.strip()
    if LOOKS_LIKE_A_CODE.match(cleaned):
        found = rows(
            "SELECT hts, full_description, units, rate_text, rate_kind, rate_ad_valorem_pct,"
            " 1 AS rank, 0 AS programmes FROM hts_base WHERE hts LIKE %(prefix)s"
            " ORDER BY hts LIMIT %(limit)s",
            {"prefix": f"{cleaned}%", "limit": limit},
        )
        return {"query": cleaned, "matched_by": "code", "results": found}

    found = rows(queries.SEARCH, {"q": cleaned, "limit": limit})
    if found:
        return {"query": cleaned, "matched_by": "words", "results": found}

    return {
        "query": cleaned,
        "matched_by": "spelling",
        "results": rows(queries.SEARCH_FUZZY, {"q": cleaned, "limit": limit}),
    }
