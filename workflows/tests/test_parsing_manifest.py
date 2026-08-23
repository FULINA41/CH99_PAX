import json

import pytest

from parsing.manifest import ManifestError, load_manifest
from sources import SOURCES

PAYLOAD = b"payload"


def stage(root, release, *, resolved_at=1.0, complete=True, drop=None, sizes=None):
    directory = root / "raw" / release
    directory.mkdir(parents=True)

    entries = []
    for source in SOURCES:
        if source.key != drop:
            (directory / source.filename).write_bytes(PAYLOAD)
        entries.append({
            "source_key": source.key,
            "status": "fetched",
            "sha256": None if source.key == drop and not complete else "abc123",
            "bytes": (sizes or {}).get(source.key, len(PAYLOAD)),
            "path": f"/data/raw/{release}/{source.filename}",
            "url": source.url(release),
            "fetched_at": "2026-08-23T00:00:00+00:00",
        })

    (directory / "manifest.json").write_text(json.dumps({
        "release": {"name": release, "title": None, "resolved_at": resolved_at},
        "complete": complete,
        "sources": entries,
    }))
    return directory


def test_a_manifest_that_lost_a_source_is_refused(tmp_path):
    stage(tmp_path, "2026HTSRev16", complete=False, drop="notes_pdf")

    with pytest.raises(ManifestError, match="notes_pdf"):
        load_manifest("2026HTSRev16", tmp_path)


def test_a_payload_named_in_the_manifest_but_absent_from_disk_is_refused(tmp_path):
    directory = stage(tmp_path, "2026HTSRev16")
    (directory / "base.json").unlink()

    with pytest.raises(ManifestError, match="not on disk"):
        load_manifest("2026HTSRev16", tmp_path)


def test_a_payload_whose_size_no_longer_matches_is_refused(tmp_path):
    stage(tmp_path, "2026HTSRev16", sizes={"base": 999})

    with pytest.raises(ManifestError, match="changed after it was fetched"):
        load_manifest("2026HTSRev16", tmp_path)


def test_the_newest_release_is_parsed_when_none_is_named(tmp_path):
    stage(tmp_path, "2026HTSRev15", resolved_at=1.0)
    stage(tmp_path, "2026HTSRev16", resolved_at=2.0)

    assert load_manifest(root=tmp_path)["release"]["name"] == "2026HTSRev16"


def test_an_incomplete_release_is_skipped_even_when_it_is_the_newest(tmp_path):
    stage(tmp_path, "2026HTSRev15", resolved_at=1.0)
    stage(tmp_path, "2026HTSRev16", resolved_at=2.0, complete=False, drop="base")

    assert load_manifest(root=tmp_path)["release"]["name"] == "2026HTSRev15"


def test_paths_are_rebuilt_locally_rather_than_taken_from_the_manifest(tmp_path):
    # The scraper records the path it wrote inside its own container. Part 2 may run
    # somewhere that path does not exist.
    directory = stage(tmp_path, "2026HTSRev16")

    loaded = load_manifest("2026HTSRev16", tmp_path)

    assert loaded["sources"]["ch99"]["path"] == str(directory / "ch99.json")


def test_an_empty_data_root_says_to_run_the_scraper(tmp_path):
    (tmp_path / "raw").mkdir()

    with pytest.raises(ManifestError, match="run the scraper"):
        load_manifest(root=tmp_path)
