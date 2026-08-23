from typing import Any

from hatchet_sdk import Context
from pydantic import BaseModel

from client import hatchet
from parsing.db import resolve_source_fetch_ids
from parsing.manifest import load_manifest


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
            ctx.log(
                f"no source_fetch row for {key}; rebuilt one from the manifest")

    ctx.log(f"parsing {loaded['release']['name']} from {loaded['directory']}")
    return loaded


@parse_workflow.task(parents=[load_payloads])
def summarize(input: ParseInput, ctx: Context) -> dict[str, Any]:
    loaded = ctx.task_output(load_payloads)

    return {
        "release": loaded["release"]["name"],
        "directory": loaded["directory"],
        "sources": {
            key: entry["source_fetch_id"] for key, entry in loaded["sources"].items()
        },
    }
