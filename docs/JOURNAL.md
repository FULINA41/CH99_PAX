# Work journal

Chronological, append-only. One section per working session. Records what was
attempted, what broke, what was verified (with the output, not a claim), and where a
coding agent helped or misled. Feeds `SUBMISSION.md` §4 and §6, and the demo video.

---

## 2026-08-20 — Reading the sources before writing anything

**Goal.** Understand the shape of the three data sources well enough to design the
schema, before committing to any parsing approach.

**Done.**
- Read the provided docs: `README.md`, `AGENTS.md`, `parts/*.md`, `db/schema.sql`,
  `docker-compose.yaml`, the `app/` and `workflows/` scaffolds.
- Fetched two of the three sources by hand (curl, into a scratch directory outside the
  repo) and inspected them with Python. The notes PDF was **not** downloaded yet.
- Wrote `CLAUDE.md` for future agent sessions.

**Verified facts** (live API, 2026-08-20):

| Check | Result |
| --- | --- |
| `GET /reststop/currentRelease` | `2026HTSRev16` — README documented Rev 15 as of 2026-08-03 |
| Chapter 99 export rows | 3,336 |
| Base schedule (1–97) rows | 31,860 |
| Ch99 rows containing `provided for in` | 2,556 |
| Ch99 rows citing a U.S./statistical note | 595 |
| Ch99 rows with `except` / `other than` | 307 |
| Ch99 rows with an empty `htsno` (parent heading rows) | 238 |
| Base rows with an empty `general` rate | 20,446 of 31,860 |
| Base rate shapes | 4,315 `Free` · 5,863 pure ad valorem · 771 specific (`14.27¢/liter`) · 417 compound (`4.4¢/kg + 8.5%`) · ~30 prose |

**Findings that will drive the schema** (each is now a pending decision in
[`DECISIONS.md`](DECISIONS.md)):

1. Cited codes are 8-digit, base rows are 10-digit — `2922.49.30` vs `2922.49.30.00`.
   A naive join matches nothing.
2. Most base rows inherit their rate from an ancestor row through `indent`
   (`2922.49.49.10` Alanine is empty; the 4.2% lives on `2922.49.49`).
3. Additive rates are spelled two ways in the same export: `+ 25%` on `9903.01.01`,
   `plus 25%` on `9903.88.01`. 204 rows say "The duty provided in the applicable
   subheading" with no delta, i.e. no change.
4. 238 rows carry no `htsno`; they are parent headings such as
   `Described in U.S. note 15(a) to this subchapter:` — the product scope sits on the
   parent, the rate on the children. Losing the `indent` tree loses the meaning.
5. `9903.88.01` scopes itself by reference to "the subheadings enumerated in U.S. note
   20(b)". That list is not in the JSON at all — it is the reason the notes PDF is a
   required source rather than a nice-to-have.
6. `9903.88.01` excludes 17 other headings in one sentence, confirming exclusions are a
   graph traversal, not a lookup.

**Not done / open.**
- Repo is not a git repository (`git status` → *not a repository*). The submission
  requires full git history. Original `.git` needs to be recovered, or the repo
  initialized now and committed normally from here.
- Docker stack never started; `./dev.sh`, `./setup.sh` unrun. Nothing in this session
  touched Postgres or Hatchet.
- Notes PDF not fetched or inspected — its structure is still unknown, and it is the
  least predictable of the three sources.

**Agent notes.** The agent's summary of the domain was accurate against the primary
docs, and pulling the live exports turned two of the README's illustrative examples into
checkable numbers — including one that had already gone stale (Rev 15 → Rev 16). Nothing
was written to the repo except `CLAUDE.md` and these two log files, so there is no
generated code carrying unverified assumptions yet.

---

## 2026-08-21 — Repository setup

**Goal.** Put the work under version control before writing any code, since the
submission requires full history and rewriting it later is not an option.

**Done.**
- Searched for upstream history before initializing anything. `~/Downloads/chp99-takehome`
  is an extracted copy with no repository, and the archive it came from,
  `chp99-takehome-1871fc6.zip`, is a zip containing a zip whose listing has **0** entries
  under `.git/`. Conclusion: the scaffold shipped without history (D-0002).
- Wrote a root `.gitignore`: macOS and editor noise, local compose overrides, and `.env`
  with an explicit `!workflows/.env` negation.
- `git init -b main`, identity set repo-locally to `Tong Mo <tm4371@nyu.edu>`
  (global config had an empty `user.name`, so commits would otherwise have been
  attributed to a guessed system identity).
- Three commits: scaffold baseline, own additions, skill registration.

**Verified.**
- `workflows/.env` is committed, not ignored: `git status --porcelain -uall` listed it as
  `??` before staging, and it appears as `A workflows/.env` in commit 1. The negation in
  the root `.gitignore` works as intended — worth checking explicitly, because the
  blanket `.env` rule above it would otherwise have silently dropped the Hatchet token
  the worker needs.
- `git status` is clean after the three commits; nothing untracked was left behind.
- `diff -r skills/hatchet-cli .claude/skills/hatchet-cli` reports no differences.

**Notes.**
- `.claude/skills/hatchet-cli/` exists as a byte-identical copy of the vendored skill,
  committed separately so it can be dropped on its own. Claude Code only auto-discovers
  skills under `.claude/skills/`; the vendored copy is harness-neutral and is reached by
  the pointer in `AGENTS.md` instead.
- The `hatchet` CLI is not installed on this machine (`which hatchet` → not found). Not
  blocking: the dashboard on :8080 needs no login. Install it before the first failed run
  needs diagnosing, following `skills/hatchet-cli/references/setup-cli.md`.

**Next.** Work through the pending decisions in `DECISIONS.md` — the schema is the part
of Part 2 that carries the most weight, and P-a through P-f all have to be answered
before the parser can be written.

---

## 2026-08-21 (later) — Stack verification

**Goal.** Prove the provided stack actually runs before designing Part 1 against it.
Nothing had been executed up to this point; the work so far was reading and fetching.

