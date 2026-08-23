import httpx

from fetching import fetch_source
from sources import source_by_key

CH99 = source_by_key("ch99")
RELEASE = "2026HTSRev16"
PAYLOAD = b'[{"htsno": "9902.04.06"}]'


def client_answering(*answers):
    """A client that serves `answers` in order; an Exception class is raised instead."""
    remaining = iter(answers)

    def handler(request):
        answer = next(remaining)
        if answer is TIMEOUT:
            raise httpx.ReadTimeout("timed out", request=request)
        return answer

    return httpx.Client(transport=httpx.MockTransport(handler))


TIMEOUT = object()


def fetch(directory, client):
    return fetch_source(CH99, RELEASE, directory, client=client, sleep=lambda _: None)


def test_server_error_is_retried_until_it_succeeds(tmp_path):
    result = fetch(tmp_path, client_answering(httpx.Response(500), httpx.Response(200, content=PAYLOAD)))

    assert result["status"] == "fetched"
    assert result["attempts"] == 2
    assert (tmp_path / CH99.filename).read_bytes() == PAYLOAD


def test_timeout_is_retried(tmp_path):
    result = fetch(tmp_path, client_answering(TIMEOUT, httpx.Response(200, content=PAYLOAD)))

    assert result["status"] == "fetched"
    assert result["attempts"] == 2


def test_not_found_is_not_retried(tmp_path):
    # A wrong URL will not fix itself, so spending retries on it only delays the report.
    result = fetch(tmp_path, client_answering(httpx.Response(404)))

    assert result["status"] == "failed"
    assert result["attempts"] == 1


def test_identical_bytes_are_reported_unchanged(tmp_path):
    (tmp_path / CH99.filename).write_bytes(PAYLOAD)

    result = fetch(tmp_path, client_answering(httpx.Response(200, content=PAYLOAD)))

    assert result["status"] == "unchanged"
    assert list(tmp_path.glob("*.part")) == []


def test_exhausted_retries_leave_the_previous_payload_intact(tmp_path):
    dest = tmp_path / CH99.filename
    dest.write_bytes(b"previous release")

    result = fetch(tmp_path, client_answering(*[httpx.Response(503)] * 3))

    assert result["status"] == "failed"
    assert dest.read_bytes() == b"previous release"


def test_a_payload_the_endpoint_would_not_pin_is_not_claimed_for_the_release(tmp_path):
    # The directory is named for a release, but exportList ignores the parameter and
    # serves current, so the manifest must not let that name speak for these bytes.
    export = fetch_source(CH99, RELEASE, tmp_path,
                          client=client_answering(httpx.Response(200, content=PAYLOAD)),
                          sleep=lambda _: None)
    pdf = fetch_source(source_by_key("notes_pdf"), RELEASE, tmp_path,
                       client=client_answering(httpx.Response(200, content=PAYLOAD)),
                       sleep=lambda _: None)

    assert export["release_pinned"] is False
    assert pdf["release_pinned"] is True


def test_a_stale_pin_leaves_the_historical_payload_untouched(tmp_path):
    # client_answering() has no answers queued: if a request were made at all, the mock
    # transport raises. The skip has to happen before any HTTP.
    dest = tmp_path / CH99.filename
    dest.write_bytes(b"the genuine Rev15 export")

    result = fetch_source(CH99, "2026HTSRev15", tmp_path, client=client_answering(),
                          live_release="2026HTSRev18", sleep=lambda _: None)

    assert result["status"] == "skipped"
    assert dest.read_bytes() == b"the genuine Rev15 export"


def test_a_current_pin_still_fetches(tmp_path):
    result = fetch_source(CH99, "2026HTSRev16", tmp_path,
                          client=client_answering(httpx.Response(200, content=PAYLOAD)),
                          live_release="2026HTSRev16", sleep=lambda _: None)

    assert result["status"] == "fetched"
