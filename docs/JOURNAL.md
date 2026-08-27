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

---

## 2026-08-24 — Part 2, Step 4: the notes PDF

`parsing/notes.py`, wired in as `parse_us_notes` after `parse_chapter99`. 84 unit tests
(73 before).

```
note          345 records across 9 subchapters   10 mixed  301 prose  34 subheading_list
           36,764 codes listed by a note
```

**The riskiest step, and the survey was worth the time.** Extracted the text first and read
it before writing any pattern. That is how the page furniture turned out to be written two
ways — `99-III-1` on a subchapter's first page and `99 - III - 377` with spaces on the rest
— and how the note-page runs were found: 468 pages in 9 blocks, subchapter III's notes alone
spanning pages 172-596.

**Three segmentation attempts, three failures on real data.** Each was caught by measuring,
not by reading the code:

1. `^(\d{1,3})\.` opened "note 44" on `44.5 percent ad valorem`. Because a similar false
   match had already taken 74, note **52** — cited 98 times — could never open. Fixed with a
   lookahead for whitespace or end of line.
2. After that, the plain monotonic rule accepted `(vvv)` — a label quoted inside note 20's
   own prose — right after `(a)`, which then blocked the real `(b)` and the **874 codes**
   under it. That is the Section 301 List 1 scope, the single most important list in the
   document. Fixed by allowing a label at most two places ahead.
3. `(?<!\d)\d{4}\.\d{2}` read one code out of `0201.10.500201.10.10`. The lookbehind broke
   exactly the case it was written for, since the second code is preceded by a digit. A unit
   test caught this one before any run.

**A constraint caught a fourth.** `UNIQUE NULLS NOT DISTINCT` on `note` rejected the load
with `Key (us_note, I, 3, i) already exists` — the same subdivision letter twice in one
note, because `(i)` is both the ninth letter and the first roman numeral. That constraint was
added in Step 0 for a different reason and paid for itself here.

**Verification.** The real acceptance test is not a row count but whether the citations
extracted from Chapter 99 can find their notes:

```
 resolves                          | 737
 chapter note - different document | 126
 NOT FOUND                         |  63
```

737 of 800 in-PDF citations resolve (92%); the 126 are `additional U.S. note N to chapter N`,
which belong to another chapter's document and are correctly not here. Note 20(b) lands as
`subheading_list`, pages 261-265, 874 codes. Checked that `7208` is **not** among them, which
is right — steel is Section 232 under note 16, not Section 301 List 1. Two consecutive runs
give `345/36764/4a6f1b1f…` for count, code count and a digest of every label, kind and body
length.

**Agent notes.** The pattern across all four failures is the same: a rule that looks correct
in isolation and is wrong against the document. Every one was found by running the extractor
over the real 807 pages and asking a question with a checkable answer — does note 52 exist,
does 20(b) have codes, do the citations resolve — rather than by inspecting output that
looked reasonable. The two failures that would have been most damaging (note 52 missing, 20(b)
empty) produced no error and no empty result: they produced a smaller, entirely plausible
set of notes.

---

## 2026-08-25 — Part 2, Step 5: resolving citations, and Part 2 complete

`parsing/resolve.py`, wired in as `resolve_citations` after the three parse tasks. 91 unit
tests (84 before). The whole pipeline now runs from an empty database to a queryable one.

```
hts_base   26,246 rows      11,779 / 11,778 rates inherited      305 uncomputable
rule        3,098 rows      13,370 references   859 exclusions   397 countries
note          345 records   36,764 listed codes
resolved   16,958 provision -> base matches (cited directly)
           79,087 note -> base matches (once per note)
              738 citations linked to a note
              306 provisions rescoped once their note was read
          scope now  2,877 by_code  102 by_country_all_goods  119 unknown
```

**The first version did not finish, and the reason was a design error, not a slow loop.**
Putting the note path into `rule_base_match` means storing note 52's 4,166 codes once for
each of the 98 provisions that cite it. Measured offline rather than guessed: 805,762
prefix lookups and roughly **4.7 million rows**, ~98% of them repetition. Split into
`note_base_match`, keyed by note, it is **79,087** — sixty times smaller (D-0036).

This is the same product D-0018 refused to materialise for country-wide provisions,
arriving from the other direction, and it is now the second place where the schema trades a
UNION for a row count.

**D-0025 paid for itself twice.** `TRUNCATE hts_base, rule_base_match` failed with
`Table "note_base_match" references "hts_base"` — exactly the loud failure that naming
tables instead of using CASCADE was chosen for. One line to fix, and nothing was silently
emptied.

### Flagship query, end to end

Steel `7208.51.00.30` from China:

```
base duty      Free, inherited from 7208.51.00
by code/note   14 provisions, all via U.S. note 30(d) and note 31 — Section 232 steel
by country     63 provisions naming China
```

`9903.88.01` correctly does **not** appear in the code path: it was rescoped to `by_code`
once note 20(b) was read, and 7208 is not in that list — Section 301 List 1 is machinery
and electronics. The Section 232 headings that do apply arrive through their own notes.
The country path returns 63 rows, most of them `no_change` exclusion headings, which an
application has to narrow with `rule_edge(excludes)`; that is the graph the starting schema
described and it is now populated.

Ran twice from the same payloads: every figure above is identical on the second run —
16,958 / 79,087 / 738 / 306 and the same scope split — so the whole pipeline is idempotent
end to end, not only per task.

288 `parse_issue` rows from this stage: citations naming a note this parse did not find,
and cited codes matching no row in the base schedule. Both are the residue Step 4 predicted
and neither is silent.

**Agent notes.** The failure mode here was mine and structural: I wrote the resolver to the
shape of the existing table instead of asking what the table would contain. The estimate
that caught it took two minutes and could have been made before writing any of it — the
same "count first" habit that this repo has now recorded three times, skipped again under
time pressure.

## 2026-08-25 — Part 3 design, and three parser defects it uncovered

Started on Part 3. Spent the session clarifying scope with the user and then, while sizing
one UI decision, found that Part 2 was reporting duties that do not apply.

**How it surfaced.** The Part 3 duty page was going to show the applicable provisions as a
one-line formula, `base + ch99 = final`. To know whether a single line was enough I counted
the terms for the flagship query — `7208.51.00.30`, hot-rolled steel, from China — and got
**14 additive provisions**, including `9903.91.01 +25%`, `.02 +50%` and `.03 +100%`. Three
mutually exclusive rates, same goods, same day. The layout question was answered by finding
out the number was wrong.

**What was wrong.** Three separate defects, each measured before being fixed:

1. `subdivision (g) of U.S. note 31` was not read as a subdivision citation — only the
   inline `U.S. note 31(g)` form was. 202 provisions linked to the parent note, which holds
   the union of its subdivisions' lists. `9903.91.06` cites a note about graphite and
   magnets and was reaching steel. → D-0037
