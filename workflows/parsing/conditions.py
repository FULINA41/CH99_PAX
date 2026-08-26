"""Eligibility conditions a provision states in its own prose.

``rate_kind`` says what a provision does to the duty; ``rule_country`` says which origins it
reaches; ``effective_from`` says when. Nothing said **on what terms**, and 31 provisions state
one: they apply only where the base rate is above or below a threshold. Unread, they applied
regardless -- `9903.05.39` replaced a 16.5% base with 10% while its own text says it covers
goods "with an ad valorem rate of duty under column 1 less than 10 percent". D-0057.

The phrasing is regular: two comparators and three thresholds across all 31, and they come in
complementary pairs (less than 15 / equal to or greater than 15), which is the check that the
extraction is reading the schedule rather than a pattern in it.
"""

import re
from dataclasses import dataclass
from decimal import Decimal

KIND = "col1_rate"

CONDITION = re.compile(
    r"rate of duty under column 1\s+"
    r"(?P<compare>less than|equal to or greater than)\s+"
    r"(?P<value>\d+(?:\.\d+)?)\s+percent",
    re.IGNORECASE)

COMPARATORS = {"less than": "lt", "equal to or greater than": "gte"}


@dataclass(frozen=True)
class Condition:
    kind: str
    operator: str
    value: Decimal
    verbatim: str


def parse_conditions(text: str) -> list[Condition]:
    """Read the eligibility conditions a provision states about the base rate.

    Args:
        text: The provision's full description.

    Returns:
        One Condition per distinct threshold stated, in the order printed. Empty when the
        provision states none, which is the common case.
    """
    found: list[Condition] = []
    seen: set[tuple[str, str, Decimal]] = set()

    for match in CONDITION.finditer(text):
        operator = COMPARATORS[match.group("compare").lower()]
        value = Decimal(match.group("value"))
        key = (KIND, operator, value)
        if key in seen:
            continue
        seen.add(key)
        found.append(Condition(KIND, operator, value, match.group(0)))

    return found


def satisfied(condition: Condition, col1_pct: Decimal | None) -> bool | None:
    """Judge one condition against a base rate.

    Args:
        condition: The condition as parsed.
        col1_pct: The Column 1 General ad valorem rate of the classified good, or None when
            that rate is a sentence rather than a number.

    Returns:
        True or False, or None when the base rate is not a percentage and so the condition
        cannot be judged either way -- which is an unknown, not a pass.
    """
    if col1_pct is None:
        return None
    return col1_pct < condition.value if condition.operator == "lt" else col1_pct >= condition.value
