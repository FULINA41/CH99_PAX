# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A take-home exercise from Pax AI: turn US tariff data (HTSUS **Chapter 99**) into a
structured database and build an app on top of it. The repo currently contains
**only scaffolding** — the three deliverables are not written yet.

- **Part 1 — Scraper** (`parts/PART1_SCRAPER.md`): a Hatchet workflow that fetches
  three USITC sources and lands the raw payloads in `data/`.
- **Part 2 — Parser** (`parts/PART2_PARSER.md`): a *separate* Hatchet workflow that
  reads those payloads (no network) and structures them into Postgres.
- **Part 3 — App** (`parts/PART3_APP.md`): a full-stack app that explains Chapter 99
  to a novice. Open-ended by design.

Read `README.md` for the domain background, `AGENTS.md` for infrastructure detail,
and the three `parts/*.md` files for the actual requirements. `SUBMISSION.md` is the
graded write-up and must be filled in as work progresses, not at the end.

## Conventions

- **All code comments, docstrings, commit messages, and Markdown are written in
  English**, even when the conversation is in another language.
- Every part must be runnable **on its own**, in order, from a fresh clone and an
  empty database, with no code edits and no hand-applied SQL. Re-running any part
  must be safe (idempotent).
- Hatchet is **required** for Parts 1 and 2 — orchestration is explicitly being
  assessed. Do not replace it with a plain script.
- When a domain interpretation is ambiguous, record the assumption in
  `SUBMISSION.md` and move on.
- **Docstrings go on the entry points, in Google style** — a summary line, then `Args:` /
  `Returns:` / `Raises:` sections where they carry something the signature does not. An
  entry point is what a caller outside this codebase reaches for: `fetch_source`,
  `current_release`, `record_fetch`. Everything else — helpers, dataclass methods,
  plumbing that only exists to serve an entry point — gets none, whether or not another
  module imports it. Where such a function needs explaining, the explanation is a comment
  on the line that earns it, and it says *why*, since *what* is already in the code.
- **Tests assert behaviour, not existence.** A test earns its place by pinning down what
  the code does under one named condition — "an interrupted write leaves nothing at the
  target path", "a 404 is not retried". Do not write tests that check a value is non-empty,
  that a key is present, or that a function returns the type it declares: they pass whether
  or not the behaviour is correct. Each test should read as one sentence, with one reason
  to fail.
- Every technical decision gets written down as it is made — see **Decision log** below.
  This is not optional bookkeeping; it is how `SUBMISSION.md` gets written.
- **Commit subjects are one line, ten words or fewer, and there is no body.** The reasoning
  belongs in `docs/DECISIONS.md` and `docs/JOURNAL.md`, where it is searchable and can be
  superseded; a commit message cannot be corrected without rewriting history, which this
  submission forbids. Keep the `Co-Authored-By` trailer.

## Working with the user

**Say what you are about to do, and why, before doing it.** One or two sentences ahead of
the action — what the step is and what it buys — not a plan dump, and not a narration
after the fact. This applies to anything that changes state: writing or editing files,
running commands that touch Docker, the database, or git, and committing. Reads and
searches need no announcement.

**Report what actually happened when the task ends.** Name the files that changed, the
commands that ran, and their real output. Separate what is finished from what is still
open, and say plainly when something was skipped, failed, or left half-done — the journal
convention below is worthless if the reporting above it is optimistic.

**Be brief.** Report in as few words as the facts need. Lead with the result, name what
changed, give the evidence for anything claimed to work — then stop. No recaps of what was
already agreed, no restating a decision's rationale that is already in `DECISIONS.md`, no
summary paragraph after a table that says what the table said. This applies to documents
too: a section that repeats another section is a maintenance cost, not thoroughness.

**Committing needs approval, and so does starting the next step.** When executing a plan,
finish the step, run its verification, and report — then stop. Do not commit and do not
begin the following step until the user approves. Approval covers both: the commit and the
step after it. A commit made before review has to be reverted or amended to change, and
amending is not available here — the submission requires history to stand as written.

Write both in the user's language; code, comments, and committed documents stay in English.

## Decision log (required)

