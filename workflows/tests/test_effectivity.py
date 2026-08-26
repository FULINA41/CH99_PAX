from datetime import date

from parsing.effectivity import parse_effectivity


def test_a_window_stated_with_through_includes_its_last_day():
    found = parse_effectivity(
        "Effective with respect to entries on or after June 4, 2020, and through "
        "December 31, 2020, articles the product of China")

    assert found.effective_from == date(2020, 6, 4)
    assert found.effective_to == date(2020, 12, 31)


def test_a_window_stated_with_before_ends_the_day_earlier():
    # 'and before January 1, 2026' means the last day in force is December 31, 2025.
    # Storing both forms as the last day is what lets a caller compare with <= alone.
    found = parse_effectivity(
        "Effective with respect to entries on or after January 1, 2025, and before "
        "January 1, 2026, articles the product of China")

    assert found.effective_to == date(2025, 12, 31)


def test_a_transit_carve_out_is_not_read_as_the_start_date():
    # 9903.01.51 exempts goods already at sea before a cut-off. A pattern looking for
    # 'on or after <date>' anywhere would report April 9 as the day the duty began.
    found = parse_effectivity(
        "Except for goods loaded onto a vessel at the port of loading and in transit on "
        "the final mode of transit before 12:01 a.m. eastern daylight time on April 9, "
        "2025, articles the product of Namibia")

    assert found.effective_from is None


def test_a_termination_with_no_date_still_stops_the_provision():
    # 36 provisions read exactly this and give no date; date columns alone leave them
    # looking current.
    found = parse_effectivity(
        "Articles the product of China "
        "[Compiler's note: provision terminated. See 90 Fed. Reg. 37963.]")

    assert found.status == "terminated"
    assert found.effective_to is None


def test_a_dated_termination_records_the_day_as_well_as_the_status():
    found = parse_effectivity("Bicycles [Compiler's note: provision terminated as of "
                              "February 7, 2026.]")

    assert (found.status, found.effective_to) == ("terminated", date(2026, 2, 7))


def test_a_suspension_is_kept_apart_from_a_termination():
    # 9903.01.63 is the 34% reciprocal rate on China, suspended rather than repealed.
    found = parse_effectivity("Articles the product of China "
                              "[Compiler's note: provision suspended. See 90 Fed. Reg. 50729.]")

    assert found.status == "suspended"


def test_the_federal_register_citation_survives_verbatim():
    # Our dataset holds the tariff line, not the instrument that made it. The citation is
    # the only thing a reader can follow, so it is kept as printed.
    found = parse_effectivity("x [Compiler's note: provision terminated. See 90 Fed. Reg. 37963.]")

    assert found.status_note == "provision terminated. See 90 Fed. Reg. 37963."


def test_an_abbreviated_month_parses_like_a_spelled_one():
    found = parse_effectivity("x [Compiler's note: Subheading was enacted; expired at the "
                              "close of Dec. 31, 2020.]")

    assert found.effective_to == date(2020, 12, 31)


def test_a_provision_saying_nothing_about_dates_is_in_force():
    found = parse_effectivity("Articles the product of Mexico, as provided for in U.S. note 2(a)")

    assert (found.status, found.effective_from, found.effective_to) == ("in_force", None, None)