**Verified, in order:**

| Step | Command | Result |
| --- | --- | --- |
| Daemon and ports | `docker info`, `lsof -nP -iTCP:<p>` | Docker 28.3.0; 5432 / 8080 / 7077 / 3000 all free |
| Infrastructure | `docker compose up -d` | `db`, `hatchet`, `hatchet_db` all healthy within 10s of the poll starting |
| Schema | `./setup.sh` | `hts_base`, `rule`, `rule_edge` created; the DROP notices confirm it is a reset, not a migration |
| Worker | `docker compose --profile worker up -d` | `'chp99-worker' started, waiting for tasks...` |
| Run, in container | `docker compose exec -T worker uv run python -m echo_run "hello chapter 99"` | `message='hello chapter 99' length=16` |
| Run, from host | `cd workflows && uv sync && uv run python -m echo_run "host trigger"` | `message='host trigger' length=12` |
| Hatchet API | `curl -o /dev/null -w '%{http_code}' localhost:8080/api/ready` | `200`; dashboard root also `200` |
| Database | `psql -tAc "select count(*) …"` | `3 tables` |

Both trigger paths work. The in-container path is the better one to put in `SUBMISSION.md`:
it needs nothing installed on the grader's machine, while the host path requires `uv` and
a synced venv.

**Bug found — `cleanup.sh` cannot see this project.** Compose derives the project name
from the directory, which here is `chp99-takehome 2`, giving `chp99-takehome2`.
`cleanup.sh` hardcodes `PROJECT=chp99-takehome`. Consequences:

- The `docker compose … down --volumes` line still works; it runs in the current project's
  context and does not use the variable.
- Every label filter (`label=com.docker.compose.project=$PROJECT`) matches nothing, so the
  stranded-container and leftover-volume fallbacks are dead.
- The verification block at the end therefore always counts 0/0/0 and prints
  `clean: no containers, volumes or networks left` — **a false success**, regardless of
  what is actually left behind.

This is an artifact of the local directory name, not of the scaffold: a grader cloning
into `chp99-takehome` gets the intended behaviour. Fix options, cheapest first: a local
`.env` with `COMPOSE_PROJECT_NAME=chp99-takehome` (gitignored, touches no tracked file);
renaming the directory; or adding `name: chp99-takehome` to `docker-compose.yaml`, which
would fix it for any directory name but means editing the provided infrastructure.
Not applied yet — changing the project name orphans the running containers, so it should
happen at the next teardown.

**Also noted.** The worker logs from an earlier run of the day are full of
`time since last successful heartbeat: 919.73s, expects 4s` warnings — the machine slept
while the worker was connected. Harmless, but worth recognizing so it is not mistaken for
a Hatchet fault later. It also means `docker compose logs worker` mixes runs; use
`--since` when checking whether the current process started cleanly. The first grep for
readiness matched a stale line for exactly this reason.

**Next.** The four Part 1 decisions: workflow decomposition, idempotency key, provenance
grain, and failure semantics.

---

## 2026-08-22 — Step 0: measuring Hatchet's actual behaviour

**Goal.** The Part 1 design left four questions about Hatchet unanswered, and how
`summarize` is written depends entirely on them. Measure before writing real code.

**Method.** A throwaway `probe.py` with a four-task DAG — `root` → (`good` sleeping 8s,
`bad` raising immediately) → `join(parents=[good, bad])` — plus an `on_failure_task`.
Every task printed a `PROBE` line so `docker compose logs worker` gave the true execution
order. SDK version 1.37.1, read from the installed package rather than the docs.

**Findings.**

| Question | Answer |
| --- | --- |
| Does a sibling of a failed parallel task still run? | **Yes.** `good` printed `finished` after `bad` had failed twice. Final state: `good` COMPLETED, `bad` FAILED |
| Does a join task with a failed parent run? | **No.** `join` never printed, and the run detail reports it `CANCELLED` — not skipped, cancelled |
| Does an on-failure task run, and what can it read? | **Runs.** It read `output(root)` fine and `get_task_run_error(bad)` returned the real traceback. But `output(good)` raised `ValueError: Step output for 'good' not found` |
| Does `replay` re-run everything or only failures? | **Everything.** After `runs.replay(...)`, `root` and `good` both executed again; `bad`'s attempt counter continued at 2 and 3 rather than resetting |

**The finding that changes the design.** The on-failure task fires as soon as a task
fails, *not* after the other branches settle: all of its output lines appeared **before**
`PROBE good: finished`. `good` was still mid-sleep when the on-failure task tried to read
its output. So writing the manifest inside an on-failure task would produce an incomplete
manifest whenever a fetch fails fast while another is still downloading — precisely the
common case, since a 404 fails instantly while the 14 MB PDF is still in flight.

Recorded as **D-0007**, which supersedes the `summarize` shape in the design spec.

**Two API facts worth keeping.**

- `execution_timeout` defaults to **`timedelta(seconds=60)`**. The design budgets 300s for
  the PDF, so the fetch tasks must set it explicitly or the engine cancels a slow download
  at one minute.
- `retries=1` produced attempts 0 and 1 — **N retries means N+1 attempts**.

**A gotcha `AGENTS.md` does not cover.** From *inside* the worker container, the REST
client needs `HATCHET_CLIENT_SERVER_URL=http://hatchet:8888`. `AGENTS.md` documents the
host case (`http://localhost:8080`) but not this one: the token's `server_url` claim is
`localhost:8888`, which inside a container resolves to the container itself, so
`h.runs.get(...)` fails with `Connection refused` on port 8888. gRPC is unaffected — it
already has `HATCHET_CLIENT_HOST_PORT: hatchet:7077` from the compose file.

**Consequence for "resumable".** Since `replay` re-runs every task, resumability cannot
come from the orchestrator replaying only the failed part. It has to come from the tasks
themselves being idempotent — which is what D-0004 buys: a replayed fetch re-downloads,
hashes, finds the bytes identical, and rewrites nothing.

