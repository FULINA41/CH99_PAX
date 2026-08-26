import json
import re
from dataclasses import dataclass, field
from typing import Any

from parsing.countries import country_code, is_not_a_country
from parsing.db import connect
from parsing.issues import Issue, insert_issues
from parsing.rates import Rate, parse_rate
from parsing.tree import build_nodes

STAGE = "ch99"

# A dotted code that is not itself a Chapter 99 heading. 4, 6, 8 or 10 digits, because
# provisions cite whole families as readily as single lines.
BASE_CODE = re.compile(r"\b(?!99\d{2})(\d{4}\.\d{2}(?:\.\d{2})?(?:\.\d{2})?)\b")
CHAPTER99_CODE = re.compile(r"\b(99\d{2}\.\d{2}\.\d{2})\b")
# An exclusion has to be recognised by its lead-in, not by the word "except". 217 of the
# 431 "except" clauses in this revision are parentheticals inside a product description
# -- "of bovine (except calfskin) leather" -- and carve out no heading at all.
#
# The clause then runs to the end of its sentence, and that boundary must admit the dots
# inside a code: '9903.01.02' is four characters of clause, not the end of one, so a
# period only terminates when it is not followed by a digit.
EXCEPT_CLAUSE = re.compile(
    r"\bexcept\s+(?:for\s+(?:products|goods|articles)\s+described\s+in|"
    r"as\s+provided(?:\s+for)?\s+in)\b(?:[^.;]|\.(?=\d))*",
    re.IGNORECASE,
)

# Three things this has to survive, all of them found by querying for provisions that name
# a country in their prose and have no rule_country row -- 21 of them did. D-0042.
#
#   'Potash that is a product of Canada'    the subject is not always the word 'articles'
#   'Myanmar (Burma)'                       a parenthesis ends the name
#   'Cote d`Ivoire', 'Cote d'Ivoire'        the name is not ASCII, and the apostrophe is
#                                           printed as a backtick on one line and a curly
#                                           quote on another
#
# A China query returning Myanmar's rate is the failure this prevents, so the name class is
# widened and the terminators carry the weight: the capture is lazy and stops at the first
# punctuation or clause word, rather than trying to enumerate what a country name may hold.
COUNTRY = re.compile(
    r"\b(?:articles?|products?|goods|[^\W\d_]+)\s+(?:that\s+(?:are|is)\s+)?"
    r"(?:the|a)\s+products?\s+of\s+"
    r"([^\W\d_][^,.;:()\[\]]*?)"
    r"(?=\s*(?:[,.;:()]|$|\bas\b|\bthat\b|\bentered\b|\bwhich\b|\bprovided\b"
    r"|\bunder\b|\bwith\b|\bclassified\b))",
    re.IGNORECASE,
)
# 'any country', 'a member state of the European Union', and -- from "the product of any
# country or area including the United States", where the list splits on 'or' -- 'area'.
# The provision does key on origin, but not on a country this row can name.
GENERIC_COUNTRY = re.compile(r"^(?:any\b|a member state\b|area\b)", re.IGNORECASE)

# 'of the United Kingdom' comes from "the product of Germany or of the United Kingdom":
# splitting the list leaves the preposition attached to the second name.
ARTICLE = re.compile(r"^(?:of\s+)?(?:the\s+)?", re.IGNORECASE)

# ISO 3166 country names that contain the word "and". Without them, splitting a list on
# "and" turns 'Bosnia and Herzegovina' into two things that are not countries -- while
# still splitting 'China and Hong Kong', which genuinely is two (D-0033). Every entry is
# checkable
# against the ISO register, and this set is the natural thing to derive from it should a
# country-code source ever be added.
COMPOUND_NAMES = frozenset(name.lower() for name in (
    "Antigua and Barbuda",
    "Bonaire, Sint Eustatius and Saba",
    "Bosnia and Herzegovina",
    "Heard Island and McDonald Islands",
    "Saint Helena, Ascension and Tristan da Cunha",
    "Saint Kitts and Nevis",
    "Saint Pierre and Miquelon",
    "Saint Vincent and the Grenadines",
    "Sao Tome and Principe",
    "South Georgia and the South Sandwich Islands",
    "Svalbard and Jan Mayen",
    "Trinidad and Tobago",
    "Turks and Caicos Islands",
    "Wallis and Futuna",
))

