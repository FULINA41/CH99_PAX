from datetime import date
from decimal import Decimal

import pycountry

from db import one, rows
from duty import queries
from duty.applicable import applicable
from duty.compute import ASSUMPTION, combine, term
from models import (BaseRate, Classification, DutyStack, ExclusionGroup, Layer, Query,
                    Term, Total, Unknown)
from reference.column2 import COLUMN_2_COUNTRIES, column_for
from reference.sources import UNKNOWNS

REDUCTION_PREFIX = "9902"

CEILING = (
    "The higher figure adds the provisions that name your country of origin but describe the "
    "goods they cover in words rather than by code. Whether any of them covers your shipment "
    "is a question about the goods, which this data cannot answer — read them and decide."
)


class NotClassified(LookupError):
    """No such code in the base schedule."""


def explain(
    hts: str,
    *,
    country_code: str | None = None,
    on_date: date | None = None,
    declared_value_usd: Decimal | None = None,
    quantity: Decimal | None = None,
) -> DutyStack:
    """Answer 'what does Chapter 99 do to this good from this country', showing the working.

    The layers are sorted into four piles rather than one list, because they are four
    different things and a reader who is shown them together has to do the sorting instead:
    duties that change the rate, reductions that stand in for it, exclusions that could
    remove one, and provisions not in force on the date asked about.

    Args:
        hts: A base schedule code.
        country_code: ISO 3166-1 alpha-2 country of origin. Without one, the provisions that
            key on origin cannot be judged, and an unknown says so.
        on_date: The date to judge each provision against. Defaults to today.
        declared_value_usd: For the ad valorem money.
        quantity: For specific duties. Without it they are left uncomputed, never zeroed.

    Returns:
        The whole answer, including what it could not settle.

    Raises:
        NotClassified: The code is not in the base schedule.
    """
    on_date = on_date or date.today()
    row = one(queries.CLASSIFICATION, {"hts": hts})
    if row is None:
        raise NotClassified(hts)

    column = column_for(country_code)
    base = _base_rate(row, column, declared_value_usd, quantity)
    other = _base_rate(row, "2" if column == "1-general" else "1-general",
                       declared_value_usd, quantity)

    found = applicable(hts, country_code, on_date,
                       declared_value_usd=declared_value_usd, quantity=quantity,
                       # Column 1 even on a Column 2 query: the condition names that column.
                       col1_pct=row["rate_ad_valorem_pct"])

    inactive = [layer for layer in found if layer.effectivity.standing != "in_force"]
    # A provision whose own sentence rules these goods out is not a duty that might apply; it
    # is one that does not. Removed before anything else is sorted, and shown with the words
    # that removed it.
    not_eligible = [layer for layer in found
                    if layer.effectivity.standing == "in_force"
                    and any(c.met is False for c in layer.conditions)]
    live = [layer for layer in found
            if layer.effectivity.standing == "in_force" and layer not in not_eligible]
    exclusions = [layer for layer in live if layer.term.operator == "no_change"]
    reductions = [layer for layer in live
                  if layer.hts.startswith(REDUCTION_PREFIX) and layer not in exclusions]
    rest = [layer for layer in live if layer not in exclusions and layer not in reductions]
    # A provision that arrived on the country alone has not been shown to cover these goods.
    # Its own description says what it covers -- "Aluminum articles that are the product of
    # Russia" -- in words the parser could not turn into codes, so it reaches every import
    # from that origin, steel included. Summing it would put 200% on the wrong shipment.
    origin_scoped = [layer for layer in rest if layer.scope == "by_country_all_goods"]
    # Bounded by an origin set this data cannot list, so it belongs with the range rather than
    # the figure -- the same treatment, for a different reason. D-0056.
    origin_unresolved = [layer for layer in rest
                         if layer.origin_scope == "unresolved" and layer not in origin_scoped]
    layers = [layer for layer in rest
              if layer not in origin_scoped and layer not in origin_unresolved]

    # Two provisions both standing in lieu of the base rate cannot both apply, and the
    # schedule does not choose between them -- 9903.45.01 and 9903.45.02 are a tariff-rate
    # quota's in-quota 14% and over-quota 30%, told apart by how much has been imported this
    # year. Keep the lowest in the figure and put the rest in the range. D-0058.
    replacements = [layer for layer in layers if layer.term.operator == "replace"]
    competing: list[Layer] = []
    if len(replacements) > 1:
        competing = sorted(replacements, key=_rate_of)[1:]
        layers = [layer for layer in layers if layer not in competing]

    expression, percent, specific, money = combine(
        base.term, layers, declared_value_usd=declared_value_usd)
    maybe = origin_scoped + origin_unresolved + competing
    ceiling = combine(base.term, _worst_case(base.term, layers, maybe),
                      declared_value_usd=declared_value_usd) if maybe else None

    return DutyStack(
        query=Query(
            hts=hts, country=country_code, country_name=_country_name(country_code),
            on_date=on_date, declared_value_usd=declared_value_usd, quantity=quantity,
            quantity_unit=(row["units"] or [None])[0],
        ),
        classification=Classification(
            hts=row["hts"], description=row["description"],
            full_description=row["full_description"], units=row["units"] or [],
            chain=row["ancestors"] or [],
        ),
        base_rate=base,
        column2=other if column == "1-general" else None,
        layers=layers,
        origin_scoped=origin_scoped,
        origin_unresolved=origin_unresolved,
        not_eligible=not_eligible,
        competing_replacements=competing,
        reductions=reductions,
        exclusions=_group_exclusions(exclusions),
        inactive=inactive,
        total=Total(
            expression=expression, ad_valorem_pct=percent, specific_terms=specific,
            amount_usd=money, assumption=ASSUMPTION,
            ceiling_expression=ceiling[0] if ceiling else None,
            ceiling_ad_valorem_pct=ceiling[1] if ceiling else None,
            ceiling_amount_usd=ceiling[3] if ceiling else None,
            ceiling_note=CEILING if ceiling else None,
        ),
        unknowns=_unknowns(base, layers, origin_scoped, origin_unresolved, competing,
                           reductions, exclusions, inactive, country_code, hts),
    )