**Cleanup.** `probe.py` and `probe_run.py` deleted, `worker.py` restored to registering
`echo_workflow` only.

---

## 2026-08-22 — Step 1: making `cleanup.sh` tell the truth

**Goal.** Fix the project-name mismatch found during stack verification, because Step 7's
first acceptance check runs `./cleanup.sh` and trusts its report.

**Done.** Branch `task1` created; Part 1 work happens there, one commit per step. Wrote a
root `.env` containing `COMPOSE_PROJECT_NAME=chp99-takehome`, with a comment explaining
what it fixes. Nothing tracked changed — `.env` is gitignored, and the provided
infrastructure was not edited.

**The rename costs the volumes.** Compose scopes volumes by project name, so the old
`chp99-takehome2_*` volumes were orphaned by the change rather than carried over. They
were removed deliberately and the stack rebuilt from empty: Hatchet re-ran its migrations
against a fresh database and the committed worker token still authenticated, which is what
the dev image's fixed token is for. `data/` was untouched throughout — it is a host bind
mount, not a volume.

**Verified.**

| Check | Before | After |
| --- | --- | --- |
| `docker compose config` project name | `chp99-takehome2` | `chp99-takehome` |
| `cleanup.sh`'s `PROJECT=` | `chp99-takehome` | unchanged — now matches |
| Containers matching the project label | 0 | 4 |
| Volumes matching the project label | 0 | 4 |
| Networks matching the project label | 0 | 1 |
| `git check-ignore -v .env` | — | matched `.gitignore:15` |

Stack re-verified after the rebuild: three services healthy, `./setup.sh` recreated the
three tables, worker registered, and `echo_run "step1 ok"` returned
`message='step1 ok' length=8`.

The label counts are the point: every fallback in `cleanup.sh` filters on that label, so
at 0 they were silently no-ops and the script's closing "clean" was unconditional.

---

## 2026-08-22 — Reviewing the DAG: two ways the manifest could have been lost

**Goal.** Read `scrape.py` back against D-0006/D-0007 before calling Part 1 done. Both
decisions rest on one guarantee — `summarize` always runs and always writes a manifest —
so the review looked specifically for paths that break it.

**Found two, both real.**

1. **`FETCH_TIMEOUT` budgeted one attempt, not the retry sequence.** `TOTAL_TIMEOUT + 60`
   = 360s, while `fetching.py` can spend `3 × 300s + 3s` = 903s. Against a hung server the
   engine cancels the fetch task at 360s; a task whose parent is CANCELLED never runs, so
   `summarize` never writes the manifest. The two constants lived in different files with
   nothing tying them together.
2. **The mid-run release re-check could abort `summarize` before `write_manifest`.**
   `current_release()` raises by design. Placed at the top of `summarize`, a USITC blip
   would kill the task with all three payloads already on disk and no manifest.

Both are the same class of bug: something incidental was given the power to destroy the
artefact the whole failure design exists to produce.

**Fixed.**
- `fetching.py` now exports `WORST_CASE_SECONDS = MAX_ATTEMPTS * TOTAL_TIMEOUT +
  BACKOFF_SECONDS`; `scrape.py` derives `FETCH_TIMEOUT` from it (D-0008). Verified:
  `WORST_CASE 903.0s / FETCH_TIMEOUT 963.0s / covers worst case: True`.
- The re-check is wrapped; on failure the manifest carries `release_recheck_failed`
  and the run continues (D-0009).

**Verified, with output.**
- Added `tests/test_scrape.py`, three cases driven through the SDK's own
  `Task.mock_run(parent_outputs=...)` — no engine, no network, no database.
- Checked the new test actually catches the old behaviour by reverting the fix in place:
  `1 failed, 2 passed`, failing with `RuntimeError: could not resolve the current release:
  HTTP 503` propagating out of `summarize`. Restored, then `18 passed in 0.82s`.

**Agent notes.** The agent wrote `scrape.py` and both bugs came through its code; neither
was caught by the tests it wrote at the time, because those tests covered the modules
below the DAG and nothing exercised `summarize`. The review that found them was a
line-by-line read against the decision log, not a test run — the decisions were specific
enough ("summarize must always write the manifest") to check code against, which is the
main argument for having written them down. `Task.mock_run` was found by introspecting the
installed SDK rather than recalled, after `ctx`-faking was considered and rejected.

**Not done.** `FETCHED_SOURCES` in `scrape.py` is unused. Nothing has run against the live
API since the fixes — the verification plan in §9 of the design spec is still unrun, and
`data/raw/2026HTSRev16/manifest.json` is still the hand-written prototype.

---

## 2026-08-22 — Step 7: the five end-to-end checks

**Goal.** Run the verification plan from §9 of the design spec against the live API, with
the post-review code, and record the output rather than a verdict.

**Setup.** `data/raw` moved aside to simulate a fresh clone, then `./cleanup.sh` — which,
now that Step 1 pinned the project name, actually named and removed the four
`chp99-takehome_*` volumes instead of silently matching nothing. Stack rebuilt from empty,
schema applied, worker started.

**1 · Clean run.** 26 MB in 9.4s, three sources `fetched`, byte counts and sha256 prefixes
identical to the values hand-fetched on 2026-08-20: `ch99` 1,992,914 / `5a7ca6b0`,
`base` 10,349,905 / `221e1560`, `notes_pdf` 13,969,270 / `58b2a00d`.

**2 · Idempotency.** Second run reported three `unchanged`. The payload mtimes were
byte-for-byte the same before and after — 21:49:42 / :44 / :47 — and only `manifest.json`
advanced, to 21:50:13. `source_fetch` holds six rows under two run ids: three `fetched`,
then three `unchanged`. The mtimes are the real evidence; the status string is only a
claim about them.

