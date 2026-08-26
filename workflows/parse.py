from datetime import timedelta
from typing import Any

from hatchet_sdk import Context
from pydantic import BaseModel

from client import hatchet
from parsing.base import load_base, parse_base
from parsing.ch99 import load_ch99, parse_ch99
from parsing.db import resolve_source_fetch_ids
from parsing.manifest import load_manifest
from parsing.notes import load_notes, parse_notes
from parsing.programmes import load_programmes
from parsing.resolve import resolve

# Loading 26,246 rows takes longer than the engine's 60s default, and a task cancelled
# mid-insert would roll back rather than corrupt -- but it would also report nothing.
PARSE_TIMEOUT = timedelta(minutes=10)


class ParseInput(BaseModel):
    release: str | None = None


parse_workflow = hatchet.workflow(name="ParseHTS", input_validator=ParseInput)


@parse_workflow.task()
def load_payloads(input: ParseInput, ctx: Context) -> dict[str, Any]:
    # Unlike the scraper's tasks, this one raises. Part 1 reports failures instead of
    # raising so that summarize still runs and the manifest still covers every source
    # (D-0007); Part 2 has nothing to protect, and a run that parsed half the data
    # should be red.
    loaded = load_manifest(input.release)

    for key, provenance in resolve_source_fetch_ids(
        loaded["release"], loaded["sources"]
    ).items():
        loaded["sources"][key].update(provenance)
        if provenance["reconstructed"]:
            ctx.log(f"no source_fetch row for {key}; rebuilt one from the manifest")

    ctx.log(f"parsing {loaded['release']['name']} from {loaded['directory']}")
    return loaded


@parse_workflow.task(parents=[load_payloads], execution_timeout=PARSE_TIMEOUT)
def parse_base_schedule(input: ParseInput, ctx: Context) -> dict[str, Any]:
    source = ctx.task_output(load_payloads)["sources"]["base"]

    rows, issues = parse_base(source["path"], source_fetch_id=source["source_fetch_id"])
    written = load_base(rows, issues, run_id=ctx.workflow_run_id)

    ctx.log(f"hts_base: {written['rows']:,} rows, {written['inherited']:,} inherited "
            f"rates, {written['issues']:,} issues")
    return written


@parse_workflow.task(parents=[load_payloads], execution_timeout=PARSE_TIMEOUT)
def parse_chapter99(input: ParseInput, ctx: Context) -> dict[str, Any]:
    # Runs beside parse_base_schedule, not after it: the fact tables it writes carry no
    # foreign key into hts_base. Only the resolver needs both, and that is Step 5.
    source = ctx.task_output(load_payloads)["sources"]["ch99"]

    data = parse_ch99(source["path"], source_fetch_id=source["source_fetch_id"])
    written = load_ch99(data, run_id=ctx.workflow_run_id)

    ctx.log(f"rule: {written['rules']:,} rows, {written['references']:,} references, "
            f"{written['excludes']:,} exclusions, {written['issues']:,} issues")
    return written


@parse_workflow.task(parents=[load_payloads, parse_chapter99], execution_timeout=PARSE_TIMEOUT)
def parse_us_notes(input: ParseInput, ctx: Context) -> dict[str, Any]:
    # After parse_chapter99 rather than beside it: loading the notes clears
    # rule_note.note_id, and that column belongs to rows parse_chapter99 writes.
    source = ctx.task_output(load_payloads)["sources"]["notes_pdf"]

    data = parse_notes(source["path"], source_fetch_id=source["source_fetch_id"])
    written = load_notes(data, run_id=ctx.workflow_run_id)

    ctx.log(f"note: {written['notes']:,} records across {written['subchapters']} "
            f"subchapters, {written['subheadings']:,} listed codes")
    return written


@parse_workflow.task(
    parents=[parse_base_schedule, parse_chapter99, parse_us_notes],
    execution_timeout=PARSE_TIMEOUT,
)
def resolve_citations(input: ParseInput, ctx: Context) -> dict[str, Any]:
    # Last, and the only task that reads tables three others wrote. Everything it produces
    # is derived, so it can be rebuilt without re-reading a payload (D-0015).
    written = resolve(run_id=ctx.workflow_run_id)

    ctx.log(f"rule_base_match {written['rule_matches']:,} rows, note_base_match "
            f"{written['note_matches']:,} rows, {written['rescoped']:,} provisions rescoped")
    return written


@parse_workflow.task(parents=[resolve_citations], execution_timeout=PARSE_TIMEOUT)
def materialize(input: ParseInput, ctx: Context) -> dict[str, Any]:
    # Everything derived, rebuilt in the same run that rewrites the tables under it, so there
    # is no window in which it is stale rather than a short one. After the resolver, because
    # rule_coverage counts what the resolver wrote.
    #
    # Only one thing is precomputed for speed, and only after measuring the shape a page
    # actually asks for: coverage for one provision costs 4 ms, for the 88 a laptop from
    # China matches it costs 1,568 ms. D-0044 records what was measured and not built;
    # D-0047 records the one measurement that was taken wrongly and what it cost.
    written = load_programmes()

    ctx.log(f"rule_coverage: {written['coverage_rows']:,} provisions; "
            f"trade_programme: {written['programmes']} programmes labelling "
            f"{written['rules_labelled']:,} of {written['subchapter_iii_rules']:,} "
            f"subchapter III provisions")
    return written


@parse_workflow.task(
    parents=[load_payloads, parse_base_schedule, parse_chapter99, parse_us_notes,
             resolve_citations, materialize])
def summarize(input: ParseInput, ctx: Context) -> dict[str, Any]:
    loaded = ctx.task_output(load_payloads)

    return {
        "release": loaded["release"]["name"],
        "directory": loaded["directory"],
        "sources": {
            key: entry["source_fetch_id"] for key, entry in loaded["sources"].items()
        },
        "hts_base": ctx.task_output(parse_base_schedule),
        "chapter99": ctx.task_output(parse_chapter99),
        "notes": ctx.task_output(parse_us_notes),
        "resolved": ctx.task_output(resolve_citations),
        "programmes": ctx.task_output(materialize),
    }
