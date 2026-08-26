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


COUNTRIES = """
SELECT country_code, min(country_name) AS name, count(DISTINCT rule_hts) AS provisions
FROM rule_country WHERE country_code IS NOT NULL AND relation = 'product_of'
GROUP BY 1 ORDER BY 2
"""


@router.get("/countries")
def read_countries() -> dict:
    """Every country of origin the schedule can be asked about.

    Two lists, because they answer different questions. `named` is the countries Chapter 99
    actually names, with how many provisions name each -- 95 of them, and the ones a user is
    most likely to be here about. `all` is the ISO register, because a shipment from a country
    Chapter 99 never mentions still has an answer: the base rate, and nothing added.

    Returns:
        The named countries with their provision counts, and the full ISO 3166-1 list.
    """
    import pycountry

    named = rows(COUNTRIES)
    seen = {row["country_code"] for row in named}
    return {
        "named": named,
        "all": [
            {"country_code": country.alpha_2, "name": country.name,
             "named_by_chapter_99": country.alpha_2 in seen}
            for country in sorted(pycountry.countries, key=lambda c: c.name)
        ],
    }
