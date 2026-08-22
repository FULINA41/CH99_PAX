import hashlib
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Iterator

from sources import SOURCE_KEYS

MANIFEST_NAME = "manifest.json"
PART_SUFFIX = ".part"
READ_CHUNK = 1024 * 1024

# Statuses that mean the payload is on disk and trustworthy.
LANDED = frozenset({"fetched", "unchanged"})


def data_root() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


def release_dir(release: str, root: Path | None = None) -> Path:
    return (root or data_root()) / "raw" / release


@dataclass
class Staged:
    handle: BinaryIO
    path: Path
    keeping: bool = False

    def keep(self) -> None:
        self.keeping = True


@contextmanager
def staged_write(dest: Path) -> Iterator[Staged]:
    # A fetch only knows whether the payload changed after hashing it, so the caller keeps.
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + PART_SUFFIX)
    handle = part.open("wb")
    staged = Staged(handle=handle, path=part)

    try:
        yield staged
        handle.flush()
        os.fsync(handle.fileno())
    except BaseException:
        handle.close()
        part.unlink(missing_ok=True)
        raise

    handle.close()
    if staged.keeping:
        os.replace(part, dest)
    else:
        part.unlink(missing_ok=True)


@contextmanager
def atomic_write(dest: Path) -> Iterator[BinaryIO]:
    with staged_write(dest) as staged:
        yield staged.handle
        staged.keep()


def clear_stale_parts(directory: Path) -> list[Path]:
    # Swept once before the fetches start; they share this directory and run in parallel.
    if not directory.exists():
        return []

    removed = sorted(directory.glob(f"*{PART_SUFFIX}"))
    for path in removed:
        path.unlink(missing_ok=True)
    return removed


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(READ_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(release: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any]:
    # `complete` is what downstream code reads before trusting the directory.
    landed = {
        entry["source_key"] for entry in entries if entry.get("status") in LANDED
    }
    return {
        "release": release,
        "complete": landed >= SOURCE_KEYS,
        "sources": entries,
    }


def write_manifest(directory: Path, manifest: dict[str, Any]) -> Path:
    # Atomic, so a reader never sees a truncated manifest.
    dest = directory / MANIFEST_NAME
    with atomic_write(dest) as handle:
        handle.write(json.dumps(manifest, indent=2).encode())
    return dest
