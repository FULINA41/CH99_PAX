from decimal import Decimal

from models import Layer, RateKind, Term

# rate_kind is an operator and the columns beside it are its operands (D-0013). What it does
# to the running rate depends on whether it is the base row or a Chapter 99 provision:
# a base row always *is* the rate, while a provision either replaces it or adds to it.
OPERATORS: dict[RateKind, str] = {
    "free": "replace",
    "replace": "replace",
    "additive": "add",
    "no_change": "no_change",
    # A rate written as a sentence: there IS a duty and we cannot compute it.
    "prose": "unknown",
    # No rate printed at all -- a superior heading, or a row whose children carry the rates.
    # It changes nothing, and saying "a duty stated in words" about it would invent one.
    "none": "no_change",
}

ASSUMPTION = (
    "Assumes every duty listed applies at once and that none of the exclusions covers your "
    "goods. Stacking order is set by CBP in its filing instructions, not by the tariff "
    "schedule, so it is not in this data."
)


def term(
    *,
    kind: RateKind,
    text: str | None,
    ad_valorem_pct: Decimal | None = None,
    specific_amount: Decimal | None = None,
    specific_unit: str | None = None,
    is_base: bool = False,
    declared_value_usd: Decimal | None = None,
    quantity: Decimal | None = None,
) -> Term:
    """Turn one stored rate into a formula term, with its money if the money is knowable.

    Args:
        kind: The stored ``rate_kind``.
        text: The rate as the schedule printed it.
        ad_valorem_pct: Percent operand.
        specific_amount: Per-unit operand, already in dollars.
        specific_unit: What that amount is per, including any qualification the schedule
            attached -- 'clean kg' is not 'kg' and a calculator handed the plain unit
            overcharges.
        is_base: True for the base schedule row, which is the rate rather than a change to it.
        declared_value_usd: Shipment value, for the ad valorem part.
        quantity: Shipment quantity, for the specific part.

    Returns:
        The term. ``amount_usd`` is None whenever it cannot be computed honestly -- in
        particular a specific duty with no quantity, which is an unknown and never a zero.
    """
    operator = "base" if is_base else OPERATORS[kind]

    money: Decimal | None = None
    if declared_value_usd is not None and ad_valorem_pct is not None:
        money = (declared_value_usd * ad_valorem_pct / Decimal(100)).quantize(Decimal("0.01"))
    if specific_amount is not None:
        if quantity is None:
            # Refusing here is the point. Treating a missing quantity as zero would report a
            # duty of $0 on a line that charges 46.3 cents a kilo.
            money = None
        else:
            specific = (specific_amount * quantity).quantize(Decimal("0.01"))
            money = specific if money is None else (money + specific).quantize(Decimal("0.01"))

    return Term(
        operator=operator,
        text=text or "",
        ad_valorem_pct=ad_valorem_pct,
        specific_amount=specific_amount,
        specific_unit=specific_unit,
        amount_usd=money,
    )


def combine(base: Term, layers: list[Layer], *, declared_value_usd: Decimal | None = None):
    """Work the formula out: the base rate, what replaces it, and what stacks on top.

    Terms that share no unit are not collapsed. A percentage and a rate per kilogram are two
    numbers however the page is laid out, so the result carries both and the expression says
    so -- '25% + 46.3c/kg' is the answer, and inventing a single number would be a fiction.

    Args:
        base: The base schedule term.
        layers: The Chapter 99 provisions in force, in the order they should be read.
        declared_value_usd: Shipment value, for the ad valorem total.

    Returns:
        ``(expression, ad_valorem_pct, specific_terms, amount_usd)``. The percent is None when
        no term in the stack carries one; the amount is None when any part of it is unknown.
    """
    percent: Decimal | None = base.ad_valorem_pct
    specific: list[str] = []
    if base.specific_amount is not None:
        specific.append(_printed(base))

    unknown = base.operator == "unknown"

    for layer in layers:
        item = layer.term
        if item.operator == "no_change":
            continue
        if item.operator == "unknown":
            unknown = True
            continue
        if item.operator == "replace":
            # A subchapter II provision does not add to the base rate; it stands in for it.
            percent = item.ad_valorem_pct
            specific = [_printed(item)] if item.specific_amount is not None else []
        elif item.operator == "add":
            percent = (percent or Decimal(0)) + (item.ad_valorem_pct or Decimal(0))
            if item.specific_amount is not None:
                specific.append(_printed(item))

    parts: list[str] = []
    if percent is not None:
        parts.append("Free" if percent == 0 and not specific else f"{_plain(percent)}%")
    parts.extend(specific)
    if unknown:
        parts.append("plus a duty stated in words")

    money: Decimal | None = None
    if declared_value_usd is not None and percent is not None and not specific and not unknown:
        money = (declared_value_usd * percent / Decimal(100)).quantize(Decimal("0.01"))

    return " + ".join(parts) or "no rate found", percent, specific, money


def _printed(item: Term) -> str:
    return f"${_plain(item.specific_amount)}/{item.specific_unit or 'unit'}"


def _plain(number: Decimal) -> str:
    # normalize() strips trailing zeros but writes 50 as 5E+1, which no reader wants; the
    # 'f' format expands it back without reintroducing them.
    return f"{number.normalize():f}"
