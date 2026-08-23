import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

from sources import Source
from storage import sha256_of, staged_write

CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 60.0
TOTAL_TIMEOUT = 300.0
CHUNK = 1024 * 1024

MAX_ATTEMPTS = 3
BACKOFF_BASE = 2.0

# What one fetch costs at worst: every attempt burning its full timeout, plus the backoff
# waited between them. scrape.py sizes the Hatchet execution_timeout from this rather than
# from a single attempt, so the retry policy and the task budget cannot drift apart.
BACKOFF_SECONDS = sum(BACKOFF_BASE**exponent for exponent in range(MAX_ATTEMPTS - 1))
WORST_CASE_SECONDS = MAX_ATTEMPTS * TOTAL_TIMEOUT + BACKOFF_SECONDS

# 429 asks for a retry; 5xx is the server's problem, not ours. Any other 4xx means the
# request itself is wrong, and repeating it only delays the report.
RETRYABLE_STATUSES = frozenset({429})
RETRYABLE_ERRORS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.RemoteProtocolError,
)


class RetryableResponse(Exception):
    pass


def default_client() -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(TOTAL_TIMEOUT, connect=CONNECT_TIMEOUT, read=READ_TIMEOUT),
        follow_redirects=True,
    )


def fetch_source(
    source: Source,
    release: str | None,
    directory: Path,
    *,
    client: httpx.Client | None = None,
    force: bool = False,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Fetch one source into ``directory`` and report what happened.

    Args:
        source: Which source to fetch.
        release: Release to pin the URL to, where the endpoint supports it.
        directory: The release directory the payload belongs in.
        client: An httpx client to reuse. One is created and closed when omitted.
        force: Rewrite the payload even when the bytes are identical.
        sleep: Injection point for the backoff delay, so tests do not wait.

    Returns:
        A JSON-serializable result carrying ``status`` (``fetched``, ``unchanged`` or
        ``failed``), the sha256, byte count, http status, attempts, duration and error.

    This never raises. A failure is reported as a result so the summarize task still
    runs and the manifest still covers every source (D-0007).
    """
    url = source.url(release)
    dest = Path(directory) / source.filename
    started = time.monotonic()
    owned = client is None
    client = client or default_client()
    error: str | None = None
    attempt = 0

    try:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                status, http_status, sha, size = _attempt(client, url, dest, force)
            except (RetryableResponse, *RETRYABLE_ERRORS) as exc:
                error = f"{type(exc).__name__}: {exc}"
                if attempt < MAX_ATTEMPTS:
                    sleep(BACKOFF_BASE ** (attempt - 1))
                    continue
            except Exception as exc:  # noqa: BLE001 - reported, not raised
                error = f"{type(exc).__name__}: {exc}"
            else:
                return _result(source, url, dest, status, attempt, started,
                               http_status=http_status, sha256=sha, size=size)
            break
    finally:
        if owned:
            client.close()

    return _result(source, url, dest, "failed", attempt, started, error=error)


def _attempt(
    client: httpx.Client, url: str, dest: Path, force: bool
) -> tuple[str, int, str, int]:
    # One download: stream to a staged file, hash it, keep it only if it differs.
    digest = hashlib.sha256()
    size = 0

    with staged_write(dest) as staged:
        with client.stream("GET", url) as response:
            if response.status_code >= 500 or response.status_code in RETRYABLE_STATUSES:
                raise RetryableResponse(f"HTTP {response.status_code}")
            response.raise_for_status()

            for chunk in response.iter_bytes(CHUNK):
                staged.handle.write(chunk)
                digest.update(chunk)
                size += len(chunk)

        sha = digest.hexdigest()
        # Hash the file on disk rather than trusting a recorded hash, so a payload
        # truncated by an earlier crash is replaced instead of being trusted forever.
        unchanged = not force and dest.exists() and sha256_of(dest) == sha
        if not unchanged:
            staged.keep()

    return ("unchanged" if unchanged else "fetched"), response.status_code, sha, size


def _result(
    source: Source,
    url: str,
    dest: Path,
    status: str,
    attempts: int,
    started: float,
    *,
    http_status: int | None = None,
    sha256: str | None = None,
    size: int | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "source_key": source.key,
        "url": url,
        "path": str(dest),
        "status": status,
        "http_status": http_status,
        "bytes": size,
        "sha256": sha256,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "attempts": attempts,
        "error": error,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