# A subdivision is named two ways and both have to be read. Inline -- 'U.S. note 20(b)' --
# and in front -- 'subdivision (g) of U.S. note 31'. Reading only the inline form sent 202
# provisions to the parent note, which carries the union of its subdivisions' lists:
# 9903.91.06 names note 31(g), a list of graphite and magnets, and inherited note 31's 412
# codes instead, reaching steel it has nothing to do with. D-0037.
#
# The path can nest -- 'subdivision (j)(7)(iii) of U.S. note 52' -- and one clause can name
# several -- 'subdivisions (d) and (f) of U.S. note 37'.
SUBDIVISION_PATH = r"\([a-z0-9]+\)(?:\([a-z0-9]+\))*"
NOTE_CITATION = re.compile(
    rf"(?:(?P<paths>(?:sub)?divisions?\s+{SUBDIVISION_PATH}"
    rf"(?:\s*(?:,|and|or)\s*{SUBDIVISION_PATH})*)\s+(?:of|to)\s+)?"
    rf"(?P<note>(?:additional\s+)?U\.S\.\s+note\s+\d+(?P<inline>(?:\([a-z0-9]+\))*)"
    r"(?:\s+to\s+(?:this subchapter|chapter\s+\d+|section\s+[IVX]+))?)",
    re.IGNORECASE,
)
EACH_PATH = re.compile(SUBDIVISION_PATH, re.IGNORECASE)
# The CAS registry number itself rather than the 'CAS No.' label: the label is spelled
# six ways in this revision, and four provisions write the number with no label at all.
CAS_NUMBER = re.compile(r"\b(\d{2,7}-\d{2}-\d)\b")

NO_ADDITIONAL_DUTY = "no additional duty"