**3 · Partial failure.** Injected without touching code: `--release BOGUSREL` gives the
PDF endpoint a release that does not exist, while the two exports ignore the parameter and
succeed. Result: `ch99` and `base` `fetched`, `notes_pdf` `failed` after `attempts=3`,
manifest written with `complete: false`, all three rows in `source_fetch` including the
error text, exit code 1, and the `2026HTSRev16` directory untouched. The report printed
normally on the failed run, which is the payoff for reading it from `source_fetch` rather
than from task outputs.

Two notes. The server answers a nonexistent release with **503**, not 404, so the retry
policy spends all three attempts on a request that could never succeed — the classification
is right in general and wrong here, and nothing in the response distinguishes the cases.
And the client-side failure message is the SDK's generic `Workflow run <id> failed.`; the
useful text (`1 source(s) failed: notes_pdf`) stays in the run detail. The table below it
carries the same information, so this was left alone.

**4 · Interrupted write.** Triggered `--force` and sent SIGKILL to the worker 1.5s in.
Left behind three 0-byte `.part` files, and all three payloads hashed **identically** to
before the kill. A hard kill cannot reach the final path. On restart the re-run logged
`cleared 3 stale .part file(s) left by an earlier run` and completed with three
`unchanged` — which is why `clear_stale_parts` returns what it removed instead of sweeping
silently.

**5 · Release scoping.** `--release 2026HTSRev15` created a new directory rather than
overwriting: `2026HTSRev15/ch99-notes.pdf` is 13,957,698 B / `92822e8f`, genuinely
different from Rev16's 13,969,270 B / `58b2a00d`.

**Defect found by check 5 — a directory name that overstates what it holds.** The two
bulk exports take no release parameter, so `data/raw/2026HTSRev15/` contains a Rev15 PDF
next to `ch99.json` and `base.json` that are whatever the API served at fetch time, which
was Rev16. The directory asserts a revision for all three files, and it is only true of
one. `Source.pinnable` already encodes which is which, and each entry's `url` shows it to
a careful reader, but nothing states it. Not fixed yet; raised for a decision.

**Agent notes.** Two of the checks were made cheaper by probing the API first rather than
editing code to inject faults: a nonexistent release yields 503 and an old release still
serves its PDF, which turned checks 3 and 5 into flag changes. The first attempt to read
the exit code measured `$?` after a pipe and read `tail`'s status instead — corrected by
capturing the command's output into a variable.

**Defect fixed (D-0010).** `release_pinned` now rides on every fetch result and into the
manifest. Verified against the live API by re-running the command that exposed it:
`data/raw/2026HTSRev15/manifest.json` reports `notes_pdf` as `release_pinned: true` and
both exports as `false`. 19 unit tests pass.

The overwrite hazard behind the same defect is deliberately left open and written up in
D-0010: it needs `--release` naming a stale revision after a new one has landed, which
the documented command never does.

**Reworked to prevent the defect, not just declare it (D-0011).** `release_pinned` alone
left the overwrite hazard open, so the fix became: skip a source whose endpoint cannot
serve the pinned release, before any request is made.

Verified against the live API with an unambiguous setup — two 40-byte marker files stood
in for a historical Rev15 snapshot, so an overwrite would have been visible as 2 MB and
10 MB files. After `--release 2026HTSRev15`: both markers still 40 bytes and byte-identical,
the PDF genuinely fetched at 13,957,698 B, `source_fetch` recording `skipped` with the
existing files' size, and the manifest reporting `complete: true` — the directory holds
all three payloads even though two were not re-fetched. A bare run against Rev16 was
unaffected. 23 unit tests pass, including one that queues no HTTP answers at all, so any
request during a skip would raise.

---

## 2026-08-23 — Part 2, Step 0: the schema

Four questions had to be answered from the data before the schema could be fixed, because
each one changes a primary key or a column type.

**Heading rows carry no rate.** Counted across both exports: of the rows with
`superior="true"` — 5,614 in base, 238 in Chapter 99 — **zero** have `general`, `other`,
`special` or `additionalDuties`. That is what makes D-0012 safe: rate inheritance always
terminates on a coded row, so dropping heading rows cannot lose a rate.

**Codes are unique.** 26,246 coded base rows and 3,098 coded Chapter 99 rows, no duplicates
in either. `hts` stays a natural primary key; no surrogate key is needed anywhere except
`note` and `parse_issue`.

**`indent` jumps by more than one in 12 places** in the base export, which would have
broken a naive stack-based tree builder. Printed all 12 with two rows of context: every one
is a 10-digit statistical line sitting two levels below the 8-digit parent immediately
above it (`2620.99.75` → `2620.99.75.20`). "Nearest preceding row of smaller indent" gets
them all right, and the parent's code is a dotted prefix of the child's in every case — so
that becomes a validation rule rather than an assumption.

**`subchapter` is derivable.** The distinct headings are 9901, 9902, 9903, 9904, 9908,
9915, 9917–9922. The heading's last two digits are the subchapter number in Arabic
(9915 → XV), so no hardcoded lookup table is needed. This was not obvious from the JSON and
was found by listing the headings rather than assuming.

**`units` is an array.** 4,725 base rows report two units (`{doz.,kg}`), so a `text`
column would have silently truncated a fifth of the rows that have units at all.

### D-0011 was missing

`PART1_SCRAPER.md` and `JOURNAL.md` both cite D-0011, and D-0010 is marked "superseded by
D-0011", but the entry was never written — it was lost at the end of the Part 1 session.
Backfilled from the code and the verification already recorded here. Worth noting as a
process failure: the decision log's value depends on it being complete, and a dangling
cross-reference is the only reason this was caught.

### Verification

Applied `db/schema.sql` twice against a running stack. Both runs exited 0 and `\dt` listed
the same **11 tables** each time. The first run emitted seven "table does not exist,
skipping" notices; the second emitted only "extension pg_trgm already exists".

Two constructs are unusual enough to be worth testing for behaviour rather than existence:

```
INSERT  → full_description_tsv = 'acid':3 'alanin':5 'amino':2
UPDATE  → full_description_tsv = 'acid':3 'amino':2 'amino-acid':1 'ester':6
```

