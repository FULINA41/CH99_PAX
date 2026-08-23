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

## D-0008 — Size the fetch task budget from the retry policy, not from one attempt
**Date:** 2026-08-22 · **Area:** scraper · **Status:** accepted · **Amends D-0007**

**Context.** `FETCH_TIMEOUT` was `TOTAL_TIMEOUT + 60` = 360s, which budgets for a single
HTTP attempt. `fetching.py` makes up to `MAX_ATTEMPTS` = 3 attempts of `TOTAL_TIMEOUT` =
300s each plus 1s + 2s of backoff, so one fetch can legitimately run 903s. Against a
hung server the engine would cancel the task at 360s, mid-second-attempt. Cancellation is
not merely slow: a task whose parent is CANCELLED never runs, so `summarize` would never
write the manifest — the precise failure D-0007 was written to prevent. The two numbers
lived in different files with nothing tying them together.

**Options.**
- Raise `FETCH_TIMEOUT` to a hand-picked larger constant — fixes today, drifts again the
  next time `MAX_ATTEMPTS` or `TOTAL_TIMEOUT` moves.
- Lower `TOTAL_TIMEOUT` to ~100s so three attempts fit inside 360s — keeps the slot short,
  but overturns a deliberate ceiling (§6: "the 14 MB PDF takes seconds normally; 5 minutes
  is a generous ceiling") and would abort a genuinely slow 14 MB download.
- Derive the budget: `fetching.py` exports `WORST_CASE_SECONDS = MAX_ATTEMPTS *
  TOTAL_TIMEOUT + BACKOFF_SECONDS`, and `scrape.py` sets `FETCH_TIMEOUT` from it.
- Call `ctx.refresh_timeout()` before each retry so only a retrying task earns more time.

**Decision.** The third. The module that owns the retry policy also publishes what that
policy can cost; the orchestrator adds a 60s margin on top. `FETCH_TIMEOUT` is now 963s.

**Tradeoff.** A genuinely wedged fetch holds a worker slot for ~16 minutes before the run
fails. Acceptable here — three sources, no concurrency pressure, and D-0007 ranks manifest
completeness above promptness. `ctx.refresh_timeout()` is the better answer if slot
occupancy ever matters; it was not taken now because it puts engine coupling into
`fetching.py`, which is currently Hatchet-free and unit-testable without an engine.

**Feeds.** SUBMISSION.md §3, §4

---

## D-0009 — The mid-run release re-check is best-effort and cannot fail the run
**Date:** 2026-08-22 · **Area:** scraper · **Status:** accepted

**Context.** `summarize` re-resolves the release after the fetches, because the two
`exportList` endpoints take no release parameter and a revision published mid-run cannot
be prevented, only detected. That call was `current_release()`, which raises by design.
It sat *before* `write_manifest`, so a USITC blip at that moment would abort `summarize`
with all three payloads already on disk and no manifest describing them — 26 MB that
Part 2 cannot judge as trustworthy, caused by a check whose only job is to add a field.

**Options.**
- Move the re-check after `write_manifest` — the manifest then never carries the finding.
- A non-raising variant of `current_release` — a second contract for one caller.
- Wrap the call: on failure record `release_recheck_failed` in the manifest and continue.

**Decision.** The third. `release.py` keeps its raise-always contract, which is correct in
`resolve_release` — with no release there is no directory to write into. By `summarize`
the bytes have landed and the context has changed, so the caller, not the callee, decides
that this failure is survivable.

**Tradeoff.** A run can now finish green while silently not knowing whether the release
moved. The manifest says so explicitly rather than omitting the field, so a reader can
tell "checked, unchanged" from "could not check". Wrong if the re-check ever becomes a
correctness gate rather than an annotation.

**Feeds.** SUBMISSION.md §3, §5

---

## D-0010 — A payload says whether the directory's release actually speaks for it
**Date:** 2026-08-22 · **Area:** scraper · **Status:** superseded by D-0011

**Context.** Found by acceptance check 5. Payloads are stored under `data/raw/<release>/`,
but only the notes PDF endpoint accepts a release parameter; `exportList` ignores it and
serves whatever is current. So `data/raw/2026HTSRev15/` holds a genuine Rev15 PDF beside
`ch99.json` and `base.json` that were Rev16 at fetch time. The directory name asserts a
revision for all three files and is true of one. `Source.pinnable` already knows which is
which and each entry's `url` shows it, but nothing said so, and Part 2 would reasonably
read that directory as a complete snapshot of one revision.

**Options.**
- Per-entry `release_pinned` in the manifest — the information exists, so declare it.
- Refuse `--release` when it does not match the current release — safe, but removes the
  ability to re-fetch a historical PDF, which is why the flag exists.
- Name mixed directories for what they hold, e.g. `2026HTSRev15+exports@Rev16` — the name
  stops lying, at the cost of unstable paths every downstream reader must parse.
- Skip non-pinnable sources when a non-current release is pinned, recording `skipped` —
  neither lies nor overwrites, but adds a fourth status and a partial-directory case.

**Decision.** The first. `fetch_source` records
`release_pinned = source.pinnable and release is not None`, and it rides into the manifest
and the fetch result. A reader can now tell which bytes the directory name speaks for.

**Tradeoff.** This buys knowledge, not protection. The related hazard is untouched: a
re-run pinned to an older release re-downloads the exports, finds the hash different from
the correct historical copy, and replaces it — quietly turning a good snapshot into a
mixed one while reporting a normal `fetched`. Reaching that requires passing `--release`
with a stale value after a revision has landed; the documented command never does. The
fourth option above is the fix if it ever matters, and would supersede this entry.

**Feeds.** SUBMISSION.md §2, §5

---

## D-0011 — Skip a source whose endpoint cannot serve the pinned release
**Date:** 2026-08-22 · **Area:** scraper · **Status:** accepted · supersedes D-0010

**Context.** Written late: D-0010 was recorded as superseded by this entry, and
`PART1_SCRAPER.md` and `JOURNAL.md` both cite D-0011, but the entry itself was never
added. Backfilled here from the code and the verification in JOURNAL 2026-08-22.
D-0010 declared the hazard without preventing it. Only the notes PDF endpoint accepts a
release parameter; `exportList` ignores it and serves current. So `--release 2026HTSRev15`
after Rev16 has landed re-downloads the exports, finds a different hash from the correct
historical copy, and replaces it — reporting a normal `fetched` while turning a good
snapshot into a mixed one.

**Options.**
- Leave it: reaching the hazard needs a stale `--release`, which the documented command
  never passes.
- Refuse `--release` unless it matches the live release — safe, but removes re-fetching a
  historical PDF, which is the only reason the flag exists.
- Skip the sources whose endpoint cannot honour the pin, before any request is made.

**Decision.** The third. `fetch_source` returns `status='skipped'` with the on-disk size
and hash when `release` differs from `live_release` and `not source.pinnable`. The branch
sits ahead of the HTTP call, so a skip cannot touch the network or the file.

**Tradeoff.** A pinned run now produces a partial directory by design, and `skipped` had
to become a fourth status in `source_fetch` and the manifest. Verified with 40-byte marker
files standing in for a historical snapshot: after `--release 2026HTSRev15` both markers
were still 40 bytes and byte-identical, the PDF genuinely re-fetched at 13,957,698 B, and
the manifest still reported `complete: true`.

**Feeds.** SUBMISSION.md §2, §5

---

## D-0012 — Store only the rows that can be classified against
**Date:** 2026-08-23 · **Area:** parser · **Status:** accepted

**Context.** 5,614 of 31,860 base rows and 238 of 3,336 Chapter 99 rows carry no code.
They are heading rows — `superior="true"` holds on exactly those rows in both files. A
count over the export confirms they carry no rate of any kind: zero of them have
`general`, `other`, `special` or `additionalDuties`. Their content is prose that scopes
their children, and it is load-bearing: `9903.17.01` reads "Eligible to be imported under
the first quota period", which means nothing until the two ancestors above it —
"Sugars, syrups and molasses provided for in subheading 1701.12.10, …" and "Described in
U.S. note 15(a) to this subchapter:" — are attached.

**Options.**
- Store every row, giving heading rows a surrogate key — highest fidelity, but forces a
  surrogate primary key on all four tables and leaves every query filtering out rows that
  can never be an answer.
- Store only coded rows and drop the heading prose — simplest, and loses the scope of
  9903.17.01 entirely.
- Store only coded rows, and materialise the ancestor prose onto every descendant.

**Decision.** The third. `hts_base` and `rule` hold 26,246 and 3,098 rows, keyed by the
natural code — verified unique, zero duplicates in either file. `description` keeps the
row's own prose; `full_description` is the ancestor chain joined onto it. Cross-references,
note citations and countries are extracted from `full_description`, so a provision inherits
its ancestors' scope, which is how the schedule is read legally.

**Tradeoff.** Row counts no longer match the source files, and a reviewer diffing against
the JSON will find 5,852 rows missing. The prose survives, but only in joined form: the
boundaries between ancestor and descendant are not recoverable from `full_description`
alone. Wrong if a heading row ever carries a rate — worth re-checking on a future revision,
since the check above holds for 2026HTSRev16 and is not guaranteed by the format.

**Feeds.** SUBMISSION.md §2, §5

---

## D-0013 — Rate kind is an operator; its operands are separate columns
**Date:** 2026-08-23 · **Area:** schema · **Status:** accepted · settles P-c

**Context.** "Rates must be computable, not just displayable" is an explicit requirement,
and a single `numeric` cannot hold what the schedule actually prints: 5,863 pure ad valorem
rates, 771 specific duties (`14.27¢/liter`), 417 compound duties (`4.4¢/kg + 8.5%`), and
about 30 rows whose rate is an English sentence. Chapter 99 adds forms that are *relative*
to the base rate — "The duty provided in the applicable subheading" (204 rows) and
"…applicable subheading + 25%" (91 rows, spelled both `+ 25%` and `plus 25%`).

**Options.**
- Keep the scaffold's `rate_kind` vocabulary (`free`/`additive`/`ad_valorem`/`no_change`/
  `specific`/`other`) and add columns — but `ad_valorem` and `specific` describe the
  *operand*, not the operator, so a compound duty has no valid value.
