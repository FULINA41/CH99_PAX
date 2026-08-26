import re
from dataclasses import dataclass, field
from typing import Any, Iterable

import pypdf

from parsing.db import connect
from parsing.issues import Issue, insert_issues

STAGE = "notes"

SUBCHAPTER_BANNER = re.compile(r"^SUBCHAPTER\s+([IVXL]+)\s*$", re.MULTILINE)
NOTE_HEADER = re.compile(r"^U\.S\. Notes?(?:\s*\(con\.\))?$")

# Running heads, page numbers and the section marker, which pypdf emits as body text.
# The marker is written '99 - III - 377' on most pages and '99-III-1' on the first of each
# subchapter, so the separators have to tolerate spaces.
FURNITURE = re.compile(
    r"^(?:Harmonized Tariff Schedule of the United States.*"
    r"|Annotated for Statistical Reporting Purposes"
    r"|U\.S\. Notes?(?:\s*\(con\.\))?"
    r"|SUBCHAPTER\s+[IVXL]+"
    r"|99\s*-\s*[IVXL]+\s*-\s*\d+"
    r"|XXII"
    r"|\d{1,3})\s*$"
)

# A note opens with its number, a period, and then whitespace or the end of the line. The
# lookahead is what keeps '44.5 percent' from being read as the start of note 44.
NOTE_START = re.compile(r"^(\d{1,3})\.(?=\s|$)\s*(.*)$")
# Subdivisions run past (z) into (aa) and as far as (www) in note 20, so the letter class
# cannot be capped at two.
SUBDIVISION_START = re.compile(r"^\(([a-z]{1,4})\)\s*(.*)$")

CODE = re.compile(r"\d{4}\.\d{2}(?:\.\d{2})?")
# A note can name its codes in running prose rather than on a list page: as numbered items,
# '(1) 2504.10.10 (2) 2504.10.50'; or behind a lead-in, 'classified in 8-digit subheading
# 4015.12.10', 'described in statistical reporting number 6307.90.9870'. Density reads all
# of it as prose, so the codes were dropped -- and a provision whose note yields no codes
# keeps the scope it had before the note was read, 'all goods of this country'. That put
# 9903.91.08's 100% duty on rubber gloves onto every Chinese import, steel included. D-0039.
#
# Read only from a note that says what it applies to and never says what it does not. 107
# prose notes do both in one body, and a code sitting in running text does not carry which
# sentence it belonged to; those are left alone rather than guessed at.
# Never a Chapter 99 code: "Heading 9903.91.08 applies to ..." is the note naming the
# provision it belongs to, not a good that provision covers.
COVERED = r"(?!99\d{2})(\d{4}\.\d{2}(?:\.\d{2})?(?:\.\d{2})?)"
ENUMERATED = re.compile(rf"\(\d{{1,3}}\)\s*{COVERED}")
SCOPED_CODE = re.compile(
    rf"(?:statistical\s+reporting\s+numbers?|(?:\d+-digit\s+)?(?:sub)?headings?)\s+{COVERED}",
    re.IGNORECASE,
)
AFFIRMS = re.compile(r"appl(?:ies|y)\s+to", re.IGNORECASE)
NEGATES = re.compile(r"not\s+apply|shall\s+not", re.IGNORECASE)

LIST_DENSITY = 0.5
MIXED_DENSITY = 0.25
# Below this a dense-looking body is a sentence quoting a couple of headings, not a list.
LIST_MINIMUM = 20

# How far ahead of the last subdivision a label may be and still be one.
MAX_GAP = 2


@dataclass
class NotesData:
    notes: list[dict[str, Any]] = field(default_factory=list)
    subheadings: list[dict[str, Any]] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)


def extract_pages(path: str) -> list[str]:
    """Pull the text of every page out of the notes PDF."""
    reader = pypdf.PdfReader(path)
    return [page.extract_text() or "" for page in reader.pages]


def parse_notes(path: str, *, source_fetch_id: int | None) -> NotesData:
    """Read the notes PDF and build the `note` and `note_subheading` rows.

    Args:
        path: The staged ``ch99-notes.pdf``.
        source_fetch_id: The fetch these rows are attributed to.

    Returns:
        One record per note and per subdivision, the codes any of them list, and the
        issues raised while segmenting.
    """
    pages = extract_pages(path)
    data = NotesData()

    for subchapter, numbered in _by_subchapter(pages):
        for number, lines in numbered:
            lead, subdivisions = _split_subdivisions(lines)
            _add(data, subchapter, number, None, lines, source_fetch_id)
            for letter, sub_lines in subdivisions:
                _add(data, subchapter, number, letter, sub_lines, source_fetch_id)
            _union_subdivisions(data, subchapter, number)

    if not data.notes:
        raise RuntimeError(f"no notes found in {path}; the PDF layout has changed")
    return data


