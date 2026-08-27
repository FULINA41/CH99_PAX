import re

from reference.sources import UNKNOWNS

TARIFF_CODE = re.compile(r"\d{4}\.\d{2}")


def test_no_unknown_names_a_tariff_code_it_cannot_know_is_the_reader_s():
    # UNKNOWNS is static and renders on every query that raises the key, so a code written
    # into the prose is asserted about codes it has nothing to do with: the 'alternatives'
    # entry told a reader looking at 3808.92.15.00 that "four provisions cite 2922.49.30".
    named = {key: TARIFF_CODE.findall(entry["why"]) for key, entry in UNKNOWNS.items()}

    assert {key: found for key, found in named.items() if found} == {}
