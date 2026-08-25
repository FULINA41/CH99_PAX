import re
from bisect import bisect_left
from dataclasses import dataclass, field
from typing import Any

from parsing.db import connect
from parsing.issues import Issue, insert_issues

STAGE = "resolve"

# 'U.S. note 20(b) to this subchapter', 'additional U.S. note 1 to chapter 4'. The scope
# clause is optional: 82 citations name a note and leave the collection implied.
CITATION = re.compile(
    r"(?P<additional>additional\s+)?U\.S\.\s+note\s+(?P<number>\d+)"
    r"(?P<subdivisions>(?:\([a-z0-9]+\))*)"
    r"(?:\s+to\s+(?P<scope>this subchapter|chapter\s+\d+|section\s+[IVX]+))?",
    re.IGNORECASE,
)


@dataclass
class Resolution:
    note_links: list[tuple[int, str]] = field(default_factory=list)   # (note_id, rule_note.id)
    rule_matches: list[tuple] = field(default_factory=list)
    note_matches: list[tuple] = field(default_factory=list)
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


def parse_citation(cited_text: str, rule_subchapter: str) -> tuple | None:
    """Work out which note a citation names.

    Returns:
        ``(subchapter, number, subdivision)`` for a note in this document, or None when
        the citation names a chapter-level note, which lives in another chapter's
        document and is not in the Chapter 99 PDF at all.
    """
    match = CITATION.search(cited_text)
    if not match:
        return None
    if match.group("additional") or (match.group("scope") or "").lower().startswith("chapter"):
        return None

    subdivisions = re.findall(r"\(([a-z0-9]+)\)", match.group("subdivisions") or "")
    return rule_subchapter, match.group("number"), (subdivisions[0] if subdivisions else None)


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

        cursor.execute(
            "SELECT n.id, n.rule_hts, n.cited_text, r.subchapter "
            "FROM rule_note n JOIN rule r ON r.hts = n.rule_hts")
        citations = cursor.fetchall()

        _link_notes(cursor, citations, notes, result)
        _match_from_descriptions(cursor, reach, result)
        _match_from_notes(cursor, reach, result)

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

        insert_issues(cursor, run_id, result.issues)
        cursor.execute("SELECT scope, count(*) FROM rule GROUP BY 1")
        scopes = dict(cursor.fetchall())

    return {
        "notes_linked": len(result.note_links),
        "rule_matches": len(result.rule_matches),
        "note_matches": len(result.note_matches),
        "rescoped": rescoped,
        "scopes": scopes,
        "issues": len(result.issues),
    }


def _copy(cursor, table: str, owner: str, rows: list[tuple]) -> None:
    if not rows:
        return
    statement = f"COPY {table} ({owner}, base_hts, cited_code, match_kind) FROM STDIN"
    with cursor.copy(statement) as copy:
        for row in rows:
            copy.write_row(list(row))


def _link_notes(cursor, citations, notes, result):
    updates = []
    for citation_id, rule_hts, cited_text, subchapter in citations:
        key = parse_citation(cited_text, subchapter)
        if key is None:
            continue                      # a chapter note, correctly not in this PDF
        note_id = notes.get(key)
        if note_id is None:
            result.issues.append(Issue(
                STAGE, "unresolved_note", rule_hts,
                f"{cited_text!r} names no note this parse found"))
            continue
        updates.append((note_id, citation_id))
        result.note_links.append((note_id, citation_id))

    cursor.executemany("UPDATE rule_note SET note_id = %s WHERE id = %s", updates)


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