- One `duty_rate` table keyed by (owner, column) — normalises Column 1, Column 2 and the
  additional duty into rows, at the cost of a polymorphic owner with no referential
  integrity and a join on every lookup.
- Split operator from operands: six operator values, three operand columns, filled in
  whatever combination the printed rate needs.

**Decision.** The third. `rate_kind ∈ (free, replace, additive, no_change, prose, none)`
with `rate_ad_valorem_pct`, `rate_specific_amount`, `rate_specific_unit` beside it. A
compound duty fills both operand groups. `free` is `replace` with pct 0 and is kept
separate only because the schedule writes it as a word, so a calculation may ignore the
distinction while a display honours it. `rate_text` always keeps the string as printed.
The same five columns appear on `hts_base` (twice — Column 1 General and Column 2) and on
`rule`.

**Tradeoff.** Wide tables and a repeated column group instead of a normalised rate table;
adding a fourth rate column means a migration rather than a row. Accepted because every
duty calculation is then a single-row read, and because a polymorphic owner column would
have given up foreign keys on the one join Part 3 makes constantly. `prose` is an admission,
not a category — those ~30 rows are not computable and the UI has to say so.

**Feeds.** SUBMISSION.md §2

---

## D-0014 — Materialise inherited base rates and record where each came from
**Date:** 2026-08-23 · **Area:** parser · **Status:** accepted · settles P-b

