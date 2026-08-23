# Part 1 — Scraper design

**Date:** 2026-08-21 · **Status:** implemented, with four amendments

> This is the design as written **before** implementation, kept unedited as the record of
> what was intended. For the system as it actually stands, read
> [`docs/PART1_SCRAPER.md`](../../PART1_SCRAPER.md). Building it amended this document in
> four places, each recorded in `DECISIONS.md`: D-0007 (fetch tasks report rather than
> raise), D-0008 (the task timeout is derived from the retry policy), D-0009 (the release
> re-check cannot fail the run) and D-0011 (a source whose endpoint cannot serve the
> pinned release is skipped).

A Hatchet workflow that fetches the three USITC sources and lands them in durable storage
with enough provenance to answer "where did this come from, and when?".

Requirements are in [`parts/PART1_SCRAPER.md`](../../../parts/PART1_SCRAPER.md). The shape
of the data is in [`DATA_INVENTORY.md`](../../DATA_INVENTORY.md). Decisions D-0003 to
D-0006 in [`DECISIONS.md`](../../DECISIONS.md) are the ones this design turns on.

---

## 1. Acceptance criteria

Taken from the requirements, restated as things that can be checked:

1. All three sources are fetched: Chapter 99 JSON, chapters 1–97 JSON, notes PDF.
2. Raw bytes land on disk **before** any parsing, unmodified.
3. Every fetch records provenance: URL, timestamp, release, size, checksum.
4. Running it twice is safe — no duplication, no corruption.
5. Network failure is handled as normal: timeouts, retries with backoff.
6. Partial success leaves the data coherent — a failure in one source does not
   invalidate the two that succeeded.

Not in scope: parsing anything (Part 2), and the optional external sources (CROSS,
Federal Register), which are recorded in `SUBMISSION.md` as deliberate omissions.

---

## 2. Evidence that shapes the design

Measured against the live API on 2026-08-21, not assumed:

| Observation | Consequence |
| --- | --- |
| No `ETag`, no `Last-Modified`; `cache-control: no-cache, no-store` | Conditional requests are impossible. Idempotency has to be **content-based**: download, hash, compare |
| `HEAD` on the PDF endpoint returns `content-length: 1` | The server's `HEAD` is unreliable. Never pre-flight with it; `GET` and stream |
| `?release=2026HTSRev16` on the PDF endpoint returns the same 13,969,270 bytes as `currentRelease` | The release **can be pinned**, which removes the race between resolving the release and downloading against it |
| `exportList` takes no release parameter | The two JSON exports always serve current. The release is therefore re-checked after the batch, and a mid-run change is recorded rather than hidden |
| The live release moved 15 → 16 during this exercise | Release is data, not a constant. It names the storage directory |

---

## 3. Decisions

**D-0003 · One workflow, parallel fetch tasks.** A single `ScrapeHTS` workflow with a
five-task DAG rather than three separate workflows or one serial task.

```
resolve_release
      │
      ├──────────────┬──────────────┐
      ▼              ▼              ▼
 fetch_ch99     fetch_base    fetch_notes_pdf     (parallel)
      └──────────────┴──────────────┘
                     ▼
                 summarize          (tolerates partial failure)
```

`resolve_release` has to come first because the release names the target directory and
pins the PDF URL. The three fetches are independent, so they run in parallel; the 14 MB
PDF is the slowest and most failure-prone, and this keeps its risk off the other two.
`summarize` writes the manifest and reports what succeeded.

Three separate workflows would allow re-running one source alone, but cost a parent
workflow, four registrations, and cross-run state aggregation — not worth it at three
sources. A single serial task fails all three when one fails, which contradicts
acceptance criterion 6.

**D-0004 · Idempotency is release-scoped and content-addressed.** Files land in
`data/raw/<release>/`. A re-run of the same release downloads to a temp file, hashes it,
and compares to what is already there:

- identical hash → keep the existing file untouched, record the fetch with status `unchanged`
- different hash → atomically replace, record status `fetched`
- absent → write, record status `fetched`

Downloading again to compare is not wasted work: without caching headers, it is the only
way to know. 26 MB over a home connection is seconds.

**D-0005 · Provenance is written to both disk and Postgres.** `manifest.json` next to the
payloads makes `data/` self-describing to anyone who opens the directory. A `source_fetch`
table lets a parsed row point back at the exact fetch it came from.

The two are not redundant. `./setup.sh` is a schema reset, so applying it wipes the
`source_fetch` history — the manifest survives that and can rebuild it. Conversely, the
table is what Part 2 and Part 3 can join against; a JSON file on disk is not.

**D-0006 · Failure is per-source; the run reports.** Each fetch task succeeds or fails on
its own. `summarize` runs on whatever completed, writes the manifest for the successful
sources, and returns a per-source status. The run is marked failed if any source failed —
the operator should see red — but the successful payloads stay on disk and stay valid.
Nothing is rolled back, because a correct payload is never made wrong by a sibling's
failure.

---

## 4. Storage layout

```
data/
  raw/
    2026HTSRev16/
      ch99.json
      base.json
      ch99-notes.pdf
      manifest.json
    2026HTSRev15/          ← a superseded release is kept, not overwritten
      …
```

Every write is atomic: stream to `<name>.part` in the same directory, `fsync`, then
`os.replace()` onto the final name. `os.replace` is atomic within a filesystem, so an
interrupted download can leave a `.part` file but never a truncated `ch99-notes.pdf`.
Stale `.part` files are removed at the start of the next fetch of the same target.

Payloads are streamed in chunks and hashed while streaming — the 14 MB PDF is never held
in memory in full, and hashing costs one pass rather than a re-read.

---

## 5. Schema addition

