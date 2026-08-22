# Decision log

Append-only. One entry per technical or design decision, newest at the bottom.
Never rewrite an entry — a decision that turns out wrong gets a new entry that
supersedes it. Format and scope rules are in [`CLAUDE.md`](../CLAUDE.md).

---

## D-0001 — Keep a written decision log alongside the code
**Date:** 2026-08-21 · **Area:** process · **Status:** accepted

**Context.** The submission is graded on the reasoning behind the code, not only the
code: `SUBMISSION.md` asks for the data model *and why*, the assumptions made where the
data was ambiguous, what was shipped unverified, and where AI tools were used. All four
are far cheaper to capture at the moment of the decision than to reconstruct at the end,
and the exercise runs across several sessions where earlier context is lost.

**Options.**
- Write `SUBMISSION.md` at the end from memory and git history — cheapest now, lossy later.
- One ADR file per decision under `docs/adr/` — standard, but heavy for a five-day exercise.
- A single append-only `DECISIONS.md` plus a chronological `JOURNAL.md` — one place to
  append, two files because durable decisions and session narrative age differently.

**Decision.** The third: `docs/DECISIONS.md` for decisions, `docs/JOURNAL.md` for the
work log. Both in English, both committed, both treated as deliverables.

**Tradeoff.** Costs a few minutes per decision and adds files a reviewer may not read.
Wrong if entries degrade into a changelog of what was typed — an entry with no rejected
alternative and no tradeoff is not worth writing.

**Feeds.** SUBMISSION.md §2, §4, §5, §6

---

## D-0002 — Start git history with an unmodified import of the provided scaffold
**Date:** 2026-08-21 · **Area:** process · **Status:** accepted

**Context.** The submission requires keeping all git history and commits, but the
exercise was distributed as a plain archive: `chp99-takehome-1871fc6.zip` contains zero
`.git/` entries, and the working directory had no repository. There is no upstream
history to preserve, so "keep all history" can only mean the history created from here —
which makes the starting point a choice rather than a given.

**Options.**
- One initial commit containing everything, provided files and own work mixed together —
  simplest, but a reviewer can no longer tell the two apart by diffing.
- Import the scaffold byte-for-byte as commit 1, then add own work in later commits.
- Reconstruct upstream history from the archive's commit sha (`1871fc6`) — not possible
  without the origin repository.

**Decision.** The second. Commit 1 is the scaffold exactly as distributed; everything
authored for this exercise lands in later commits, each scoped to one concern. Commit
identity is set repo-locally to `Tong Mo <tm4371@nyu.edu>` so it matches the address the
exercise was sent to.

**Tradeoff.** Costs one extra commit and requires resisting the urge to fix anything in
the scaffold before the baseline lands. It is wrong only if the scaffold itself needs
editing early and often, which would make the baseline diff noisy rather than useful.
No rebasing or squashing from here — the requirement rules out rewriting.

**Feeds.** SUBMISSION.md §6

---

## D-0003 — One workflow with parallel fetch tasks, not three workflows
**Date:** 2026-08-21 · **Area:** scraper · **Status:** accepted

**Context.** Three independent sources, one of which (the 14 MB notes PDF) is an order of
magnitude larger and the most likely to time out. The requirements ask for partial success
to leave the data coherent.

**Options.**
- One workflow, one serial task — simplest, but one slow PDF fails all three fetches.
- One workflow, `resolve_release` then three parallel fetch tasks then `summarize`.
- Three separate workflows plus a parent that spawns them — best isolation, allows
  re-running a single source, at the cost of four registrations and cross-run aggregation.

**Decision.** The second. `resolve_release` must precede the fetches because the release
names the storage directory and pins the PDF URL; the three fetches are independent and
run in parallel; `summarize` tolerates partial failure.

**Tradeoff.** Re-running one source alone means replaying the whole run, which re-fetches
the other two. Cheap here because of D-0004 — a re-fetch of unchanged bytes is a hash
comparison, not a write. It would be the wrong call if a source were expensive, rate
limited, or paid.

**Feeds.** SUBMISSION.md §3

---

## D-0004 — Idempotency is release-scoped and content-addressed
**Date:** 2026-08-21 · **Area:** scraper · **Status:** accepted

**Context.** Measured against the live API: the endpoints return no `ETag` and no
`Last-Modified`, and send `cache-control: no-cache, no-store`. `HEAD` on the PDF endpoint
returns `content-length: 1`, so it cannot even be used to compare sizes. Meanwhile the
live release moved from Revision 15 to Revision 16 during this exercise, so "the current
data" is a moving target.

**Options.**
- Conditional requests on `ETag` / `Last-Modified` — impossible, the headers are absent.
- Skip the fetch if a file already exists — fast, but cannot detect a changed payload
  within the same release, and a truncated earlier file would be trusted forever.
- Always download to a temp file, hash it, compare against what is on disk, and replace
  atomically only when the hash differs.

**Decision.** The third, with payloads stored under `data/raw/<release>/`. A re-run
records `unchanged` when the hash matches and `fetched` when it does not. A new release
gets a new directory; nothing is overwritten across releases.

**Tradeoff.** Every run transfers ~26 MB even when nothing changed. Acceptable at this
size and unavoidable without caching headers; it would need revisiting if the payloads
grew by an order of magnitude or the source imposed rate limits.

**Feeds.** SUBMISSION.md §2, §5

---

## D-0005 — Provenance is written to both disk and Postgres
**Date:** 2026-08-21 · **Area:** scraper, schema · **Status:** accepted · **Supersedes P-f**

