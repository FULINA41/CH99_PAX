from fastapi import APIRouter, HTTPException

from db import one, rows
from reference.wording import reading

router = APIRouter(tags=["provisions"])

RULE = """
SELECT r.hts, r.heading, r.subchapter, r.description, r.full_description, r.scope,
       r.rate_text, r.rate_kind, r.rate_ad_valorem_pct,
       r.rate_specific_amount, r.rate_specific_unit,
       r.additional_duty_text, r.additional_duty_pct,
       r.additional_duty_amount, r.additional_duty_unit,
       r.effective_from, r.effective_to, r.status, r.status_note,
       c.base_codes, c.direct_codes, c.note_codes,
       p.heading_prefix, p.label, p.statute, p.agency, p.evidence, p.reference_url
FROM rule r
LEFT JOIN rule_coverage c ON c.rule_hts = r.hts
LEFT JOIN trade_programme p ON left(r.hts, 7) = p.heading_prefix
WHERE r.hts = %(hts)s
"""

# Both directions of the exclusion graph, in one read. They are different claims: what this
# provision carves out, and what carves this provision out. One hop only -- the graph is 859
# edges at depth 1, 23 at depth 2, and contains a cycle (9903.91.12 <-> 9903.91.13), so a
# recursive walk buys 23 edges for a visited set. D-0044.
EDGES = """
SELECT e.edge_type, e.source_hts, e.target_hts,
       CASE WHEN e.source_hts = %(hts)s THEN 'carves out' ELSE 'is carved out by' END AS direction,
       r.description, r.rate_text
FROM rule_edge e
LEFT JOIN rule r ON r.hts = CASE WHEN e.source_hts = %(hts)s THEN e.target_hts ELSE e.source_hts END
WHERE e.edge_type = 'excludes' AND (e.source_hts = %(hts)s OR e.target_hts = %(hts)s)
ORDER BY direction, 3
"""

CITED_CODES = """
SELECT e.target_hts AS cited_code,
       (SELECT count(*) FROM rule_base_match m
        WHERE m.rule_hts = %(hts)s AND m.cited_code = e.target_hts) AS reaches
FROM rule_edge e WHERE e.source_hts = %(hts)s AND e.edge_type = 'references'
ORDER BY 1
"""

NOTES = """
SELECT rn.cited_text, rn.cited_subdivision, rn.match_precision,
       n.id AS note_id, n.label, n.content_kind, n.page_from, n.page_to,
       (SELECT count(*) FROM note_subheading s WHERE s.note_id = n.id) AS listed_codes
FROM rule_note rn LEFT JOIN note n ON n.id = rn.note_id
WHERE rn.rule_hts = %(hts)s ORDER BY n.label
"""

COUNTRIES = "SELECT country_name, country_code, relation FROM rule_country WHERE rule_hts = %(hts)s ORDER BY 1"
IDENTIFIERS = "SELECT kind, value FROM rule_identifier WHERE rule_hts = %(hts)s ORDER BY 2"

# A sample rather than the whole reach: note 52 lists 4,166 codes and a page that prints them
# all is a page nobody reads. The count is on the provision; this is what it looks like.
SAMPLE = """
SELECT base_hts, cited_code, match_kind, 'named directly' AS path FROM rule_base_match
WHERE rule_hts = %(hts)s
UNION ALL
SELECT nbm.base_hts, nbm.cited_code, nbm.match_kind, 'through a note'
FROM note_base_match nbm JOIN rule_note rn ON rn.note_id = nbm.note_id
WHERE rn.rule_hts = %(hts)s
ORDER BY 1 LIMIT 25
"""


@router.get("/rule/{hts}")
def read_rule(hts: str) -> dict:
    """One Chapter 99 provision: what it says, what it reaches, and what can undo it.

    Args:
        hts: A Chapter 99 code.

    Returns:
        The provision, its coverage by both paths, the notes it cites, the countries and CAS
        numbers it names, both directions of its exclusion edges, and a sample of the base
        codes it reaches.

    Raises:
        HTTPException: 404 when no such provision exists in this revision.
    """
    found = one(RULE, {"hts": hts})
    if found is None:
        raise HTTPException(404, f"{hts} is not a Chapter 99 provision in this revision")

    edges = rows(EDGES, {"hts": hts})
    # The stored token never reaches the page; a reader is told what the provision does.
    for field in ("rate_kind", "scope", "status"):
        found[f"{field}_reading"] = reading(field, found[field])
    sample = rows(SAMPLE, {"hts": hts})
    for row in sample:
        row["how"] = reading("match_kind", row["match_kind"])
    return {
        "rule": found,
        "cited_codes": rows(CITED_CODES, {"hts": hts}),
        "notes": rows(NOTES, {"hts": hts}),
        "countries": rows(COUNTRIES, {"hts": hts}),
        "identifiers": rows(IDENTIFIERS, {"hts": hts}),
        "carves_out": [e for e in edges if e["direction"] == "carves out"],
        "carved_out_by": [e for e in edges if e["direction"] == "is carved out by"],
        "sample": sample,
    }