Two append-only files under `docs/`. Both are written in English and are part of the
submission — the grader reads them, and they are what `SUBMISSION.md` is assembled from
at the end.

| File | Holds | Feeds |
| --- | --- | --- |
| `docs/DECISIONS.md` | One entry per technical or design decision, ADR-lite | `SUBMISSION.md` §2 data model, §5 assumptions |
| `docs/JOURNAL.md` | Chronological work log: what was attempted, what broke, what was verified, where the AI agent helped or misled | `SUBMISSION.md` §4 next week, §6 AI usage, and the demo video |

**Write an entry as part of the step, not afterwards.** A decision recorded a day later
loses the alternatives that were rejected, which is the part worth keeping.

**What counts as a decision worth logging** — anything a reviewer could reasonably ask
"why did you do it that way?" about:

- schema shape: a table, a column, a type, a constraint, something deliberately *not* normalized
- how a piece of prose is parsed, and what the parser does when it does not match
- idempotency and failure strategy: what the retry key is, what a partial run leaves behind
- workflow boundaries: what is one task vs. several, what is retried vs. failed
- what gets precomputed for Part 3, and how it is kept true when the tables under it change
- a domain interpretation chosen where the source data was ambiguous
- anything knowingly shipped incomplete, shortcut, or unverified

Skip the mechanical: renaming a variable, formatting, a dependency bump with no tradeoff.

### `docs/DECISIONS.md` entry format

```markdown
## D-0007 — Short imperative title
**Date:** 2026-08-21 · **Area:** parser · **Status:** accepted | superseded by D-00xx

**Context.** What forced the decision. Cite evidence — a row count, a sample record,
an error message — not an impression.

**Options.** The alternatives actually considered, one line each.

**Decision.** What was chosen.

**Tradeoff.** What this costs, and what would make it wrong.

**Feeds.** SUBMISSION.md §2
```

Number entries sequentially and never rewrite one. A decision that turns out wrong gets a
new entry that supersedes it — the reversal is itself evidence of engineering judgment.

### `docs/JOURNAL.md` entry format

One dated section per working session, appended to. Record verification results as
*outcomes with output*, not claims: "ran the parser twice, row counts identical (3,336)"
rather than "idempotency works". Note where a coding agent produced something wrong or
unverified the moment it happens — that observation is explicitly requested in the
submission and cannot be reconstructed later.

## Commands

```bash
./dev.sh        # whole stack (db + hatchet + worker + app) with hot reload, foreground
./setup.sh      # apply db/schema.sql to the chp99 database (needs the stack up)
./cleanup.sh    # remove all containers, volumes, networks -> back to an empty database
```

`setup.sh` is a **schema reset, not a migration**: `db/schema.sql` drops what it
creates, so applying it wipes parsed rows.

Plain compose also works; `worker` and `app` are opt-in profiles:

```bash
docker compose up -d                                  # just Postgres + Hatchet
docker compose --profile worker watch                 # worker, restarts on .py edits
docker compose --profile app up -d                    # the Part 3 app
docker compose logs -f worker
docker compose exec -T db psql -U postgres -d chp99   # psql shell
```

Triggering a workflow (from the host, worker already running):

```bash
cd workflows && uv sync
uv run python -m echo_run "hello"     # -> message='hello' length=5
```

Hatchet CLI, for inspecting failed runs (token lives in `workflows/.env`):

```bash
export HATCHET_CLIENT_SERVER_URL=http://localhost:8080   # export for EVERY command
hatchet profile add --name chp99 \
  --token "$(grep '^HATCHET_CLIENT_TOKEN=' workflows/.env | cut -d= -f2-)"
hatchet runs list -p chp99 --since 1h -o json
```

Unit tests over the parsing pure functions -- rates, hierarchy, citations, countries,
effectivity. No linter and no build step; if you add one, add its command here.

```bash
cd workflows && uv run pytest        # 115 tests, no database or network needed
cd api       && uv run pytest        # 15 tests, same
docker compose exec -T app npx tsc --noEmit
```

## Services