ROMAN = ((10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"))


@dataclass
class Ch99Data:
    rules: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    countries: list[dict[str, Any]] = field(default_factory=list)
    identifiers: list[dict[str, Any]] = field(default_factory=list)
    notes: list[dict[str, Any]] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)


def parse_ch99(path: str, *, source_fetch_id: int | None) -> Ch99Data:
    """Read the Chapter 99 export and build every row the fact tables need.

    Everything is extracted from the ancestor chain rather than the row's own
    description, because a provision inherits its ancestors' scope -- `9903.17.01` reads
    "first quota period" and says nothing about sugar without them (D-0012).

    Args:
        path: The staged ``ch99.json``.
        source_fetch_id: The fetch these rows are attributed to.

    Returns:
        Rules in insertion order, plus the edges, countries, identifiers and note
        citations found, and every issue raised while extracting them.
    """
    with open(path) as handle:
        export = json.load(handle)

    nodes, issues = build_nodes(export, STAGE)
    data = Ch99Data(issues=issues)

    for node in nodes:
        text = node.full_description
        rate = parse_rate(node.row.get("general"))
        additional = _additional_duty(node.row.get("additionalDuties"))

        excluded = _excluded_codes(text)
        referenced = sorted(set(BASE_CODE.findall(text)))
        countries, generic = _countries(text)

        if rate.kind == "prose":
            data.issues.append(Issue(STAGE, "unparsed_rate", node.hts, rate.text))
        for phrase in generic:
            data.issues.append(Issue(
                STAGE, "unnamed_country", node.hts,
                f"keys on origin but names no country: {phrase!r}"))

        data.rules.append({
            "hts": node.hts,
            "heading": node.hts[:4],
            "subchapter": _subchapter(node.hts),
            "parent_hts": node.parent_hts,
            "indent": node.indent,
            "description": node.description,
            "full_description": text,
            "scope": _scope(referenced, countries),
            "rate_text": rate.text,
            "rate_kind": rate.kind,
            "rate_ad_valorem_pct": rate.ad_valorem_pct,
            "rate_specific_amount": rate.specific_amount,
            "rate_specific_unit": rate.specific_unit,
            "additional_duty_text": additional.text,
            "additional_duty_pct": additional.ad_valorem_pct,
            "additional_duty_amount": additional.specific_amount,
            "additional_duty_unit": additional.specific_unit,
            "source_fetch_id": source_fetch_id,
        })

        for code in referenced:
            data.edges.append({"source_hts": node.hts, "edge_type": "references",
                               "target_hts": code})
        for code in excluded:
            data.edges.append({"source_hts": node.hts, "edge_type": "excludes",
                               "target_hts": code})
        for name in countries:
            code = country_code(name)
            if code is None and not is_not_a_country(name):
                data.issues.append(Issue(
                    STAGE, "unresolved_country", node.hts,
                    f"no ISO 3166 code for {name!r}"))
            data.countries.append({"rule_hts": node.hts, "country_name": name,
                                   "country_code": code, "relation": "product_of"})
        for value in sorted(set(CAS_NUMBER.findall(text))):
            data.identifiers.append({"rule_hts": node.hts, "kind": "cas", "value": value})
        for cited, subdivision in _note_citations(text):
            data.notes.append({"rule_hts": node.hts, "cited_text": cited,
                               "cited_subdivision": subdivision, "note_id": None})

    return data


def _note_citations(text: str) -> list[tuple[str, str | None]]:
    found = set()
    for match in NOTE_CITATION.finditer(text):
        cited = _tidy(match.group(0))
        # A clause naming several subdivisions is several citations sharing one span, so
        # each gets its own row rather than one row nobody can resolve.
        if match.group("paths"):
            for path in EACH_PATH.findall(match.group("paths")):
                found.add((cited, path))
        else:
            found.add((cited, match.group("inline") or None))
    return sorted(found, key=lambda pair: (pair[0], pair[1] or ""))


def _excluded_codes(text: str) -> list[str]:
    codes: set[str] = set()
    for clause in EXCEPT_CLAUSE.findall(text):
        codes.update(CHAPTER99_CODE.findall(clause))
    return sorted(codes)


def _countries(text: str) -> tuple[list[str], list[str]]:
    named: set[str] = set()
    generic: set[str] = set()
    for capture in COUNTRY.findall(text):
        for name in _split_names(capture):
            (generic if GENERIC_COUNTRY.match(name) else named).add(name)
    return sorted(named), sorted(generic)


def _split_names(capture: str) -> list[str]:
    names = []
    # 'or' always separates alternatives; 'and' does too, unless the whole phrase is one
    # country whose name happens to contain it.
    for alternative in re.split(r"\s+or\s+", capture.strip(), flags=re.IGNORECASE):
        cleaned = _bare(alternative)
        if not cleaned:
            continue
        if cleaned.lower() in COMPOUND_NAMES:
            names.append(cleaned)
            continue
        names.extend(n for n in (_bare(part) for part in
                                 re.split(r"\s+and\s+", cleaned, flags=re.IGNORECASE)) if n)
    return names


def _bare(name: str) -> str:
    return ARTICLE.sub("", name.strip(), count=1).strip()


def _scope(referenced: list[str], countries: list[str]) -> str:
    # Provisional. A provision reaching base codes only through a note looks like
    # 'by_country_all_goods' here, because whether that note is a list of subheadings is
    # unknown until the PDF is parsed; the resolver corrects it in Step 5 (D-0018).
    if referenced:
        return "by_code"
    if countries:
        return "by_country_all_goods"
    return "unknown"


def _additional_duty(text: str | None) -> Rate:
    cleaned = (text or "").strip()
    # 'No additional duty' is a stated zero, not a missing value. parse_rate would call
    # it prose, which reads as "we could not work this out" and would send 50 provisions
    # to parse_issue for saying something perfectly clear.
    if cleaned.lower() == NO_ADDITIONAL_DUTY:
        return Rate("free", cleaned, ad_valorem_pct=0.0)
    return parse_rate(cleaned)


def _subchapter(hts: str) -> str:
    number = int(hts[2:4])
    roman = ""
    for value, numeral in ROMAN:
        while number >= value:
            roman += numeral
            number -= value
    return roman


def _tidy(citation: str) -> str:
    return re.sub(r"\s+", " ", citation).strip()


RULE_COLUMNS = (
    "hts", "heading", "subchapter", "parent_hts", "indent", "description",
    "full_description", "scope", "rate_text", "rate_kind", "rate_ad_valorem_pct",
    "rate_specific_amount", "rate_specific_unit", "additional_duty_text",
    "additional_duty_pct", "additional_duty_amount", "additional_duty_unit",
    "source_fetch_id",
)
CHILD_TABLES = (
    ("rule_edge", ("source_hts", "edge_type", "target_hts")),
    ("rule_country", ("rule_hts", "country_name", "country_code", "relation")),
    ("rule_identifier", ("rule_hts", "kind", "value")),
    ("rule_note", ("rule_hts", "cited_text", "cited_subdivision", "note_id")),
)

# rule is referenced by five tables. Naming them, rather than CASCADEing, means a table
# added later fails here with its name in the message instead of being quietly emptied.
TRUNCATE = ("TRUNCATE rule, rule_edge, rule_country, rule_identifier, rule_note, "
            "rule_base_match")


def load_ch99(data: Ch99Data, *, run_id: str | None, dsn: str | None = None) -> dict[str, Any]:
    """Replace the Chapter 99 fact tables with this parse, in one transaction.

    Args:
        data: Everything ``parse_ch99`` produced.
        run_id: The Hatchet run, recorded on each issue.
        dsn: Connection string. Falls back to ``DATABASE_URL``.

    Returns:
        Row counts per table, and how the rules divided by scope.
    """
    children = {
        "rule_edge": data.edges,
        "rule_country": data.countries,
        "rule_identifier": data.identifiers,
        "rule_note": data.notes,
    }

    with connect(dsn) as conn, conn.cursor() as cursor:
        cursor.execute("DELETE FROM parse_issue WHERE stage = %s", (STAGE,))
        cursor.execute(TRUNCATE)

        _copy(cursor, "rule", RULE_COLUMNS, data.rules)
        for table, columns in CHILD_TABLES:
            _copy(cursor, table, columns, children[table])

        insert_issues(cursor, run_id, data.issues)

    scopes: dict[str, int] = {}
    for rule in data.rules:
        scopes[rule["scope"]] = scopes.get(rule["scope"], 0) + 1

    return {
        "rules": len(data.rules),
        "references": sum(1 for e in data.edges if e["edge_type"] == "references"),
        "excludes": sum(1 for e in data.edges if e["edge_type"] == "excludes"),
        "countries": len(data.countries),
        "identifiers": len(data.identifiers),
        "note_citations": len(data.notes),
        "issues": len(data.issues),
        "scopes": scopes,
    }


def _copy(cursor, table: str, columns: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    statement = f"COPY {table} ({', '.join(columns)}) FROM STDIN"
    with cursor.copy(statement) as copy:
        for row in rows:
            copy.write_row([row[column] for column in columns])
