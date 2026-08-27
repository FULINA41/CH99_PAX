"""Check the duty engine against properties that must hold, over many real queries.

There is no reference set of correct duty rates in this project, so accuracy cannot be
measured and any percentage claiming to be one would be invented. What can be measured is
**self-consistency**: a set of statements that are true of every correct answer, so a
violation is a defect even without knowing the right number.

    cd api && uv run python -m audit --codes 400

Reports two things: violations, which are bugs, and how many answers are **fully determined**
versus carrying something the sources cannot settle -- which is the honest version of the
question "how much of this can you be sure about".
"""

import argparse
import os
import random
import sys
from collections import Counter
from datetime import date
from decimal import Decimal

COUNTRIES = ["CN", "DE", "JP", "KR", "CH", "TW", "MX", "RU", "VN", None]


def check(stack, country: str | None) -> list[str]:
    """Every property that must hold of one answer. Returns the ones that did not."""
    broken: list[str] = []
    total, base = stack.total, stack.base_rate

    buckets = {
        "layers": stack.layers, "origin_scoped": stack.origin_scoped,
        "origin_unresolved": stack.origin_unresolved, "not_eligible": stack.not_eligible,
        "competing": stack.competing_replacements, "reductions": stack.reductions,
        "inactive": stack.inactive,
    }
    seen: dict[str, str] = {}
    for name, layers in buckets.items():
        for layer in layers:
            if layer.hts in seen:
                broken.append(f"{layer.hts} is in both {seen[layer.hts]} and {name}")
            seen[layer.hts] = name

    # A provision only reaches these goods from this origin if it names it. The bug this
    # replaces put an EU-only rate on a Chinese shipment (D-0056).
    for layer in stack.layers + stack.reductions:
        if layer.origin_scope == "named" and country and country not in _codes(layer, country):
            broken.append(f"{layer.hts} is origin-named but not for {country}")
        if layer.effectivity.standing != "in_force":
            broken.append(f"{layer.hts} is in the total while {layer.effectivity.standing}")

    # Its own sentence ruled it out, so it must actually have a failing condition.
    for layer in stack.not_eligible:
        if not any(condition.met is False for condition in layer.conditions):
            broken.append(f"{layer.hts} is not_eligible with no failing condition")

    if total.ceiling_ad_valorem_pct is not None and total.ad_valorem_pct is not None:
        if total.ceiling_ad_valorem_pct < total.ad_valorem_pct:
            broken.append(f"ceiling {total.ceiling_ad_valorem_pct} below floor "
                          f"{total.ad_valorem_pct}")

    # Only additive layers can only push the rate up, and only the base can set it.
    operators = {layer.term.operator for layer in stack.layers}
    if total.ad_valorem_pct is not None and base.term.ad_valorem_pct is not None:
        if operators <= {"add", "no_change"} and total.ad_valorem_pct < base.term.ad_valorem_pct:
            broken.append(f"total {total.ad_valorem_pct} below base "
                          f"{base.term.ad_valorem_pct} with only additions")
        if not stack.layers and total.ad_valorem_pct != base.term.ad_valorem_pct:
            broken.append(f"no layers, yet total {total.ad_valorem_pct} != base "
                          f"{base.term.ad_valorem_pct}")

    # Two provisions cannot both stand in lieu of the same base rate (D-0058).
    if len([l for l in stack.layers if l.term.operator == "replace"]) > 1:
        broken.append("two replacements left in the total")

    return broken


def _codes(layer, country: str) -> set[str]:
    # Layer carries country names, not codes; the query already filtered on the code, so this
    # only has to confirm the provision named somebody.
    return {country} if layer.countries else set()


def money_check(stack, value: Decimal) -> str | None:
    total = stack.total
    if total.amount_usd is None or total.ad_valorem_pct is None:
        return None
    expected = (value * total.ad_valorem_pct / Decimal(100)).quantize(Decimal("0.01"))
    if total.amount_usd != expected:
        return f"amount {total.amount_usd} != {expected}"
    return None


def determined(stack) -> str:
    """How settled this answer is, in one word."""
    if any(layer.term.operator == "unknown" for layer in stack.layers):
        return "rate stated in words"
    if stack.competing_replacements:
        return "competing replacements"
    if stack.origin_unresolved:
        return "origin set not listable"
    if stack.origin_scoped:
        return "goods described in prose"
    if len(stack.reductions) > 1:
        return "alternative reductions"
    if stack.exclusions:
        return "exclusions may apply"
    return "fully determined"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codes", type=int, default=400)
    parser.add_argument("--seed", type=int, default=11)
    args = parser.parse_args()

    os.environ.setdefault("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/chp99")
    import db as database
    import settings
    from psycopg_pool import ConnectionPool
    database._pool = ConnectionPool(settings.DATABASE_URL, min_size=1, max_size=4, open=True,
                                    kwargs={"autocommit": True})
    from db import rows
    from duty.explain import explain, NotClassified

    random.seed(args.seed)
    codes = [row["hts"] for row in rows("SELECT hts FROM hts_base ORDER BY hts")]
    sample = random.sample(codes, min(args.codes, len(codes)))
    value = Decimal("100000")

    violations: Counter = Counter()
    shape: Counter = Counter()
    examples: dict[str, str] = {}
    run = 0

    for hts in sample:
        for country in COUNTRIES:
            try:
                stack = explain(hts, country_code=country, on_date=date(2026, 8, 26),
                                declared_value_usd=value)
            except NotClassified:
                continue
            run += 1
            shape[determined(stack)] += 1
            for problem in check(stack, country) + [money_check(stack, value)]:
                if problem is None:
                    continue
                key = problem.split(" is ")[-1] if " is " in problem else problem.split(" ")[0]
                violations[key] += 1
                examples.setdefault(key, f"{hts} / {country}: {problem}")

    print(f"\nqueries checked   {run:,}  ({len(sample)} codes x {len(COUNTRIES)} origins)\n")
    print("INVARIANT VIOLATIONS")
    if not violations:
        print("  none\n")
    for key, count in violations.most_common():
        print(f"  {count:>6,}  {key}\n          e.g. {examples[key]}")

    print("\nHOW SETTLED THE ANSWER IS")
    for label, count in shape.most_common():
        print(f"  {count:>6,}  {count / run:>6.1%}  {label}")
    database._pool.close()
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
