"""Every read behind a duty answer, in one file.

These are not hidden plumbing. A page says "this provision matched because U.S. note 31(b)
lists your code", and the query below is what that claim rests on -- so the SQL is written to
be read, and `/api/duty` returns what it produced.
"""

# The classified good, with the ancestor chain that gives its description meaning. "Other"
# alone says nothing, which is why full_description exists (D-0012).
CLASSIFICATION = """
WITH RECURSIVE chain(hts, parent_hts, depth) AS (
    SELECT hts, parent_hts, 0 FROM hts_base WHERE hts = %(hts)s
    UNION ALL
    SELECT b.hts, b.parent_hts, c.depth + 1
    FROM hts_base b JOIN chain c ON b.hts = c.parent_hts
)
SELECT b.hts, b.description, b.full_description, b.units,
       b.rate_text, b.rate_kind, b.rate_ad_valorem_pct, b.rate_specific_amount,
       b.rate_specific_unit, b.rate_inherited_from, b.special_text,
       b.col2_rate_text, b.col2_rate_kind, b.col2_ad_valorem_pct,
       b.col2_specific_amount, b.col2_specific_unit, b.col2_inherited_from,
       (SELECT array_agg(hts ORDER BY depth DESC) FROM chain WHERE depth > 0) AS ancestors
FROM hts_base b WHERE b.hts = %(hts)s
"""

# Which provisions apply, and the whole of the reason they do.
#
# Three ways in, and a provision can arrive by more than one:
#
#   A  it names the code in its own description        rule_base_match
#   B  it cites a note whose list contains the code    note_base_match through rule_note
#   C  it names the country and limits no goods        scope = 'by_country_all_goods'
#
# Path B is the one that is easy to forget. rule_base_match holds only what a provision wrote
# down itself; 9903.91.01 writes down no code at all and reaches steel through U.S. note
# 31(b). Querying the first table alone under-reports by most of subchapter III (D-0036).
#
# The country filter is a veto, not a third path: a provision that names China is not about a
# Vietnamese shipment however its codes match. A provision naming no country is not filtered,
# because the reciprocal baseline genuinely does apply to everyone.
APPLICABLE = """
WITH reached AS (
    SELECT rule_hts FROM rule_base_match WHERE base_hts = %(hts)s
    UNION
    SELECT rn.rule_hts FROM note_base_match nbm
      JOIN rule_note rn ON rn.note_id = nbm.note_id
    WHERE nbm.base_hts = %(hts)s
),
named AS (
    SELECT rule_hts FROM rule_country
    WHERE relation = 'product_of' AND country_code = %(country)s
),
origin_scoped AS (SELECT DISTINCT rule_hts FROM rule_country)
SELECT r.hts, r.description, r.full_description, r.scope,
       r.rate_text, r.rate_kind, r.rate_ad_valorem_pct,
       r.rate_specific_amount, r.rate_specific_unit,
       r.additional_duty_text, r.additional_duty_pct,
       r.additional_duty_amount, r.additional_duty_unit,
       r.effective_from, r.effective_to, r.status, r.status_note,
       p.heading_prefix, p.label, p.statute, p.agency, p.evidence, p.reference_url
FROM rule r
LEFT JOIN trade_programme p ON left(r.hts, 7) = p.heading_prefix
WHERE (
        r.hts IN (SELECT rule_hts FROM reached)
        AND (r.hts NOT IN (SELECT rule_hts FROM origin_scoped)
             OR r.hts IN (SELECT rule_hts FROM named))
      )
   OR (r.scope = 'by_country_all_goods' AND r.hts IN (SELECT rule_hts FROM named))
ORDER BY r.hts
"""

# Path A's evidence: the code the provision itself printed, and whether the match was the
# code exactly or a family beneath it.
EVIDENCE_DIRECT = """
SELECT rule_hts, cited_code, match_kind
FROM rule_base_match WHERE base_hts = %(hts)s
"""

# Path B's evidence. match_precision travels with it because it changes what the reader is
# being told: 'parent_fallback' means the note we could isolate is the parent of the one the
# provision named, so this coverage is wider than the provision's real scope (D-0038).
EVIDENCE_NOTE = """
SELECT rn.rule_hts, nbm.cited_code, nbm.match_kind,
       n.id AS note_id, n.label AS note_label, n.page_from,
       rn.match_precision, rn.cited_subdivision
FROM note_base_match nbm
JOIN rule_note rn ON rn.note_id = nbm.note_id
JOIN note n ON n.id = nbm.note_id
WHERE nbm.base_hts = %(hts)s
"""