2. The notes PDF segmenter loses note 2's subdivisions past `(c)` (label sequence jumps
   `(c)` → `(j)`, past `MAX_GAP`) and mis-accepts a three-levels-down `(d)` as top-level.
   Not fixed — the outline has three levels with reused labels and pypdf reports leading
   whitespace 0 on every line, so there is nothing to reconstruct it from. Recorded in a
   column instead. → D-0038
3. Notes that name their codes in running prose (`classified in 8-digit subheading
   4015.12.10`) yielded no codes, so provisions citing them stayed `by_country_all_goods`.
   `9903.91.08` is a 100% duty on rubber gloves and was landing on every Chinese import.
   → D-0039

**Verified.**

```
additive layers on 7208.51.00.30 from China   14  ->  3
  the one matching by code does so via note 31(b), which is the steel list
no_change exclusion provisions on that query  61  ->  58
resolve/unresolved_note issues                62  ->  1
citations linked to a note                   738  ->  850
rule_note.match_precision   exact 573 · parent_fallback 277 · chapter_note 126 · unresolved 1
note content_kind           mixed 23 -> 63, prose 288 -> 248
parse_issue                609 -> 825  (211 of the increase is the new
                                        subdivision_not_segmented, which is the point)
```

Ran the parser twice with no code change between: every table identical, including
`parse_issue` at 825. Idempotency holds.

**Then three more, found the same way.** Asked whether an LLM should read the prose notes.
Partitioning the 164 still-blocked provisions by what would actually unblock each one turned
the question from "should we" into "not yet, and not for most of them":

```
44  parent note whose subdivisions already carry codes    deterministic  -> D-0040
54  note that points at another note                      deterministic  -> D-0041
48  note stating both what it does and does not cover     the real LLM case, deferred
27  note naming no code at all -- a quota trigger price, a definition, an ad valorem
    equivalence formula. Nothing to extract, by any method.
```

D-0041 turned on one measurement: the notes point at each other 224 times, and the two
directions are separable by wording — `subheadings enumerated in` (70, coverage) versus
`and provided for in` (154, an exclusion). Following both would have filed every USTR
exclusion list as the scope of the duty it exempts goods from.

A control query then caught a fourth defect that had nothing to do with notes: laptops from
China returned Canada's and Myanmar's provisions, because those rows have no `rule_country`
at all and a country filter cannot see what is not there. → D-0042

**Verified, cumulative over the session.**

```
additive layers, 7208.51.00.30 steel + China    14  ->  2
no_change exclusions on that query               61  ->  20
additive layers, 8471.30.01.00 laptop + China    14  ->  8   (survivors all name China,
                                                              or are the IEEPA universal
                                                              baseline, which does apply)
note_subheading                              36,764  ->  48,170
note_base_match                              79,087  ->  136,325
citations linked to a note                      738  ->  850
provisions rescoped to by_code                  306  ->  343
scope by_country_all_goods                      341  ->  67
rule_country links                              397  ->  422
country names that would not resolve             11  ->  0  (only 'European Union' left,
                                                              correctly not a country)
resolve/unresolved_note                          62  ->  1
parse_issue                                     609  ->  848
```

Parser run twice with no code change between: all eleven tables identical, `parse_issue`
848 both times.

**Agent notes.** Three things worth recording.

The defect was found by *designing the UI*, not by testing the parser. Part 2's own
verification asked "did every provision get a note link" and got yes; it never asked "is
this the right note", because nothing downstream had yet tried to use the answer for
anything. A count of duty layers on one real query found in two minutes what a full
verification pass had missed.

I also over-estimated defect 3 before measuring it. The plan recorded "103 notes / 374
citations" from a wide `body ~ code-pattern` probe; the real figure once the extraction rule
was written was 13 notes and 548 codes. Wrote the wide number into the plan as if it were
the measurement. Corrected in the report to the user before any code was written against it.

The user asked whether an LLM should handle the prose notes, and the useful move was not to
answer yes or no but to partition the 164 blocked provisions by what would unblock each. Two
groups were deterministic and larger than the LLM's; one group was unreachable by any
method. The LLM's genuine share is 48 provisions across 34 notes — real, but fourth in line,
and invisible until the partition existed. Scope questions phrased as tool questions are
worth re-asking as measurement questions.

**Step 0b — effectivity.** Added `effective_from`, `effective_to`, `status` and
`status_note` to `rule`, read from the two prose signals the sources leave (D-0043). The
compiler's asides turned out to be twice what the plan estimated: 42 provisions in their own
description, 70 counting a superior text's, against the 21 dated windows the plan had
counted. Splitting status from dates was forced by the largest group — 36 provisions read
`provision terminated. See 90 Fed. Reg. 37963.` and give no date at all, so date columns
alone would have left them looking current.

The domain behaviour that fell out of this is the part worth recording: `9903.01.63`, the
34% reciprocal rate on China, comes back `suspended — see 90 Fed. Reg. 50729`, and
`9903.88.16`, section 301 list 4B at 15%, likewise. Neither was special-cased; both are the
compiler's own words.

```
status            in_force 3,028 · terminated 45 · suspended 25
carrying a date   52
on 2026-08-25     in force 3,005 · expired 26 · not yet in force 5
laptop control    additive layers 8 -> 6
```

Parser run twice with no code change: identical, `parse_issue` 848 both times.

One thing nearly went wrong. The same descriptions carry a transit carve-out — "Except for
goods loaded onto a vessel ... in transit before 12:01 a.m. eastern daylight time on April
9, 2025" — and my first instinct was to match `on or after <date>` anywhere in the text.
That reads a carve-out for goods already at sea as the date the provision starts, on
`9903.01.51` and `9903.02.43`. Anchoring on `effective with respect to entries` was the fix,
and the eight-case check that caught it was written before the regex, not after.

**Step 0c — the step that measurement cancelled.** The plan carried three derived tables.
Measuring them first withdrew all three (D-0044), and the number that had put them in the
plan turned out to be my own mistake: "the note path costs 3,988 ms" is a `GROUP BY` over all
26,246 base codes at once, which no screen runs. Shaped the way a page actually asks, the
same work is **3.762 ms**, and the slowest thing in the whole app — a full duty stack for one
code and one country — is **44.8 ms**.

Each table also failed on its own terms, and two of the failures were arguments I had made
myself without checking:

- I said `rule_coverage` would substantiate D-0038's over-breadth warning. It does not:
  `parent_fallback` provisions have a *lower* median coverage than `exact` ones (4,146 against
  9,579). I invented the correlation.
- I said `base_profile`'s provision count would teach a novice which goods are in a trade
  action. Sampled, 1,038 of ~1,187 codes have 20 or more — the number is the same everywhere,
  because the reciprocal tariff really does cover almost everything.
- `rule_exclusion_closure` has nothing to close: 859 edges at depth 1, 23 at depth 2, and a
  **cycle** below that (`9903.91.12` ↔ `9903.91.13`). The finding worth keeping is the cycle,
  not the table — any recursive walk needs a depth cap or it does not terminate.