**Context.** 20,446 of 31,860 base rows have an empty `general` and inherit it from the
nearest ancestor that states one: `2922.49.49.10` (Alanine) has no rate of its own and is
dutiable at the 4.2% printed on `2922.49.49`. Resolving that at query time means a
recursive CTE on the hot path of every duty calculation.

**Options.**
- Resolve at query time — always consistent, but the recursion is repeated per lookup and
  every consumer has to know the rule.
- Materialise the inherited rate onto every row — one read, at the cost of storing a
  derived value.
- Materialise and record the source row, so the derivation stays visible.

**Decision.** The third. Every row carries a resolved rate; `rate_inherited_from` names the
ancestor when the rate was not the row's own, and is NULL when it was. Verified that
inheritance always terminates on a coded row, since no heading row carries a rate (D-0012).
The parent chain is rebuilt from `indent` — nearest preceding row of smaller indent —
which survives the 12 places where indent jumps by more than one: all 12 are 10-digit
statistical lines sitting two levels below the 8-digit parent immediately above them.
Where both rows carry a code, the parent's code must be a dotted prefix of the child's, and
a violation goes to `parse_issue` rather than being written.

**Tradeoff.** A derived value stored is a value that can go stale, so the whole table is
rebuilt in one transaction per run rather than updated in place (D-0020). `rate_inherited_from`
is a self-referencing foreign key, which means rows must be inserted parents-first — true of
the export's document order, and a constraint on any future loader.

