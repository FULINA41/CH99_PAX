from datetime import timedelta
from pathlib import Path
from typing import Any

from hatchet_sdk import Context, Hatchet
from pydantic import BaseModel

from fetching import WORST_CASE_SECONDS, fetch_source
from provenance import record_fetch
from release import current_release
from sources import source_by_key
from storage import build_manifest, clear_stale_parts, release_dir, write_manifest

hatchet = Hatchet()

# The engine cancels a task at execution_timeout, which defaults to 60s -- shorter than
# one fetch is allowed to take. Measured in Step 0, not assumed.
#
# Sized from the whole retry policy, not one attempt: fetching.py retries three times and
# a task cancelled mid-retry takes summarize with it (a task whose parent is CANCELLED
# never runs), leaving payloads on disk with no manifest -- the exact failure D-0007
# exists to prevent.
FETCH_TIMEOUT = timedelta(seconds=WORST_CASE_SECONDS + 60)


class ScrapeInput(BaseModel):
    release: str | None = None
    force: bool = False


scrape_workflow = hatchet.workflow(name="ScrapeHTS", input_validator=ScrapeInput)


@scrape_workflow.task()
def resolve_release(input: ScrapeInput, ctx: Context) -> dict[str, Any]:
    if input.release:
        release, pinned = {"name": input.release, "title": None}, True
    else:
        release, pinned = current_release(), False

    directory = release_dir(release["name"])
    directory.mkdir(parents=True, exist_ok=True)

    # Swept here, once, rather than inside the fetches: they share this directory and
    # run in parallel, so a sweep during them would delete a sibling's live .part.
    swept = clear_stale_parts(directory)
    if swept:
        ctx.log(f"cleared {len(swept)} stale .part file(s) left by an earlier run")

    return {"release": release, "directory": str(directory), "pinned": pinned}


def _fetch(key: str, input: ScrapeInput, ctx: Context) -> dict[str, Any]:
    resolved = ctx.task_output(resolve_release)
    release = resolved["release"]

    result = fetch_source(
        source_by_key(key),
        release["name"],
        Path(resolved["directory"]),
        force=input.force,
    )

    if result["status"] == "failed":
        # The task itself succeeds so that summarize still runs (D-0007); this log line
        # and the source_fetch row are where the failure is visible.
        ctx.log(f"FAILED {key} after {result['attempts']} attempt(s): {result['error']}")

    try:
        record_fetch(result, release=release, run_id=ctx.workflow_run_id)
    except Exception as exc:  # noqa: BLE001 - a payload on disk is not invalidated by this
        result["provenance_error"] = f"{type(exc).__name__}: {exc}"
        ctx.log(f"provenance write failed for {key}: {exc}")

    return result


@scrape_workflow.task(parents=[resolve_release], execution_timeout=FETCH_TIMEOUT, retries=0)
def fetch_ch99(input: ScrapeInput, ctx: Context) -> dict[str, Any]:
    # retries=0 throughout: fetching.py already retries with backoff, and it must, because
    # a task that reports failure instead of raising gets no retries from the engine.
    return _fetch("ch99", input, ctx)


@scrape_workflow.task(parents=[resolve_release], execution_timeout=FETCH_TIMEOUT, retries=0)
def fetch_base(input: ScrapeInput, ctx: Context) -> dict[str, Any]:
    return _fetch("base", input, ctx)


@scrape_workflow.task(parents=[resolve_release], execution_timeout=FETCH_TIMEOUT, retries=0)
def fetch_notes_pdf(input: ScrapeInput, ctx: Context) -> dict[str, Any]:
    return _fetch("notes_pdf", input, ctx)


@scrape_workflow.task(parents=[resolve_release, fetch_ch99, fetch_base, fetch_notes_pdf])
def summarize(input: ScrapeInput, ctx: Context) -> dict[str, Any]:
    resolved = ctx.task_output(resolve_release)
    release = resolved["release"]
    directory = Path(resolved["directory"])

    entries = [
        ctx.task_output(task) for task in (fetch_ch99, fetch_base, fetch_notes_pdf)
    ]
    manifest = build_manifest(release, entries)

    # The two bulk exports take no release parameter, so a revision published mid-run
    # would land in a directory named for the previous one. It cannot be prevented, only
    # detected and recorded.
    if not resolved["pinned"]:
        try:
            after = current_release()
        except Exception as exc:  # noqa: BLE001 - a detection must not veto the manifest
            # current_release raises by design, which is right in resolve_release: with no
            # release there is nowhere to write. Here the bytes have already landed, so a
            # USITC blip must not cost us the manifest that describes them.
            manifest["release_recheck_failed"] = f"{type(exc).__name__}: {exc}"
            ctx.log(f"release re-check failed, manifest written anyway: {exc}")
        else:
            if after["name"] != release["name"]:
                manifest["release_changed_during_run"] = {
                    "before": release["name"],
                    "after": after["name"],
                }
                ctx.log(f"release moved {release['name']} -> {after['name']} mid-run")

    write_manifest(directory, manifest)

    failed = [e["source_key"] for e in entries if e["status"] == "failed"]
    if failed:
        raise RuntimeError(
            f"{len(failed)} source(s) failed: {', '.join(failed)}. "
            f"The manifest in {directory} records what did land."
        )

    return {
        "release": release["name"],
        "directory": str(directory),
        "complete": manifest["complete"],
        "sources": {e["source_key"]: e["status"] for e in entries},
    }
