from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

RateKind = Literal["free", "replace", "additive", "no_change", "prose", "none"]
Column = Literal["1-general", "2"]


class Programme(BaseModel):
    """The trade action a provision belongs to. EDITORIAL -- see D-0045.

    The schedule never names a statute: of 345 U.S. notes exactly one does. Every field here
    except `evidence` is an attribution made by this project, not read from a source, and
    every surface that shows one must say so.
    """

    heading_prefix: str
    label: str
    statute: str
    agency: str
    evidence: str = Field(description="What the parsed rows say, checkable against the database")
    reference_url: str
    editorial: Literal[True] = True


class Evidence(BaseModel):
    """Why a provision is in this answer at all.

    One per reason, because a provision can be here for more than one -- naming the country
    and listing the code are different claims and a reader may accept one and not the other.
    """

    kind: Literal["cited_code", "note_list", "country", "country_wide"]
    detail: str = Field(description="The reason as a sentence, for a reader")
    cited_code: str | None = None
    match_kind: Literal["exact", "prefix"] | None = None
    note_id: int | None = None
    note_label: str | None = None
    note_page: int | None = None
    # 'parent_fallback' means the coverage shown is WIDER than the provision's real scope,
    # because the subdivision it cites could not be isolated from the PDF. D-0038.
    note_precision: Literal["exact", "parent_fallback", "chapter_note", "unresolved"] | None = None


class CitedNote(BaseModel):
    """A note a provision points at, whatever path the provision matched by.

    Separate from Evidence on purpose. Evidence answers "why is this in my answer"; this
    answers "what document defines it" -- and for the exclusion provisions, which match on
    country alone, the note is the only thing a reader can act on.
    """

    note_id: int | None = None
    label: str | None = None
    cited_text: str
    cited_subdivision: str | None = None
    page_from: int | None = None
    precision: Literal["exact", "parent_fallback", "chapter_note", "unresolved"]


class Term(BaseModel):
    """One item in the formula: an operator and its operands.

    This is the schema's own shape (D-0013) carried to the screen unchanged. `operator` says
    what the term does to the running rate; the operands are what it does it with.
    """

    operator: Literal["base", "add", "replace", "no_change", "unknown"]
    text: str = Field(description="The rate exactly as the schedule prints it")
    ad_valorem_pct: Decimal | None = None
    specific_amount: Decimal | None = Field(
        default=None, description="Always in dollars; a rate printed in cents is divided by 100"
    )
    specific_unit: str | None = None
    # Filled only when the caller supplied a value, and for a specific duty a quantity too.
    # Never guessed: a specific duty with no quantity is an unknown, not a zero.
    amount_usd: Decimal | None = None


class Effectivity(BaseModel):
    status: Literal["in_force", "terminated", "suspended"]
    status_note: str | None = None
    effective_from: date | None = None
    effective_to: date | None = Field(default=None, description="The last day in force")
    # Against the date the caller asked about, not against today.
    standing: Literal["in_force", "not_yet", "expired", "stopped"]


class Layer(BaseModel):
    """One Chapter 99 provision that applies, and everything needed to check that claim."""

    hts: str
    description: str
    # 'by_country_all_goods' is the important one: the provision names the country and limits
    # the goods in prose that could not be turned into codes, so it reaches every import from
    # that origin. 9903.85.67 says "Aluminum articles ... product of Russia" and matches a
    # steel shipment. Shown, never silently summed.
    scope: Literal["by_code", "by_country_all_goods", "unknown"] = "by_code"
    term: Term
    effectivity: Effectivity
    programme: Programme | None = None
    evidence: list[Evidence]
    countries: list[str] = Field(default_factory=list)
    cas_numbers: list[str] = Field(default_factory=list)
    # Provisions that carve goods out of this one. Whether a shipment is described by any of
    # them is a question about the goods, which this data cannot answer.
    cited_notes: list[CitedNote] = Field(default_factory=list)
    excluded_by: list[str] = Field(default_factory=list)
    coverage: int | None = Field(default=None, description="Base codes this provision reaches")


class Classification(BaseModel):
    hts: str
    description: str
    full_description: str = Field(description="The ancestor chain joined onto the row's own prose")
    units: list[str] = Field(default_factory=list)
    chain: list[str] = Field(default_factory=list, description="Ancestor codes, outermost first")


class BaseRate(BaseModel):
    column: Column
    term: Term
    # NULL when the row states its own rate; a code when it was inherited. D-0014.
    inherited_from: str | None = None
    # Column 1 Special, as printed. Never interpreted -- eligibility needs the General Notes,
    # the rules of origin and the importer's claim, none of which is in these sources. D-0027.
    special_text: str | None = None


class Unknown(BaseModel):
    """Something this data cannot settle, and where the reader can settle it.

    A first-class part of the answer, not a disclaimer: for most of these the honest answer
    is a pointer, and a pointer with a search term is worth more than a hedge.
    """

    question: str
    why: str
    source_name: str
    url: str
    what_to_search: str
    related_hts: list[str] = Field(default_factory=list)


class ExclusionGroup(BaseModel):
    note_label: str | None
    note_id: int | None
    provisions: list[str]


class Total(BaseModel):
    """The arithmetic, and the assumption it rests on.

    Never a single number when the terms do not share a unit: '25% + 46.3c/kg' is the answer
    and collapsing it would be a fiction.
    """

    expression: str
    ad_valorem_pct: Decimal | None = None
    specific_terms: list[str] = Field(default_factory=list)
    amount_usd: Decimal | None = None
    assumption: str
    # A floor and a ceiling, because the honest answer to a Chinese steel query is a range.
    # The floor counts only what the data shows reaching this code. The ceiling adds the
    # provisions that name the origin and limit the goods in words -- section 301 list 4A
    # among them, whose note is prose. Reporting the floor alone would understate by 25
    # points; reporting the ceiling alone would put an aluminium duty on steel.
    ceiling_expression: str | None = None
    ceiling_ad_valorem_pct: Decimal | None = None
    ceiling_amount_usd: Decimal | None = None
    ceiling_note: str | None = None


class Query(BaseModel):
    hts: str
    country: str | None = None
    country_name: str | None = None
    on_date: date
    declared_value_usd: Decimal | None = None
    quantity: Decimal | None = None
    quantity_unit: str | None = None


class DutyStack(BaseModel):
    """The whole answer to 'what does Chapter 99 do to this good from this country'.

    The same object the web app renders, so any number on a page can be checked here against
    the rows behind it.
    """

    query: Query
    classification: Classification
    base_rate: BaseRate
    column2: BaseRate | None = None
    layers: list[Layer] = Field(default_factory=list)
    # Named your country, limited the goods in words. Kept out of the total on purpose: their
    # own text says what they cover and this data cannot check it against your shipment.
    origin_scoped: list[Layer] = Field(default_factory=list)
    reductions: list[Layer] = Field(default_factory=list)
    exclusions: list[ExclusionGroup] = Field(default_factory=list)
    inactive: list[Layer] = Field(default_factory=list)
    total: Total
    unknowns: list[Unknown] = Field(default_factory=list)
