"""
Which HTS revision is live right now.

Unlike a fetch, this raises when it cannot be resolved. Without a release name there
is no directory to write into and no value to record as provenance, so continuing
would produce payloads that cannot be attributed to a revision.
"""

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