**Feeds.** SUBMISSION.md §2

---

## D-0015 — Store a citation as printed and as resolved, in different tables
**Date:** 2026-08-23 · **Area:** schema · **Status:** accepted · settles P-a

**Context.** Chapter 99 cites 8-digit subheadings — `(provided for in subheading
2922.49.30)` — while the rate-bearing rows in the base export are 8 or 10 digits
(`2922.49.30.00`). An equality join returns zero rows, and this affects 2,556 of 3,336
provisions. Matching is therefore prefix matching, and prefixes expand unevenly: `2922.49.30`
reaches 1 base row, `7208.51` reaches 4, `4202` reaches 108. Separately, 69 cited codes
resolve to nothing at all — some are provisions naming codes that no longer exist in this
revision, some are noise the regex picked up (`2022`, `0090`).

**Options.**
- Store the cited string only, resolve at query time — honest, but every consumer
  reimplements prefix matching, and the 108-row expansion is recomputed constantly.
- Store the resolved codes only — fast, but the evidence is gone: a resolver bug can only
  be found by re-parsing the prose, and the 69 unresolvable citations disappear.
- Store both, in separate tables with different rules.

**Decision.** The third. `rule_edge` is the fact layer: `target_hts` is the string exactly
as printed, no foreign key, no normalisation, so a dead code is recorded rather than
dropped. `rule_base_match` is the interpretation layer: a real foreign key to `hts_base`,
plus `cited_code`, `match_kind` (exact/prefix) and `via` (description/note) saying how the
match was reached. Prefix matching is anchored at a separator (`x == c or
x.startswith(c + '.')`), because a bare `startswith` would let `2922.49.3` match
`2922.49.30`.

**Tradeoff.** The same citation is stored twice and the two can disagree if the resolver is
re-run without the parser. Accepted because that is exactly the failure the split is meant
to make visible: `rule_base_match` is fully derivable from `rule_edge` and `note_subheading`,
so it can be rebuilt without touching the prose, and a reviewer can audit the interpretation
without trusting it.

**Feeds.** SUBMISSION.md §2, §5

---

## D-0016 — Notes are tables, and list-type notes expand into codes
**Date:** 2026-08-23 · **Area:** schema · **Status:** accepted · settles P-e

**Context.** 547 provisions across 33 note numbers define their scope by pointing at a U.S.
note rather than by naming codes. `9903.88.01` covers "the subheadings enumerated in U.S.
note 20(b)", and that list exists only in the PDF — pages of bare 8-digit codes, well over a
thousand of them. Without the notes the parser cannot answer what the Section 301 headings
actually cover. The requirement is also explicit: notes must be modelled and linked back to
the headings that cite them.

**Options.**
- A `note_ref text` column on `rule`, as the scaffold has — records that a note was cited,
  but cannot store the note, so the scope stays unknown.
- Store note bodies only, as text — makes the prose readable but leaves 20(b) as an
  unqueryable wall of digits.
- Three tables: the note, the citation, and the codes a list note contains.

