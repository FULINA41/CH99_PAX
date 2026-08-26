import re
from bisect import bisect_left
from dataclasses import dataclass, field
from typing import Any

from parsing.db import connect
from parsing.cumulation import DISAGREEMENT, disagrees, states_cumulation
from parsing.issues import Issue, insert_issues

STAGE = "resolve"

# 'U.S. note 20(b) to this subchapter', 'additional U.S. note 1 to chapter 4'. The scope
# clause is optional: 82 citations name a note and leave the collection implied. Any inline
# subdivision is consumed but not captured here -- ch99 already recorded the path, in either
# of the two forms it is printed in, as rule_note.cited_subdivision.
CITATION = re.compile(
    r"(?P<additional>additional\s+)?U\.S\.\s+note\s+(?P<number>\d+)"
    r"(?:\([a-z0-9]+\))*"
    r"(?:\s+to\s+(?P<scope>this subchapter|chapter\s+\d+|section\s+[IVX]+))?",
    re.IGNORECASE,
)
LABEL = re.compile(r"\(([a-z0-9]+)\)", re.IGNORECASE)

# A note can define its scope by pointing at another note rather than listing anything:
# "products of China that are classified in the subheadings enumerated in U.S. note 20(b)".
# Only this phrasing is followed, and the choice is not stylistic -- the notes point at each
# other 224 times and the two directions are told apart by the words:
#
#   'the subheadings enumerated in U.S. note X'   70 times   what the duty COVERS
#   'and provided for in U.S. note X'            154 times   an exclusion FROM it,
#                                                            always after a 9903 heading
#
# Following both would file every USTR exclusion list as the scope of the duty it exempts
# goods from, which is the exact inverse of what the note says. D-0041.
DELEGATION = re.compile(
    r"subheadings\s+enumerated\s+in\s+"
    r"((?:additional\s+)?U\.S\.\s+note\s+\d+(?:\([a-z0-9]+\))*"
    r"(?:\s+to\s+(?:this subchapter|chapter\s+\d+|section\s+[IVX]+))?)",
    re.IGNORECASE,
)
# One hop is what the data uses -- 20(a) names 20(b), which is a list. The cap is a
# backstop against a cycle, not a modelled depth.
MAX_DELEGATION_HOPS = 2


@dataclass
class Resolution:
    note_links: list[tuple] = field(default_factory=list)   # (note_id, rule_note.id, precision)
    rule_matches: list[tuple] = field(default_factory=list)
    note_matches: list[tuple] = field(default_factory=list)
    chapter_notes: int = 0
    delegated: int = 0
    issues: list[Issue] = field(default_factory=list)


def base_matcher(codes: list[str]):
    """Build a prefix matcher over the base schedule.

    Citations are 8-digit and base rows are 8 or 10, so a citation reaches a row when the
    row's code equals it or extends it at a separator. Anchoring on the dot matters:
    ``2922.49.3`` must not reach ``2922.49.30``.

    Args:
        codes: Every code in ``hts_base``.

    Returns:
        A function taking a cited code and returning the codes it reaches, in order.
    """
    ordered = sorted(codes)

    def reach(cited: str) -> list[str]:
        found = []
        for index in range(bisect_left(ordered, cited), len(ordered)):
            code = ordered[index]
            if not code.startswith(cited):
                break
            if code == cited or code.startswith(cited + "."):
                found.append(code)
        return found

    return reach


def parse_citation(cited_text: str, cited_subdivision: str | None,
                   rule_subchapter: str) -> tuple | None:
    """Work out which note a citation names.

    Args:
        cited_text: The citation as the provision printed it.
        cited_subdivision: The subdivision path beside it -- '(b)', '(j)(7)(iii)' -- or
            None when the citation named no subdivision.
        rule_subchapter: The citing provision's subchapter, since 'this subchapter' is
            relative to it.

    Returns:
        ``(subchapter, number, labels)`` for a note in this document, where labels is the
        subdivision path outermost first; or None when the citation names a chapter-level
        note, which lives in another chapter's document and is not in this PDF at all.
    """
    match = CITATION.search(cited_text)
    if not match:
        return None
    if match.group("additional") or (match.group("scope") or "").lower().startswith("chapter"):
        return None

    labels = [label.lower() for label in LABEL.findall(cited_subdivision or "")]
    return rule_subchapter, match.group("number"), labels


