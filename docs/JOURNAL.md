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