**Decision.** The third. `note` holds the body, its kind, and where it was found in the PDF.
`rule_note` is the citation, carrying `cited_text` as the description wrote it and a
nullable `note_id` — a citation that matches no note keeps the text, gets a NULL, and a
`parse_issue` row. `note_subheading` holds the codes a list note prints, in order, as a
fact layer feeding `rule_base_match` the same way `rule_edge` does.

**Tradeoff.** `note.content_kind` is a judgement made by the parser about a page of text,
and a note classified `prose` that actually contains a list will silently under-cover its
provisions. Extraction is also the weakest link in the chain: pypdf flattens a four-column
table into runs of fixed-width codes, and the grey shading that marks expired provisions is
lost entirely (P-i).

**Feeds.** SUBMISSION.md §2, §5

---

## D-0017 — Nothing the parser cannot read is discarded
**Date:** 2026-08-23 · **Area:** parser · **Status:** accepted · settles P-d

**Context.** A prose tariff schedule will always leave residue: ~30 rate strings that are
sentences, 69 cited codes that resolve to nothing, countries written in forms the pattern
does not cover. The failure mode worth preventing is not having residue — it is losing it
quietly, which produces a database that looks complete and is not.

**Options.**
- Log to stderr — visible during the run, gone afterwards, and invisible to anyone reading
  the database.
- A status column on each table — keeps the problem next to the row, but only works when
  there is a row; a citation that produced nothing has nowhere to live.
- A dedicated `parse_issue` table.

**Decision.** The third. `parse_issue(run_id, stage, issue_kind, subject, detail)`, written
by every parse task. `subject` is the code or note the issue is about, `detail` the offending
fragment. An empty `parse_issue` after a full run means the parser is not looking, not that
the data is clean, and the acceptance check treats it that way.

**Tradeoff.** Issues are recorded, not resolved, and a table nobody reads is only marginally
better than a log. It is surfaced in the run summary and in the Part 2 write-up to make that
less likely.

**Feeds.** SUBMISSION.md §2, §5

---

## D-0018 — A provision's scope can be a country instead of a code
**Date:** 2026-08-23 · **Area:** schema · **Status:** accepted

**Context.** Of the 3,098 coded Chapter 99 rows, 2,203 cite a base code in their own
description and 558 point at a note that lists codes. The remaining 211 name a country and
no product at all — "articles the product of Mexico". These have **no join key to the base
schedule**: `9903.01.01` covers every good from Mexico, and each of `9903.05.20`–`9903.05.84`
covers every good from its own country. They are also the most frequently applied duties in
the current schedule.

**Options.**
- Materialise them against all 26,246 base rows — makes them look like every other rule, at
  5.5 million rows per country-wide provision and a table that has to be rebuilt whenever
  either side changes.
- Leave them out of the resolved layer and handle them as a special case in application
  code — cheap, and invisible to anyone reading the schema.
- Give `rule` a `scope` column and let the resolver skip them deliberately.

**Decision.** The third. `rule.scope ∈ (by_code, by_country_all_goods, unknown)`. A
country-wide provision has no `rule_base_match` rows by design, and its applicability is
decided by `rule_country` alone. `unknown` exists so that a provision the classifier cannot
place is visible rather than silently filed as one of the other two.

**Tradeoff.** Answering "what applies to this shipment" now needs two queries — a code path
and a country path — and forgetting the second is a silent 25-point understatement on
Chinese goods. Materialising would have made it one query; the row count is what rules it
out.

**Feeds.** SUBMISSION.md §2

---

## D-0019 — Goods identity is its own table, because the code does not choose
**Date:** 2026-08-23 · **Area:** schema · **Status:** accepted

**Context.** Of the 994 base codes Chapter 99 cites, 439 — 44% — are cited by more than one
provision; `3808.92.15` is cited by 34. This is not messy data. The base code is a bucket
and a 9902 provision picks one substance out of it: four provisions cite `2922.49.30`, and
they name 4-Chlorophenylglycine (CAS 6212-33-5), 2-Amino-5-sulfobenzoic acid (3577-63-7),
3,4-Diaminobenzoic acid (619-05-6) and Methyl 2-amino-3-chlorobenzoate (77820-58-7). A query
keyed on base code plus country therefore returns candidates, not an answer. 1,009 provisions
carry a CAS number, which is exact and globally unique.