Appended to `db/schema.sql`, which stays the single command that builds the schema:

```sql
CREATE TABLE source_fetch (
  id            bigserial PRIMARY KEY,
  run_id        text,                        -- Hatchet run id, to trace back to the run
  source_key    text NOT NULL,               -- 'ch99' | 'base' | 'notes_pdf'
  release_name  text NOT NULL,               -- '2026HTSRev16'
  release_title text,                        -- 'Revision 16 (2026)'
  url           text NOT NULL,
  path          text,                        -- data/raw/<release>/<file>
  status        text NOT NULL
    CHECK (status IN ('fetched','unchanged','failed')),
  http_status   int,
  bytes         bigint,
  sha256        text,
  duration_ms   int,
  error         text,
  fetched_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX source_fetch_lookup_idx
  ON source_fetch (release_name, source_key, fetched_at DESC);
```

`status` distinguishes "downloaded new bytes" from "verified the bytes we already had",
which is what makes a second run legible rather than looking like a no-op.

Part 2 will add `source_fetch_id` references to the parsed tables so a row on screen can
name the fetch it came from. That is out of scope here; the table is designed to support
it.

---

## 6. Failure and retry policy

| Setting | Value | Why |
| --- | --- | --- |
| Connect timeout | 10s | A dead host should fail fast |
| Read timeout | 60s per chunk | Covers a stalled transfer without killing a slow one |
| Total per fetch | 300s | The 14 MB PDF takes seconds normally; 5 minutes is a generous ceiling |
| Retries | 3, exponential backoff | Delegated to Hatchet's task retries rather than hand-rolled, so each attempt is visible in the dashboard |
| Retryable | timeouts, connection errors, 5xx, 429 | Transient |
| Not retryable | 4xx other than 429 | A wrong URL will not fix itself; fail loudly |

Retries are safe because of D-0004: a retried fetch either rewrites identical bytes or
replaces them atomically.

---

## 7. Module boundaries

Small units with one job each, so the parts that have no I/O can be tested without a
network or a database.

| Module | Responsibility | Depends on |
| --- | --- | --- |
| `workflows/sources.py` | The three source definitions: key, URL builder, filename | — |
| `workflows/release.py` | Resolve `currentRelease`; build a release-pinned URL | httpx |
| `workflows/fetching.py` | Stream a URL to a temp file, return bytes/sha256/http status/duration | httpx |
| `workflows/storage.py` | Release directory, atomic write, manifest read/write | stdlib |
| `workflows/provenance.py` | Insert `source_fetch` rows | psycopg |
| `workflows/scrape.py` | The Hatchet workflow wiring the above into the DAG | hatchet-sdk |
| `workflows/scrape_run.py` | CLI trigger | hatchet-sdk |

New dependencies in `workflows/pyproject.toml`: `httpx` (timeouts and streaming) and
`psycopg[binary]`. Editing `pyproject.toml` restarts the worker under compose watch, which
picks them up via `uv sync`.

The provided `echo.py` and `echo_run.py` are deleted once `scrape.py` runs — the scaffold
says to, and leaving a dead sample workflow registered is noise.

---

## 8. How it is run

The command that goes in `SUBMISSION.md`, chosen so the grader needs nothing installed
beyond Docker:

```bash
docker compose exec -T worker uv run python -m scrape_run
```

Both trigger paths were verified working on 2026-08-21. The host path
(`cd workflows && uv run python -m scrape_run`) also works but requires `uv` and a synced
venv, so it stays a development convenience rather than the documented command.

Expected output on success:

```
release  2026HTSRev16  Revision 16 (2026)
  ch99         fetched     1,992,914 B  sha 5a7ca6b0…
  base         fetched    10,349,905 B  sha 221e1560…
  notes_pdf    fetched    13,969,270 B  sha 58b2a00d…
3 fetched, 0 unchanged, 0 failed → data/raw/2026HTSRev16/
```

On a second run the three lines read `unchanged`, which is the visible proof of
idempotency.

---

## 9. Verification plan

Each is a real check with an observable result, run before Part 1 is called done:

1. **Clean run.** `./cleanup.sh` → `./dev.sh` → `./setup.sh` → trigger. Expect three
   payloads plus `manifest.json` in `data/raw/<release>/`, and three `source_fetch` rows
   with status `fetched`.
2. **Idempotency.** Trigger again. Expect identical file hashes, three new rows with
   status `unchanged`, and no change in file mtimes for the payloads.
3. **Partial failure.** Point one source at a deliberately broken URL. Expect that task
   `FAILED` after its retries, the other two `fetched`, the manifest written for the two,
   and a run summary naming the failure.
4. **Interrupted write.** Kill the worker mid-PDF. Expect no `ch99-notes.pdf` in place —
   at most a `.part` file — and a clean re-run afterwards.
5. **Release change.** Force a different release name and confirm a new directory is
   created rather than the existing one being overwritten.

Unit tests cover the pure parts: URL building, release parsing, manifest round-trip, and
the atomic write helper against a temp directory. Fetching is tested against a stub
transport rather than the live API.

---

## 10. To verify during implementation

Open questions that the design tolerates either way, but which should be settled with an
experiment and recorded:

- **Hatchet's parallel-failure semantics.** Whether sibling tasks continue when one fails,
  and whether `replay` re-runs the whole run or only the failed tasks. This decides how
  `summarize` reads its inputs. Test with a deliberately failing task before writing the
  real one.
- **Hatchet's retry configuration API** — the exact decorator arguments for retry count
  and backoff in the installed SDK version.
- **Mid-run release change.** The two JSON exports cannot be pinned, so the release is
  read again after the batch; if it moved, the run records both values and reports the
  discrepancy rather than silently mixing two releases.