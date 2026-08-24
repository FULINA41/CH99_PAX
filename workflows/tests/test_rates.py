import pytest

from parsing.rates import parse_rate


@pytest.mark.parametrize("text, kind", [
    ("Free", "free"),
    ("2.5%", "replace"),
    ("14.27¢/liter", "replace"),
    ("4.4¢/kg + 8.5%", "replace"),
    ("No change", "no_change"),
    ("The duty provided in the applicable subheading", "no_change"),
    ("The duty provided in the applicable subheading + 25%", "additive"),
    ("The rate applicable to each garment in the set", "prose"),
    ("", "none"),
])
def test_the_operator_is_read_from_the_printed_rate(text, kind):
    assert parse_rate(text).kind == kind


def test_cents_are_converted_to_dollars_so_amounts_are_comparable():
    # 46.3¢/kg and $1.104/kg must be multipliable without re-reading the symbol.
    assert parse_rate("46.3¢/kg").specific_amount == pytest.approx(0.463)
    assert parse_rate("$1.104/kg").specific_amount == pytest.approx(1.104)


def test_a_compound_rate_keeps_both_operands():
    rate = parse_rate("4.4¢/kg + 8.5%")

    assert (rate.specific_amount, rate.specific_unit, rate.ad_valorem_pct) == (
        pytest.approx(0.044), "kg", 8.5)


def test_a_three_part_rate_is_prose_rather_than_a_truncated_pair():
    # Storing only two of three operands would understate the duty silently.
    rate = parse_rate("8.8¢/kg on copper content + 3.3¢/kg on lead content "
                      "+ 3.7¢/kg on zinc content")

    assert rate.kind == "prose"
    assert rate.specific_amount is None


def test_a_qualified_basis_stays_in_the_unit_instead_of_being_dropped():
    # 'kg on drained weight' is not 'kg'; a calculator given plain kg would overcharge.
    assert parse_rate("7.4¢/kg on drained weight").specific_unit == "kg on drained weight"


def test_a_fractional_percentage_is_computed_not_abandoned():
    assert parse_rate("33 1/3%").ad_valorem_pct == pytest.approx(100 / 3)


@pytest.mark.parametrize("text", [
    "The duty provided in the applicable subheading + 25%",
    "The duty provided in the applicable subheading plus 25%",
    "The duty provided inthe applicable subheading+ 25%",
])
def test_every_spelling_of_the_additive_form_yields_the_same_operand(text):
    # The third is a typo in the published data, not a different rule.
    rate = parse_rate(text)

    assert (rate.kind, rate.ad_valorem_pct) == ("additive", 25.0)


def test_the_printed_text_survives_a_rate_that_cannot_be_parsed():
    assert parse_rate("See additional U.S. note 1").text == "See additional U.S. note 1"


# 'a duty of' is a wording variant of '+ 25%', but only when the percentage is the whole
# operand. '25% upon the value of the non-U.S. content' applies to a different basis, and
# storing it as a plain 25% would overcharge the full entered value (D-0026).
def test_a_duty_of_is_read_as_an_ordinary_additive_rate():
    rate = parse_rate("The duty provided in the applicable subheading + a duty of 25%")

    assert rate.kind == "additive"
    assert rate.ad_valorem_pct == 25.0


def test_an_additive_rate_on_a_narrower_basis_stays_unparsed():
    rate = parse_rate(
        "The duty provided in the applicable subheading + a duty of 25% upon the "
        "value of the non-U.S. content"
    )

    assert rate.kind == "prose"
    assert rate.ad_valorem_pct is None