# The two rate columns are not named symmetrically in hts_base -- Column 1 has
# rate_ad_valorem_pct, Column 2 has col2_ad_valorem_pct with no 'rate' in it -- so the columns
# are listed rather than built from a prefix. A prefix would compile and fail at runtime.
COLUMNS: dict[str, dict[str, str]] = {
    "1-general": {
        "kind": "rate_kind", "text": "rate_text", "pct": "rate_ad_valorem_pct",
        "amount": "rate_specific_amount", "unit": "rate_specific_unit",
        "inherited": "rate_inherited_from",
    },
    "2": {
        "kind": "col2_rate_kind", "text": "col2_rate_text", "pct": "col2_ad_valorem_pct",
        "amount": "col2_specific_amount", "unit": "col2_specific_unit",
        "inherited": "col2_inherited_from",
    },
}


def _base_rate(row, column: str, value: Decimal | None, quantity: Decimal | None) -> BaseRate:
    field = COLUMNS[column]
    return BaseRate(
        column=column,
        term=term(
            kind=row[field["kind"]] or "none",
            text=row[field["text"]],
            ad_valorem_pct=row[field["pct"]],
            specific_amount=row[field["amount"]],
            specific_unit=row[field["unit"]],
            is_base=True, declared_value_usd=value, quantity=quantity,
        ),
        inherited_from=row[field["inherited"]],
        # Special belongs to Column 1 only, and is never interpreted (D-0027).
        special_text=row["special_text"] if column == "1-general" else None,
    )


def _group_exclusions(exclusions: list[Layer]) -> list[ExclusionGroup]:
    # Grouped by the note that granted them, because that is the document a reader has to
    # open: 58 separate rows saying "covered by an exclusion granted by the USTR" is not
    # information, and one line per note with the count is.
    grouped: dict[tuple[int | None, str | None], list[str]] = {}
    for layer in exclusions:
        # The note the provision cites, not the one it matched by: these match on country and
        # have no note evidence at all, yet each names a different exclusion list.
        note = layer.cited_notes[0] if layer.cited_notes else None
        key = (note.note_id if note else None, note.label if note else None)
        grouped.setdefault(key, []).append(layer.hts)
    return [ExclusionGroup(note_id=note_id, note_label=label, provisions=sorted(provisions))
            for (note_id, label), provisions in sorted(grouped.items(), key=lambda kv: kv[0][1] or "")]


