# Part 1 — The scraper

A Hatchet workflow that fetches the three USITC sources and lands the raw payloads with
enough provenance to answer "where did this come from, and when?".

Reasoning behind the choices below is in [`DECISIONS.md`](DECISIONS.md); measured
behaviour and verification output are in [`JOURNAL.md`](JOURNAL.md); the shape of the data
itself is in [`DATA_INVENTORY.md`](DATA_INVENTORY.md).

---

## 1. Where it sits

```
USITC (public internet)
  Chapter 99 JSON · Chapters 1–97 JSON · Chapter 99 notes PDF
        │
        │  HTTP GET, retried with backoff
        ▼
  ┌─────────────────────────────────────────────────────────┐
  │ ScrapeHTS workflow          ← Part 1, this document     │
  └─────────────────────────────────────────────────────────┘
        │  raw bytes, unmodified, + manifest.json
        ▼
   data/raw/<release>/          ← the boundary. Nothing below here touches the network
        │
        ▼
   Parser workflow (Part 2) ──► Postgres ──► App (Part 3)
```

The boundary matters more than the fetching. Parsing is lossy and parsers have bugs, so
the raw payloads are kept exactly as served and re-parsed from disk. Part 2 must be
runnable against payloads fetched an hour ago with the network unplugged, which is only
possible if Part 1 never mixes the two concerns.

The scraper writes to two places: the bytes and their manifest go to `data/`, and one row
per source per run goes to the `source_fetch` table. Neither is redundant — see §5.

## 2. What it fetches

| Source | Endpoint | Size | Can pin a release? |
| --- | --- | ---: | --- |
| `ch99` | `exportList?from=9900&to=9999` | 2.0 MB, 3,336 rows | no |
| `base` | `exportList?from=0100&to=9799` | 10.3 MB, 31,860 rows | no |
| `notes_pdf` | `file?release=…&filename=Chapter 99` | 14.0 MB, 807 pages | **yes** |

Four measured facts shaped the design more than any preference:

- **No `ETag`, no `Last-Modified`, `cache-control: no-store`.** Conditional requests are
  impossible, so idempotency has to be content-addressed.
- **`HEAD` on the PDF endpoint returns `content-length: 1`.** It cannot be used to
  pre-flight anything.
- **The PDF endpoint accepts a specific release; `exportList` does not.** This asymmetry
  runs through the whole design (§6).
- **The live release moved from Revision 15 to Revision 16, and then to Revision 17,
  during this exercise.** The release is data, not a constant.

## 3. Shape of the workflow

```
resolve_release
      │
      ├──────────────┬────────────────┐
      ▼              ▼                ▼
 fetch_ch99     fetch_base     fetch_notes_pdf      (parallel, independent)
      └──────────────┴────────────────┘
                     ▼
                 summarize
```

`resolve_release` runs first because the release names the storage directory and pins the
PDF URL, and because sweeping abandoned `.part` files has to happen once, before the
parallel fetches start — a sweep from inside a fetch would delete a sibling's live
temporary file.

The three fetches are independent, so they run in parallel. The 14 MB PDF is the slowest
and the most likely to fail; running it alongside rather than in series keeps its risk off
the other two.

`summarize` writes the manifest and reports per-source status. It is a plain join task,
which means it only runs if all three parents succeed — the reason the fetches never
raise (§7).

**Why one workflow rather than three.** Three separate workflows would allow re-running a
single source, at the cost of a parent that spawns them, four registrations, and
cross-run state aggregation. At three sources that is not worth it, and re-fetching an
unchanged payload costs a hash comparison rather than a write (D-0003).

## 4. Modules

| File | Responsibility |
| --- | --- |
| `sources.py` | The three source definitions: key, filename, URL builder, and whether the endpoint can pin a release |
| `release.py` | Resolve the live revision. Raises when it cannot — a run with no release has nowhere to write |
| `fetching.py` | Stream, hash, retry, and decide fetched / unchanged / skipped / failed. No Hatchet, no database |
| `storage.py` | Release directories, atomic writes, stale `.part` cleanup, manifest construction |
| `provenance.py` | One `source_fetch` row per source per run |
| `scrape.py` | The Hatchet DAG. Wiring only — the logic lives below it |
| `scrape_run.py` | CLI: trigger a run, print the report, exit non-zero if a source failed |

`fetching.py` and `storage.py` know nothing about Hatchet or Postgres, which is why the
tests for them need neither an engine nor a database.

## 5. Provenance

Every fetch is recorded twice, for two different readers.

`data/raw/<release>/manifest.json` sits with the payloads and describes them: release,
per-source status, byte count, sha256, duration, attempts, and whether the release
actually applies to that source. It makes the directory self-describing to anyone who
opens it.

The `source_fetch` table carries the same facts as rows, keyed by the Hatchet run id, so
Part 2 can join a parsed row back to the exact fetch it came from.

They are not redundant. `./setup.sh` is a schema reset, so applying it wipes the table
while the manifest survives with the bytes it describes — the manifest is authoritative
when they disagree (D-0005).

