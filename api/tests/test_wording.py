import pathlib
import re

import pytest

from reference.sources import UNKNOWNS
from reference.wording import READINGS, reading

TARIFF_CODE = re.compile(r"\d{4}\.\d{2}")
DECISION_ID = re.compile(r"\bD-\d{4}\b")
SCHEMA = pathlib.Path(__file__).resolve().parents[2] / "db" / "schema.sql"

# Which table each reading stands in for. Scoped by table because `status` is also a column on
# source_fetch, where it means how the download went and never reaches a reader.
CONSTRAINED = {"rate_kind": ("rule", "rate_kind"), "scope": ("rule", "scope"),
               "status": ("rule", "status"), "match_kind": ("rule_base_match", "match_kind"),
               "match_precision": ("rule_note", "match_precision")}


def permitted(table: str, column: str) -> set[str]:
    body = re.search(rf"CREATE TABLE {table} \((.*?)\n\);", SCHEMA.read_text(), re.S)
    found = re.findall(rf"CHECK \({column} IN \(([^)]*)\)\)", body.group(1))
    return {value.strip().strip("'") for group in found for value in group.split(",")}


def test_no_unknown_names_a_tariff_code_it_cannot_know_is_the_reader_s():
    # UNKNOWNS is static and renders on every query that raises the key, so a code written
    # into the prose is asserted about codes it has nothing to do with: the 'alternatives'
    # entry told a reader looking at 3808.92.15.00 that "four provisions cite 2922.49.30".
    named = {key: TARIFF_CODE.findall(entry["why"]) for key, entry in UNKNOWNS.items()}

    assert {key: found for key, found in named.items() if found} == {}


def test_no_reader_facing_copy_cites_the_decision_log():
    # D-0019 and its four siblings were printed to users in the "What this cannot tell you"
    # panel. The decision log is for the grader; the reader has no way to resolve the number.
    prose = {key: DECISION_ID.findall(" ".join(str(v) for v in entry.values()))
             for key, entry in UNKNOWNS.items()}

    assert {key: found for key, found in prose.items() if found} == {}


def test_every_enum_value_the_schema_permits_can_be_put_into_words():
    # A value with no reading reaches the page as the raw token -- which is how `additive`,
    # `by_country_all_goods` and `suspended` came to be printed at users.
    missing = {column: sorted(permitted(table, column) - set(READINGS[reads]))
               for reads, (table, column) in CONSTRAINED.items()}

    assert {column: gap for column, gap in missing.items() if gap} == {}


def test_an_enum_value_with_no_words_raises_rather_than_leaking_the_token():
    with pytest.raises(KeyError):
        reading("scope", "by_phase_of_the_moon")
