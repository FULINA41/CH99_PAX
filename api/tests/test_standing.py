from datetime import date

from duty.applicable import standing

TODAY = date(2026, 8, 26)


def provision(**overrides):
    row = {"status": "in_force", "status_note": None,
           "effective_from": None, "effective_to": None}
    return row | overrides


def test_a_provision_that_starts_later_is_not_yet_in_force():
    # 9903.91.14 begins on 2026-11-10; showing it today as applicable is a wrong answer.
    found = standing(provision(effective_from=date(2026, 11, 10)), TODAY)

    assert found.standing == "not_yet"


def test_a_provision_whose_window_closed_is_expired():
    found = standing(provision(effective_from=date(2020, 6, 4),
                               effective_to=date(2020, 12, 31)), TODAY)

    assert found.standing == "expired"


def test_a_termination_with_no_dates_still_stops_the_provision():
    # 36 provisions read "provision terminated. See 90 Fed. Reg. 37963." and give no date,
    # so a window alone would leave every one of them looking current.
    found = standing(provision(status="terminated"), TODAY)

    assert found.standing == "stopped"


def test_standing_is_judged_against_the_date_asked_about_not_today():
    row = provision(effective_from=date(2024, 9, 27))

    assert standing(row, date(2020, 8, 1)).standing == "not_yet"
    assert standing(row, TODAY).standing == "in_force"


def test_a_provision_stating_no_dates_at_all_is_in_force():
    assert standing(provision(), TODAY).standing == "in_force"
