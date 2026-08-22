import pytest

from storage import atomic_write, build_manifest, clear_stale_parts

RELEASE = {"name": "2026HTSRev16", "title": "Revision 16 (2026)"}


def test_interrupted_write_leaves_nothing_at_the_destination(tmp_path):
    dest = tmp_path / "payload.json"

    with pytest.raises(RuntimeError):
        with atomic_write(dest) as handle:
            handle.write(b"half a payload")
            raise RuntimeError("connection dropped")

    assert not dest.exists()
    assert list(tmp_path.glob("*.part")) == []


def test_completed_write_replaces_the_previous_payload(tmp_path):
    dest = tmp_path / "payload.json"
    dest.write_bytes(b"previous release")

    with atomic_write(dest) as handle:
        handle.write(b"current release")

    assert dest.read_bytes() == b"current release"


def test_clearing_stale_parts_spares_finished_payloads(tmp_path):
    (tmp_path / "payload.json.part").write_bytes(b"abandoned")
    (tmp_path / "payload.json").write_bytes(b"finished")

    clear_stale_parts(tmp_path)

    assert list(tmp_path.glob("*.part")) == []
    assert (tmp_path / "payload.json").read_bytes() == b"finished"


@pytest.mark.parametrize(
    "entries, complete",
    [
        ([("ch99", "fetched"), ("base", "unchanged"), ("notes_pdf", "fetched")], True),
        ([("ch99", "fetched"), ("base", "failed"), ("notes_pdf", "fetched")], False),
        ([("ch99", "fetched"), ("base", "unchanged")], False),
    ],
)
def test_manifest_claims_completeness_only_when_every_source_landed(entries, complete):
    payload = [{"source_key": key, "status": status} for key, status in entries]

    assert build_manifest(RELEASE, payload)["complete"] is complete