**Options.**
- Leave it in the description and match on words — the substance names are in the prose, but
  matching them is fuzzy exactly where the answer must be exact.
- A `cas_number` column on `rule` — one column, but a provision can name more than one
  substance and the next identifier kind (a chemical name, a brand, a mill certificate)
  needs another column.
- A `rule_identifier(rule_hts, kind, value)` table.

**Decision.** The third, with `kind` currently constrained to `'cas'`. Extracting CAS
numbers turns a third of Chapter 99 into a deterministic lookup for an importer who knows
what they are shipping.

**Tradeoff.** The 2,089 provisions with no identifier still need prose matching, so this
solves a third of the problem and makes the remaining two thirds look solved. The `kind`
CHECK will need widening the moment a second identifier type is extracted.

**Feeds.** SUBMISSION.md §2

---

## D-0020 — One revision resident; each task rebuilds its own tables in one transaction
**Date:** 2026-08-23 · **Area:** parser · **Status:** accepted

**Context.** Re-running any part must be safe, and the parser writes derived values —
inherited rates, resolved matches — that go stale rather than merely duplicate. An upsert
keyed on `hts` would leave behind rows for codes that a new revision deleted, and those rows
would still satisfy every foreign key.

**Options.**
- Upsert on the natural key — no downtime, but deleted codes survive as ghosts.
- Version every table by release and query the latest — supports comparing revisions, at the
  cost of a release column in every key and every join.
- Delete then insert, per task, inside one transaction.

**Decision.** The third. The database holds exactly one revision. Each parse task opens a
transaction, deletes the tables it owns, bulk-inserts, and commits, so a crash mid-task
leaves the previous contents intact rather than a half-loaded table. `source_fetch_id` on
`hts_base`, `rule` and `note` records which fetch the rows came from.

**Tradeoff.** No revision-over-revision comparison — a genuinely interesting question this
schema cannot answer without a migration. `data/raw/` keeps the payloads for every release
fetched, so the history is recoverable by re-parsing, just not queryable. Task ordering
becomes load-bearing: `resolve` must run after `parse_base`, since deleting `hts_base`
cascades `rule_base_match` away.

**Feeds.** SUBMISSION.md §2, §5

---

## D-0021 — What became of the scaffold's three tables
**Date:** 2026-08-23 · **Area:** schema · **Status:** accepted

**Context.** The exercise supplies `hts_base`, `rule` and `rule_edge` and calls them "a floor,
not a ceiling". Extending them is expected; renaming and removing their columns is not, and a
reviewer who knows the starting schema should be able to see every departure in one place
rather than by diffing SQL. Recorded here for that reason.

**Original.**

```sql
CREATE TABLE hts_base (
  hts          text PRIMARY KEY,
  description  text,
  mfn_rate_pct numeric
);

CREATE TABLE rule (
  hts         text PRIMARY KEY,
  subchapter  text NOT NULL,
  description text NOT NULL,
  rate_kind   text NOT NULL
    CHECK (rate_kind IN ('free','additive','ad_valorem','no_change','specific','other')),
  rate_value  numeric,
  note_ref    text
);

CREATE TABLE rule_edge (
  source_hts text NOT NULL REFERENCES rule(hts) ON DELETE CASCADE,
  edge_type  text NOT NULL CHECK (edge_type IN ('references','excludes')),
  target_hts text NOT NULL,
  PRIMARY KEY (source_hts, edge_type, target_hts)
);
```

**Column by column.**

