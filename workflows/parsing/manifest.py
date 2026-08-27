import json
from pathlib import Path
from typing import Any

from sources import SOURCE_KEYS, source_by_key
from storage import MANIFEST_NAME, data_root, release_dir


class ManifestError(RuntimeError):
    """The staged payloads cannot be trusted, so parsing must not start."""


def load_manifest(release: str | None = None, root: Path | None = None) -> dict[str, Any]:
    """Find a release directory the parser is allowed to read, and describe it.

    Args:
        release: Release to parse, e.g. ``2026HTSRev17``. When omitted, the most
            recently resolved complete directory under ``data/raw/`` is used.
        root: Data root. Falls back to ``DATA_DIR``.

    Returns:
        The release, the directory, and one entry per source carrying the path on
        this machine, the recorded hash, size, status and URL.

    Raises:
        ManifestError: No directory qualifies, the manifest says a source never
            landed, or a payload is missing or the wrong size on disk.
    """
    root = root or data_root()
    directory = _resolve_directory(release, root)
    manifest = _read(directory)

    landed = {e["source_key"]
              for e in manifest.get("sources", []) if e.get("sha256")}
    if not manifest.get("complete") or landed < SOURCE_KEYS:
        missing = ", ".join(sorted(SOURCE_KEYS - landed)) or "nothing"
        raise ManifestError(
            f"{directory} is incomplete — never landed: {missing}. "
            "Run the scraper before the parser."
        )

    sources = {}
    for entry in manifest["sources"]:
        key = entry["source_key"]
        # The filename, not the manifest's `path`: that path was recorded wherever the
        # scraper ran, and Part 2 may well be running somewhere else.
        path = directory / source_by_key(key).filename
        _check_on_disk(path, entry)
        sources[key] = {
            "path": str(path),
            "sha256": entry["sha256"],
            "bytes": entry.get("bytes"),
            "status": entry.get("status"),
            "url": entry.get("url"),
            "fetched_at": entry.get("fetched_at"),
        }

    return {
        "release": manifest["release"],
        "directory": str(directory),
        "sources": sources,
    }


def _check_on_disk(path: Path, entry: dict[str, Any]) -> None:
    if not path.exists():
        raise ManifestError(f"{path} is in the manifest but not on disk")

    size = path.stat().st_size
    if entry.get("bytes") and size != entry["bytes"]:
        raise ManifestError(
            f"{path} is {size:,} B, but the manifest recorded {entry['bytes']:,} B — "
            "the payload changed after it was fetched"
        )


def _resolve_directory(release: str | None, root: Path) -> Path:
    if release:
        directory = release_dir(release, root)
        if not (directory / MANIFEST_NAME).exists():
            raise ManifestError(
                f"no manifest in {directory} — has the scraper run?")
        return directory

    # Without the network there is nothing to ask which release is current, so the choice
    # comes from what the scraper already recorded: the newest resolved_at among the
    # directories whose manifest calls itself complete.
    candidates = []
    for path in sorted((root / "raw").glob(f"*/{MANIFEST_NAME}")):
        try:
            manifest = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if manifest.get("complete"):
            candidates.append(
                (manifest["release"].get("resolved_at", 0), path.parent))

    if not candidates:
        raise ManifestError(
            f"no complete release directory under {root / 'raw'} — run the scraper, "
            "or name a release explicitly"
        )
    return max(candidates)[1]


def _read(directory: Path) -> dict[str, Any]:
    path = directory / MANIFEST_NAME
    try:
        return json.loads(path.read_text())
    except OSError as exc:
        raise ManifestError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"{path} is not valid JSON: {exc}") from exc