def resolve(*, run_id: str | None, dsn: str | None = None) -> dict[str, Any]:
    """Turn the citations and note lists into `rule_base_match`, and link notes to rules.

    Runs last because it reads every other table: `rule_edge` for what a provision named,
    `note_subheading` for what a note listed, and `hts_base` for what those reach. Nothing
    here is a new fact -- the whole table can be dropped and rebuilt without re-reading a
    single payload (D-0015).

    Args:
        run_id: The Hatchet run, recorded on each issue.
        dsn: Connection string. Falls back to ``DATABASE_URL``.

    Returns:
        How many citations resolved, how many matches were written and by which path.
    """
    result = Resolution()

    with connect(dsn) as conn, conn.cursor() as cursor:
        cursor.execute("SELECT hts FROM hts_base")
        reach = base_matcher([row[0] for row in cursor.fetchall()])

        cursor.execute("SELECT id, subchapter, note_number, subdivision FROM note")
        notes = {(sub, num, div): note_id for note_id, sub, num, div in cursor.fetchall()}

        # Reset first, so a rerun cannot leave a link this pass did not make.
        cursor.execute("UPDATE rule_note SET note_id = NULL, match_precision = 'unresolved'")
        cursor.execute(
            "SELECT n.id, n.rule_hts, n.cited_text, n.cited_subdivision, r.subchapter "
            "FROM rule_note n JOIN rule r ON r.hts = n.rule_hts")
        citations = cursor.fetchall()

        _link_notes(cursor, citations, notes, result)
        _match_from_descriptions(cursor, reach, result)
        _match_from_notes(cursor, reach, result)
        _follow_delegations(cursor, notes, result)

        cursor.execute("DELETE FROM parse_issue WHERE stage = %s", (STAGE,))
        cursor.execute("TRUNCATE rule_base_match, note_base_match")
        _copy(cursor, "rule_base_match", "rule_hts", result.rule_matches)
        _copy(cursor, "note_base_match", "note_id", result.note_matches)

        # A provision that reaches base codes only through a note was filed as
        # by_country_all_goods or unknown, because whether that note is a list was not
        # known until now (D-0018).
        cursor.execute("""
            UPDATE rule SET scope = 'by_code' WHERE scope <> 'by_code' AND (
                EXISTS (SELECT 1 FROM rule_base_match m WHERE m.rule_hts = rule.hts)
                OR EXISTS (SELECT 1 FROM rule_note n JOIN note_base_match nm
                           ON nm.note_id = n.note_id WHERE n.rule_hts = rule.hts))""")
        rescoped = cursor.rowcount
        cumulation = _read_cumulation(cursor, result)

        insert_issues(cursor, run_id, result.issues)
        cursor.execute("SELECT scope, count(*) FROM rule GROUP BY 1")
        scopes = dict(cursor.fetchall())

    precision: dict[str, int] = {}
    for _, _, kind in result.note_links:
        precision[kind] = precision.get(kind, 0) + 1

    return {
        "notes_linked": len(result.note_links),
        "note_precision": precision | {"chapter_note": result.chapter_notes},
        "rule_matches": len(result.rule_matches),
        "note_matches": len(result.note_matches),
        "note_matches_delegated": result.delegated,
        "rescoped": rescoped,
        "scopes": scopes,
        "cumulation": cumulation,
        "issues": len(result.issues),
    }


# The subchapter default, and then the notes a provision actually cites. A note that states
# nothing leaves the default standing, which is why the fallback is read first and overwritten
# rather than consulted last.
SUBCHAPTER_NOTES = """
SELECT subchapter, body FROM note
WHERE note_kind = 'us_note' AND note_number = '1' AND subdivision IS NULL
  AND subchapter IS NOT NULL
"""

CITED_NOTE_BODIES = """
SELECT rn.rule_hts, n.body
FROM rule_note rn JOIN note n ON n.id = rn.note_id
"""


def _read_cumulation(cursor, result: Resolution) -> dict[str, int]:
    cursor.execute(SUBCHAPTER_NOTES)
    default = {row[0]: states_cumulation(row[1]) for row in cursor.fetchall()}

    cursor.execute("SELECT hts, subchapter, rate_kind, rate_text FROM rule")
    rules = cursor.fetchall()

    cursor.execute(CITED_NOTE_BODIES)
    stated: dict[str, str] = {}
    for rule_hts, body in cursor.fetchall():
        found = states_cumulation(body)
        # A cited note that displaces note 1 beats one that merely restates it, whichever
        # order the citations came back in.
        if found == "cumulative" or (found and rule_hts not in stated):
            stated[rule_hts] = found

    updates: list[tuple[str, str]] = []
    for hts, subchapter, rate_kind, rate_text in rules:
        value = stated.get(hts) or default.get(subchapter) or "unstated"
        updates.append((value, hts))
        if disagrees(value, rate_kind, rate_text):
            result.issues.append(Issue(
                STAGE, "rate_silent_note_decides", hts,
                DISAGREEMENT.format(cumulation=value, rate_kind=rate_kind,
                                    rate_text=rate_text)))

    cursor.executemany("UPDATE rule SET cumulation = %s WHERE hts = %s", updates)

    cursor.execute("SELECT cumulation, count(*) FROM rule GROUP BY 1")
    return dict(cursor.fetchall())


def _copy(cursor, table: str, owner: str, rows: list[tuple]) -> None:
    if not rows:
        return
    statement = f"COPY {table} ({owner}, base_hts, cited_code, match_kind) FROM STDIN"
    with cursor.copy(statement) as copy:
        for row in rows:
            copy.write_row(list(row))


