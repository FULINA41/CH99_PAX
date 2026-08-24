import re
from dataclasses import dataclass

WHITESPACE = re.compile(r'\s+')

PERCENT = re.compile(r'^(\d+(?:\.\d+)?)\s*%$')
# '33 1/3%' is the schedule's way of writing a third; 84 rows use it.
FRACTION_PERCENT = re.compile(r'^(\d+)\s+(\d+)/(\d+)\s*%$')
AMOUNT = re.compile(
    r'^(?:(\$)(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*¢)\s*(?:/\s*(.+)|(each))$'
)

NO_CHANGE = ('no change', 'the duty provided in the applicable subheading')
ADDITIVE = re.compile(
    r'^the duty provided in\s*the applicable subheading\s*(?:\+|plus)\s*'
    r'(\d+(?:\.\d+)?)\s*%$',
    re.IGNORECASE,
)

KINDS = ('free', 'replace', 'additive', 'no_change', 'prose', 'none')


@dataclass(frozen=True)
class Rate:
    kind: str
    text: str | None
    ad_valorem_pct: float | None = None
    specific_amount: float | None = None
    specific_unit: str | None = None


def parse_rate(text: str | None) -> Rate:
    """Turn a printed duty rate into an operator and its operands.

    ``specific_amount`` is always in **dollars**: a rate printed in cents is divided by
    100, so ``46.3¢/kg`` and ``$1.104/kg`` can be compared and multiplied without
    re-reading ``text`` to find out which currency was meant.

    Args:
        text: The rate exactly as the schedule prints it.

    Returns:
        A ``Rate``. ``kind`` is the operator and the other fields are its operands:
        ``free`` (pct 0), ``replace``, ``additive``, ``no_change``, ``prose`` for a
        rate that cannot be computed, and ``none`` for an empty string. ``text``
        always keeps the original.
    """
    cleaned = WHITESPACE.sub(' ', (text or '').strip())
    if not cleaned:
        return Rate('none', None)

    lowered = cleaned.lower()
    if lowered == 'free':
        return Rate('free', cleaned, ad_valorem_pct=0.0)
    if lowered in NO_CHANGE:
        return Rate('no_change', cleaned)

    additive = ADDITIVE.match(cleaned)
    if additive:
        return Rate('additive', cleaned, ad_valorem_pct=float(additive.group(1)))

    # A compound rate is two operands joined by '+'. Three or more -- 94 strings do it,
    # e.g. copper + lead + zinc content -- needs a second amount column the schema does
    # not have, so it stays prose rather than being silently truncated to two.
    parts = [part.strip() for part in cleaned.split('+')]
    if len(parts) > 2:
        return Rate('prose', cleaned)

    operands = [_operand(part) for part in parts]
    if any(operand is None for operand in operands):
        return Rate('prose', cleaned)

    pct = amount = unit = None
    for operand in operands:
        if operand[0] == 'pct':
            if pct is not None:
                return Rate('prose', cleaned)
            pct = operand[1]
        else:
            if amount is not None:
                return Rate('prose', cleaned)
            amount, unit = operand[1], operand[2]

    return Rate('replace', cleaned, ad_valorem_pct=pct,
                specific_amount=amount, specific_unit=unit)


def _operand(part: str) -> tuple | None:
    match = PERCENT.match(part)
    if match:
        return ('pct', float(match.group(1)))

    match = FRACTION_PERCENT.match(part)
    if match:
        whole, numerator, denominator = (int(g) for g in match.groups())
        return ('pct', whole + numerator / denominator)

    match = AMOUNT.match(part)
    if match:
        dollar, dollars, cents, slash_unit, each = match.groups()
        amount = float(dollars) if dollar else float(cents) / 100
        return ('spec', amount, (slash_unit or each).strip())

    return None