| Original | Now | Why |
| --- | --- | --- |
| `hts_base.hts` | kept, PRIMARY KEY | Codes are unique in the export — verified, zero duplicates in 26,246 rows |
| `hts_base.description` | kept, plus `full_description` | "Other" means nothing without its ancestors (D-0012) |
| `hts_base.mfn_rate_pct` | **removed** → `rate_kind` + 3 operand columns | Cannot hold 771 specific and 417 compound duties (D-0013). Keeping it beside `rate_ad_valorem_pct` would be two names for one number, and they would drift |
| `rule.hts` | kept, PRIMARY KEY | Unique across 3,098 coded rows |
| `rule.subchapter` | kept, now derived | The heading's last two digits are the subchapter number (9915 → XV). Not stated in the JSON, but exact |
| `rule.description` | kept, plus `full_description` | Same reason as `hts_base` |
| `rule.rate_kind` | kept, **vocabulary changed** | `ad_valorem` and `specific` name the *operand*, so a compound duty has no valid value. Now `free`/`replace`/`additive`/`no_change`/`prose`/`none` — purely operators (D-0013) |
| `rule.rate_value` | **removed** → 3 operand columns | One numeric cannot express `4.4¢/kg + 8.5%`, and could not say whether 25 meant percent or cents |
| `rule.note_ref` | **removed** → `rule_note` + `note` | A text pointer records that a note was cited but cannot store it; 547 provisions get their scope from notes (D-0016) |
| `rule_edge` (all) | **unchanged** | Its design was already right: `target_hts` unnormalised and not a foreign key is exactly the fact layer D-0015 needs |

**Added.** `hts_base`: `parent_hts`, `units`, Column 2 as five parsed columns, `special_text`,
`rate_inherited_from`, `source_fetch_id`, a generated `tsvector`. `rule`: `heading`,
`parent_hts`, `indent`, `scope`, four `additional_duty_*` columns, `source_fetch_id`, a
generated `tsvector`. New tables: `source_fetch`, `rule_identifier`, `rule_country`, `note`,
`rule_note`, `note_subheading`, `rule_base_match`, `parse_issue`.

**Tradeoff.** Three scaffold columns no longer exist, so anyone with a query written against
the starting schema has to rewrite it. The alternative — keeping `mfn_rate_pct` and
`rate_value` as aliases — costs a rule about which column wins, and that rule is the kind
that is right for a month.

**Feeds.** SUBMISSION.md §2

---

# Pending decisions

Open questions raised by verified evidence (see JOURNAL 2026-08-20). Each becomes a
numbered entry above once decided — do not decide them here.

- **P-g · Part 3 is intended to be an agent.** Stated 2026-08-22, ahead of Part 2 and
  explicitly not a constraint on it. It may amend the earlier choice of a rate explainer
  as the Part 3 shape, so revisit that before designing Part 3 — and check then whether an
  agent wants anything the schema does not already give a UI, such as text worth
  retrieving over rather than joining.
- **P-h · Alternatives versus stacking.** Several 9902 provisions on one base code are
  treated as mutually exclusive alternatives, because a shipment is one substance and their
  descriptions are disjoint — but **nothing in the data states this**, so it is an
  assumption that belongs in SUBMISSION.md §5. A 9902 reduction combined with a 9903
  additional duty is not an assumption: note 20(a) states that goods eligible for
  subchapter II reductions remain subject to the Section 301 duty.
- **P-i · Effectivity.** Expired provisions are marked in the PDF by grey shading, which
  text extraction destroys, and by 161 "Compiler's note" asides in prose. The JSON carries
  no effective or expiry field at all. Decide whether to extract the compiler notes into a
  field, and how the UI says "this may no longer be in force".
- ~~**P-a · Cross-reference code granularity.**~~ Settled by **D-0015**: stored twice, as
  printed in `rule_edge` and as resolved in `rule_base_match`.
- ~~**P-b · Inherited base rates.**~~ Settled by **D-0014**: materialised onto every row,
  with `rate_inherited_from` naming the ancestor.
- ~~**P-c · Rate representation.**~~ Settled by **D-0013**: `rate_kind` is an operator and
  three operand columns hold the number, the amount and the unit.
- ~~**P-d · Unparsed prose.**~~ Settled by **D-0017**: a `parse_issue` row, never a drop.
- ~~**P-e · Notes as a table.**~~ Settled by **D-0016**: `note`, `rule_note` and
  `note_subheading`.
- ~~**P-f · Provenance grain.**~~ Settled by **D-0005**: per source per run, written to
  both `manifest.json` and a `source_fetch` table.