**Context.** "Where did this row come from, and when?" has to be answerable, and the
release can change mid-exercise. Two consumers need the answer for different reasons: a
person opening `data/` and a query joining parsed rows back to their source.

**Options.**
- `manifest.json` on disk only — self-describing directory, but nothing to join against.
- A `source_fetch` table only — joinable, but wiped by `./setup.sh`, which is a schema
  reset rather than a migration, leaving the payloads on disk unexplained.
- Both, with the manifest as the durable record and the table as the queryable one.

**Decision.** Both. `manifest.json` sits next to the payloads; `source_fetch` carries one
row per source per run with url, release, status, bytes, sha256, duration and error.
Part 2 will reference `source_fetch.id` from the parsed tables.

**Tradeoff.** Two writes to keep consistent, and they can drift if a run dies between
them. The manifest is authoritative when they disagree, because it lives with the bytes it
describes.

**Feeds.** SUBMISSION.md §2

---

## D-0006 — Failure is per-source; nothing is rolled back
**Date:** 2026-08-21 · **Area:** scraper · **Status:** accepted

**Context.** The requirement is that "a failure should leave the data in a coherent
state". Coherent is not the same as empty.

**Options.**
- Transactional: any failure removes the payloads written by the run. Coherent, but throws
  away good data and makes a flaky network maximally expensive.
- Per-source: each fetch stands alone; the run reports which sources succeeded.

**Decision.** Per-source. A correct payload is not made incorrect by a sibling's failure,
so successful files stay. `summarize` writes the manifest for what completed and returns a
per-source status; the run itself is marked failed if any source failed, so the failure is
visible rather than buried in a green run.

**Tradeoff.** `data/raw/<release>/` can hold a partial set, so downstream code must not
assume all three files are present. The manifest lists what is actually there, and Part 2
reads the manifest rather than globbing the directory.

**Feeds.** SUBMISSION.md §3, §4

---

## D-0007 — Fetch tasks report status instead of raising, so `summarize` always runs
**Date:** 2026-08-22 · **Area:** scraper · **Status:** accepted · **Amends D-0006**

**Context.** Measured, not assumed (see the Step 0 journal entry). A join task whose
parent failed is `CANCELLED` and never executes, so a `summarize` that depends on all
three fetches cannot write the manifest after a partial failure. An `on_failure_task` does
run — but it fires the moment a task fails, while sibling branches are still in flight:
in the probe it read `Step output for 'good' not found` because `good` was still mid-sleep
and only printed `finished` afterwards. A manifest written there would be missing sources
that were seconds from completing, which is the common case when a 404 fails instantly
while the 14 MB PDF is still downloading.

**Options.**
- Fetch tasks raise; the manifest is written by an on-failure task — rejected by the
  measurement above: the manifest would be incomplete and silently wrong.
- Fetch tasks raise; no manifest at all, rebuild it from `source_fetch` at read time —
  pushes the problem into Part 2 and makes `data/` no longer self-describing, losing what
  D-0005 was for.
- Fetch tasks catch their own failure, return a status object, and never raise.
  `summarize` therefore always runs, writes a complete manifest covering every source with
  its outcome, and raises at the end if any source failed so the run is still marked
  FAILED.

**Decision.** The third. Retry moves inside the task — Hatchet's task-level `retries` only
trigger on an exception, so a task that swallows its failure gets no engine retries and
must implement backoff itself in `fetching.py`.

**Tradeoff.** A failed source shows a **green** task in the dashboard, which costs
observability — the dimension being assessed. Mitigated three ways: the fetch task logs
the failure through `ctx.log`, the `source_fetch` row carries `status='failed'` with the
error text, and `summarize` fails the run with a message naming the failed sources. If
per-task colour turns out to matter more than manifest completeness, this is the entry to
supersede.

**Also settled by the same experiment**, and carried into the implementation:
`execution_timeout` defaults to 60s and must be raised for the fetch tasks; `retries=N`
means N+1 attempts; `replay` re-runs every task, so resumability rests entirely on the
idempotency from D-0004 rather than on the orchestrator.

**Feeds.** SUBMISSION.md §3, §4

---

# Pending decisions

Open questions raised by verified evidence (see JOURNAL 2026-08-20). Each becomes a
numbered entry above once decided — do not decide them here.

- **P-a · Cross-reference code granularity.** Chapter 99 cites 8-digit subheadings
  (`provided for in subheading 2922.49.30`); the base export carries 10-digit lines
  (`2922.49.30.00`). An equality join returns zero rows. Normalize to what, and does
  `rule_edge.target_hts` store the cited string, the resolved code, or both?
- **P-b · Inherited base rates.** 20,446 of 31,860 base rows have an empty `general`
  rate and inherit it from an ancestor row via `indent`. Materialize the inherited rate
  onto every row, or resolve it at query time?
- **P-c · Rate representation.** `mfn_rate_pct numeric` cannot hold specific duties
  (`14.27¢/liter`, 771 rows), compound duties (`4.4¢/kg + 8.5%`, 417 rows), or the ~30
  rows whose rate is a sentence. What replaces or supplements that column?
- **P-d · Unparsed prose.** What happens to a description whose cross-reference or rate
  does not match any pattern — dropped, flagged, or stored with a parse-status column?
  Silent loss is the failure mode the parser is most likely to have.
- **P-e · Notes as a table.** `9903.88.01` defines its own scope by pointing at
  "the subheadings enumerated in U.S. note 20(b)", whose list exists only in the notes
  PDF. How are notes stored, and how does a rule cite one?
- ~~**P-f · Provenance grain.**~~ Settled by **D-0005**: per source per run, written to
  both `manifest.json` and a `source_fetch` table.