# Path C's evidence, and the country names every matched provision carries -- a provision can
# name several, and 'China and Hong Kong' is two.
COUNTRIES = """
SELECT rule_hts, country_name, country_code
FROM rule_country WHERE rule_hts = ANY(%(rules)s) ORDER BY rule_hts, country_name
"""

# What carves goods out of a provision. Direction matters: source excludes target, so these
# are the provisions that can remove the duty above, not ones that add to it.
#
# One hop only, deliberately. The graph is 859 edges at depth 1 and 23 at depth 2, and it
# contains a cycle -- 9903.91.12 and 9903.91.13 exclude each other -- so a recursive walk
# needs a visited set to terminate and buys 23 edges for it (D-0044).
EXCLUSIONS = """
SELECT e.source_hts, e.target_hts, r.description, r.rate_kind,
       n.id AS note_id, n.label AS note_label
FROM rule_edge e
LEFT JOIN rule r ON r.hts = e.target_hts
LEFT JOIN rule_note rn ON rn.rule_hts = e.target_hts
LEFT JOIN note n ON n.id = rn.note_id
WHERE e.edge_type = 'excludes' AND e.source_hts = ANY(%(rules)s)
ORDER BY e.source_hts, e.target_hts
"""

# Substance identity, where the HTS code cannot choose. Four provisions cite 2922.49.30, each
# naming a different substance by CAS number; the classification does not pick between them
# and the goods do (D-0019).
IDENTIFIERS = """
SELECT rule_hts, kind, value FROM rule_identifier
WHERE rule_hts = ANY(%(rules)s) ORDER BY rule_hts, value
"""

# How many base codes each matched provision reaches. Read from rule_coverage rather than
# counted here: a duty page needs this for every provision it matched at once, and computing
# it live cost 1,568 ms of a 2,034 ms response for a laptop from China. D-0047.
COVERAGE = """
SELECT rule_hts, base_codes AS codes FROM rule_coverage WHERE rule_hts = ANY(%(rules)s)
"""


# Every note a matched provision points at, regardless of how the provision matched. The 58
# exclusion provisions on a Chinese query all arrive by country and carry no note evidence,
# yet each names a different USTR exclusion list -- which is the one document a reader can do
# something about.
CITED_NOTES = """
SELECT rn.rule_hts, rn.cited_text, rn.cited_subdivision, rn.match_precision,
       n.id AS note_id, n.label, n.page_from
FROM rule_note rn LEFT JOIN note n ON n.id = rn.note_id
WHERE rn.rule_hts = ANY(%(rules)s)
ORDER BY rn.rule_hts, n.label
"""


# Keyword search over the schedule's own wording. Two passes, because they fail differently:
# full text finds "steel plate hot-rolled" in a description written in that order, and
# trigram finds a misspelling or a fragment that stemming will not reach. Neither knows what
# a product is -- this matches prose, and classification stays the importer's job.
#
# The programme count is computed live. Measured at 3.8 ms for a page of 30 codes, against
# 1,568 ms for the coverage figure a duty page needs; the difference is cardinality, and
# D-0047 is about telling those two cases apart.
SEARCH = """
WITH hit AS (
    SELECT b.hts, b.full_description, b.units,
           b.rate_text, b.rate_kind, b.rate_ad_valorem_pct,
           ts_rank(b.full_description_tsv, plainto_tsquery('english', %(q)s)) AS rank
    FROM hts_base b
    WHERE b.full_description_tsv @@ plainto_tsquery('english', %(q)s)
    ORDER BY rank DESC, length(b.full_description)
    LIMIT %(limit)s
)
SELECT hit.*, (
    SELECT count(DISTINCT p.heading_prefix) FROM (
        SELECT rule_hts FROM rule_base_match WHERE base_hts = hit.hts
        UNION
        SELECT rn.rule_hts FROM note_base_match nbm
          JOIN rule_note rn ON rn.note_id = nbm.note_id
        WHERE nbm.base_hts = hit.hts
    ) reach
    JOIN trade_programme p ON p.heading_prefix = left(reach.rule_hts, 7)
) AS programmes
FROM hit ORDER BY rank DESC
"""

SEARCH_FUZZY = """
SELECT b.hts, b.full_description, b.units, b.rate_text, b.rate_kind, b.rate_ad_valorem_pct,
       similarity(b.full_description, %(q)s) AS rank, 0 AS programmes
FROM hts_base b
WHERE b.full_description %% %(q)s
ORDER BY rank DESC LIMIT %(limit)s
"""
