from typing import Any

from parsing.db import connect

STAGE = "materialize"

PROGRAMMES: tuple[dict[str, str], ...] = (
    {
        "heading_prefix": "9903.01",
        "label": "IEEPA — border actions and the reciprocal baseline",
        "statute": "International Emergency Economic Powers Act, 50 U.S.C. 1701",
        "agency": "The President",
        "evidence": "75 provisions naming Canada, Mexico, China and ~90 others; scope from "
                    "U.S. note 2 to subchapter III",
    },
    {
        "heading_prefix": "9903.02",
        "label": "IEEPA — reciprocal tariffs, country-specific rates",
        "statute": "International Emergency Economic Powers Act, 50 U.S.C. 1701",
        "agency": "The President",
        "evidence": "91 provisions, 69 of them additive, one per country, scope from "
                    "subdivision (v) of U.S. note 2",
    },
    {
        "heading_prefix": "9903.82",
        "label": "Section 232 — steel and aluminium",
        "statute": "Trade Expansion Act of 1962, section 232, 19 U.S.C. 1862",
        "agency": "Department of Commerce",
        "evidence": "the provisions read 'Articles of aluminum or of steel and derivative "
                    "aluminum or steel articles'",
    },
    {
        "heading_prefix": "9903.85",
        "label": "Section 232 — aluminium of Russian origin",
        "statute": "Trade Expansion Act of 1962, section 232, 19 U.S.C. 1862",
        "agency": "Department of Commerce",
        "evidence": "the provisions read 'Aluminum articles that are the product of Russia, "
                    "or where any amount of primary aluminum used in the manufacture...'",
    },
    {
        "heading_prefix": "9903.88",
        "label": "Section 301 — China",
        "statute": "Trade Act of 1974, section 301, 19 U.S.C. 2411",
        "agency": "Office of the U.S. Trade Representative",
        "evidence": "66 provisions, every one naming China and no other country; scope and "
                    "exclusions from U.S. note 20 and its subdivisions",
    },
    {
        "heading_prefix": "9903.91",
        "label": "Section 301 — China, 2024 review",
        "statute": "Trade Act of 1974, section 301, 19 U.S.C. 2411",
        "agency": "Office of the U.S. Trade Representative",
        "evidence": "16 provisions, every one naming China, scope from U.S. note 31, rates "
                    "stepping 25/50/100% across effective dates in 2024, 2025 and 2026",
    },
    {
        "heading_prefix": "9903.94",
        "label": "Section 232 — automobiles and automobile parts",
        "statute": "Trade Expansion Act of 1962, section 232, 19 U.S.C. 1862",
        "agency": "Department of Commerce",
        "evidence": "32 provisions reading 'Automobile parts the product of Japan / the "
                    "European Union / South Korea / Taiwan'",
    },
)

# A search rather than a document id. The Federal Register API is open and the search is
# reproducible; a specific document number quoted from memory is not checkable from the
# payloads this project fetched, and would read as sourced when it is not.
SEARCH = ("https://www.federalregister.gov/documents/search"
          "?conditions%5Bterm%5D=heading+{prefix}")

COLUMNS = ("heading_prefix", "label", "statute", "agency", "evidence", "reference_url")


def load_programmes(dsn: str | None = None) -> dict[str, Any]:
    """Replace the editorial trade-programme reference, in one transaction.

    Nothing here is parsed from a payload, so this is the one loader that takes no
    ``source_fetch_id``: the rows are attributable to this file and to nothing else.

    Args:
        dsn: Connection string. Falls back to ``DATABASE_URL``.

    Returns:
        How many programmes were written and how many Chapter 99 provisions they cover.
    """
    with connect(dsn) as conn, conn.cursor() as cursor:
        cursor.execute("TRUNCATE trade_programme")
        with cursor.copy(
            f"COPY trade_programme ({', '.join(COLUMNS)}) FROM STDIN"
        ) as copy:
            for programme in PROGRAMMES:
                copy.write_row([
                    *(programme[column] for column in COLUMNS[:-1]),
                    SEARCH.format(prefix=programme["heading_prefix"]),
                ])

        cursor.execute("""
            SELECT count(*) FROM rule r
            WHERE EXISTS (SELECT 1 FROM trade_programme p
                          WHERE left(r.hts, 7) = p.heading_prefix)""")
        covered = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM rule WHERE hts LIKE '9903%'")
        subchapter_iii = cursor.fetchone()[0]

    return {
        "programmes": len(PROGRAMMES),
        "rules_labelled": covered,
        "subchapter_iii_rules": subchapter_iii,
    }