The generated column follows an update with no trigger, which is the property it was chosen
for. The GIN indexes answer: `to_tsquery('english', 'amino & acid')` returns the row, and
`similarity(full_description, 'amino acids esters')` returns 0.667.

`UNIQUE NULLS NOT DISTINCT` on `note` was tested by inserting two chapter-level notes with
the same number and no subdivision:

```
ERROR:  duplicate key value violates unique constraint
DETAIL:  Key (note_kind, subchapter, note_number, subdivision)=(chapter, null, 1, null)
         already exists.
```

Without `NULLS NOT DISTINCT` both rows would have inserted, since Postgres treats NULLs as
distinct by default. Test rows were removed by re-applying the schema; `hts_base` and
`note` are back to 0 rows.

**Dropped columns.** Searched the repo for `mfn_rate_pct`, `rate_value` and `note_ref`.
`app/server.ts` only lists table names, so it is unaffected. `parts/PART2_PARSER.md` quotes
them but is a supplied requirements document and is not edited. `CLAUDE.md` described
`rule.rate_value` as current and was corrected.

### Agent notes

The schema was drafted once before any of the four probes above were run, and it was wrong
in two places that the probes caught: it assumed heading rows might carry rates (which
would have made dropping them unsafe), and it typed `units` as `text`. Writing SQL before
counting rows produces confident, plausible, wrong columns.

The first draft also carried a `rate_kind` vocabulary copied from the scaffold
(`ad_valorem`, `specific`) without noticing that those name the *operand* and leave a
compound duty like `4.4¢/kg + 8.5%` with no valid value — 417 rows that would have had to
be filed under `other`. Caught while writing the decision entry, not while writing the
schema, which is an argument for writing the entry first.

---

## 2026-08-23 — Part 2, Step 1: the parser skeleton, and a payload that was not ours

Built `parsing/manifest.py`, `parsing/db.py`, `parse.py`, `parse_run.py`, and a shared
`client.py`; registered `ParseHTS` in `worker.py`. 30 unit tests pass (23 before).

**`client.py` exists because two `Hatchet()` instances cannot serve one worker.** The
worker registers workflows by object, so `scrape.py` and `parse.py` had to share a client
rather than each constructing one.

### The check that was nearly deleted

The first draft of `load_manifest` re-hashed every payload and compared against the
manifest. Challenged as redundant, and the challenge was right on its own terms: the
scraper writes through a staged file and `os.replace`, so a crash cannot leave a truncated
payload at the target path — that was verified with SIGKILL during Part 1. Re-hashing
second-guesses a guarantee the design already provides.

Replaced with `exists` plus a size comparison — two stat calls, and the point is failing
early with a clear message rather than verifying bytes.

**It fired on the first real run.**

```
ManifestError: /data/raw/2026HTSRev16/ch99.json is 2,060,842 B,
               but the manifest recorded 1,992,914 B
```

Not a false positive. `sha256` on disk was `7283b218…` against the manifest's `5a7ca6b0…`;
`base.json` and the PDF matched exactly. `ch99.json` had an mtime of 12:17 against the
manifest's 10:56 — something outside the workflow had written it, almost certainly an
exploratory `curl` during the data analysis.

Re-running the scraper resolved it, and the resolution is the uncomfortable part:

```
  ch99         fetched      1,992,914 B  sha 5a7ca6b0…
```

The API served the *manifest's* bytes. The 2,060,842 B file was never what this pipeline
fetches, and it has now been replaced.

### What that costs

**Every Chapter 99 count in `DATA_INVENTORY.md` was measured against that file.** The base
schedule is unaffected — `base.json` hashes identically, so every base-side number stands.

Recounting the same fields against the authoritative payload, with the same definitions:

| Metric | Documented | Authoritative |
| --- | ---: | ---: |
| rows / coded / superior | 3,336 / 3,098 / 238 | unchanged |
| `general`, `other`, `Free`, `+ 25%`, `+ 15%` | 2,220 / 2,075 / 1,364 / 47 / 44 | 2,219 / 2,075 / 1,364 / 47 / 44 |
| `additionalDuties` non-empty | 810 | **512** |
| rows containing "provided for in" | 2,556 | **2,456** |

Two of those are real differences under an identical definition. The rest of the recount
(note citations, cited codes, CAS, exclusions) moved as well, but there the definitions
were not identical, so the delta cannot be attributed cleanly and the numbers have to be
re-derived rather than compared.

### A second error the recount exposed, unrelated to the payload

Classifying provisions into "cites a code / points at a note / country only" was done on
each row's own `description`. Reading the ancestor chain instead — which is what the
parser will do, and what the schedule means — `9903.01.01` reads:

> Except for products described in headings 9903.01.02, 9903.01.03, 9903.01.04 and
> 9903.01.05 **articles the product of Mexico**, as provided for in U.S. note 2(a) to
> this subchapter

It cites a note, but note 2(a) is prose defining country of origin, not a list of
subheadings. So a note citation only puts a provision on the code path **if that note is a
list**, and which notes are lists is not known until the notes are parsed.

**The 2,203 / 558 / 211 split in `DATA_INVENTORY.md` §4 is therefore not a fact that can be
established before Step 4.** It is a parser output. The design it justifies is unaffected —
`9903.01.01` still has no join key to the base schedule, so `rule.scope` (D-0018) is still
needed — but the specific counts cited as evidence are not trustworthy and are marked as
such until the resolver produces them.

### Verification

`ParseHTS` run from the host against the running worker:

```
release  2026HTSRev16
source   /data/raw/2026HTSRev16/
  base         source_fetch #5
  ch99         source_fetch #4
  notes_pdf    source_fetch #6
```

Provenance reconstruction tested by deleting every `source_fetch` row and re-running:
three rows reappeared with `run_id` NULL, which is how a reconstructed row is
distinguished from an observed one. Running again reused ids 4/5/6 and left the count at
3, so it is idempotent.

### Agent notes

Two failures worth recording.

