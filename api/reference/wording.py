"""Plain English for the values the schema stores as enums.

A reader is told what a provision does. Which token the parser wrote in the column is an
implementation detail, and `additive`, `by_country_all_goods` and `suspended` were all printed
to users before this module existed.
"""

RATE_KIND = {
    "additive": "Adds to the duty these goods already pay",
    "replace": "Stands in for the duty these goods would otherwise pay",
    "free": "Makes these goods duty-free",
    "no_change": "Leaves the duty unchanged — it carves goods out of another provision",
    "prose": "States its rate in words rather than a number, so this site does not total it",
    "none": "Prints no rate of its own",
}

SCOPE = {
    "by_code": "Names the tariff codes it covers",
    "by_country_all_goods": "Names a country, and describes the goods in words rather than "
                            "by code",
    "unknown": "Does not say which goods it covers in any form this site could read",
}

STATUS = {
    "in_force": "In force",
    "terminated": "No longer in force",
    "suspended": "Suspended",
}

MATCH_KIND = {
    "exact": "that code exactly",
    "prefix": "a code filed beneath it",
}

MATCH_PRECISION = {
    "exact": "the subdivision it cites",
    "parent_fallback": "the whole note, which is wider than the subdivision it cites",
    "chapter_note": "a note kept in another chapter's document",
    "unresolved": "a note this site could not find",
}

READINGS = {
    "rate_kind": RATE_KIND, "scope": SCOPE, "status": STATUS,
    "match_kind": MATCH_KIND, "match_precision": MATCH_PRECISION,
}


def reading(field: str, value: str) -> str:
    """Put one stored enum value into words.

    Args:
        field: The column the value came from.
        value: The stored token.

    Returns:
        The sentence to print in its place.

    Raises:
        KeyError: The value has no wording. Deliberate — a value added to the schema has to be
            given words before it can reach a page, rather than leaking as a bare token.
    """
    return READINGS[field][value]
