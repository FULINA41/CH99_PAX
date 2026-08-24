import pycountry

# D-0032. Names the schedule prints that the ISO register carries differently. Every entry is a
# rename or an inversion inside ISO 3166 itself, checkable against the register -- not a
# judgement about which country was meant.
ALIASES = {
    "russia": "RU",                            # ISO name: 'Russian Federation'
    "turkey": "TR",                            # ISO renamed it 'Türkiye' in 2022
    "democratic republic of the congo": "CD",  # ISO inverts: 'Congo, The Democratic Republic of the'
    "brunei": "BN",                            # ISO name: 'Brunei Darussalam'
    "falkland islands": "FK",                  # ISO name: 'Falkland Islands (Malvinas)'
}

# Named as an origin by the schedule, but not a country, so a NULL code is the right
# answer rather than a failure. Listed so that an unrecognised name stays distinguishable
# from one that legitimately has no code.
NOT_A_COUNTRY = frozenset({"european union"})


def country_code(name: str) -> str | None:
    """Resolve a country named in the schedule to its ISO 3166-1 alpha-2 code.

    Exact lookups against the ISO register only. ``pycountry.search_fuzzy`` would resolve
    three more names here, but it guesses: it happens to map 'Russia' correctly today and
    nothing about it guarantees the next unfamiliar name lands on the right neighbour.
    Those three are handled by ``ALIASES`` instead, where the reason is written down.

    Args:
        name: The country as extracted, article already stripped.

    Returns:
        The alpha-2 code, or None if the name is not a country (``European Union``) or is
        not in the register under any of its ISO names.
    """
    cleaned = name.strip()
    for field in ("name", "common_name", "official_name"):
        found = pycountry.countries.get(**{field: cleaned})
        if found:
            return found.alpha_2
    return ALIASES.get(cleaned.lower())


def is_not_a_country(name: str) -> bool:
    return name.strip().lower() in NOT_A_COUNTRY
