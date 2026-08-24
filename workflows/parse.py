from datetime import timedelta
from typing import Any

from hatchet_sdk import Context
from pydantic import BaseModel

from client import hatchet
from parsing.base import load_base, parse_base
from parsing.db import resolve_source_fetch_ids
from parsing.manifest import load_manifest

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


@parse_workflow.task(parents=[load_payloads, parse_base_schedule])
def summarize(input: ParseInput, ctx: Context) -> dict[str, Any]:
    loaded = ctx.task_output(load_payloads)

    return {
        "release": loaded["release"]["name"],
        "directory": loaded["directory"],
        "sources": {
            key: entry["source_fetch_id"] for key, entry in loaded["sources"].items()
        },
        "hts_base": ctx.task_output(parse_base_schedule),
    }
