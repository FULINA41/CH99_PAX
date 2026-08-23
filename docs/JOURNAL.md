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