What replaced them is one editorial table (D-0045). Measured: of 345 U.S. notes exactly one
names a statute. So `9903.88.04 +25%` cannot be told from the data to be Section 301, and the
app that exists to explain Chapter 99 could not say what any duty was. Seven heading families
are labelled, each carrying an `evidence` column quoting what the parsed rows themselves say,
and 9903.89 and 9903.90 are left blank rather than guessed at.

The flagship query now reads as something a person can follow:

```
7208.51.00.30   hot-rolled steel, product of China
   Free                       Column 1 General, inherited from 7208.51.00
   + 25%   9903.88.04         Section 301 — China
   + 25%   9903.91.01         Section 301 — China, 2024 review   (via note 31(b), the steel list)
```

**An hour lost to infrastructure, and one real fix out of it.** Hatchet Lite degraded after
three days up and a dozen runs: heartbeats timing out, `acquired_connections=38`,
`listing actions for 0 workers`. Recreating the container did not help; wiping its own
database volume did. But the real damage was downstream — the worker had been killed
mid-`COPY hts_base`, and `pg_stat_activity` showed that COPY still `active` in
`wait_event_type='Client'` **42 minutes later**, with nine `TRUNCATE`s stacked behind it on
locks. Nothing failed and nothing logged; runs simply never finished. Fixed by setting
`lock_timeout = 10s` on every parser connection (D-0046) — this parser holds exclusive locks
for seconds, so a ten-second wait means broken, not busy.

```
trade_programme   7 programmes labelling 308 of 624 subchapter III provisions
```

Parser run twice with no code change: all ten tables identical, `parse_issue` 848 both times.

**Agent notes.** Twice in this step I defended a design with a reason I had not checked — the
coverage/over-breadth correlation, and the "how many provisions" count as a teaching signal.
Both took under two minutes to test and both were wrong. The 3,988 ms figure is the same
failure one level down: a real measurement, of a query the application will never issue,
carried into the plan as if it were evidence. Measuring the wrong thing reads exactly like
measuring, which is what makes it worse than not measuring at all.

## 2026-08-26 — Part 3: the API skeleton, then the duty engine

**Step 1 — two services.** Replaced the Bun scaffold with FastAPI (`api/`) and Next.js
(`app/`). The split earns its keep in one line: Server Components fetch from `api:8000` over
the compose network, the browser goes through a rewrite in `next.config.ts`, so there is no
CORS and no API origin in a bundle. `API_URL` is deliberately not `NEXT_PUBLIC_`.

An hour of it went to memory. Docker was allocated 1,792 MiB, and `next dev`'s first compile
plus the worker's `uv sync` peak do not fit beside Postgres and Hatchet; the app container
printed `Killed` and nothing else, three times, before I stopped guessing and read
`settings-store.json`. At 3.8 GiB the whole stack runs at **1,504 MB** and all six services
coexist. Measured numbers are in `app/README.md` now, since a grader on a small VM will hit
exactly this.

I also wrote three tests for `routes/meta.py` and deleted them ten minutes later. They
asserted that a SQL string contains `ORDER BY 3 DESC` — which passes whether or not the query
is right. That is the failure mode CLAUDE.md names explicitly, written by me, in the same
session I had been congratulating myself for measuring things.

**Step 2 — the engine.** `api/duty/` is four files: the SQL, the three reach paths, the
arithmetic, and the assembly. Two design points survived contact with the data and one did
not.

Survived: `rate_kind` as an operator carries straight to the screen, so the formula on a page
is the schema's own shape rather than a re-derivation. And a specific duty with no quantity
reports as uncomputable, never as zero — a `$0` on a line charging 46.3¢/kg is the worst
possible wrong answer.

Did not survive: counting every matched provision into one total. `/duty/7208.51.00.30?country=RU`
reported **220%**, and the 200% was `9903.85.67`, *"Aluminum articles that are the product of
Russia"*, applied to a steel shipment. It matched on country alone because its goods
limitation is in prose. The mirror case is section 301 on Chinese steel, which arrives the
same way and must not be dropped. Split into an `origin_scoped` bucket with a floor and a
ceiling (D-0049):

```
steel from China    25%  ..  up to 50%
steel from Russia   20%  ..  up to 220%
steel from Germany  Free
```

**The measurement I got wrong twice.** D-0044 withdrew three derived tables after measuring
each one. Then the finished engine timed a real page:

```
GET /duty/8471.30.01.00?country=CN     2,034 ms
  COVERAGE   1,567.9 ms   <-- 88 provisions matched
  everything else, all nine queries, under 6 ms
```

D-0044 had measured coverage for **one** provision (4 ms). A duty page never asks for one.
Materialised it as `rule_coverage`, 2,825 rows, and the same page is **70 ms** (D-0047).

This is the third time this session the same mistake has appeared, and it is worth naming
precisely because each instance looked like diligence: the note-path GROUP BY over all 26,246
codes, the coverage-versus-over-breadth correlation I asserted without testing, and now
coverage measured at cardinality one. Measuring the wrong shape is indistinguishable from
measuring, right up until something real runs.

```
api tests        15 passed          workflows tests  115 passed
parser run twice, no code change: nine tables identical, parse_issue 848 both times
/duty response   6-9 ms typical, 70 ms worst measured
```

**Agent notes.** The engine found two defects the parser's own verification could not: the
Russian aluminium duty on steel, and the coverage query. Neither is visible from inside Part
2, because Part 2's question is "did every row get parsed" and this one is "is the answer
right". Building the consumer is the test.

**Step 3 — the three core pages.** Tailwind v4, native HTML for every interaction, no client
JavaScript anywhere. `<details>` does the collapsing, `<select>` does the country, a plain GET
form does the recalculation — all of which are keyboard- and screen-reader-correct without a
component library, and all of which keep the pages server-rendered. Radix and lucide were
considered and dropped for exactly that reason: they would have turned components that need no
JavaScript into client components, in an app whose whole claim is that the server computed the
answer.

Two structural changes fell out of building it:

- Country moved from a path segment to a query parameter. `/duty/7208.51.00.30/CN` cannot be
  changed by a form without JavaScript; `/duty/7208.51.00.30?country=CN` can, with a `<select>`
  and a submit button.
- `next.config.ts` became `next.config.mjs`. Next transpiles a `.ts` config at startup and a
  failure in that step surfaced as `ReferenceError: x is not defined` with no file and no line
  — fifteen minutes to find, and nothing to gain from the types.

The palette is four operator colours on a warm paper ground, and each is paired with a symbol
— `+` `→` `±` `?` — so the meaning survives without the colour. Type is IBM Plex in three
roles: serif for headings, sans for prose, mono for every code, rate and amount.

Verified by reading the rendered pages rather than by trusting the components:

```
/                                            200   0.63 s
/search?q=hot-rolled+steel+plate&country=CN  200   0.22 s   40 results
/duty/7208.51.00.30?country=CN&value=100000  200   0.38 s   25% .. up to 50%
/duty/2922.49.30.00?country=DE&value=50000   200   0.19 s   4 alternative reductions, by CAS
/duty/7208.51.00.30?country=RU&value=100000  200   0.25 s   Column 2, 20% .. up to 220%
/duty/7208.51.00.30?country=DE&value=100000  200   0.12 s   Free, nothing applies
/duty/9999.99.99.99                          404
tsc --noEmit                                 clean
```

