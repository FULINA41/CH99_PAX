from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from db import rows
from duty import queries
from duty.compute import term
from models import CitedNote, Condition, Effectivity, Evidence, Layer, Programme


def applicable(
    hts: str,
    country_code: str | None,
    on_date: date,
    *,
    declared_value_usd: Decimal | None = None,
    quantity: Decimal | None = None,
    col1_pct: Decimal | None = None,
) -> list[Layer]:
    """Every Chapter 99 provision that reaches this good from this origin, with its reasons.

    Reaching is three separate questions and a provision may answer more than one of them; the
    reasons are kept apart rather than merged, because a reader may accept "the note lists
    your code" and still doubt "the provision names your country". See ``queries.APPLICABLE``.

    Nothing is filtered by date here. A provision that expired in 2020 or starts in November
    is still an answer to "what touches this good" — it is the caller that decides where to
    put it, and hiding it would be the same silence the dataset already suffers from.

    Args:
        hts: A base schedule code, 8 or 10 digits.
        country_code: ISO 3166-1 alpha-2 of the country of origin, or None.
        on_date: The date each provision's standing is judged against.
        declared_value_usd: Shipment value, for the money on each term.
        quantity: Shipment quantity, for specific duties.
        col1_pct: The good's **Column 1 General** ad valorem rate, for judging the conditions
            provisions state. Column 1 even when the query resolved to Column 2, because that
            is the column the schedule's own sentence names.

    Returns:
        One Layer per provision, ordered by heading.
    """
    found = rows(queries.APPLICABLE, {"hts": hts, "country": country_code})
    if not found:
        return []

    codes = [row["hts"] for row in found]
    evidence = _evidence(hts, country_code, codes)
    countries = _grouped(rows(queries.COUNTRIES, {"rules": codes}), "rule_hts", "country_name")
    identifiers = _grouped(rows(queries.IDENTIFIERS, {"rules": codes}), "rule_hts", "value")
    excluded = _grouped(rows(queries.EXCLUSIONS, {"rules": codes}), "source_hts", "target_hts")
    coverage = {row["rule_hts"]: row["codes"] for row in rows(queries.COVERAGE, {"rules": codes})}
    conditions: dict[str, list[Condition]] = defaultdict(list)
    for row in rows(queries.CONDITIONS, {"rules": codes}):
        conditions[row["rule_hts"]].append(Condition(
            kind=row["kind"], operator=row["operator"], value=row["value"],
            verbatim=row["verbatim"], met=_met(row["operator"], row["value"], col1_pct)))
    cited: dict[str, list[CitedNote]] = defaultdict(list)
    seen_notes: set[tuple[str, int | None, str | None]] = set()
    for row in rows(queries.CITED_NOTES, {"rules": codes}):
        # A provision can print the same citation twice in one description, in two different
        # sentences, and rule_note keys on the text so both are rows. One note, once.
        key = (row["rule_hts"], row["note_id"], row["cited_subdivision"])
        if key in seen_notes:
            continue
        seen_notes.add(key)
        cited[row["rule_hts"]].append(CitedNote(
            note_id=row["note_id"], label=row["label"], cited_text=row["cited_text"],
            cited_subdivision=row["cited_subdivision"], page_from=row["page_from"],
            precision=row["match_precision"],
        ))

    return [
        Layer(
            hts=row["hts"],
            description=row["full_description"],
            origin_scope=row["origin_scope"],
            conditions=conditions.get(row["hts"], []),
            scope=row["scope"],
            cumulation=row["cumulation"],
            term=term(
                kind=row["rate_kind"],
                cumulation=row["cumulation"],
                text=row["rate_text"],
                ad_valorem_pct=row["rate_ad_valorem_pct"],
                specific_amount=row["rate_specific_amount"],
                specific_unit=row["rate_specific_unit"],
                declared_value_usd=declared_value_usd,
                quantity=quantity,
            ),
            effectivity=standing(row, on_date),
            programme=_programme(row),
            evidence=evidence.get(row["hts"], []),
            countries=countries.get(row["hts"], []),
            cas_numbers=identifiers.get(row["hts"], []),
            cited_notes=cited.get(row["hts"], []),
            excluded_by=excluded.get(row["hts"], []),
            coverage=coverage.get(row["hts"]),
        )
        for row in found
    ]