def _rate_of(layer: Layer) -> Decimal:
    # Compared on the percentage alone. A replacement carrying only a per-unit amount sorts as
    # zero, which is wrong in principle and affects no provision in this release -- every
    # replacement in Chapter 99 that competes with another states a percentage.
    return layer.term.ad_valorem_pct if layer.term.ad_valorem_pct is not None else Decimal(0)


def _worst_case(base: Term, layers: list[Layer], maybe: list[Layer]) -> list[Layer]:
    """The most a shipment could owe if every uncertain provision also covered it.

    Replacements are mutually exclusive -- U.S. note 1 says each applies *in lieu of* the
    ordinary rate, so two cannot both -- so the uncertain ones are not extra duties to pile
    on but **alternatives** to whatever already stands in for the base. Two ways that goes
    wrong, both found by the audit rather than by reasoning:

      * adding them all and letting the last one win reported 200% and "up to 40%" on
        0406.20.15.00 from Japan;
      * taking the highest of them still lowers the answer when nothing certain replaced the
        base and an uncertain provision would -- 2401.20.87.30 from Japan, floor 350%, and a
        40% alternative.

    An uncertain provision **not** applying is itself one of the cases, so a replacement joins
    the worst case only where it beats what the figure already rests on.

    Args:
        base: The base schedule term, which stands unless something certain replaced it.
        layers: The provisions counted in the figure.
        maybe: The ones that might also apply.

    Returns:
        Every addition from both, and at most one replacement: the highest, and only if it is
        higher than what the floor already uses.
    """
    candidates = layers + maybe
    replacements = [layer for layer in candidates if layer.term.operator == "replace"]
    additions = [layer for layer in candidates if layer.term.operator != "replace"]
    if not replacements:
        return additions

    certain = [layer for layer in layers if layer.term.operator == "replace"]
    floor_rate = _rate_of(certain[0]) if certain else (base.ad_valorem_pct or Decimal(0))
    highest = max(replacements, key=_rate_of)
    return additions + ([highest] if _rate_of(highest) >= floor_rate else certain)


def _unknowns(base, layers, origin_scoped, origin_unresolved, competing, reductions,
              exclusions, inactive, country_code, hts) -> list[Unknown]:
    # Only what this query actually raised. Listing all nine every time would train a reader
    # to skip the panel, and the one that matters here would go with it.
    keys: list[str] = ["classification"]
    if len(layers) > 1:
        keys.append("stacking")
    if origin_scoped:
        keys.append("origin_scoped")
    if origin_unresolved:
        keys.append("origin_unresolved")
    if competing:
        keys.append("competing_replacements")
    if exclusions:
        keys.append("exclusion")
    if len(reductions) > 1:
        keys.append("alternatives")
    if base.special_text:
        keys.append("special")
    if country_code is None or country_code in COLUMN_2_COUNTRIES:
        keys.append("column2")
    if inactive:
        keys.append("effectivity")
    if layers:
        keys.append("instrument")
    if any(e.note_precision == "parent_fallback" for layer in layers for e in layer.evidence):
        keys.append("scope_widened")

    related = {
        "stacking": [layer.hts for layer in layers],
        "exclusion": [layer.hts for layer in exclusions],
        "alternatives": [layer.hts for layer in reductions],
        "effectivity": [layer.hts for layer in inactive],
        "instrument": [layer.hts for layer in layers],
        "classification": [hts],
        "origin_scoped": [layer.hts for layer in origin_scoped],
        "origin_unresolved": [layer.hts for layer in origin_unresolved],
        "competing_replacements": [layer.hts for layer in competing],
        "scope_widened": [layer.hts for layer in layers
                          if any(e.note_precision == "parent_fallback" for e in layer.evidence)],
    }
    return [Unknown(**UNKNOWNS[key], related_hts=related.get(key, [])) for key in keys]


def _country_name(country_code: str | None) -> str | None:
    if not country_code:
        return None
    found = pycountry.countries.get(alpha_2=country_code.upper())
    return found.name if found else None