**Agent notes.** I wrote user-facing copy with `--` in it, because the Python source around it
uses `--` for dashes, and shipped it to the page before noticing. Small, but it is the same
class as the SQL-substring tests: a convention from one context carried into another where it
is wrong, and only caught by looking at the actual output.

**Step 4 — the citation trail.** `/rule/[hts]` and `/note/[id]`, which turn the evidence on a
duty card from a claim into something a reader can open. Both endpoints answer in about 12 ms.

The provision page keeps the two directions of an exclusion apart — *this carves out* versus
*this is carved out by* — because they mean opposite things and a single list of neighbours
would say neither. It also states, on any provision whose note citation fell back to a parent,
that what is shown is wider than the provision is; the same sentence appears wherever that
fact is relevant, from one place in `reference/sources.py`.

The note page is where Chapter 99's strangest fact becomes visible: `9903.91.01` charges 25%
on "the subheadings enumerated in U.S. note 31(b)", and that list is 349 codes printed in a
PDF and nowhere else. The page shows the note as printed, its sibling subdivisions with a
count each, the codes in the order the note prints them, 200 at a time, and every provision
citing it. Codes that match no row in this revision are marked rather than dropped.

```
/rule/9903.91.01   200  0.14 s      /note/493          200  0.23 s
/rule/9903.88.01   200  0.09 s      /note/445?from=200 200  0.09 s
/rule/9999.99.99   404              /note/999999       404
tsc --noEmit clean   ·   api tests 15 passed
```

Every link on a duty page now resolves: the provision codes on each card, the exclusion
groups, and the note references in the evidence.

**Agent notes.** Two English plurals shipped wrong in one step — "1 trade programme reach this
code" and "1 provision take their scope" — both from writing `{n} thing{s}` and forgetting the
verb agrees too. Caught by reading the rendered text, not by types or tests, which is the same
lesson as the `--` dashes an hour earlier: the only check for prose is looking at it.

## 2026-08-26 — Part 3, Step 5: the two sentences no source wrote

**What this step is.** Two things the app wants are judgements, not facts: a plain-English
restatement of a provision, and a label saying what a prose U.S. note *does*. Both are
paraphrase, both are jobs a model does well, and both had to be added without weakening the
one claim this build rests on — that every figure on screen traces to a row.

**The decision that made it safe** is where the model call happens. Not at request time
(latency, cost, two readers told different things, no key means no app) and not in the parse
workflow (which would need network and a secret, exactly what its separation from Part 1
prevents). Offline, into a JSON file, committed: `workflows/build_interpretation.py` writes
`workflows/seed/*.json`, and `materialize` only loads them. So the parse run needs no key, two
parses of one release produce identical rows, and what a reviewer diffs is the model's actual
output rather than a claim about it. D-0050.

Each record carries the SHA-256 of the text it was written from and the loader recomputes it.
That is the whole answer to the brief's *"how do you keep it true when the tables under it
change?"* — and it is checkable rather than asserted:

```
poisoned one record's digest, invented a note the release does not contain, reloaded:
  {'roles': {'offered': 157, 'loaded': 155, 'stale': 2}}

  stale_note_role  ('us_note','III','13',None)   source text changed since this was written
  stale_note_role  ('us_note','III','999',None)  written for a record this release does not contain

restored from the real artifact:
  {'roles': {'offered': 157, 'loaded': 157, 'stale': 0}}
```

The 157/157 with zero stale is also the determinism check passing: the artifacts were built
against one parse, the database was then wiped by `./setup.sh` and rebuilt from the payloads,
and every digest still matched.

**Measured reliability of the model, note pass.** 167 notes, **157 kept, 10 rejected by the
checks in code** — not by reading them:

```
us_note|III|32|a   introduces 1.36, 25, 28, absent from the source
us_note|III|31|e   introduces 31
us_note|XIX|3      introduces 2025          us_note|XV|6|a   introduces 2024
us_note|XIX|4|a    introduces 2027          us_note|XV|7|a   introduces 2024
us_note|XIX|4|b    introduces 2027          us_note|XV|7|b   introduces 2024
us_note|XVIII|3    introduces 2020
us_note|XV|9       not one of the notes asked about
```

Six of the ten supplied a year the note never states — the model completing "January 1" from
context, which is the most plausible-looking way to be wrong about a tariff. One invented three
numbers outright. One answered about a note that was not in the batch. **All ten read
perfectly.** Nine lines of deterministic checking caught 6% of answers that prose review would
not have.

The rule pass, run afterwards: **3,098 provisions, 3,060 kept, 38 rejected, 0 batches
lost**, across 124 batches with two retries that both succeeded. All 38 rejections turned
out to be defects in my check rather than in the answers — see the entry below.

**Two prompt defects found by reading the output, not by any test.**

The first eight summaries came back naming the goods and saying nothing about the duty — which
is the half a reader came for. Cause: the rate is not in `full_description`, it is a column
beside it, so the model could not have said. Fixed by sending `rate_text` and the operator
alongside, and by explaining in the prompt what `additive` and `no_change` mean.

The second is more interesting. `9903.91.01` reads *"as provided for in subdivision (b) of
U.S. note 31"*, and the summary came back as *"Goods listed in U.S. note 31"*. Dropping the
subdivision widens the provision from 349 codes to 412 — **the same defect the parser had, and
D-0037 exists to record fixing it.** A paraphrase can reintroduce a bug the schema already
solved. Fixed with an explicit constraint, verified on five provisions that cite subdivisions:

```
9903.88.01 — Chinese articles listed in U.S. note 20(a) and 20(b): 25% on top of the normal duty.
9903.91.01 — Chinese articles listed in U.S. note 31(b): 25% on top of the normal duty.
9903.91.06 — Chinese articles listed in U.S. note 31(g): 25% on top of the normal duty.
```

**Two transports, because this machine has no API key.** `env`, `workflows/.env` and the
Claude settings all lack one, so the SDK path could not have been run here and the artifacts
would have shipped ungenerated. `workflows/llm.py` picks the Anthropic SDK when
`ANTHROPIC_API_KEY` is set and shells out to `claude -p --output-format json` otherwise
(D-0052). Everything in `seed/` was built through the CLI; **the API transport is written and
typed but has not produced a row**, which is stated in the decision rather than left for a
reader to find. One trap earned a test: the CLI reports a model-side failure *in its JSON body
with exit code 0*, so a return-code check alone would have written "I cannot help with that"
into the artifact as a summary.

**What the note labels turned out to be worth.** The distribution is not what "we could not
parse this note" implies:

```
condition 73 · exclusion_list 31 · list_of_goods 28 · administrative 16 · definition 9
```

Only 28 of 157 are lists the parser arguably should have found. The other 129 have no code
list to extract, and the app can now say which is which. The best case is `9903.88.04` — the
Section 301 provision that matches Chinese steel on country alone, with no code evidence at
all. Its card now reads *"Lists goods · machine-read: Lists categories of Chinese products
subject to additional 25% duty with exclusions"*, which is exactly why it sits in the
origin-scoped bucket rather than in the total (D-0049).

