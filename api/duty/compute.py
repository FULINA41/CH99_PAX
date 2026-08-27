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

# `rate_kind` reads the rate text; `cumulation` reads the note that governs it. They answer
# different halves of the same question and the schedule expects both to be read.
#
# A rate printed as "The duty provided in the applicable subheading + 7.5%" names the base and
# is additive whatever any note says -- that is note 1's "unless the context requires
# otherwise", and 62 provisions are in exactly that position. A rate printed as a bare "10%"
# is silent about the base, and then the note decides: U.S. note 52(a) says headings
# 9903.05.20-9903.05.84 "impose ADDITIONAL ad valorem rates of duty" and that products "shall
# ALSO be subject to the general rates of duty imposed under subheadings in chapters 1 to 97",
# so that 10% is charged on top rather than instead. Reading the rate text alone made it a
# replacement and wiped out the base. 18 provisions. D-0058.
CUMULATIVE_INSTEAD: dict[str, str] = {"replace": "add", "free": "add"}

ASSUMPTION = (
    "Assumes every duty in this figure applies at once and that none of the exclusions covers "
    "your goods. The schedule states how each duty combines with the ordinary rate — that is "
    "read here — but which 9903 line goes on which entry line is set by CBP in its filing "
    "instructions, and that is not in this data."
)

# combine() is never handed the reductions, so the figure is silent about them. A page that
# lists 34 and says "every duty listed applies at once" contradicts its own section heading.
REDUCTIONS_ASIDE = (
    " The duty reductions below are alternatives to the base rate rather than additions to it, "
    "so they are not in this figure — which one applies, if any, depends on what the goods are."
)


def assumption(reductions: list[Layer]) -> str:
    """Say what the figure took for granted, raising only what this query actually has.

    Args:
        reductions: The subchapter II provisions found for the query, which never reach
            ``combine`` and so need saying that the total left them out.

    Returns:
        The sentence printed under the total.
    """
    return ASSUMPTION + (REDUCTIONS_ASIDE if reductions else "")


def term(
    *,
    kind: RateKind,
    text: str | None,
    ad_valorem_pct: Decimal | None = None,
    specific_amount: Decimal | None = None,
    specific_unit: str | None = None,
    is_base: bool = False,
    cumulation: str = "unstated",
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
        cumulation: What the governing U.S. note says about how this rate combines with the
            rate in chapters 1 to 98. Promotes a bare rate from a replacement to an addition,
            and is ignored for a rate that already names the base.
        declared_value_usd: Shipment value, for the ad valorem part.
        quantity: Shipment quantity, for the specific part.

    Returns:
        The term. ``amount_usd`` is None whenever it cannot be computed honestly -- in
        particular a specific duty with no quantity, which is an unknown and never a zero.
    """
    operator = "base" if is_base else OPERATORS[kind]
    if not is_base and cumulation == "cumulative":
        operator = CUMULATIVE_INSTEAD.get(operator, operator)

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
        layers: The Chapter 99 provisions in force. Order does not matter: this sorts them
            by what each operator acts on, which is what the notes settle.
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

    # Ordered by what each operator acts on, not by heading number. U.S. note 1 to subchapter
    # III says a Chapter 99 rate applies "in lieu of the rate provided therefor in chapters 1
    # to 98" -- it stands in for the BASE, never for another Chapter 99 duty -- while a
    # cumulative duty applies "in addition to the duties otherwise imposed", which includes
    # whatever replaced the base. So replacements resolve first and additions go on top, and
    # addition commutes so nothing below that depends on order. Iterating in `ORDER BY hts`
    # let a replacement that happened to sort late wipe out additions already applied: 346 of
    # 2,160 sampled queries were order-dependent. D-0058.
    for layer in sorted(layers, key=lambda l: l.term.operator != "replace"):
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