The first is mine and was caught by the tool: editing `scrape.py` in two steps left the
file referencing `Hatchet` after the import had been removed, and `compose watch`
restarted the worker into that state, producing a `NameError` restart loop for about a
minute. Nothing was lost, but a multi-edit refactor of a file under a watcher should be
one write, not two.

The second is that a check argued to be redundant found a real defect within minutes of
being weakened. The redundancy argument was correct about the mechanism it addressed — the
scraper's atomic write — and wrong about the threat, which was a human with `curl`. The
weakened version still caught it, so the outcome was good, but the reasoning that produced
it ("the design already guarantees this") would have justified removing the check
entirely.

### A review question that exposed a missing decision

Asked in review why `parsing/db.py` is not redundant, given that the documented recovery
after a schema reset is `setup.sh` → scrape → parse, which re-creates the rows. The premise
was right and the conclusion was not: re-running the scraper needs the network, which is the
one thing Part 2 is defined as not needing, and for a superseded release it cannot work at
all — both `exportList` sources are `pinnable=False`. Checked rather than assumed that
`./cleanup.sh` leaves `data/` intact: `./data` is a bind mount, and the script filters on the
Compose project label, so it never sees it.

The reconstruction had no entry in `DECISIONS.md` at all. Written up as D-0023 with the
challenge itself as the first rejected option, since it is the objection a reviewer reaches
first. Second time in two sessions that a dangling or absent decision was found by someone
asking about the code rather than by reading the log.

---

## 2026-08-23 — Part 2, Step 2: the base schedule

`parsing/rates.py`, `parsing/tree.py`, `parsing/issues.py` and `parsing/base.py`, wired
into the DAG as `parse_base_schedule`. 54 unit tests pass (30 before).

**Counted before writing, this time.** The last step's lesson held: every shape the parser
handles was enumerated from the data first. 22,829 non-empty rate strings across `general`
and `other`, 1,419 distinct, and the four obvious patterns cover all but 420 of them. The
420 turned out to be six different things — a fractional percentage (`33 1/3%`, 84 rows), a
qualified basis (`7.4¢/kg on drained weight`), a sliding scale, a pointer to another
heading's rate, `See additional U.S. note N`, and three-operand compounds. Only the first
two are parseable, and knowing that before writing the regex is why `rate_specific_unit`
carries the qualification instead of dropping it (D-0024).

**The tree needed no special cases.** 26,246 coded rows, and the "nearest preceding row of
smaller indent" rule produced **zero** parent-prefix violations across all of them —
including the 12 places where indent jumps by more than one. The code hierarchy and the
indent hierarchy agree everywhere in this revision, which is a stronger result than
expected and is now asserted per row rather than assumed.

**Every leaf has a rate.** 3,053 rows end up `rate_kind='none'` — no rate of their own and
no ancestor with one. All 3,053 are 4- or 6-digit codes and **all 3,053 have children**;
zero leaves are left without a duty. That is what makes `none` a structural marker rather
than a gap.

### Verification

```
hts_base   26,246 rows
           11,779 rates inherited from an ancestor
              305 rates that cannot be computed
              305 parse_issue rows
```

Acceptance queries:

```
2922.49.49.10 | Alanine | 4.2% | replace | 4.2 | inherited from 2922.49.49
0402.99.90.00 | 46.3¢/kg + 14.9%  ->  pct 14.9, amount 0.463, unit kg
2922.49.30.00 | general 6.5%      vs  column 2 '15.4¢/kg + 50%'
```

Prose accounting reconciles: 421 rows carry `rate_kind='prose'`, of which 150 printed one
themselves and 271 inherited it from an ancestor; the 305 issues are 150 `general` plus 155
`other`. Ran from an empty database (`./setup.sh`, `hts_base` at 0 rows) straight through
to 26,246. Ran twice more and compared `md5(string_agg(t::text, '|' ORDER BY hts))` over
the whole table: identical.

### Two performance findings, one of which I got wrong first

Switched the loader to `COPY` on the assumption that `executemany` was the bottleneck, and
**wrote the speedup into a code comment before measuring it**. It was not the bottleneck:
COPY changed nothing. Measured properly:

| | |
| --- | ---: |
| `DELETE FROM hts_base` | **10.41s** |
| `TRUNCATE hts_base, rule_base_match` | 0.00s |
| COPY 26,246 rows | 1.58s |
| `executemany` 26,246 rows | 2.25s |

The cost was the delete, not the insert, and the reason is in the schema I wrote: two
self-referencing foreign keys with `ON DELETE SET NULL` mean deleting the table nulls out
~26,000 references one at a time (D-0025). COPY is kept — it is 30% better, not the order
of magnitude the comment claimed, and the comment now says so.

Total wall clock for the workflow is ~37s against ~2s of database work. The remainder is
scheduling latency in the Hatchet Lite dev image across three tasks; not chased, since it
is outside our code and does not affect the result. Recorded rather than explained.

### Agent notes

The comment written before the measurement is the notable failure — the same shape as the
regex-escaping bug recorded twice already: producing a confident artifact and only then
checking it. It was caught within minutes because the next thing done was a measurement,
but nothing about the process forced that.

`compose watch` syncs files without restarting, and Python caches modules, so a run against
"the new code" was ambiguous until the worker was restarted explicitly. The gotcha is in
CLAUDE.md; noticing it required reading `Up 3 minutes` on the container and realising it
had not restarted.

### A cap questioned, measured, and kept

Asked in review why `parse_rate` refuses three or more terms when it handles two. Measured
rather than argued: 138 strings, 94 distinct, all in the base export — chapters 26, 65, 91 —
and none in Chapter 99. The samples settled it in the opposite direction from the question:
`75¢ each + 45% on the case + 35% on the battery` is not a longer compound rate, it is two
ad valorem terms with different bases, which no number of extra columns can hold. The cap at
two is where "one percentage and one amount, both on the whole good" stops being true.