**A defect I introduced and caught in the same hour.** `load_interpretation` did not clear its
own stage's `parse_issue` rows before inserting, which the other four loaders all do. A second
run of the same release would have doubled this stage's residue — in the one table whose whole
job is to be trustworthy about what failed. Found while restoring the database after the
staleness test above, because the poisoned run's two rows were still there. Fixed.

**Schema.** `rule_summary` and `note_role`, both keyed to their subject with the digest, model
and prompt version beside the sentence. `parse_issue.stage` gained `materialize`.
`note_role.source_truncated` records that the longest note bodies (912,964 characters at the
extreme) were sent as their first 6,000 — a label written from an eighth of a note is a weaker
claim than one written from all of it, and the difference is on screen rather than assumed.

Adding `rule_summary` made the parser fail loudly on the next run:

```
FeatureNotSupported: cannot truncate a table referenced in a foreign key constraint
DETAIL:  Table "rule_summary" references "rule".
```

That is D-0025 working as designed, for the second time — a derived table nobody registered
cannot silently survive a run.

**Verification.**

```
setup.sh + parse from empty, no artifacts present:   ran clean, app renders verbatim text
  → "a missing artifact is a supported state" is exercised, not just claimed
parse with note_roles.json present:                  157 loaded, 0 stale
workflows tests                                      123 passed (8 new)
api tests                                            15 passed
tsc --noEmit                                         clean
/duty/7208.51.00.30?country=DE   Free,  2 unknowns   (control: nothing applies)
/duty/7208.51.00.30?country=CN   25% .. up to 50%,  4 unknowns
/duty/7208.51.00.30?country=RU   Column 2 20% .. up to 220%
/duty/2922.49.30.00?country=DE   10%,  4 alternative reductions,  8 unknowns
```

**Agent notes.** I piped both build runs through `| tail -30`, which buffers the whole stream —
so for the fifty minutes they ran there was no interim output at all, and no way to see a
batch retrying. The progress printer I wrote was useless for exactly the case it existed for.
Second, I wrote `2,940` as the `rule_summary` count into `SCHEMA.md` before the build had
finished, as a placeholder. A placeholder that looks like a measurement is worse than a blank,
and it is the same failure as measuring the wrong query: it reads as evidence.

## 2026-08-26 — Removing the machine-written layer, and what it cost to learn

The entry above stands as written; this one records what happened to what it describes.
The two model-written tables are gone. Not because they were wrong — because they restated
what the page had already said.

**The audit that preceded the decision.** Before removing anything I went looking for
evidence the summaries were unreliable, expecting to find some. I did not:

```
3,094 summaries checked against the rate_kind operator each one describes:
  free / additive / replace     zero cross-contamination between the three
  135 'none'-rate summaries matching /no duty/
     → sampled: "no duty rate specified", which is correct for a row stating no rate
  2 'no_change' summaries saying "duty-free"
     → 9903.01.04 reads "Articles that are entered free of duty under general note 11"
       the sentence is faithful to the provision
```

That matters more than it looks. I had a hypothesis — *the number check validates numbers,
not claims, so wrong claims must be getting through* — and I nearly reported it as a finding
before running it. It did not hold. **The argument for removal is redundancy, and saying so
plainly is worth more than a stronger-sounding argument that the evidence does not support.**

**The redundancy, concretely.** A duty card already carries:

```
9903.91.01    + 25%    [Section 301 — China · editorial]
Why this is in your answer
  · The provision points at U.S. note 31(b), whose list includes 7208.51
  · The provision names China as the country of origin
```

and then said: *"Chinese articles listed in U.S. note 31(b): 25% on top of the normal
duty."* The formula strip, the programme chip and the evidence lines had done the work
already. An hour of wall clock and $6.50 bought a fourth telling.

**What the hour actually taught**, kept because it would otherwise have to be relearned:

```
one CLI call, 25 provisions:
  wall            35.3s
  ttft            27.6s      ← 80% of the call is before the first token
  output          3,898 tokens, of which 2,862 are thinking
  cache_create    15,421 every single call — a fresh process never reads a warm cache
  cost            $0.0520  ×124 batches ≈ $6.50, not the ~$1 estimated
```

Two flags were measured against that baseline. `--effort low` came back at **14.3 s** with
936 thinking tokens — 2.5× faster — but its one sampled reply did not begin with the JSON
array, so it was not adopted mid-run. Replacing Claude Code's system prompt with a two-line
one was **worse, not better**: 90.8 s and 9,626 thinking tokens. The scaffolding that costs
15,000 cached tokens is also what keeps the model terse.

**The check that was wrong in the safe direction.** The first version compared numbers by
their *printed* form, so `5.0%` → `5%`, `1,000` → `1000` and `$20.00` → `$20` all read as
fabrications: **38 correct summaries rejected**. Comparing by value recovered 34. A regex
anchored on a leading digit never saw the schedule's `.4mm`, which recovered one more. The
last 4 were the model rewriting `6-1/2 digits` as `6.5` — arithmetic the check cannot verify,
correctly refused. Failing conservative is right; failing conservative *and unmeasured* meant
38 rows were silently missing and I only found out by counting the artifact against the table.

**Two defects I shipped and caught within the hour.** `load_interpretation` did not clear its
own stage's `parse_issue` rows the way the other four loaders do, so a second run of the same
release would have doubled this stage's residue — in the one table whose job is to be
trustworthy about failure. And `--only` **overwrote** the artifact instead of merging into it,
which made the flag worse than useless: it looked like a repair and was a deletion of 3,056
records. Both fixed, both with tests, and both now deleted along with the feature.

**The removal itself.** `./cleanup.sh` then `./setup.sh` rather than hand-dropping the two
tables — `setup.sh` only drops what it creates, so a *removed* table survives a schema reset
and would have lingered in my database while being absent from a grader's. Worth knowing:
the reset is a reset of the file, not of the database.

Verified from an empty database afterwards:

```
14 tables · parse from empty ran clean
hts_base 26,246 · rule 3,098 · note 345 · rule_note 977 · note_subheading 48,053
rule_base_match 16,958 · note_base_match 136,325 · rule_coverage 2,825 · parse_issue 848
workflows tests 115 passed   api tests 15 passed   tsc --noEmit clean

/                                            200  0.09s
/search?q=hot-rolled+steel+plate&country=CN  200  0.23s
/duty/7208.51.00.30?country=CN&value=100000  200  0.16s   25% .. up to 50%  ·  $25,000
/duty/2922.49.30.00?country=DE&value=50000   200  0.24s
/duty/7208.51.00.30?country=DE               200  0.23s   Free, nothing applies
/duty/7208.51.00.30?country=RU               200  0.22s   Column 2, 20% .. up to 220%
/rule/9903.91.01  200  0.21s      /note/148        200  1.20s (cold) / 0.15s
/rule/9999.99.99  404             /note/999999     404      /duty/9999.99.99.99  404
```

