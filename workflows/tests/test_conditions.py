from decimal import Decimal

from parsing.conditions import parse_conditions, satisfied


def condition(text):
    return parse_conditions(text)[0]


def test_a_threshold_stated_on_the_base_rate_is_read_with_its_comparator():
    found = condition("articles the product of a member state of the European Union, with an "
                      "ad valorem (or ad valorem equivalent) rate of duty under column 1 less "
                      "than 10 percent, as provided for in U.S. note 52")

    assert (found.operator, found.value) == ("lt", Decimal("10"))


def test_the_complementary_form_is_read_as_the_other_comparator():
    # The schedule states these in pairs -- less than 15 / equal to or greater than 15 -- and
    # reading both as the same comparator would apply both halves to every good.
    found = condition("articles with an ad valorem rate of duty under column 1 equal to or "
                      "greater than 15 percent")

    assert (found.operator, found.value) == ("gte", Decimal("15"))


def test_a_provision_stating_no_condition_yields_none():
    assert parse_conditions("Articles the product of China, as provided for in U.S. note 20(b)") == []


def test_a_good_above_the_threshold_fails_a_less_than_condition():
    # 6109.10.00.12 is 16.5%, and 9903.05.39 covers goods under 10%. Applying it anyway
    # replaced that 16.5% base with 10% and understated the duty by a third.
    assert satisfied(condition("rate of duty under column 1 less than 10 percent"),
                     Decimal("16.5")) is False


def test_a_good_below_the_threshold_meets_it():
    assert satisfied(condition("rate of duty under column 1 less than 10 percent"),
                     Decimal("6.5")) is True


def test_a_base_rate_stated_in_words_leaves_the_condition_unjudged_rather_than_met():
    # 305 base rows carry a rate that is a sentence. Treating "cannot be judged" as "passes"
    # is the failure this whole change exists to remove.
    assert satisfied(condition("rate of duty under column 1 less than 10 percent"), None) is None