| Service | Host | In-container | Notes |
| --- | --- | --- | --- |
| `db` | `localhost:5432` | `db:5432` | Postgres 16, database `chp99`, `postgres`/`postgres` |
| `hatchet` | `localhost:8080` UI, `localhost:7077` gRPC | `hatchet:7077` | Hatchet Lite dev image, no login |
| `hatchet_db` | — | `hatchet_db:5432` | Hatchet's own DB — never put project data here |
| `worker` | — | — | profile `worker`, bind-mounts `workflows/` and `data/` |
| `api` | `localhost:8000` | `api:8000` | profile `app`, FastAPI, `/docs` is generated |
| `app` | `localhost:3000` | — | profile `app`, Next.js, rewrites `/api/*` to `api:8000` |

Stock ports, so free 5432/8080/8000/3000 before starting. From inside a container the
database is `db:5432`, not `localhost:5432` — both `worker` and `app` read
`DATABASE_URL` from the environment for this reason.

## Architecture and layout

```
workflows/   Hatchet workflows (Python, uv). scrape.py and parse.py are Parts 1 and 2;
             parsing/ holds what Part 2 does; worker.py is the worker process.
db/schema.sql  The single command that builds the schema from empty.
api/         Part 3 backend: FastAPI, read-only. The duty logic lives here, in
             api/duty/, so page and JSON endpoint are two adapters over one computation.
app/         Part 3 frontend: Next.js App Router, server-rendered. Draws pages; computes
             nothing. src/lib/api.ts is the only place that knows where the API is.
data/        Raw downloaded payloads. Gitignored, bind-mounted into the worker at /data
             (env var DATA_DIR), same path on host and container.
parts/       The three requirement documents.
skills/hatchet-cli/  Agent skill for the Hatchet CLI (setup, start worker, trigger,
             debug, replay). Read the matching reference before debugging a run.
```

**The data flow is scraper → `data/` → parser → Postgres → app.** The boundary
between the two workflows matters: the parser must run against payloads fetched an
hour ago, with the network unplugged.

**Domain shape driving the schema.** Chapter 99 lines do not classify goods; they
modify goods classified in chapters 1–97, and they say so in prose — a parenthetical
like `(provided for in subheading 2922.49.30)` is the join key. Subchapter III lines
key on country of origin and exclude other 9903 lines, so exclusions form a graph,
not a list. Rates are frequently *additive* ("the duty provided in the applicable
subheading + 25%"), which is why `rate_kind` is an operator and the columns beside it
are its operands. The three starter tables were "a floor, not a ceiling"; the schema is
now eleven tables, and `docs/SCHEMA.md` documents every column and when it is used.
`docs/DECISIONS.md` D-0021 records what became of each column the scaffold shipped.

## Gotchas

- **Register every new workflow in `workflows/worker.py`.** Otherwise Hatchet accepts
  the run and it sits queued forever with nothing to pick it up.
- **Python caches imported modules.** A worker left running after an edit serves stale
  code and the run *succeeds* with old results, silently. Use `./dev.sh` or
  `docker compose --profile worker watch` so edits restart it.
- **Run one worker at a time.** A host worker and the container worker share the token
  in `workflows/.env`; Hatchet will hand tasks to whichever it picks.
- Before wiping volumes, stop any host-side worker (`lsof -nP -iTCP:7077 | grep -v com.docke`
  should print nothing), or the orphan floods Hatchet with `could not get worker <uuid>`.
- `HATCHET_CLIENT_SERVER_URL` must be exported for *every* CLI command — the token names
  the container-internal port `8888`, and requests 403 without the override.
- The token in `workflows/.env` is committed on purpose: the dev image has auth compiled
  out and ships one fixed, non-expiring token. It is not a secret and does not need rotating.
- The HTSUS is revised several times a year. Record the release
  (`curl -s https://hts.usitc.gov/reststop/currentRelease`) as provenance rather than
  assuming a constant.

## Submission requirements

- Keep full git history — real commits as work progresses, not one squashed drop.
- Keep and maintain the specs and Markdown files already in the repo.
- Fill in all six sections of `SUBMISSION.md`, including where AI tools were used and
  anything shipped without full verification.
- The grader runs the commands in `SUBMISSION.md` literally, from a clean clone.