`grep -riE 'anthropic|openai|claude|llm|gpt|embedding' api/ app/src` returns nothing, and
the API's runtime dependencies are FastAPI, uvicorn, psycopg and pycountry. The product
contains no model output of any kind.

**Agent notes.** The honest summary of my part in this: I proposed the feature, built it,
and it worked — and it was still the wrong thing to build, because I did not ask what the
page already said before adding a fourth way of saying it. The user's read of it as marginal
was correct and mine was not. Second, when asked to justify keeping or dropping it, my first
instinct was to reach for a correctness argument; the audit refuted it, and reporting that
refutation is the only reason the redundancy argument is trustworthy.

## 2026-08-26 — A reported wrong answer, and what it was actually caused by

A user brought a case: men's knitted cotton T-shirts from China, `6109.10.00.12`. Base 16.5%,
Section 301 List 4A +7.5%. The app said **17.5%**. Reproduced immediately:

```
BASE   16.5%                      TOTAL 17.5%
  9903.05.31  add      +12.5%     IEEPA reciprocal, China, via note 52
  9903.05.39  replace  10%        ← replaced the 16.5% base
  9903.88.15  add      +7.5%      Section 301 List 4A, found correctly
```

Their diagnosis was that the parser is too rigid and needs a model to check eligibility. That
turned out to be the wrong reading of a real bug, and the truth is worse and cheaper to fix.

**The parser had already caught it.** `9903.05.39` is not an FTA or quota rate — it is EU-only:

```
"articles the product of a member state of the European Union, with an ad valorem
 (or ad valorem equivalent) rate of duty under column 1 less than 10 percent"
```

and `parse_issue` held, for exactly the three provisions in that family:

```
9903.05.38 / .39 / .97   keys on origin but names no country:
                         'a member state of the European Union'
```

`countries.py` even carried `NOT_A_COUNTRY = {"european union"}` with a comment saying a NULL
code "is the right answer rather than a failure". It was. **The app then read the resulting
silence as permission** — its veto was "no `rule_country` rows means no origin restriction" —
and applied an EU provision to a Chinese shipment. The honesty table did its job and nothing
downstream read it.

That is the lesson worth keeping from this whole session: **recording a limitation is only
half of handling it.** `parse_issue` has been treated as a report for humans; here it held a
fact the query needed.

**The blast radius was measured, not guessed.** 36 `unnamed_country` issues, six phrase groups,
and the kind conflates two opposite meanings:

```
'any country'                                 18   universal   -> must pass the veto
'any country or area including the US'         9   universal   -> must pass
'a member state of the European Union'         3   a bloc      -> 27 named origins
'any country not exempt under note 41(c)'      3   bounded     -> must not pass
'any country identified in general note 3(b)'  2   bounded     -> must not pass
'any country determined by CBP ... transshipped' 1 bounded     -> must not pass
```

Failing closed on all 36 would have dropped the reciprocal baseline from every query. Failing
open, which is what shipped, applied EU rates to everyone.

**Two fixes, both deterministic, neither needing a model.** `rule.origin_scope` with four
values (D-0056), and `rule_condition` for the eligibility terms provisions state about the base
rate (D-0057). Results:

```
6109.10.00.12  CN   17.5%  ->  36.5%      (16.5 base + 12.5 + 7.5)
6109.10.00.12  DE   10%    ->  16.5%      (the EU provision was wrong for EU goods too)
rule_country   422   ->  503              (+81, the EU expanded into 27 members x 3)
rule_condition   -   ->   31
```

The German case is the one worth noticing: the provision was wrong even for the origin it was
written for, because 16.5% is not "less than 10 percent". Fixing origin alone would have left
that understatement in place.

**A wrong hypothesis I checked before acting on it.** Note 52(a) says headings
9903.05.20–9903.05.84 "impose **additional** ad valorem rates of duty", so I suspected the
parser had misread `9903.05.39`'s bare `10%` as `replace` when it should be additive. It had
not. The complementary heading settles it:

```
9903.05.38  no_change  "The duty provided in the applicable subheading"   column 1 >= 10%
9903.05.39  replace    "10%"                                             column 1 <  10%
```

That is a "top up to 10%" structure and `replace` is right. Two provisions, partitioning the
space on a condition — which is the second finding: **the schedule frequently prevents a
stacking ambiguity by making provisions mutually exclusive**, and reading the condition is what
reproduces that here.

**The stacking question, measured.** A user asked what decides the order when a `replace` and an
`add` both apply, since `replace → Free` then `+5%` and the reverse give different answers. The
honest answer is that nothing decides it: `combine` applies layers in the order `APPLICABLE`
returns them, which is `ORDER BY r.hts`. The docstring says "in the order they should be read"
and no caller ever made that decision. Swept 2,160 real queries:

```
queries run                    2,160
with a replace in the total      531
replace AND add in one total     346    <- 16%, order-dependent
```

and worse, a query can carry **two replaces**: `9903.45.01` (14%, in-quota) and `9903.45.02`
(30%, over-quota) both reach `8450.20.00.10`, and the higher heading silently overwrites the
lower. Those two are a tariff-rate quota pair — which one applies depends on how much has been
imported this year, a number in no source here. Recorded as **P-l**, undecided, rather than
patched with a guess.

**What the reported case still does not agree with.** The user expected 24.0%; the fixed answer
is 36.5%. The difference is `9903.05.31`, +12.5% IEEPA reciprocal on China, which note 52(a)
states is additional and stacks. It carries no date, no status, and note 52 does not contain the
word "suspend". So from these three sources it applies. The 24.0% presumably reflects a
suspension published as an executive order or a CBP message — which is precisely what the
"What this can't tell you" panel exists to point at, and is not a defect in the reading.

**Verification.**

```
setup.sh + parse from empty:  rule_country 503 · rule_condition 31 · parse_issue 848
origin_scope   none 2,667 · named 407 · any 18 · unresolved 6
workflows tests 126 passed (11 new)   api tests 15 passed   tsc --noEmit clean
/duty/6109.10.00.12?country=CN   36.5%  ceiling 61.5%
/duty/6109.10.00.12?country=DE   16.5%  · 9903.05.39 shown under "Ruled out by their own
                                          wording" with the sentence that ruled it out
/duty/7208.51.00.30?country=CN   25% .. up to 50%   (unchanged)
/duty/7208.51.00.30?country=DE   Free               (unchanged)
```

**Agent notes.** I introduced a bug inside the fix and caught it by reading a count: expanding
the EU bloc, I appended ISO **codes** to a list of country **names**, so 81 rows each raised
"no ISO 3166 code for 'AT'" and `parse_issue` jumped 39 → 120. Nothing failed; the number was
the only symptom. Second, I nearly reported the `replace`/`additive` operator as a fourth bug
on the strength of one sentence in note 52(a), and the complementary heading refuted it — the
same shape as the audit two entries above, where a hypothesis I liked did not survive being
checked. Third, after adding two new buckets to the API I had to remember to render them;
shipping data the UI ignores is the exact failure this entry is about.

