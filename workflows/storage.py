"""
Where payloads land, and how they get there without leaving half-written files.

A download that dies mid-transfer must never leave something at the final path that
looks like a complete payload, because the next run would hash it, find it unchanged,
and trust it forever. Everything is written to a sibling `.part` file and moved into
place with os.replace, which is atomic within a filesystem.
"""

import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO, Iterator

from sources import SOURCE_KEYS

MANIFEST_NAME = "manifest.json"
PART_SUFFIX = ".part"
READ_CHUNK = 1024 * 1024

# Statuses that mean the payload is on disk and trustworthy.
LANDED = frozenset({"fetched", "unchanged"})


def data_root() -> Path:
    """The bind-mounted download directory: /data in the worker, ./data on the host."""
    return Path(os.environ.get("DATA_DIR", "/data"))


def release_dir(release: str, root: Path | None = None) -> Path:
    """Payloads are scoped by release, so a new revision never overwrites an old one."""
    return (root or data_root()) / "raw" / release


@contextmanager
def atomic_write(dest: Path) -> Iterator[BinaryIO]:
    """Yield a handle to write `dest`; the caller's bytes only appear on success."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + PART_SUFFIX)
    handle = part.open("wb")

    try:
        yield handle
        handle.flush()
        os.fsync(handle.fileno())
    except BaseException:
        handle.close()
        part.unlink(missing_ok=True)
        raise

    handle.close()
    os.replace(part, dest)


def clear_stale_parts(directory: Path) -> list[Path]:
    """Remove `.part` files an earlier run abandoned, e.g. by being killed mid-write."""
    if not directory.exists():
        return []

    removed = sorted(directory.glob(f"*{PART_SUFFIX}"))
    for path in removed:
        path.unlink(missing_ok=True)
    return removed


def sha256_of(path: Path) -> str:
    """Hash a file already on disk, so a re-fetch can tell identical bytes from new ones."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(READ_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(release: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Describe what is on disk for one release.

    `complete` is the flag downstream code reads before trusting the directory: it is
    true only when every known source has an entry and every entry landed. A run that
    lost one source still writes a manifest, but an honest one.
    """
    landed = {
        entry["source_key"] for entry in entries if entry.get("status") in LANDED
    }
    return {
        "release": release,
        "complete": landed >= SOURCE_KEYS,
        "sources": entries,
    }


def write_manifest(directory: Path, manifest: dict[str, Any]) -> Path:
    """Write the manifest atomically, so a reader never sees a truncated one."""
    dest = directory / MANIFEST_NAME
    with atomic_write(dest) as handle:
        handle.write(json.dumps(manifest, indent=2).encode())
    return dest
