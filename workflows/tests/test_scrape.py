import json

import pytest

import scrape
from scrape import ScrapeInput, summarize

RELEASE = {"name": "2026HTSRev16", "title": "Revision 16 (2026)"}


def landed(key):
    return {"source_key": key, "status": "fetched", "bytes": 1, "sha256": "abc"}


def parent_outputs(directory):
    return {
        "resolve_release": {
            "release": RELEASE,
            "directory": str(directory),
            "pinned": False,
        },
        "fetch_ch99": landed("ch99"),
        "fetch_base": landed("base"),
        "fetch_notes_pdf": landed("notes_pdf"),
    }


def test_manifest_is_written_even_when_the_release_recheck_fails(tmp_path, monkeypatch):
    # The re-check is a detection, not a gate: the payloads are already on disk, so a
    # USITC blip must not cost us the manifest that describes them.
    def unreachable():
        raise RuntimeError("could not resolve the current release: HTTP 503")

    monkeypatch.setattr(scrape, "current_release", unreachable)

    summarize.mock_run(input=ScrapeInput(), parent_outputs=parent_outputs(tmp_path))

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["complete"] is True
    assert "could not resolve" in manifest["release_recheck_failed"]


def test_a_release_change_during_the_run_is_recorded(tmp_path, monkeypatch):
    monkeypatch.setattr(scrape, "current_release", lambda: {"name": "2026HTSRev17"})

    summarize.mock_run(input=ScrapeInput(), parent_outputs=parent_outputs(tmp_path))

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["release_changed_during_run"] == {
        "before": "2026HTSRev16",
        "after": "2026HTSRev17",
    }


def test_a_failed_source_still_leaves_a_manifest_behind(tmp_path, monkeypatch):
    monkeypatch.setattr(scrape, "current_release", lambda: RELEASE)
    outputs = parent_outputs(tmp_path)
    outputs["fetch_base"] = {"source_key": "base", "status": "failed", "error": "HTTP 503"}

    with pytest.raises(RuntimeError, match="base"):
        summarize.mock_run(input=ScrapeInput(), parent_outputs=outputs)

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["complete"] is False
