from parsing.countries import bloc_members, origin_scope, country_code, is_not_a_country


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


def test_a_bloc_named_as_an_origin_expands_to_members_the_register_recognises():
    members = bloc_members("a member state of the European Union")

    assert len(members) == 27
    assert [name for name in members if country_code(name) is None] == []


def test_a_provision_bounded_to_a_bloc_is_named_rather_than_unrestricted():
    # 9903.05.39 reaches only EU origins. Recorded as unrestricted it replaced the base rate
    # of a Chinese shipment with 10%.
    assert origin_scope(list(bloc_members("a member state of the European Union")),
                        {"a member state of the European Union"}) == "named"


def test_a_provision_reaching_every_origin_is_not_filtered_by_country():
    assert origin_scope([], {"any country"}) == "any"


def test_a_qualifier_on_any_country_makes_the_origin_set_unresolved():
    # "any country not exempt under U.S. note 41(c)" is bounded by a list this data does not
    # contain, and is the opposite of "any country" however similarly it reads.
    assert origin_scope([], {"any country not exempt"}) == "unresolved"


def test_a_provision_naming_no_origin_at_all_is_not_origin_keyed():
    assert origin_scope([], set()) == "none"