Kept as is and written up as D-0026, including the hybrid `rate_term` design that would fix
it and the condition that should trigger it. Also fixed a numbering collision found on the
way: two entries had been written as D-0023 in the same session, one here and one in Step 2.
Renumbered the later two and updated the three references. Third time in three sessions that
a gap in the decision log surfaced through a question about the code rather than through
reading the log.

### Column 2's inheritance had nowhere to be recorded

Asked in review what `column2_from` is for. Answering it exposed that the value was computed
and then thrown away: `parse_base` used it to pick the effective Column 2 rate but the schema
had only `rate_inherited_from`, so Column 1 could say "this rate was copied from an ancestor"
and Column 2 could not. That is the asymmetry D-0014 exists to prevent — materialising a rate
is only acceptable if the row can say where it came from.

Measured whether the second `inherit()` call is redundant before adding a column for it:

```
Column 1 needs to inherit  11,779 rows
Column 2 needs to inherit  11,778 rows
the two chains disagree on      1 row   -- 9006.59.15.20
```

`9006.59.15.20` states its own Column 2 (20%) while inheriting Column 1 (Free) from
`9006.59.15`. One row in 26,246, and reusing `general_from` for both columns would have given
that row its ancestor's Column 2 instead of its own — wrong, invisible, and impossible to
notice from the data. The second call stays, and the schema now has `col2_inherited_from`.

Verified after `./setup.sh` and a re-run: 11,779 / 11,778 / 1, and the one differing row reads
correctly. Also exercised D-0023 incidentally — the schema reset dropped `source_fetch`, and
the parser rebuilt all three rows from the manifest without the scraper running.

Worth recording as a domain fact rather than only a fix: Column 1 and Column 2 are stated on
the same row 99.99% of the time. The "almost" is the part a future optimisation must not
assume away.

---

## 2026-08-24 — Column 2 inheritance provenance

Change made by the user on top of Step 2: `col2_inherited_from`, so Column 2 records the
ancestor its materialised rate came from instead of borrowing Column 1's.

Verified rather than assumed. The two chains disagree on exactly one row in 26,246:

```
      hts      | rate_text | rate_inherited_from | col2_rate_text | col2_inherited_from
---------------+-----------+---------------------+----------------+---------------------
 9006.59.15.20 | Free      | 9006.59.15          | 20%            |
```

11,779 Column 1 rates and 11,778 Column 2 rates are inherited, across 3,267 distinct
ancestors. Schema re-applied from empty, parser re-run, 54 tests pass, and two consecutive
runs produce an identical whole-table md5. Written up as D-0028 and added to both schema
references, which had described Column 2 as "the same five columns".

---

## 2026-08-24 — Part 2, Step 3: Chapter 99 provisions

`parsing/ch99.py`, wired in as `parse_chapter99` running beside `parse_base_schedule` —
the fact tables it writes carry no foreign key into `hts_base`, so nothing makes it wait.
62 unit tests pass (54 before).

### Verification

```
rule        3,098 rows   2,571 by_code  341 by_country_all_goods  186 unknown
           13,370 code references
              859 exclusion edges
              401 country links
            1,229 CAS numbers
              926 note citations (unresolved until step 4)
               17 parse_issue rows
```

Acceptance:

```
9903.01.01 | III | by_country_all_goods | additive | 25.0 | Mexico | 4 exclusions
9903.88.01 | III | 'The duty provided in the applicable subheading plus 25%' -> additive 25
           |     | cites U.S. note 20(a) to this subchapter, and U.S. note 20(b)
2922.49.30 | cited by 9902.04.04/.05/.06/.07, each carrying its own CAS number
```

Subchapter derivation checked against all twelve headings present: 9901→I, 9902→II,
9903→III, 9904→IV, 9908→VIII, 9915→XV, 9917→XVII … 9922→XXII. The rule that the heading's
last two digits *are* the subchapter number holds everywhere.

Two consecutive runs produce an identical combined md5 over `rule`, `rule_edge`,
`rule_country`, `rule_identifier` and `rule_note`.

### A test invalidated an earlier measurement

`_excluded_codes` was written as `\bexcept\b[^.;]*`. A hand-written unit test returned an
empty list, and the reason was that **codes contain dots** — the clause ended at the first
`.` of `9903.01.02`. That mattered beyond the bug: the check run two hours earlier
concluding "no exclusion clause names a code outside Chapter 99, 0 cases" had used the
same expression, so it had never read past the first code. The verification was vacuous
and I had recorded it in a code comment as established fact.

Widening the boundary then showed the opposite error: `\bexcept\b` matches 431 clauses in
this revision and **217 are parentheticals inside a product description** — `of bovine
(except calfskin) leather` — not exclusions at all. Matching the lead-in instead gives 214
provisions and 859 edges (D-0029), against the 324 / 864 that D-0022 had recorded from the
loose expression. That figure is now corrected in both schema references.

### Estimates replaced by parser output

D-0022 said every figure surviving into Step 5 should become a parser output rather than
an ad-hoc count. Four were replaced today, and the estimates were not close:

| | estimated | actual |
| --- | ---: | ---: |
| `rule_edge` | ~2,900 | **14,229** |
| `rule_country` | ~250 | 401 |
| `rule_identifier` | ~1,034 | 1,229 |
| `rule_note` | ~973 | 926 |

`rule_edge` was out by a factor of five because the estimate counted provisions, not
citations, and a provision routinely names several codes.

### Two things deliberately left as they are

`country_code` is NULL for every row (D-0030): no source in this repository contains an
ISO list, and hand-writing 100 pairs would be unverifiable data that looks authoritative.

`rule_country.relation` only ever holds `product_of`. Four phrasings of a country carve-out
were searched for and every one returned zero — reciprocal-tariff headings carve out
*headings*, not countries. Both schema references said the opposite and have been fixed;
the claim was written from plausibility rather than from a query.

### Agent notes

The exclusion bug is the third instance of the same failure recorded in this journal:
producing a confident artifact — a comment, a count, a claim — and only checking it later,
if at all. What differs here is that the check was forced by a unit test written *before*
running the parser on real data, and it caught something a full-corpus run would not have,
since the wrong answer was plausible at every scale.