The manifest also carries a `complete` flag, which is what downstream code should check
before trusting a directory. It is true when every known source has bytes on disk that
this run knows the hash of.

## 6. Idempotency and release scoping

Payloads live under `data/raw/<release>/`. A new revision gets a new directory; nothing
is overwritten across releases.

Within a release, a re-run downloads to a `.part` file, hashes it while streaming, and
compares against the file already on disk:

- identical → the existing file is left untouched, recorded `unchanged`
- different → atomically replaced, recorded `fetched`

The existing file is hashed rather than trusting a recorded hash, so a payload truncated
by an earlier crash is replaced instead of trusted forever. Re-downloading to compare is
not waste; without caching headers it is the only way to know (D-0004).

**The asymmetry.** `--release <name>` pins the PDF URL to a specific revision, which
removes the race between resolving a release and downloading against it. The two bulk
exports have no such parameter: they always serve current. So asking for a past release
would fetch *current* data and overwrite the historical payload already on disk — quietly
turning a good snapshot into a mixed one. Those sources are therefore **skipped** before
any request is made, leaving what is on disk alone, and the skip is recorded (D-0011).

A run that is not pinned re-reads the live release after the fetches. If it moved
mid-run, the manifest records both names rather than silently mixing two revisions. That
re-check cannot fail the run: the bytes have already landed, and a check whose only job
is to add an annotation must not cost the manifest that describes them (D-0009).

## 7. Failure

Each source succeeds or fails on its own, and a correct payload is never removed because
a sibling failed. A failure is not the same as an empty directory (D-0006).

A fetch task **reports** its failure rather than raising it. This is deliberate and looks
backwards, so it is worth stating plainly: a task whose parent failed is CANCELLED and
never runs, so a raising fetch would take `summarize` with it and leave payloads on disk
with no manifest describing them. `summarize` therefore always runs, writes a manifest
covering every source with its outcome, and *then* raises so the run is marked failed
(D-0007).

The cost is that a failed source shows a green task in the dashboard. It is visible three
other ways: the task logs the failure, the `source_fetch` row carries `status='failed'`
with the error text, and the run fails with a message naming the sources.

Because the task no longer raises, Hatchet's own retries never fire, so `fetching.py`
retries itself: three attempts with exponential backoff. Timeouts, connection errors, 5xx
and 429 are retried; any other 4xx is not, because a wrong URL will not fix itself. The
Hatchet task timeout is derived from that policy rather than hand-picked, so the two
cannot drift apart (D-0008).

**Writes are atomic.** Every payload is streamed to a `.part` beside its destination,
fsynced, and moved into place with `os.replace`. An exception removes the `.part`; a hard
kill leaves it, and the next run sweeps it and says so in the log. The final path never
holds a truncated file — verified by SIGKILLing the worker mid-download and confirming
all three payloads still hashed identically.

## 8. Running it

```bash
./dev.sh                                              # stack, with hot reload
./setup.sh                                            # apply db/schema.sql
docker compose exec -T worker uv run python -m scrape_run
```

The in-container form is the documented one because it needs nothing installed beyond
Docker. Running it from the host works too and wants `uv` and a synced venv.

```
release  2026HTSRev17  Revision 17 (2026)
  base         fetched     10,349,906 B  sha 888c15e2…
  ch99         fetched      1,996,519 B  sha 04d27370…
  notes_pdf    fetched     13,992,373 B  sha 0a267cc2…
3 fetched → /data/raw/2026HTSRev17/
```

Run it again and all three read `unchanged`, which is the visible proof of idempotency —
`unchanged` means the bytes were downloaded and found identical, not that the fetch was
skipped. Exit status is non-zero if any source failed.

Flags: `--release <name>` pins a revision, `--force` rewrites payloads even when
unchanged. `--force` does not override a skip; forcing current bytes into a historical
directory is the corruption being prevented.

## 9. What it deliberately does not do

- **No parsing.** Not even validating that the JSON parses. Part 2 owns that, and a
  scraper that understands its payloads cannot be re-run against a new format.
- **No resume of a partial download.** A killed transfer restarts from zero. At 26 MB the
  complexity is not worth it.
- **No external sources.** CBP CROSS and the Federal Register are recorded in
  `SUBMISSION.md` as deliberate omissions.
- **No rate limiting or concurrency control.** Three requests, no pressure to manage.
- **A skipped source is unverified.** Its file is trusted because it is there, not because
  this run checked it — which is the point, since the endpoint cannot answer for that
  release.

## 10. Verification

Five end-to-end checks were run against the live API, with output recorded in
[`JOURNAL.md`](JOURNAL.md): a clean run from an empty database, idempotency proved by
unchanged payload mtimes, partial failure leaving good data intact, a SIGKILL mid-download
leaving hashes untouched, and release scoping creating a new directory rather than
overwriting one.

Unit tests cover the pure modules and `summarize`, and run without an engine, a network,
or a database:

```bash
docker compose exec -T worker uv run pytest -q
```