def _link_notes(cursor, citations, notes, result):
    updates, chapter_notes = [], []
    for citation_id, rule_hts, cited_text, cited_subdivision, subchapter in citations:
        key = parse_citation(cited_text, cited_subdivision, subchapter)
        if key is None:
            # A chapter note. Not a failure: it lives in another chapter's document, which
            # this PDF does not contain, and saying so is different from saying nothing.
            chapter_notes.append(citation_id)
            continue
        subchapter, number, labels = key
        label = labels[0] if labels else None

        note_id = notes.get((subchapter, number, label)) if label else None
        # Only one level is ever a row, so '(k)(i)' resolves no further than note 31(k) --
        # which is the parent of what was cited, not what was cited.
        precision = "exact" if len(labels) < 2 else "parent_fallback"
        if note_id is None and label:
            # The segmenter isolates one level of subdivision, and note 2's outline nests
            # three deep reusing labels at each level, so some citations name a subdivision
            # that is not a row. The parent holds the union of its subdivisions' lists, so
            # falling back keeps the coverage -- note 2 is the reciprocal tariff, the most
            # frequently applied duty here -- at the cost of being wider than the provision
            # really is. Recorded rather than hidden, and the app has to say so. D-0038.
            note_id = notes.get((subchapter, number, None))
            precision = "parent_fallback"
        elif note_id is None:
            note_id = notes.get((subchapter, number, None))

        if note_id is None:
            result.issues.append(Issue(
                STAGE, "unresolved_note", rule_hts,
                f"{cited_text!r} names no note this parse found"))
            continue
        if precision == "parent_fallback":
            result.issues.append(Issue(
                STAGE, "subdivision_not_segmented", rule_hts,
                f"{cited_text!r} names subdivision {label!r}, which the notes parse did "
                f"not isolate; matched U.S. note {number} whole, so coverage is wider "
                f"than the provision"))
        updates.append((note_id, precision, citation_id))
        result.note_links.append((note_id, citation_id, precision))

    cursor.executemany(
        "UPDATE rule_note SET note_id = %s, match_precision = %s WHERE id = %s", updates)
    if chapter_notes:
        cursor.execute(
            "UPDATE rule_note SET match_precision = 'chapter_note' WHERE id = ANY(%s)",
            (chapter_notes,))
    result.chapter_notes = len(chapter_notes)


def _match_from_descriptions(cursor, reach, result):
    cursor.execute(
        "SELECT DISTINCT source_hts, target_hts FROM rule_edge WHERE edge_type = 'references'")
    for rule_hts, cited in cursor.fetchall():
        found = reach(cited)
        if not found:
            result.issues.append(Issue(
                STAGE, "unresolved_code", rule_hts,
                f"{cited} matches no row in the base schedule"))
            continue
        for base in found:
            result.rule_matches.append(
                (rule_hts, base, cited, "exact" if base == cited else "prefix"))


def _follow_delegations(cursor, notes, result):
    cursor.execute("SELECT id, subchapter, note_number, subdivision, body FROM note")
    rows = cursor.fetchall()
    bodies = {note_id: body for note_id, _, _, _, body in rows}
    context = {note_id: subchapter for note_id, subchapter, _, _, _ in rows}

    covered: dict[int, list[tuple]] = {}
    for note_id, base, cited, kind in result.note_matches:
        covered.setdefault(note_id, []).append((base, cited, kind))

    added = 0
    for note_id in bodies:
        if note_id in covered:
            continue
        inherited, seen = [], set()
        for target in _delegation_targets(note_id, bodies, context, notes):
            for base, cited, kind in covered.get(target, ()):
                if (base, cited) in seen:
                    continue
                seen.add((base, cited))
                inherited.append((note_id, base, cited, kind))
        if inherited:
            result.note_matches.extend(inherited)
            added += len(inherited)
    result.delegated = added


def _delegation_targets(note_id, bodies, context, notes):
    found, frontier, visited = [], [note_id], {note_id}
    for _ in range(MAX_DELEGATION_HOPS):
        following = []
        for current in frontier:
            for cited in DELEGATION.findall(bodies.get(current, "")):
                key = parse_citation(cited, _inline_path(cited), context[note_id])
                if key is None:
                    continue
                subchapter, number, labels = key
                target = notes.get((subchapter, number, labels[0] if labels else None))
                if target is None or target in visited:
                    continue
                visited.add(target)
                found.append(target)
                following.append(target)
        if not following:
            break
        frontier = following
    return found


def _inline_path(cited: str) -> str | None:
    # The delegation is printed inline -- 'U.S. note 20(b)' -- so the path is inside the
    # citation itself rather than beside it as rule_note.cited_subdivision.
    labels = LABEL.findall(cited)
    return "".join(f"({label})" for label in labels) or None


def _match_from_notes(cursor, reach, result):
    # Expanded once per note. Joining rule_note in here instead would repeat note 52's
    # 4,166 codes for each of the 98 provisions that cite it (D-0036).
    cursor.execute("SELECT note_id, hts_prefix FROM note_subheading")
    seen = set()
    for note_id, cited in cursor.fetchall():
        for base in reach(cited):
            key = (note_id, base, cited)
            if key in seen:
                continue
            seen.add(key)
            result.note_matches.append(
                (note_id, base, cited, "exact" if base == cited else "prefix"))