def _by_subchapter(pages: list[str]) -> Iterable[tuple[str, list]]:
    """Group note pages under the subchapter banner that precedes them, and split each
    group into numbered notes."""
    current = None
    grouped: dict[str, list[tuple[int, str]]] = {}

    for index, page in enumerate(pages):
        banner = SUBCHAPTER_BANNER.search(page)
        if banner:
            current = banner.group(1)
        lines = [line for line in page.split("\n") if line.strip()]
        if current and any(NOTE_HEADER.match(line.strip()) for line in lines[:8]):
            grouped.setdefault(current, []).extend(
                (index, line.strip()) for line in lines
                if not FURNITURE.match(line.strip())
            )

    for subchapter, lines in grouped.items():
        yield subchapter, _split_notes(lines)


def _split_notes(lines: list[tuple[int, str]]) -> list[tuple[str, list[tuple[int, str]]]]:
    # Note numbers only ever increase down a subchapter, and the schedule skips numbers it
    # has repealed. Requiring an increase is what stops a stray '3.' inside a sentence from
    # opening a second note 3 and swallowing the rest of the subchapter.
    notes: list[tuple[str, list[tuple[int, str]]]] = []
    current: list[tuple[int, str]] | None = None
    highest = 0

    for page, line in lines:
        match = NOTE_START.match(line)
        if match and int(match.group(1)) > highest:
            highest = int(match.group(1))
            current = [(page, match.group(2))] if match.group(2) else []
            notes.append((match.group(1), current))
        elif current is not None:
            current.append((page, line))

    return notes


def _letter_index(letter: str) -> int:
    # The schedule letters subdivisions a..z, then aa..zz, then aaa..zzz -- note 20 runs
    # as far as (www). Anything not of that shape is not a subdivision label.
    if len(set(letter)) != 1:
        return -1
    return (len(letter) - 1) * 26 + (ord(letter[0]) - ord("a"))


def _split_subdivisions(lines):
    # A label is accepted only if it is the next in sequence, or close to it. Two things
    # make that necessary. Roman sub-items -- (i), (ii), (iii) -- look exactly like letter
    # subdivisions and would open new ones. And a label quoted inside prose can be far
    # ahead: note 20's body mentions (vvv), which under a plain monotonic rule was accepted
    # right after (a) and then blocked the real (b) and everything following it.
    #
    # MAX_GAP leaves room for a label lost to a page break without leaving room for a jump
    # of seventy.
    lead, subdivisions, current = [], [], None
    highest = -1

    for page, line in lines:
        match = SUBDIVISION_START.match(line)
        index = _letter_index(match.group(1)) if match else -1
        if match and highest < index <= highest + MAX_GAP:
            highest = index
            current = [(page, match.group(2))] if match.group(2) else []
            subdivisions.append((match.group(1), current))
        elif current is not None:
            current.append((page, line))
        else:
            lead.append((page, line))
    return lead, subdivisions


def _union_subdivisions(data, subchapter, number):
    # A note-level record is meant to hold what all its subdivisions hold, because a
    # provision citing the note without one is pointing at all of them. Reading that off the
    # parent's own body works until the body is mostly words: U.S. note 20 runs to 912,964
    # characters, its code density falls under the list threshold, and it was stored as
    # prose with no codes at all -- leaving 38 provisions that cite it with nothing to reach.
    # Taking the union directly does not depend on how much prose surrounds the lists. D-0040.
    parent = (subchapter, number, None)
    if any(row["note_key"] == parent for row in data.subheadings):
        return

    inherited, seen = [], set()
    for row in data.subheadings:
        key = row["note_key"]
        if key[0] != subchapter or key[1] != number or key[2] is None:
            continue
        if row["hts_prefix"] in seen:
            continue
        seen.add(row["hts_prefix"])
        inherited.append({"note_key": parent, "hts_prefix": row["hts_prefix"],
                          "ordinal": len(inherited)})
    if not inherited:
        return

    data.subheadings.extend(inherited)
    for note in data.notes:
        if (note["subchapter"], note["note_number"], note["subdivision"]) == parent:
            note["content_kind"] = "mixed"
            break


