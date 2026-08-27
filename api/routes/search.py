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
    country: str | None = Query(default=None, min_length=2, max_length=2,
                                description="ISO 3166-1 alpha-2 country of origin"),
    limit: int = Query(default=40, ge=1, le=100),
) -> dict:
    """Find candidate base-schedule codes by the schedule's own wording.

    Two passes: full text first, then trigram similarity if it finds nothing. Neither is
    classification -- the schedule describes a laptop bag as "Trunks, suitcases ... with outer
    surface of textile materials", and matching prose is not the same as deciding what a
    product is.

    Args:
        q: Search words, or a code pasted straight in.
        country: Origin, used only to decide which trade actions are named against a result.
            Without one, every action that mentions the code is named, which is a fair answer
            to a question asked without an origin. With one, the same origin filter the duty
            page applies is applied here, so the two cannot disagree.
        limit: How many candidates to return.

    Returns:
        The candidates, which pass matched them, and whether the input looked like a code.
    """
    cleaned = q.strip()
    origin = country.upper() if country else None

    if LOOKS_LIKE_A_CODE.match(cleaned):
        found = rows(queries.SEARCH_CODE,
                     {"prefix": f"{cleaned}%", "country": origin, "limit": limit})
        return {"query": cleaned, "matched_by": "code", "results": found}

    found = rows(queries.SEARCH, {"q": cleaned, "country": origin, "limit": limit})
    if found:
        return {"query": cleaned, "matched_by": "words", "results": found}

    return {
        "query": cleaned,
        "matched_by": "spelling",
        "results": rows(queries.SEARCH_FUZZY,
                        {"q": cleaned, "country": origin, "limit": limit}),
    }
