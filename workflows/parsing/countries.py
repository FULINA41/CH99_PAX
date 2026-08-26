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

# A bloc is not a country and it is not unknowable either: the European Union's membership
# is a published list, so a provision reading "the product of a member state of the European
# Union" names 27 origins exactly. Recording NULL for it and stopping there is what let
# 9903.05.39 -- an EU-only provision replacing the base rate with 10% -- apply to a Chinese
# shipment, because the app reads "no country rows" as "no origin restriction". D-0056.
EUROPEAN_UNION = (
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE",
    "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
)

BLOCS: dict[str, tuple[str, ...]] = {"a member state of the european union": EUROPEAN_UNION}

# "any country" on its own, and the "or area including the United States" that the list
# splitter leaves behind, mean every origin -- the provision keys on origin and the answer
# is "all of them". "any country not exempt under U.S. note 41(c)", "any country identified
# in general note 3(b)" and "any country determined by CBP to have been transshipped" do
# not: each names a set this data cannot enumerate, and treating them as universal applies
# them to origins they exclude.
UNIVERSAL_ORIGIN = frozenset({"any country", "any country or area"})


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
    # The schedule prints the apostrophe in "Cote d'Ivoire" as a backtick on one line and a
    # curly quote on another; ISO carries the straight one. Normalising the punctuation is
    # the fix, not two more aliases -- an alias would say these are different names.
    cleaned = name.strip().replace("\u2019", "'").replace("`", "'").replace("\u2018", "'")
    for field in ("name", "common_name", "official_name"):
        found = pycountry.countries.get(**{field: cleaned})
        if found:
            return found.alpha_2
    return ALIASES.get(cleaned.lower())


def is_not_a_country(name: str) -> bool:
    return name.strip().lower() in NOT_A_COUNTRY


def bloc_members(phrase: str) -> tuple[str, ...]:
    """Expand a trading bloc named as an origin into its member countries.

    Names, not codes: everything downstream of the extractor works in the names the schedule
    prints, and handing it codes makes each one look like a country name that failed to
    resolve. The stored list is codes because those are what ISO keeps stable.

    Args:
        phrase: The origin as printed, e.g. ``'a member state of the European Union'``.

    Returns:
        The members' ISO country names, or an empty tuple when the phrase names no bloc this
        module knows.

    Raises:
        LookupError: A code in ``BLOCS`` is not in the ISO register.
    """
    codes = BLOCS.get(phrase.strip().lower(), ())
    names = []
    for code in codes:
        found = pycountry.countries.get(alpha_2=code)
        if found is None:
            raise LookupError(f"{code} is not an ISO 3166-1 alpha-2 code")
        names.append(found.name)
    return tuple(names)


def origin_scope(named: list[str], generic: set[str]) -> str:
    """Say how a provision limits the origins it reaches, from the phrases it printed.

    This is the column the duty query filters on, and the distinction it draws is the one
    that matters: a provision reaching *every* origin and a provision reaching a set we
    cannot list look identical in ``rule_country`` -- both have no rows -- and must not be
    treated identically.

    Args:
        named: Country names the provision printed, blocs already expanded.
        generic: Origin phrases that name no country.

    Returns:
        ``'none'`` if the provision does not key on origin; ``'any'`` if it keys on origin
        and reaches all of them; ``'named'`` if ``rule_country`` holds the answer;
        ``'unresolved'`` if it is bounded by something this data cannot enumerate.
    """
    unresolved = [phrase for phrase in generic
                  if phrase.strip().lower() not in UNIVERSAL_ORIGIN
                  and not phrase.strip().lower().startswith("area")
                  and not bloc_members(phrase)]
    if unresolved:
        return "unresolved"
    if named:
        return "named"
    if generic:
        return "any"
    return "none"
