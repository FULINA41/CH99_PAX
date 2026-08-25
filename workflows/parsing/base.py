import json
from typing import Any

from parsing.db import connect
from parsing.issues import Issue, insert_issues
from parsing.rates import parse_rate
from parsing.tree import build_nodes, inherit

STAGE = "base"

COLUMNS = (
    "hts", "parent_hts", "indent", "description", "full_description", "units",
    "rate_text", "rate_kind", "rate_ad_valorem_pct", "rate_specific_amount",
    "rate_specific_unit", "rate_inherited_from",
    "col2_rate_text", "col2_rate_kind", "col2_ad_valorem_pct",
    "col2_specific_amount", "col2_specific_unit", "col2_inherited_from",
    "special_text", "source_fetch_id",
)

COPY_IN = f"COPY hts_base ({', '.join(COLUMNS)}) FROM STDIN"

# TRUNCATE, not DELETE. parent_hts and rate_inherited_from both reference this table with
# ON DELETE SET NULL, so deleting 26,246 rows makes Postgres null out ~26,000 references
# one at a time: measured at 10.4s against 0.00s truncated. The tables are named rather
# than CASCADEd so that a new table referencing hts_base fails here loudly instead of
# being emptied without anyone deciding it should be.
TRUNCATE = "TRUNCATE hts_base, rule_base_match, note_base_match"


def parse_base(path: str, *, source_fetch_id: int | None) -> tuple[list[dict[str, Any]], list[Issue]]:
    """Read the base export and build the rows `hts_base` expects.

    Args:
        path: The staged ``base.json``.
        source_fetch_id: The fetch these rows are attributed to.

    Returns:
        The rows in insertion order -- parents before children, which the self
        references on ``parent_hts`` and ``rate_inherited_from`` depend on -- and every
        issue found while parsing.
    """
    with open(path) as handle:
        export = json.load(handle)

    nodes, issues = build_nodes(export, STAGE)
    general = {node.hts: parse_rate(node.row.get("general")) for node in nodes}
    column2 = {node.hts: parse_rate(node.row.get("other")) for node in nodes}

    def states_its_own(table):
        return lambda node: table[node.hts].kind != "none"

    general_from = inherit(nodes, states_its_own(general))
    column2_from = inherit(nodes, states_its_own(column2))

    for node in nodes:
        for table, column in ((general, "general"), (column2, "other")):
            if table[node.hts].kind == "prose":
                issues.append(Issue(
                    stage=STAGE,
                    kind="unparsed_rate",
                    subject=node.hts,
                    detail=f"{column}: {table[node.hts].text}",
                ))

    rows = []
    for node in nodes:
        # The effective rate is the ancestor's, copied down. rate_inherited_from is what
        # says it was copied, so rate_text can show the rate that actually applies
        # rather than the empty string this row printed (D-0014).
        source = general_from.get(node.hts)
        rate = general[source or node.hts]
        column2_source = column2_from.get(node.hts)
        column2_rate = column2[column2_source or node.hts]

        rows.append({
            "hts": node.hts,
            "parent_hts": node.parent_hts,
            "indent": node.indent,
            "description": node.description,
            "full_description": node.full_description,
            "units": node.row.get("units") or None,
            "rate_text": rate.text,
            "rate_kind": rate.kind,
            "rate_ad_valorem_pct": rate.ad_valorem_pct,
            "rate_specific_amount": rate.specific_amount,
            "rate_specific_unit": rate.specific_unit,
            "rate_inherited_from": source,
            "col2_rate_text": column2_rate.text,
            "col2_rate_kind": column2_rate.kind,
            "col2_ad_valorem_pct": column2_rate.ad_valorem_pct,
            "col2_specific_amount": column2_rate.specific_amount,
            "col2_specific_unit": column2_rate.specific_unit,
            "col2_inherited_from": column2_source,
            "special_text": (node.row.get("special") or "").strip() or None,
            "source_fetch_id": source_fetch_id,
        })

    return rows, issues


def load_base(rows, issues, *, run_id: str | None, dsn: str | None = None) -> dict[str, Any]:
    """Replace `hts_base` with these rows, in one transaction.

    Delete then insert rather than upsert: a code the schedule dropped would otherwise
    survive as a row that still satisfies every foreign key (D-0020). A crash before
    COMMIT leaves the previous contents intact.

    Args:
        rows: Rows from ``parse_base``, parents first.
        issues: Issues from the same call.
        run_id: The Hatchet run, recorded on each issue.
        dsn: Connection string. Falls back to ``DATABASE_URL``.

    Returns:
        How many rows and issues were written, and how many rates were inherited.
    """
    with connect(dsn) as conn, conn.cursor() as cursor:
        cursor.execute("DELETE FROM parse_issue WHERE stage = %s", (STAGE,))
        cursor.execute(TRUNCATE)
        # Streamed in document order, which is what lets parent_hts and
        # rate_inherited_from reference rows written moments earlier. COPY over
        # executemany is worth 2.25s -> 1.58s here, and more once the resolver writes
        # an order of magnitude more rows.
        with cursor.copy(COPY_IN) as copy:
            for row in rows:
                copy.write_row([row[column] for column in COLUMNS])
        insert_issues(cursor, run_id, issues)

    return {
        "rows": len(rows),
        "issues": len(issues),
        "inherited": sum(1 for row in rows if row["rate_inherited_from"]),
        "col2_inherited": sum(1 for row in rows if row["col2_inherited_from"]),
        "prose_rates": sum(1 for issue in issues if issue.kind == "unparsed_rate"),
    }
