from decimal import Decimal

from conftest import layer
from duty.compute import combine, term


def base(kind: str = "free", pct: str = "0", **rest):
    return term(kind=kind, text="", ad_valorem_pct=Decimal(pct), is_base=True, **rest)


def test_a_specific_duty_without_a_quantity_is_left_uncomputed_rather_than_zeroed():
    # Treating the missing weight as zero would report $0 on a line charging 46.3c per kilo.
    priced = term(kind="replace", text="46.3c/kg", specific_amount=Decimal("0.463"),
                  specific_unit="kg", declared_value_usd=Decimal(100000))

    assert priced.amount_usd is None


def test_an_additive_duty_stacks_on_the_base_rate():
    expression, percent, _, money = combine(
        base("replace", "6.5"), [layer(pct="25")], declared_value_usd=Decimal(1000))

    assert (expression, percent, money) == ("31.5%", Decimal("31.5"), Decimal("315.00"))


def test_a_reduction_stands_in_for_the_base_rate_instead_of_adding_to_it():
    # 9902 provisions replace the duty; reading 'Free' as +0% would leave 6.5% standing.
    expression, percent, _, money = combine(
        base("replace", "6.5"), [layer(kind="free", pct="0")], declared_value_usd=Decimal(1000))

    assert (expression, percent, money) == ("Free", Decimal(0), Decimal("0.00"))


def test_an_exclusion_provision_changes_nothing_by_itself():
    # 'no_change' means the goods are carved out of a duty, not that a duty of zero applies.
    _, percent, _, _ = combine(base("replace", "6.5"), [layer(kind="no_change")])

    assert percent == Decimal("6.5")


def test_a_row_with_no_printed_rate_does_not_invent_one():
    # rate_kind 'none' is silence, not a duty written in words; saying otherwise would put
    # "plus a duty stated in words" on a superior heading that charges nothing.
    expression, _, _, _ = combine(base("replace", "6.5"), [layer(kind="none")])

    assert "words" not in expression


def test_a_rate_in_words_is_acknowledged_and_never_guessed_at():
    expression, _, _, money = combine(
        base("replace", "6.5"), [layer(kind="prose")], declared_value_usd=Decimal(1000))

    assert "words" in expression
    assert money is None


def test_a_percent_and_a_per_kilo_rate_are_not_collapsed_into_one_number():
    expression, percent, specific, money = combine(
        base("replace", "50", specific_amount=Decimal("0.154"), specific_unit="kg"),
        [layer(pct="25")], declared_value_usd=Decimal(1000))

    assert expression == "75% + $0.154/kg"
    assert specific == ["$0.154/kg"]
    # The shipment's weight is unknown, so no total can be honest.
    assert money is None


def test_a_bare_rate_under_a_cumulative_note_adds_instead_of_replacing():
    # U.S. note 52(a) says these headings "impose additional ad valorem rates of duty". Read
    # from the rate text alone, a bare "10%" is a replacement and wipes out the base.
    item = term(kind="replace", text="10%", ad_valorem_pct=Decimal("10"),
                cumulation="cumulative")

    assert item.operator == "add"


def test_a_bare_rate_under_the_in_lieu_default_still_replaces():
    item = term(kind="replace", text="10%", ad_valorem_pct=Decimal("10"), cumulation="in_lieu")

    assert item.operator == "replace"


def test_a_replacement_resolves_before_additions_whatever_order_it_arrives_in():
    # U.S. note 1 to subchapter III: a Chapter 99 rate applies "in lieu of the rate provided
    # therefor in chapters 1 to 98" -- it stands in for the base, never for another Chapter 99
    # duty. Iterating in heading order let a late replacement wipe out earlier additions.
    start = base(kind="replace", pct="6.5")
    add = layer("9903.88.15", kind="additive", pct="5")
    replace = layer("9903.05.39", kind="replace", pct="20")

    forwards = combine(start, [add, replace])[1]
    backwards = combine(start, [replace, add])[1]

    assert forwards == backwards == Decimal("25")