### A proposed fix that would have overcharged two provisions

Reviewed the 321 `parse_issue` rows. The 305 on `base` are the watch and ensemble rates
already settled by D-0026. The 17 on `ch99` split into 13 provisions that key on origin
without naming a country ("any country", "any country determined by USTR", "a member state
of the European Union") and 4 unparsed rates.

**The first reading of those 4 was wrong, and acting on it would have written bad data.**
The proposal was that three shared one bug — `ADDITIVE` wants `+ 25%`, they write `+ a duty
of 25%` — so widening the regex would recover all three. Counting the variants first, as
Step 2 established, showed otherwise:

```
234  ... applicable subheading + N%          204  ... applicable subheading (bare)
  2  ... + N% no space   1  plus N%   1  'inthe' typo
  1  ... + a duty of N%                                          <- genuinely the same rule
  2  ... + a duty of N% upon the value of the non-U.S. content   <- a narrower base
  1  The duty provided in subheadings 8716.39.00, ... + N%       <- a named base
```

Two of the three apply 25% to the non-U.S. content, not to the entered value. Stored as a
plain additive 25% they would overcharge the full value, and nothing in the row would show
it — the same failure D-0026 exists to prevent, arrived at from the opposite direction.

Fixed only the one unambiguous row, keeping the `$` anchor that excludes the other two, and
wrote a test for each side of the boundary. The test that matters is the negative one: it
asserts that the narrower base *stays* unparsed. Ran the negative test against the old regex
first — it already passed, which is the point; it protects a property, not a change.

Verified: 64 tests (62 before). Against all 446 real rows, 239 additive / 204 no_change /
3 prose, and zero reclassification among the 234 standard spellings. End to end, `ch99`
issues 17 -> 16, `9903.82.20` now `additive` with `rate_ad_valorem_pct` 25.0. Two
consecutive runs give the same whole-table md5 for `rule` (`cfe10ca8…`).

**Second numbering collision.** Step 3 wrote D-0025, D-0026 and D-0027, all three already
taken by entries written earlier the same day. Renumbered the later three to D-0028..D-0030
and repointed the three journal references; the two code comments citing D-0026 meant the
earlier entry and were left alone. The first collision was two entries; this one was three,
so appending without checking the tail is now a repeatable failure rather than a slip. A
one-line check before writing an entry — `grep -c '^## D-' docs/DECISIONS.md` — would have
caught both.

**Agent notes.** The agent proposed the three-row fix confidently and was wrong about two of
them; the error surfaced only because the repo's own habit of counting the data first was
applied before editing. Left to the proposal, the parser would have produced a wrong duty
that no test and no issue row would have flagged.

---

## 2026-08-24 — Country extraction, then country codes

Asked whether a country-code table was worth building. Answering it needed the extracted
names looked at rather than assumed, and the list had five wrong entries in it.

**Three extraction defects, found by reading the output.**

```
Bosnia | Herzegovina        <- 'Bosnia and Herzegovina' split on ' and '
Trinidad | Tobago           <- 'Trinidad and Tobago' likewise
of the United Kingdom       <- 'the product of Germany or of the United Kingdom'
```

The article stripper removed a leading `the` but not `of the`, so `9903.89.43` never joined
the other eight UK provisions.

**The obvious repair was wrong.** "Split on `or`, not on `and`" removes four bad names and
creates a fifth: `China and Hong Kong` occurs five times and is two jurisdictions, so that
rule would have dropped five China links and five Hong Kong links while inventing a name
that is neither. Fixed instead with a 14-entry set of ISO names containing "and" (D-0033).
Distinct names 100 -> 97; a query for names not matching `^[A-Z][A-Za-z'\- ]+$` returns
zero rows.

**Then the codes.** D-0030 had left `country_code` NULL, arguing that the only way to fill
it was an unverifiable hand-written table. That entry missed a correctness argument:

```
 country_code |    names_in_the_schedule    |                    rules
--------------+-----------------------------+---------------------------------------------
 RU           | Russia / Russian Federation | 9903.05.66, 9903.82.17, 9903.85.67,
              |                             | 9903.90.08, 9903.90.09
```

Two headings say `Russia` and three say `Russian Federation`, and `9903.90.08`/`.09` are
the Section 232 steel pair. Without a code a user asking about Russia got two rules or
three depending on spelling — a wrong answer, not a missing convenience. `pycountry` also
turned out not to be a hand-written table but the ISO 3166 register, so D-0030's objection
did not apply to it. Superseded by D-0032.

Exact matching only, no `search_fuzzy`. Fuzzy resolves three more names and happens to get
`Russia` right; it is a heuristic, and a wrong country is worse than a NULL. Those three
plus two others go in a five-line alias table, each a rename or inversion inside ISO 3166
with the reason on the line.

**Verified.** 391 of 397 links carry a code, 95 distinct; the six without are all
`European Union`, which is a bloc and correctly has none. Zero `unresolved_country` issues.
73 tests (67 before). Two consecutive runs give an identical md5 for `rule_country`
(`05698987…`).

**Third numbering collision, same failure again.** Appended D-0028/29/30 without reading the
tail first; all three were taken, and the "superseded" marker landed on D-0027, which is
about Column 1 Special and has nothing to do with country codes. Renumbered to D-0032 and
D-0033, and dropped a third entry entirely as a duplicate of D-0031, which had already
settled the `a duty of` variant from a fuller count than mine.

**Agent notes.** The journal already recorded this exact failure one session earlier, with
the remedy written out — check the tail before appending — and it happened again anyway.
Reading a note about a mistake is not the same as having a step that prevents it. The
recurring shape is broader than numbering: acting on the state I remember instead of the
state on disk.

The country work went the other way. The user's instruction was to split on `or` only; the
data said that would break `China and Hong Kong`, and checking before implementing turned a
correct-sounding rule into a correct one.