def _add(data, subchapter, number, subdivision, lines, source_fetch_id):
    body = " ".join(line for _, line in lines).strip()
    if not body:
        return

    pages = [page for page, _ in lines]
    codes = find_codes(body)
    kind = _content_kind(body, codes)
    if kind == "prose":
        named = _codes_named_in_prose(body)
        if named:
            codes, kind = named, "mixed"
    label = (f"U.S. note {number}"
             f"{'(' + subdivision + ')' if subdivision else ''} to subchapter {subchapter}")

    data.notes.append({
        "note_kind": "us_note",
        "subchapter": subchapter,
        "note_number": number,
        "subdivision": subdivision,
        "label": label,
        "body": body,
        "content_kind": kind,
        "page_from": min(pages) + 1,
        "page_to": max(pages) + 1,
        "source_fetch_id": source_fetch_id,
    })

    if kind == "prose":
        return
    # A note-level record repeats its subdivisions' codes, because a provision citing the
    # note without a subdivision is pointing at all of them.
    seen = set()
    for ordinal, code in enumerate(codes):
        if code in seen:
            continue
        seen.add(code)
        data.subheadings.append({
            "note_key": (subchapter, number, subdivision),
            "hts_prefix": code,
            "ordinal": ordinal,
        })


def _codes_named_in_prose(body: str) -> list[str]:
    if not AFFIRMS.search(body) or NEGATES.search(body):
        return []
    found = ENUMERATED.findall(body) + SCOPED_CODE.findall(body)
    return list(dict.fromkeys(found))


def find_codes(text: str) -> list[str]:
    """Read every code in a body, including the runs pypdf leaves unseparated.

    The list pages are four columns wide and flatten into '0201.10.500201.10.10' with no
    separator, so a code may begin immediately after the one before it. A match is kept
    when it starts at a non-digit boundary, or exactly where the previous match ended --
    which admits the runs without also reading '12345.67' out of the middle of a longer
    number.

    Args:
        text: A note body.

    Returns:
        The codes in the order they appear, duplicates included.
    """
    codes, end = [], -1
    for match in CODE.finditer(text):
        start = match.start()
        if start == 0 or start == end or not text[start - 1].isdigit():
            codes.append(match.group(0))
            end = match.end()
    return codes


def _content_kind(body: str, codes: list[str]) -> str:
    if len(codes) < LIST_MINIMUM:
        return "prose"
    density = len("".join(codes)) / max(len(body.replace(" ", "")), 1)
    if density > LIST_DENSITY:
        return "subheading_list"
    return "mixed" if density > MIXED_DENSITY else "prose"


NOTE_COLUMNS = ("note_kind", "subchapter", "note_number", "subdivision", "label", "body",
                "content_kind", "page_from", "page_to", "source_fetch_id")

# DELETE rather than TRUNCATE, which D-0025 preferred: Postgres refuses to truncate a table
# another references, and rule_note must survive -- its rows are facts from the Chapter 99
# side, written by an earlier task in this same run. Clearing note_id first leaves the
# delete with no references to chase, and 509 notes make the cost irrelevant either way.
# note_subheading cascades; rule_base_match.note_id is set null and Step 5 rebuilds it.
CLEAR = ("UPDATE rule_note SET note_id = NULL WHERE note_id IS NOT NULL", "DELETE FROM note")


def load_notes(data: NotesData, *, run_id: str | None, dsn: str | None = None) -> dict[str, Any]:
    """Replace the note tables with this parse, in one transaction.

    Args:
        data: Everything ``parse_notes`` produced.
        run_id: The Hatchet run, recorded on each issue.
        dsn: Connection string. Falls back to ``DATABASE_URL``.

    Returns:
        Row counts, and how the records divided by content kind.
    """
    with connect(dsn) as conn, conn.cursor() as cursor:
        cursor.execute("DELETE FROM parse_issue WHERE stage = %s", (STAGE,))
        for statement in CLEAR:
            cursor.execute(statement)

        statement = f"COPY note ({', '.join(NOTE_COLUMNS)}) FROM STDIN"
        with cursor.copy(statement) as copy:
            for note in data.notes:
                copy.write_row([note[column] for column in NOTE_COLUMNS])

        cursor.execute(
            "SELECT id, subchapter, note_number, subdivision FROM note")
        ids = {(sub, num, div): note_id
               for note_id, sub, num, div in cursor.fetchall()}

        with cursor.copy("COPY note_subheading (note_id, hts_prefix, ordinal) FROM STDIN") as copy:
            for row in data.subheadings:
                copy.write_row([ids[row["note_key"]], row["hts_prefix"], row["ordinal"]])

        insert_issues(cursor, run_id, data.issues)

    kinds: dict[str, int] = {}
    for note in data.notes:
        kinds[note["content_kind"]] = kinds.get(note["content_kind"], 0) + 1

    return {
        "notes": len(data.notes),
        "subheadings": len(data.subheadings),
        "issues": len(data.issues),
        "kinds": kinds,
        "subchapters": len({n["subchapter"] for n in data.notes}),
    }
