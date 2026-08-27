from fastapi import APIRouter, HTTPException, Query

from db import one, rows

router = APIRouter(tags=["notes"])

NOTE = """
SELECT n.id, n.note_kind, n.subchapter, n.note_number, n.subdivision, n.label,
       n.body, n.content_kind, n.page_from, n.page_to,
       (SELECT count(*) FROM note_subheading s WHERE s.note_id = n.id) AS listed_codes
FROM note n WHERE n.id = %(id)s
"""

# The codes the note lists, in the order it printed them, a page at a time. Note 52 lists
# 4,166; sending them all so a browser can hide most of them is the wrong end to solve it at.
CODES = """
SELECT s.hts_prefix, s.ordinal,
       (SELECT count(*) FROM note_base_match m WHERE m.note_id = s.note_id
        AND m.cited_code = s.hts_prefix) AS reaches
FROM note_subheading s WHERE s.note_id = %(id)s
ORDER BY s.ordinal OFFSET %(offset)s LIMIT %(limit)s
"""

CITING = """
SELECT DISTINCT ON (rn.rule_hts)
       rn.rule_hts, rn.cited_text, rn.cited_subdivision, rn.match_precision,
       r.rate_text, r.rate_kind, r.status,
       CASE WHEN length(r.full_description) > 180
            THEN regexp_replace(left(r.full_description, 180), '\s+\S*$', '') || '…'
            ELSE r.full_description END AS description,
       p.label AS programme
FROM rule_note rn
JOIN rule r ON r.hts = rn.rule_hts
LEFT JOIN trade_programme p ON left(r.hts, 7) = p.heading_prefix
WHERE rn.note_id = %(id)s ORDER BY rn.rule_hts, length(rn.cited_text) DESC
"""

# The parent and its subdivisions, so a reader can walk the note the way the PDF prints it.
FAMILY = """
SELECT id, label, subdivision, content_kind,
       (SELECT count(*) FROM note_subheading s WHERE s.note_id = n.id) AS listed_codes
FROM note n
WHERE n.subchapter = %(subchapter)s AND n.note_number = %(number)s AND n.note_kind = %(kind)s
ORDER BY n.subdivision NULLS FIRST
"""


@router.get("/note/{note_id}")
def read_note(
    note_id: int,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict:
    """One U.S. note: its text, the codes it lists, and every provision that cites it.

    These are the documents Chapter 99 defers to. `9903.88.01` covers "the subheadings
    enumerated in U.S. note 20(b)", and that list exists in a PDF and nowhere else -- which is
    why the notes are a table at all (D-0016).

    Args:
        note_id: The note's id, as linked from a provision.
        offset: Where to start in the note's code list.
        limit: How many codes to return.

    Returns:
        The note, a page of its codes, its siblings, and the provisions citing it.

    Raises:
        HTTPException: 404 when there is no such note.
    """
    found = one(NOTE, {"id": note_id})
    if found is None:
        raise HTTPException(404, f"no note with id {note_id}")

    return {
        "note": found,
        "codes": rows(CODES, {"id": note_id, "offset": offset, "limit": limit}),
        "codes_offset": offset,
        "family": rows(FAMILY, {"subchapter": found["subchapter"],
                                "number": found["note_number"], "kind": found["note_kind"]}),
        "citing": rows(CITING, {"id": note_id}),
    }
