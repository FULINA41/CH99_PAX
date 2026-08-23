import httpx
import pytest

from release import current_release

NEVER = lambda _: None  # noqa: E731 - no real backoff in tests


def client_always(response):
    return httpx.Client(transport=httpx.MockTransport(lambda request: response))


def test_unresolvable_release_raises_instead_of_reporting_failure(tmp_path):
    # Deliberately unlike fetch_source, which reports failure and lets the run continue:
    # without a release name there is no directory to write into.
    with pytest.raises(RuntimeError):
        current_release(client=client_always(httpx.Response(503)), sleep=NEVER)
