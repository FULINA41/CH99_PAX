# Which countries pay the Column 2 rate rather than Column 1 General.
#
# EDITORIAL, and the reason is the same one D-0027 records for Column 1 Special: the list is
# in General Note 3(b) to the tariff schedule, and the three sources this project fetches --
# the chapter 1-97 export, the chapter 99 export, and the chapter 99 notes PDF -- contain no
# General Notes at all.
#
# Four entries, and the cost of leaving them out is not neutral: hts_base carries a parsed
# Column 2 rate for every row (D-0028), and 7208.51.00.30 is 'Free' in Column 1 and '20%' in
# Column 2. Saying nothing means answering 'Free' for a Russian shipment, which is wrong by
# the whole duty. Saying it with the note named is the smaller error, and it is one a reader
# can check in a minute.
GENERAL_NOTE = "General Note 3(b) to the Harmonized Tariff Schedule of the United States"
REFERENCE_URL = "https://hts.usitc.gov/reststop/currentRelease"

COLUMN_2_COUNTRIES: dict[str, str] = {
    "CU": "Cuba",
    "KP": "North Korea",
    "RU": "Russia",
    "BY": "Belarus",
}


def column_for(country_code: str | None) -> str:
    """Say which rate column a country of origin is read against.

    Args:
        country_code: ISO 3166-1 alpha-2, or None when the caller named no country.

    Returns:
        ``'2'`` for the four countries General Note 3(b) lists, ``'1-general'`` otherwise --
        which is a default, not a finding: normal trade relations is the general case, and
        this project cannot read the note that states the exceptions.
    """
    return "2" if country_code in COLUMN_2_COUNTRIES else "1-general"