## 2026-08-26 — The schedule does state the stacking rule, and I had said it did not

P-l was open because `combine` applied provisions in `ORDER BY r.hts` — an incidental sort that
changed the answer. The user asked the right question: **what do the rules actually say?**

They say a lot, and the assumption line printed on every duty page said the opposite:

> "Stacking order is set by CBP in its filing instructions, not by the tariff schedule, so it
> is not in this data."

That is wrong about the arithmetic. It is right only about which 9903 line goes on which entry
line. The schedule settles the arithmetic in three layers, all of them in the payload we
already had:

```
U.S. note 1 to subchapter III   "subject to duty at the rate set forth herein IN LIEU OF the
                                 rate provided therefor in chapters 1 to 98"
U.S. note 1 to subchapter I     "CUMULATIVE duties which apply IN ADDITION TO the duties, if
                                 any, otherwise imposed"
31 notes override note 1        "NOTWITHSTANDING U.S. note 1 to this subchapter ... shall ALSO
                                 be subject to the general rates of duty imposed under
                                 subheadings in chapters 1 to 97"
```

**The order is then derived, not chosen.** Each operator names its own operand: an *in lieu*
rate stands in for the chapters 1–98 rate — never for another Chapter 99 duty — and a
cumulative rate applies to "the duties otherwise imposed", which includes it. Replacements
first, additions on top, and addition commutes. `rule.cumulation` records which a provision is
(798 cumulative, 619 in lieu, 1,681 unstated), and `combine` sorts by operator.

```
sampled 2,160 real queries
  order-dependent before   346
  order-dependent after      0
  reported as a range now   45   (two provisions claiming the same base)
```

**The cross-check found a real defect within minutes of existing, and it was mine.** `rate_kind`
is read from the rate text; `cumulation` from the note. 80 disagreed.

62 were rates printed as *"The duty provided in the applicable subheading + 25%"* under an
`in_lieu` default. Not a contradiction — note 1 says "unless the context requires otherwise",
and a rate naming the base **is** that context. The check was narrowed to ignore them, which is
itself worth noting: a check that fires on correct rows trains you to ignore it.

The other 18 are bare rates governed by a note that says the duties are cumulative, and they
were being applied as replacements:

```
9903.05.39   "10%"            U.S. note 52(a): the heading imposes an ADDITIONAL duty
9903.02.xx   "15%"      x5    U.S. note 2
9903.40.05   "25%"      x2    U.S. note 14(a): "cumulative duties which apply in addition to"
9901.00.50   "14.27c/liter"   U.S. note 1 to subchapter I
```

**This reverses what I told the user three hours earlier.** Investigating the same provision I
had suspected `9903.05.39`'s bare `10%` of being misread as `replace`, checked its
complementary heading, found

```
9903.05.38  no_change  "The duty provided in the applicable subheading"   column 1 >= 10%
9903.05.39  replace    "10%"                                             column 1 <  10%
```

and concluded the parser was right — a "top up to 10%" structure. Read with note 52(a) the same
pair is "+0% for high-tariff goods, +10% for low-tariff goods", which fits the shape exactly as
well. **The pair could not settle it; the note could, and I did not go and read the note.** I
had the right suspicion, checked it against the weaker evidence, and reported the wrong
conclusion with confidence. Corrected in D-0058, which says so.

**Two provisions in lieu of the same base rate** is the one case the schedule genuinely leaves
open. `9903.45.01` (14%, in-quota) and `9903.45.02` (30%, over-quota) are a tariff-rate quota's
two halves, separated by how much has been imported this year. Lowest stays in the figure, the
rest go to the ceiling with an unknown — D-0049's floor-and-ceiling mechanism, second use.

`rate_kind` was left alone. It is the fact of what the rate text says (D-0015); the operator is
composed in `duty/compute.py` from both readings. Overwriting the fact layer with the
interpretation would have made the disagreement unfindable next time.

**Verification.**

```
setup.sh + parse from empty, twice: identical counts, 15 tables
cumulation   798 cumulative · 619 in_lieu · 1,681 unstated
parse_issue  522  (resolve: 277 subdivision_not_segmented, 226 unresolved_code,
                   18 rate_silent_note_decides, 1 unresolved_note)
workflows 133 passed (7 new)   api 18 passed (3 new)   tsc --noEmit clean

6109.10.00.12  CN   36.5%  ceiling 61.5%
6109.10.00.12  DE   16.5%  · 9903.05.39 ruled out by its own condition
8450.20.00.10  CN   102.5% ceiling 172.5% · 9903.45.01/.02 shown as competing replacements
7208.51.00.30  CN   25% .. up to 50%   (unchanged)
```

**Agent notes.** Two corrections in one session, both to claims I had made confidently: the
"stacking is not in this data" line I had written into `compute.py` and onto every page, and the
`9903.05.39` operator reading. Both came from stopping at the first piece of evidence that fit.
The pattern is specific enough to name: **I checked the nearest artifact — a sibling heading, a
rate string — when the governing document was one query away.**

## 2026-08-26 — Asked how accurate the rates are, and what could honestly be answered

The question has no direct answer here: **there is no set of correct duty rates in this
project**, and building one means doing customs brokerage. Any accuracy percentage I produced
would have been invented. So I said that first, then built what can actually be measured.

**Invariants.** `api/audit.py` — nine statements true of every correct answer, swept over
`codes × origins`. It found two defects in the first run, both mine, both in the ceiling:

```
0406.20.15.00 / JP   floor 200%   ceiling  40%
2401.20.87.30 / JP   floor 350%   ceiling  40%
```

Replacements are mutually exclusive (D-0058), so the uncertain ones are **alternatives to**
whatever already stands in for the base, not extra duties to add. My first version appended
them all and let the sort decide; the second took the highest and still lowered the answer
where nothing certain had replaced the base. Neither was reachable by reading the code — both
needed the sweep.

```
20,000 queries (2,000 codes x 10 origins)     0 violations
```

**Ground truth, where it exists.** The payload is the one thing that can be checked against:
14,467 base rates are stated on their own row rather than inherited, and **all 14,467 reproduce
their payload string exactly**. That is parser fidelity — the rate was read right — not duty
correctness, and the entry says so.

That check also found a defect, and it was visible on screen:

```
0105.11.00  "0.9¢ each"  ->  0.009000000000000001
duty page:  total expression: 7.5% + $0.009000000000000001/each
```

`float(cents) / 100` — 46.3/100 in binary is 0.46299999999999997, and the `numeric` column kept
every digit. 625 rows. Fixed by parsing as `Decimal` (D-0060). **No money was ever wrong**: the
error is 3e-17 per unit and would need 1.7e14 units to move a cent. It was worth fixing because
a stored rate that is not the printed rate is a claim this schema should not have to qualify —
and because two rate tests could then drop `pytest.approx` and assert the printed value, which
is the better test. `approx` had been accommodating the defect.

**What the audit reports instead of accuracy:**