def _met(operator: str, value: Decimal, col1_pct: Decimal | None) -> bool | None:
    if col1_pct is None:
        return None
    return col1_pct < value if operator == "lt" else col1_pct >= value


def standing(row: dict[str, Any], on_date: date) -> Effectivity:
    """Judge one provision against a date rather than against today.

    'terminated' and 'suspended' beat the dates: 36 provisions say they have stopped and give
    no date at all, so a window alone would leave them looking current (D-0043).
    """
    if row["status"] != "in_force":
        where = "stopped"
    elif row["effective_from"] and row["effective_from"] > on_date:
        where = "not_yet"
    elif row["effective_to"] and row["effective_to"] < on_date:
        where = "expired"
    else:
        where = "in_force"

    return Effectivity(
        status=row["status"],
        status_note=row["status_note"],
        effective_from=row["effective_from"],
        effective_to=row["effective_to"],
        standing=where,
    )


def _evidence(hts: str, country_code: str | None, codes: list[str]) -> dict[str, list[Evidence]]:
    found: dict[str, list[Evidence]] = defaultdict(list)
    wanted = set(codes)

    for row in rows(queries.EVIDENCE_DIRECT, {"hts": hts}):
        if row["rule_hts"] not in wanted:
            continue
        exact = row["match_kind"] == "exact"
        found[row["rule_hts"]].append(Evidence(
            kind="cited_code",
            detail=(f"The provision names subheading {row['cited_code']}"
                    + ("" if exact else f", and {hts} sits beneath it")),
            cited_code=row["cited_code"],
            match_kind=row["match_kind"],
        ))

    for row in rows(queries.EVIDENCE_NOTE, {"hts": hts}):
        if row["rule_hts"] not in wanted:
            continue
        cited = row["cited_subdivision"] or ""
        inexact = row["match_precision"] == "parent_fallback"
        # The label usually already carries the subdivision -- "U.S. note 31(b) to subchapter
        # III" -- so repeating it reads as a stutter. It is worth saying only when the label
        # does not show it, which is exactly the fallback case.
        repeat = bool(cited) and cited in (row["note_label"] or "")
        detail = (f"The provision points at {row['note_label']}"
                  + (f" subdivision {cited}" if cited and not inexact and not repeat else "")
                  + f", whose list includes {row['cited_code']}")
        if inexact:
            detail += (f" — but it names subdivision {cited}, which could not be isolated from"
                       f" the notes PDF, so this coverage is wider than the provision is")
        found[row["rule_hts"]].append(Evidence(
            kind="note_list",
            detail=detail,
            cited_code=row["cited_code"],
            match_kind=row["match_kind"],
            note_id=row["note_id"],
            note_label=row["note_label"],
            note_page=row["page_from"],
            note_precision=row["match_precision"],
        ))

    if country_code:
        for row in rows(queries.COUNTRIES, {"rules": codes}):
            if row["country_code"] != country_code:
                continue
            found[row["rule_hts"]].append(Evidence(
                kind="country",
                detail=f"The provision names {row['country_name']} as the country of origin",
            ))

    return dict(found)


def _programme(row: dict[str, Any]) -> Programme | None:
    if not row.get("heading_prefix"):
        return None
    return Programme(
        heading_prefix=row["heading_prefix"], label=row["label"], statute=row["statute"],
        agency=row["agency"], evidence=row["evidence"], reference_url=row["reference_url"],
    )


def _grouped(found: list[dict[str, Any]], key: str, value: str) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for row in found:
        if row[value] is not None and row[value] not in grouped[row[key]]:
            grouped[row[key]].append(row[value])
    return dict(grouped)
