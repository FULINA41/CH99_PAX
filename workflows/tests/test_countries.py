from parsing.countries import country_code, is_not_a_country


def test_a_name_the_iso_register_carries_verbatim_resolves():
    assert country_code("Germany") == "DE"


def test_a_name_the_register_carries_under_a_common_name_resolves():
    # ISO lists it as 'Taiwan, Province of China'.
    assert country_code("Taiwan") == "TW"


def test_a_country_the_register_renamed_resolves_through_the_alias_table():
    # ISO 3166 renamed Turkey to Türkiye in 2022; the schedule still prints Turkey.
    assert country_code("Turkey") == "TR"


def test_two_spellings_of_one_country_reach_the_same_code():
    # Section 232 steel sits on 'Russian Federation' and IEEPA on 'Russia'; without this
    # a query for one silently misses the other's rules.
    assert country_code("Russia") == country_code("Russian Federation") == "RU"


def test_a_bloc_is_not_given_a_country_code():
    assert country_code("European Union") is None
    assert is_not_a_country("European Union")


def test_an_unrecognised_name_is_not_a_bloc_and_so_is_reportable():
    assert country_code("Freedonia") is None
    assert not is_not_a_country("Freedonia")


def test_the_two_apostrophes_the_schedule_prints_reach_the_same_code():
    # The schedule prints Cote d'Ivoire with a backtick on one line and a curly quote on
    # another; ISO carries the straight one. Normalising is the fix, not two aliases.
    assert country_code("C\u00f4te d`Ivoire") == country_code("C\u00f4te d\u2019Ivoire") == "CI"