```
37.4%  goods described in prose      37.3%  fully determined
17.5%  exclusions may apply           5.0%  origin set not listable
 1.6%  competing replacements         1.2%  alternative reductions
```

Just over a third of answers close on these three sources alone. That is not a defect rate; it
is the proportion of the question this data can settle, and every other category is named on
the page with somewhere to go.

**The limit of all of it, stated because it is easy to oversell.** Invariants prove
consistency, not correctness: a rule applied wrongly but consistently passes all nine. The
origin-scoped bucket is 37% of answers and the audit only checks that those are kept out of the
figure — never that keeping them out was right.

**Agent notes.** My first pass at measuring the payload compared a `Decimal` from the database
against a `float` from the parser, reported **4,151 mismatches**, and printed pairs that looked
identical — `stored ('6.8%',replace,6.8) vs payload ('6.8%',replace,6.8)`. I nearly reported a
28% parser failure rate. The tell was that the printed values matched; the fields I compared
but did not print were where the difference lived. **A check that fails has to be checked
before it is believed** — and printing less than you compare is how you end up unable to.

## 2026-08-27 — UI review, and the first of its fixes

**A read-through of the rendered app, not the source.** Rendered every page type to plain
text (`/`, `/rule`, `/note`, `/duty`, `/search`) including the awkward rows — `rate_kind`
`prose`, `scope` `unknown`, `status` `suspended` and `terminated` — because the source reads
better than the page does. Findings fell into four groups: implementation vocabulary printed
to users, monospace no longer meaning "identifier", seven real defects, and two palette tokens
below WCAG AA. The full list is in the review; this entry records only what was acted on.

**Branch `ui-polish`, off `46efd7d`.** The session's opening git snapshot was stale — two
commits (`cea503d`, `46efd7d`) landed while the review was running, changing `compute.py`,
`explain.py` and `sources.py` among others. Caught it when `compute.py` on disk did not match
the `ASSUMPTION` text the browser had just shown me. **Re-verified every finding against HEAD
before touching anything**; all of them still reproduced, and the running containers had by
then picked up the new code, so the rendered evidence below is from current source.

**Three defects fixed, all of which made the page state something untrue.**

- `/duty/3808.92.15.00?country=DE` drew **34 `→ Free` cells** between the base and the `=`,
  then printed `= 6.5%`. `combine()` never receives `reductions`, so every one of those cells
  was an operand the total had not used. Now one `± 0 · 34 duty reductions` cell. Verified by
  re-render: `6.5% (Column 1 General) ± 0 (34 duty reductions) = 6.5%`.
- The caption said `Assumes every duty listed applies at once`; the heading below said
  `These are alternatives, not a stack`. `assumption(reductions)` now appends the alternatives
  sentence only when the query has any — confirmed present on the 34-reduction page and absent
  on `/duty/7208.51.00.30?country=DE`, which has none.
- `UNKNOWNS["alternatives"]` told every reader "four provisions cite 2922.49.30". Test written
  first, failed with `assert {'alternatives': ['2922.49']} == {}`, then the copy was made
  generic.

**Verified:** `cd api && uv run pytest` → **21 passed**. `docker compose exec -T app npx tsc
--noEmit` → clean, exit 0. The three worked examples on the home page re-rendered and read
correctly, the arithmetic now legible on the second one: `6.5% + 10% + 10% + 10% = 36.5%`,
which was previously interrupted by four `→ Free` cells.

**Not yet done, and named so it is not mistaken for finished:** the `rate_kind`/`scope`/
`status` enum leakage on `/rule`, the five `D-00xx` decision IDs printed in `UNKNOWNS` prose,
the monospace and vocabulary work, duplicate `citing` rows and the React key collision they
cause, mid-word truncation, per-page `<title>`, and the `text-faint` (3.27:1) and
`border-rule-strong` (1.82:1) contrast failures.

**Agent note.** The stale-snapshot catch was luck, not method: I noticed only because I had
quoted the old `ASSUMPTION` verbatim in the review and the string had changed under me. Had the
edit been to a line I had not quoted, I would have written the fix against a file that no longer
existed. Re-reading HEAD before editing is cheap; assuming a session-start snapshot still holds
is not.

## 2026-08-27 — "1 trade programme reaches this code" — asked what it meant, and it meant less

A search result carried that badge. The question was what it means; the answer was that it
promised more than it computed. It counted trade-action families with a Chapter 99 provision
touching the code, and applied **none** of the three filters the duty page applies:

```
origin        /search took no country parameter at all — the selector only built the link.
              A German shipment was told "1 trade programme reaches this code", and the
              programme was Section 301 — China.
effectivity   terminated provisions counted.
conditions    a provision its own sentence rules out (D-0057) counted.
```

Plus a fourth: pasting a code hit a branch with `0 AS programmes` hard-coded, so the same code
answered two ways depending on how it was found.

The origin one is **D-0056 in a second place** — something scoped to an origin, presented as
though it applied to everyone. Fixed there in the duty query a day earlier and left standing
here, because nothing compared the two screens.

Fixed by making one subquery serve all three search paths, returning labels rather than a count
(*"Section 301 — China"* says something; *"1 trade programme"* does not), filtered the same four
ways — and marked `editorial`, which D-0045 requires the moment a badge names a specific
attribution rather than a generic category.

**The cross-check earned itself twice in one sitting.** I added an audit invariant comparing the
badge against the duty page, and it immediately reported 682 violations over 4,000 queries. My
first diagnosis — the missing condition filter — was a guess; I added the filter and the number
did not move. Only then did I go and look at the actual failing case:

```
8412.90.90.35 / CN  ->  five 9903.02 provisions pass the badge filter, all rate_kind='no_change'
```

Exclusions. The duty page *does* show them, in a bucket whose objects carry no programme label,
so my invariant was comparing against the wrong set — and the product answer was that an
exclusion should not put its trade action's name on a code at all, since it means the opposite.
Excluding `no_change` took it to 407, all of them the countryless case, which is a deliberate
difference between the two screens rather than a defect.

```
15,000 queries, origin given:  0 badge disagreements
```

**A worse thing the audit caught.** Rewriting the tail of `queries.py` to add the shared
subquery, I deleted `CONDITIONS` — the query the whole duty engine needs. **All 24 API unit
tests passed.** `/search` worked. The duty endpoint was returning a 500 to anything that asked,
and the only thing that noticed was the audit's first run. Unit tests over pure functions do
not touch the database; the audit is the only check here that runs the real thing end to end.

**Agent notes.** Two of my own patterns repeated, both already named in this journal.

First, I wrote three tests asserting **SQL substrings** — `assert "r.origin_scope <> 'named'" in
queries.PROGRAMMES` — the exact anti-pattern CLAUDE.md forbids and that I deleted a batch of
earlier in this same project. Deleted again, and replaced with the audit cross-check, which is
what the behaviour actually deserved.

Second, on hitting 682 violations I reached for a plausible cause and implemented the fix
before checking whether it was the cause. That is the "checked the nearest artifact when the
governing evidence was one query away" pattern from yesterday, applied to my own code this
time. The query that settled it took twenty seconds.
