import time
from typing import Any, Callable

import httpx

from fetching import (
    BACKOFF_BASE,
    MAX_ATTEMPTS,
    RETRYABLE_ERRORS,
    RETRYABLE_STATUSES,
    default_client,
)
from sources import RELEASE_URL


def current_release(
    *,
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Resolve the HTS revision that is live right now.

    Args:
        client: An httpx client to reuse. One is created and closed when omitted.
        sleep: Injection point for the backoff delay, so tests do not wait.

    Returns:
        The release, as ``{"name", "title", "resolved_at"}``.

    Raises:
        RuntimeError: Once the retries are spent. Unlike a fetch, an unresolved release
            is fatal: the run would have no directory to write into and no revision to
            record as provenance.
    """
    owned = client is None
    client = client or default_client()
    last: Exception | None = None

    try:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = client.get(RELEASE_URL)
                if response.status_code >= 500 or response.status_code in RETRYABLE_STATUSES:
                    raise httpx.HTTPError(f"HTTP {response.status_code}")
                response.raise_for_status()
                payload = response.json()
                return {
                    "name": payload["name"],
                    "title": payload.get("title"),
                    "resolved_at": time.time(),
                }
            except (httpx.HTTPError, *RETRYABLE_ERRORS) as exc:
                last = exc
                if attempt < MAX_ATTEMPTS:
                    sleep(BACKOFF_BASE ** (attempt - 1))
    finally:
        if owned:
            client.close()

    raise RuntimeError(f"could not resolve the current release: {last}")
