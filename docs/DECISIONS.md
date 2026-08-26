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
**Date:** 2026-08-23 · **Area:** schema · **Status:** accepted · settles P-c · evidence corrected by D-0022

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
**Date:** 2026-08-23 · **Area:** schema · **Status:** accepted · settles P-a · evidence corrected by D-0022

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
**Date:** 2026-08-23 · **Area:** schema · **Status:** accepted · settles P-e · evidence corrected by D-0022

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
**Date:** 2026-08-23 · **Area:** parser · **Status:** accepted · settles P-d · evidence corrected by D-0022

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
**Date:** 2026-08-23 · **Area:** schema · **Status:** accepted · evidence corrected by D-0022

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
**Date:** 2026-08-23 · **Area:** schema · **Status:** accepted · evidence corrected by D-0022

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
**Date:** 2026-08-23 · **Area:** schema · **Status:** accepted · evidence corrected by D-0022

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

## D-0022 — Re-derive the Chapter 99 evidence from the payload the workflow actually fetches
**Date:** 2026-08-23 · **Area:** process · **Status:** accepted

**Context.** Part 2's first real run refused to start:

```
ManifestError: /data/raw/2026HTSRev16/ch99.json is 2,060,842 B,
               but the manifest recorded 1,992,914 B
```

The file on disk hashed to `7283b218…` against the manifest's `5a7ca6b0…`; `base.json` and
the PDF matched exactly. `ch99.json` had been written at 12:17 against a manifest written
at 10:56, by something outside the scraper — an exploratory `curl` during the data
analysis. Re-running Part 1 fetched `5a7ca6b0…` from the API, confirming that the larger
file was never what this pipeline serves. **Every Chapter 99 count in `DATA_INVENTORY.md`
had been measured against it.**

Two of the differences hold under an identical definition, so they are the payload and not
the measurement: `additionalDuties` non-empty is 512, not 810, and rows containing
"provided for in" are 2,456, not 2,556.

Re-deriving the rest exposed a second, unrelated error. The counts had been taken from each
row's own `description`, but a provision inherits its ancestors' scope — which is how the
schedule is read, and what the parser will do. Read that way `9903.01.01` is:

> Except for products described in headings 9903.01.02 … **articles the product of
> Mexico**, as provided for in U.S. note 2(a) to this subchapter

It cites a note, but note 2(a) defines what "a product of Mexico" means; it is not a list
of subheadings. So a note citation only puts a provision on the code path when that note
*is* a list, and which notes are lists is unknown until the PDF is parsed.

**Options.**
- Correct the numbers at Step 7, when the parser produces real ones — one pass, but every
  decision entry in between ships citing evidence already known to be wrong.
- Re-derive now what can be derived offline, and mark the rest as pending.
- Drop the counts and argue the design qualitatively — removes the problem by removing the
  evidence, which is the wrong direction for a submission graded on reasoning.

**Decision.** The second. Corrected in `DATA_INVENTORY.md`, `SCHEMA.md` and the
`db/schema.sql` comments, with counts taken over the ancestor chain marked *(chain)*:

| Figure | Was | Is |
| --- | ---: | ---: |
| `additionalDuties` non-empty | 810 | **512** |
| `general` / `special` non-empty | 2,220 / 2,372 | 2,219 / 2,371 |
| rows containing "provided for in" | 2,556 | 2,456 (2,950 *chain*) |
| provisions citing a U.S. note | 547, 33 numbers | 558 own-row, **973 *chain***, 35 numbers |
| distinct base codes cited | 1,044 | 1,050 |
| exact / prefix / unresolvable | 290 / 685 / 69 | **302 / 698 / 50** |
| cited codes with >1 provision | 439 of 994 (44%) | **507 of 1,000 (51%)** |
| provisions with a CAS number | 1,009 | **1,034** (1,028 distinct) |
| provisions with an exclusion | 206, 681 edges | 233 own-row, **324 *chain***, 864 codes named |
| base rows reached, carrying a footnote | 272 of 975 | **274 of 2,233** |
| three-path split | 2,203 / 558 / 211 | **pending Step 5** |

Unchanged and re-confirmed: every base-schedule figure, since `base.json` hashed
identically throughout; `2922.49.30` cited by exactly four 9902 provisions naming CAS
6212-33-5, 3577-63-7, 619-05-6 and 77820-58-7; `3808.92.15` cited by 34; expansion factors
1 / 4 / 108; `Free` 1,364 and `no_change` 204.

**Tradeoff.** The three-path split was the cleanest sentence in the inventory and is now a
paragraph saying the number is not yet knowable. That is the honest state, and D-0018 does
not depend on it: `9903.01.01` names no base code at all, which can be checked by reading
one row, so `rule.scope` is needed whether the count is 211 or 358.

The deeper cost is to trust in the remaining numbers. They were produced by the same
process that produced the wrong ones, and only the two under identical definitions were
proven wrong by the payload rather than by a changed measurement. Every figure that
survives Step 5 should be replaced by a parser output, which is checkable, rather than an
ad-hoc count, which is not.

**Feeds.** SUBMISSION.md §5, §6

## D-0023 — The parser rebuilds a missing `source_fetch` row from the manifest
**Date:** 2026-08-23 · **Area:** parser, provenance · **Status:** accepted · Extends D-0005

**Context.** Provenance and payloads live on media with different lifetimes. `source_fetch`
sits in the Postgres volume; payloads sit in `./data`, which `docker-compose.yaml:142`
mounts as a bind mount rather than a named volume. `./setup.sh` drops all eleven tables,
and `./cleanup.sh` removes the project's volumes by label without ever naming `./data` —
so both leave a full payload directory beside an empty `source_fetch`. Both are documented
routine operations and `setup.sh` runs dozens of times while a parser is being written.
Three further routes to the same state: the scraper deliberately continues when
`record_fetch` fails (`scrape.py:84-88`), recording `provenance_error` in the manifest
instead; payloads can be staged by hand, as one `curl` already did; and a directory for a
superseded release can never regain its rows at all, because both `exportList` sources are
`pinnable=False` and serve only the current revision.

**Options.**
- Re-run the scraper to restore the rows — the obvious recovery, and the reason this entry
  was nearly not written at all. It is unavailable exactly where it is needed: it requires
  the network, and "runnable against payloads fetched an hour ago, without touching the
  network" is the property that defines Part 2. For a superseded release it cannot work at
  any time.
- Leave `source_fetch_id` NULL and have the UI say provenance is unavailable — honest, and
  smaller; all three foreign keys are already nullable.
- Look the row up by content hash and insert one transcribed from the manifest on a miss.

**Decision.** The third. `resolve_source_fetch_ids` matches on
`(release_name, source_key, sha256)` — content, not file position — and inserts from the
manifest when nothing matches. `run_id` is left NULL: it is the one field the manifest
cannot supply, which makes it the marker separating a reconstructed row from a fetched one
(`WHERE run_id IS NULL`). Nothing is invented; every other column is transcribed from the
record D-0005 already names authoritative.

**Tradeoff.** A row now asserts a fetch that this run did not perform, and a reader who
ignores `run_id` cannot tell. Re-parsing stays safe — the second lookup matches the sha256
the first run inserted, so no duplicate appears — but that idempotency rests entirely on
D-0004's content addressing, so changing how the hash is recorded would start duplicating
rows silently. Wrong if a reconstructed row is ever read as evidence that a fetch happened,
rather than as evidence of what the bytes are.

**Feeds.** SUBMISSION.md §2, §5

---

## D-0024 — Normalise specific duties to dollars, and keep the qualified basis in the unit
**Date:** 2026-08-23 · **Area:** parser · **Status:** accepted

**Context.** The base export prints specific duties in two currencies — `$1.104/kg` and
`46.3¢/kg` — and 22,829 rate strings across `general` and `other` include 1,794 pure
specific and 1,700 compound duties. Storing the printed number as-is means 46.3 and 1.104
sit in the same column meaning amounts that differ by 25×, and no consumer can tell which
is which without re-reading `rate_text`. That is the failure "rates must be computable"
exists to prevent.

A second problem sits beside it. About 200 rows qualify the basis rather than the number:
`7.4¢/kg on drained weight`, `77.2¢/clean kg`, `$1.32/t, including weight of container`. The
amount is perfectly parseable; the basis is not the shipment's gross weight, and a
calculator handed `amount=0.074, unit='kg'` would overcharge silently.

**Options.**
- Store the printed number and a currency column — faithful, and pushes a unit conversion
  into every consumer.
- Store dollars, and drop the qualification from the unit — computable and wrong for ~200
  rows, in the direction of overcharging.
- Store dollars, and keep the qualification inside `rate_specific_unit`.

**Decision.** The third. `rate_specific_amount` is always dollars, cents divided by 100.
`rate_specific_unit` holds the basis exactly as printed, qualification included, so the
unit string never claims more than the schedule said: a consumer matching it against
`hts_base.units` finds `kg` ≠ `kg on drained weight` and asks, rather than guessing.

Two things stay `prose` deliberately. A rate with three or more operands —
`8.8¢/kg on copper content + 3.3¢/kg on lead content + 3.7¢/kg on zinc content`, 94 distinct
strings — would have to be truncated to the two operand slots the schema has, so it is not
parsed at all rather than parsed to an understatement. And an ad valorem rate on a
qualified value (`2.5% on the value of the lead content`, ~6 rows) has no unit column to
carry the qualification, so it stays words.

Three source typos are tolerated on inspection, because they are the same rule spelled
badly: `plus 25%` for `+ 25%`, `inthe`, and `subheading+ 25%`. Each is one row.

**Tradeoff.** 305 of 22,829 rate strings (1.3%) end up `prose` and are not computable; each
gets a `parse_issue` row. `rate_text` is the only place the printed currency survives, so a
UI that shows the parsed amount instead of the text will show `0.463` where the schedule
says `46.3¢` — the reason `rate_text` is documented as the thing to display.

An inherited prose rate propagates: 421 rows carry `rate_kind='prose'` while only 150
printed one, the other 271 having inherited it from an ancestor. That is correct — the
effective rate really is uncomputable — but it means the issue count and the prose row
count differ by design, and 305 issues covers both `general` (150) and `other` (155).

**Feeds.** SUBMISSION.md §2, §5

---

## D-0025 — Reload with TRUNCATE, not DELETE
**Date:** 2026-08-23 · **Area:** parser · **Status:** accepted

**Context.** D-0020 chose delete-then-insert per task inside one transaction. Implemented
as `DELETE FROM hts_base` it took **10.4 seconds** against 0.00s for `TRUNCATE`, on a table
of 26,246 rows. The cause is in the schema: `parent_hts` and `rate_inherited_from` both
reference `hts_base` with `ON DELETE SET NULL`, so deleting the table makes Postgres null
out roughly 26,000 references one row at a time, each one touching three indexes. The COPY
that follows takes 1.58s, so the delete was six times the cost of the actual work.

**Options.**
- Keep `DELETE` — simplest, and the cost grows with every self-reference added later.
- `TRUNCATE ... CASCADE` — fast, but silently empties whatever else references the table.
- `TRUNCATE hts_base, rule_base_match` — fast, and names what it empties.

**Decision.** The third. Both tables are listed explicitly, so a table added later that
references `hts_base` makes this statement fail with a message naming it, rather than being
emptied because CASCADE was convenient. TRUNCATE is transactional in Postgres, so the
guarantee D-0020 relies on — a crash before COMMIT leaves the previous contents intact —
is unchanged.

**Tradeoff.** The statement now has to be kept in step with the schema by hand; forgetting
is a loud failure rather than a quiet one, which is the point. TRUNCATE also takes an
ACCESS EXCLUSIVE lock, so a reader during the reload blocks rather than seeing the old
rows — acceptable for a batch parser, and it would not be for a live service.

**Feeds.** SUBMISSION.md §2

## D-0026 — Rates with more than two terms stay unparsed, because each term has its own basis
**Date:** 2026-08-23 · **Area:** schema, parser · **Status:** accepted

**Context.** `parse_rate` splits a compound rate on `+` and refuses anything with more than
two terms. Challenged in review as an arbitrary cap — if two operands fit, why not three?
Counted across both exports: 138 rate strings, 94 distinct, every one of them in
`base.json` (chapters 26, 65 and 91) and **none in Chapter 99**. 110 have three terms, 28
have four. They are not longer versions of `4.4¢/kg + 8.5%`; each term carries its own
basis:

```
8.8¢/kg on copper content + 3.3¢/kg on lead content + 3.7¢/kg on zinc content
75¢ each + 45% on the case + 35% on the battery
```

Two *ad valorem* terms applying to different parts of one good. `rate_ad_valorem_pct`
means "percent of the entered value", so `45% on the case` cannot go in it without changing
what the column means. A third operand group would not help: the missing concept is a basis
per term, not a slot count.

**Options.**
- Add a third operand group — does not work; it hits `45% on the case` at the second term.
- A `rate_term(owner, seq, kind, pct, amount, unit, basis)` table. Correct, and the shape
  D-0013 already rejected once for turning every duty lookup into a join.
- Hybrid: wide columns for what fits, `rate_term` rows only for what does not, and split
  `prose` into `multi_term` versus genuinely unreadable.
- Leave the cap at two and write the limit down.

**Decision.** The fourth, for this submission. The 138 rows keep `rate_kind='prose'` with
`rate_text` intact and a `parse_issue` row each, so the duty is displayable, citable and
listable — just not computable.

**Tradeoff.** 0.47% of the base schedule carries a duty that cannot be calculated, and the
`prose` bucket now conflates two unlike failures — "known shape, no columns for it" and "an
English sentence" — which makes 305 issues look worse than it is. Accepted because none of
it is in Chapter 99, which is the subject of the exercise. Wrong the moment Part 3 tries to
compute a landed cost in chapter 91, or a future revision writes a Chapter 99 provision in
this form; the hybrid option is the entry that would supersede this one.

**Feeds.** SUBMISSION.md §4, §5

---

## D-0027 — Column 1 Special is stored as printed and never interpreted
**Date:** 2026-08-24 · **Area:** schema, scope · **Status:** accepted

**Context.** 7,099 of 26,246 base rows carry a Special rate, e.g.
`Free (BH,CL,JO,KR,MA,OM,P,PA,PE,SG) See 9822.04.25 (AU) See 9823.07.01-9823.07.07 (S+)`.
Asked in review how eligibility is determined. It cannot be, from these three sources.
Four things are needed and none is present: the SPI code table (`A+`, `S+`, `D`) defined in
General Note 3(a)(iv); the rules of origin, one set per agreement, living in a General Note
each (GN 4 GSP, GN 12 USMCA, GN 25 Korea); the importer's claim, since Special applies only
when an SPI prefix is filed and origin is certified; and, for 199 rows, Chapter 98 itself —
their Special treatment reads `See 9822.04.25`, and **the scraper fetches 0100-9799 and
9900-9999, so chapter 98 is in neither payload**. Those 199 citations point at nothing.
Measured: 20 distinct SPI codes appear, the widest (`OM`) on all 7,099 rows.

**Options.**
- Parse the SPI lists into a `rule_special(hts, spi_code, rate)` table — extracts country
  codes, but eligibility still cannot be answered, so it dresses an unanswerable question
  as a resolved one.
- Fetch chapter 98 and resolve the 199 citations — the scraper handles it with one more
  `Source`, but it widens scope beyond Chapter 99 for 0.8% of rows.
- Keep `special_text` as printed prose, and have the UI name the General Note a reader must
  consult.

**Decision.** The third. `special_text` is stored verbatim and nothing downstream reads it
as structure. Eligibility is a supply-chain question — whether a shirt sewn in Korea from
Chinese fabric is Korean-originating — and the answer is not in the tariff schedule at all.

**Tradeoff.** A user seeing `Free (KR)` is not told that KR is the Korea FTA, which is a
poor experience for the exact novice Part 3 targets. The cheapest fix is a hardcoded SPI
code-to-programme table of about 30 entries with its General Note cited — worth doing, and
distinct from claiming to judge eligibility. Wrong if Part 3 ever presents a duty as "what
you will pay" rather than "the Column 1 General rate", because Special is what an importer
with an FTA claim actually pays.

**Feeds.** SUBMISSION.md §4, §5

---

## D-0028 — Column 2 gets its own inheritance provenance
**Date:** 2026-08-24 · **Area:** schema · **Status:** accepted · extends D-0014

**Context.** D-0014 materialises the inherited Column 1 rate and records the ancestor it
came from. Column 2 inherits on the same tree, and the obvious economy is to let one
`rate_inherited_from` speak for both: the two rates are printed on the same row 11,414
times out of 11,415, so a single column would be right almost always.

Almost. Querying the loaded table for rows where the two chains disagree returns exactly
one:

```
      hts      | rate_text | rate_inherited_from | col2_rate_text | col2_inherited_from
---------------+-----------+---------------------+----------------+---------------------
 9006.59.15.20 | Free      | 9006.59.15          | 20%            |
```

`9006.59.15.20` states its own Column 2 rate while inheriting Column 1. A shared column
would have attributed that 20% to `9006.59.15`, which never stated it.

**Options.**
- One shared `rate_inherited_from` — one fewer column, and wrong for one row.
- A shared column plus a boolean saying the two agree — same size problem, more to read.
- A separate `col2_inherited_from`.

**Decision.** The third. Column 2 inherits on its own chain and records its own ancestor.

**Tradeoff.** A column that is redundant on 26,245 of 26,246 rows. It is worth it because
the one row it exists for is undetectable without it: a wrong `rate_inherited_from` shows
up nowhere in the rate itself, only in the provenance a reviewer would be checking *with*
this column. The frequency argument would also be revision-specific — nothing guarantees
the next revision has only one such row.

**Feeds.** SUBMISSION.md §2

---

## D-0029 — An exclusion is recognised by its lead-in, not by the word "except"
**Date:** 2026-08-24 · **Area:** parser · **Status:** accepted · corrects the exclusion figures in D-0022

**Context.** The first implementation bounded an exclusion clause as `\bexcept\b[^.;]*`.
A unit test failed on a hand-written example, and the reason invalidated an earlier
verification rather than just the code: **codes contain dots**, so `[^.;]*` ended the
clause at the first `.` of `9903.01.02`. The measurement that had concluded "no exclusion
clause names a code outside Chapter 99" was taken with that same expression, so it had
never looked past the first code.

Widening the boundary to admit a dot followed by a digit exposed the real problem in the
other direction: `\bexcept\b` matches 431 clauses, and 217 of them are parentheticals
inside a product description — `Gloves of bovine (except calfskin) leather` — which carve
out no heading at all.

**Options.**
- Keep `\bexcept\b` and rely on only 9903 codes being extracted — works today, and treats
  a description as an exclusion, so any future carve-out phrased with a base code would
  be silently misread.
- Match the lead-ins the schedule actually uses.

**Decision.** The second: `except for products|goods|articles described in` or
`except as provided (for) in`, then to the end of the sentence with a period only
terminating when not followed by a digit. That yields **214 provisions and 859 exclusion
edges**, against the 324 / 864 recorded in D-0022 from the loose expression.

**Tradeoff.** A phrasing not in this revision's four forms will be missed silently, since
there is no "unrecognised except clause" issue kind — the 217 parentheticals would flood
it. The four forms cover every exclusion in 2026HTSRev16, and a fifth appearing in a later
revision is a real risk this does not guard against.

**Feeds.** SUBMISSION.md §2, §5

---

## D-0030 — Leave `rule_country.country_code` NULL rather than hand-write an ISO map
**Date:** 2026-08-24 · **Area:** parser · **Status:** accepted · superseded by D-0032

**Context.** `rule_country` was designed with an ISO 3166-1 alpha-2 column so Part 3 could
turn "China" into a key. Extraction finds **100 distinct country names across 393
provisions**, plus 13 occurrences that name no country at all ("any country", "a member
state of the European Union") which go to `parse_issue`. None of the three sources
contains a country-code list; it would have to be written by hand.

**Options.**
- Hand-write 100 name-to-code pairs — one afternoon, unverifiable against any source in
  this repository, and authoritative-looking whether or not it is right.
- Map the frequent names only — the column then means "code, when we bothered", and a
  NULL cannot be told from a country we could not resolve.
- Leave it NULL and match on `country_name`.

**Decision.** The third. `country_name` is stored cleaned — article dropped, `X or Y`
split into two rows — and matching runs against it, which is what `pg_trgm` is installed
for. `country_code` stays in the schema as the place a sourced mapping would go.

**Tradeoff.** Part 3 matches strings, so "PRC" or "中国" will not find "China" without a
synonym layer. The column existing while empty is its own hazard — a reader may assume it
is populated — which is why both schema references now say so in the row that describes
it.

**Feeds.** SUBMISSION.md §2, §5

## D-0031 — 'a duty of' is a wording variant; 'upon the value of the non-U.S. content' is not
**Date:** 2026-08-24 · **Area:** parser · **Status:** accepted · Extends D-0026

**Context.** Four Chapter 99 provisions landed in `parse_issue` as `unparsed_rate`, and the
first reading was that three shared one bug: `ADDITIVE` requires `+ 25%` and they write
`+ a duty of 25%`. Counting every variant in the payload before touching the regex changed
the answer. 446 rows say "the duty provided", in eight spellings:

```
234  ... applicable subheading + N%                                    additive
204  ... applicable subheading                                         no_change
  2  ... + N%   (no space)          1  ... plus N%      1  'inthe' typo additive
  1  ... + a duty of N%                                                UNPARSED
  2  ... + a duty of N% upon the value of the non-U.S. content         UNPARSED
  1  The duty provided in subheadings 8716.39.00, ... + N%             UNPARSED
```

Only the single bare `+ a duty of N%` is the same rule written differently. The two rows
adding `upon the value of the non-U.S. content` apply the percentage to part of the entered
value, not all of it — the same class as D-0026's `45% on the case`. Widening the regex as
first proposed would have stored them as a plain 25%, overcharging the full value with
nothing in the data to show it.

**Options.**
- Widen `(?:\+|plus)\s*` to swallow `a duty of` anywhere after the operator — gains three
  rows and silently corrupts two of them.
- Leave all four unparsed — safe, and loses a row that is unambiguous.
- Add `(?:a\s+duty\s+of\s+)?` while keeping the `$` anchor, so the variant matches only
  when the percentage is the entire operand.

**Decision.** The third. The anchor is the whole safeguard, so the comment beside the regex
says so: it is the character most likely to be deleted by someone widening the pattern
later. Verified against all 446 rows — 239 additive, 204 no_change, 3 prose, and zero
reclassifications among the 234 already-correct standard spellings.

**Tradeoff.** One row recovered out of 3,098, for a regex that is now harder to read. Worth
it only because the rule it recovers is a Section 232 additive duty, which is the subject of
the exercise rather than a footnote. The remaining three stay `prose` and each is honest:
two have a narrower base, one takes its base from three named subheadings instead of "the
applicable subheading" — see P-k.

**Feeds.** SUBMISSION.md §5, §6

---

## D-0032 — Resolve country codes from the ISO register, exactly, with a five-line alias table
**Date:** 2026-08-24 · **Area:** parser · **Status:** accepted · supersedes D-0030

**Context.** D-0030 left `country_code` NULL because the only way to fill it looked like
hand-writing 100 name-to-code pairs, which would be unverifiable data that reads as
authoritative. Two things changed that.

The first is a correctness argument the earlier entry missed. The schedule names the same
country two ways, and without a code they are two keys:

```
 country_code |    names_in_the_schedule    |                    rules
--------------+-----------------------------+---------------------------------------------
 RU           | Russia / Russian Federation | 9903.05.66, 9903.82.17, 9903.85.67,
              |                             | 9903.90.08, 9903.90.09
```

`Russia` carries two headings and `Russian Federation` three — including `9903.90.08` and
`9903.90.09`, the Section 232 steel pair. A user asking about Russia got two rules or
three depending on which spelling they typed. That is a wrong answer, not a missing
convenience.

The second is that `pycountry` is not a hand-written table: it ships the ISO 3166
register. The objection in D-0030 was to unverifiable data entry, and it does not apply.

**Options.**
- Keep matching on `country_name` and add a synonym table for the spellings that collide —
  fixes Russia, leaves every future collision to be discovered by a user.
- `pycountry` exact matching plus `search_fuzzy` for the rest — resolves 94 of 97 names
  automatically, and `search_fuzzy` guesses: it lands on `RU` for `Russia` today, and
  nothing about it guarantees the next unfamiliar name lands on the right neighbour rather
  than a plausible one.
- Exact matching only, with the residue written down.

**Decision.** The third. `pycountry.countries.get` against `name`, `common_name` and
`official_name` resolves **91 of 97**. Five more go in an `ALIASES` dict, each a rename or
an inversion inside ISO 3166 itself with the reason on the line: `Russia` (ISO says
Russian Federation), `Turkey` (ISO renamed it Türkiye in 2022), `Democratic Republic of
the Congo` (ISO inverts the word order), `Brunei`, `Falkland Islands`. `European Union` is
listed as `NOT_A_COUNTRY` and keeps a NULL, because a bloc having no code is the right
answer rather than a failure.

A name that resolves to neither raises an `unresolved_country` issue. There are none in
this revision: 391 of 397 links carry a code and all six without are the European Union.

**Tradeoff.** A 7.7 MB dependency for 95 codes, and `ALIASES` needs revisiting whenever
ISO renames a country — which is exactly the event it exists to absorb, and the parser
will say so through `parse_issue` rather than silently dropping the country. Exact-only
matching also means a genuinely new spelling fails loudly instead of being guessed at,
which is the intended direction.

**Feeds.** SUBMISSION.md §2

---

## D-0033 — Split a country list on "and" except where the name contains one
**Date:** 2026-08-24 · **Area:** parser · **Status:** accepted

**Context.** Country extraction split captures on both `or` and `and`, which turned
`Bosnia and Herzegovina` into `Bosnia` plus `Herzegovina` and `Trinidad and Tobago` into
`Trinidad` plus `Tobago` — four names, none of them a country. Separately, dropping only a
leading `the` left `of the United Kingdom` behind from "the product of Germany **or of
the** United Kingdom", so that provision never joined the other eight UK rules.

Not splitting on `and` at all was the obvious repair, and it is wrong: `China and Hong
Kong` occurs five times and genuinely is two jurisdictions. That fix would have removed
four bad names and created a fifth, while dropping five China links and five Hong Kong
links.

**Options.**
- Split on `or` only — four bad names become one, and 10 real links are lost.
- Split on both and repair the known casualties afterwards — the repair list is the same
  data as the exception list, applied later and less obviously.
- Split on `and` unless the whole phrase is a country whose name contains one.

**Decision.** The third, with a 14-entry `COMPOUND_NAMES` set — the ISO 3166 names
containing "and". Article stripping now removes a leading `of the` as well as `the`.
Distinct country names went from 100 to **97**, and a query for names not matching
`^[A-Z][A-Za-z'\- ]+$` returns zero rows.

**Tradeoff.** A country whose name contains "and" and is missing from the set gets split
silently — the same failure the fix removes, one name at a time. The set is small enough
to check against ISO 3166 by eye, and once `pycountry` is present (D-0032) it could be
derived rather than written, which would close the gap entirely.

**Feeds.** SUBMISSION.md §2

---

## D-0034 — Segment the notes PDF by the orders it prints in, not by its layout
**Date:** 2026-08-24 · **Area:** parser · **Status:** accepted · settles part of P-e

**Context.** pypdf returns 807 pages of text with every trace of layout gone: no columns,
no indentation, no font. The notes are structured — subchapter, numbered note, lettered
subdivision — and none of that structure survives as markup. What does survive is that the
schedule prints things **in order**, and three attempts to segment without using that
ordering each failed on real data:

- `^(\d{1,3})\.` opened note 44 on the line `44.5 percent ad valorem`. Once 44 was open,
  note 52 — cited 98 times — could never start, because 52 came later in the page order but
  is not greater than 74, which a similar false match had already taken.
- `\bexcept\b`-style greedy subdivision matching accepted `(vvv)`, a label *quoted inside*
  note 20's prose, immediately after `(a)`. That hid the real `(b)` and the 874 codes under
  it — the Section 301 List 1 scope.
- `(?<!\d)\d{4}\.\d{2}` read exactly one code out of `0201.10.500201.10.10`, because the
  second code is preceded by a digit. The lookbehind broke precisely the case it was added
  for.

**Decision.** Three ordering rules, each derived from how the document is printed:

| Rule | Why that shape |
| --- | --- |
| A note opens only if its number is greater than the last accepted one, and only if the period is followed by whitespace or end of line | Notes ascend and skip repealed numbers, so "greater" not "next"; the lookahead is what rejects `44.5 percent` |
| A subdivision opens only if its label is between one and two places after the last, in the sequence a…z, aa…zz, aaa…zzz | Labels are dense, so a jump of seventy is a quotation. Two places of slack absorbs a label lost to a page break. It also rejects roman sub-items — `(i)` after `(b)` is a sub-item, `(i)` after `(h)` is the ninth letter |
| Codes are read by a scan that accepts a match starting at a non-digit **or exactly where the previous match ended** | Admits the flattened four-column runs without mining `2345.67` out of the middle of a longer number |

Classification needs both density and count: `subheading_list` above 50% code characters,
`mixed` above 25%, and fewer than 20 codes is prose regardless — a sentence citing two
headings is dense but is not a list.

**Tradeoff.** Every rule is a heuristic tuned against one revision, and each fails silently
in one direction: a note printed out of order is dropped, a subdivision after a gap of three
is dropped, a genuinely new layout produces fewer notes rather than an error. The only
guard is the count — `parse_notes` raises if it finds no notes at all — and the citation
resolution rate, which is the real acceptance test: **737 of the 800 citations that should
be in this PDF resolve (92%)**, with 126 more correctly identified as chapter notes that
live in a different document. The 63 that do not resolve become `parse_issue` rows when
Step 5 sets `rule_note.note_id`.

345 note records across 9 subchapters, 36,764 listed codes. Note 20(b) — the provision that
defines what Section 301 covers — lands as `subheading_list`, PDF pages 261–265, 874 codes.

**Feeds.** SUBMISSION.md §2, §5

---

## D-0035 — The notes reload deletes instead of truncating
**Date:** 2026-08-24 · **Area:** parser · **Status:** accepted · exception to D-0025

**Context.** D-0025 chose `TRUNCATE` over `DELETE` after measuring 10.4s against 0.00s on
`hts_base`. Applying the same statement to `note` fails outright:

```
psycopg.errors.FeatureNotSupported: cannot truncate a table referenced in a foreign key
DETAIL: Table "rule_note" references "note".
```

Truncating `rule_note` alongside would be worse than slow: its rows are facts extracted
from the Chapter 99 side by a task that ran earlier in the same workflow, and they would be
gone until the next run of that task.

**Decision.** `UPDATE rule_note SET note_id = NULL`, then `DELETE FROM note`.
`note_subheading` cascades; `rule_base_match.note_id` is set null and Step 5 rebuilds it.
The delete costs nothing because there are 345 rows and, after the update, no references
left to chase — the situation D-0025 was avoiding does not arise at this scale.

**Tradeoff.** Two reload idioms now exist in the parser, and which one is right depends on
whether another table points at the one being replaced. The comment on each says which and
why, because the wrong choice is a runtime error in one direction and a slow reload in the
other.

**Feeds.** SUBMISSION.md §2

---

## D-0036 — Expand a note's list once per note, not once per provision that cites it
**Date:** 2026-08-25 · **Area:** schema · **Status:** accepted · extends D-0018

**Context.** The resolver's first version put both paths into `rule_base_match`: the codes
a provision names, and the codes reached through a note it cites. The run did not finish.
Measured offline before rewriting:

```
reach() calls the note path would make : 805,762
worst notes: note 52 (4,166 codes x 98 citing provisions) = 408,268 calls
             note  2 (2,322 codes x 150 citing provisions) = 348,300 calls
average base rows per cited code       : 5.8
=> estimated rule_base_match rows      : ~4,700,000
```

Nearly all of those rows are the same expansion written again: note 52's 4,166 codes,
resolved identically, stored 98 times. This is the product D-0018 refused to materialise
for country-wide provisions, arriving by a different route.

**Options.**
- Materialise it — one table, one query for the app, 4.7 million rows of which ~98% are
  duplicates of each other, and a COPY that dominates the run.
- Don't materialise the note path at all; prefix-match `note_subheading` at query time —
  smallest database, and it puts the matching rule back into every consumer, which is what
  `rule_base_match` exists to prevent.
- Expand per note into its own table, and let the app join through `rule_note`.

**Decision.** The third. `note_base_match(note_id, base_hts, cited_code, match_kind)` holds
**79,087 rows** against the 4.7 million; `rule_base_match` keeps the 16,958 direct
citations and loses its `via` and `note_id` columns, which the split makes redundant. A
provision's coverage is the union of two queries, written out in `SCHEMA.md`.

**Tradeoff.** The app now needs a UNION where it needed a SELECT, and forgetting the second
half under-reports coverage — the same hazard as the country path, and now the second time
this schema has traded a query for a row count. Both are documented in the same place for
that reason. The alternative was a table 60 times larger whose contents are 98% repetition.

**Feeds.** SUBMISSION.md §2

## D-0037 — Read a subdivision citation in both forms it is printed in
**Date:** 2026-08-25 · **Area:** parser, resolver · **Status:** accepted

**Context.** Found while designing Part 3, by counting how many duty layers a single query
returns. `7208.51.00.30` from China returned **14 additive provisions**, among them
`9903.91.01 +25%`, `9903.91.02 +50%` and `9903.91.03 +100%` — three mutually exclusive
rates in force on the same day for the same goods, which cannot be right.

The cause is that a subdivision is printed two ways and only one was read. Inline,
`U.S. note 20(b)`, which `NOTE_CITATION` matched; and in front, `subdivision (g) of
U.S. note 31`, which it did not, because the label precedes the words "U.S. note". **202
provisions** name a subdivision that way. All of them linked to the parent note instead —
and a parent note holds the union of its subdivisions' lists, so:

```
9903.91.06 says   "as provided for in subdivision (g) of U.S. note 31"
note 31(g) is     2504.10.10, 2504.10.50, 2504.90.00, 8505.11.00, 8507.60.00   (graphite, magnets)
note 31 parent is 412 codes, 7208.51.00 among them
```

The provision reached steel through a note about graphite. The prose has four shapes,
including nesting and multiple labels in one clause:

```
subdivision (v) of U.S. note 2                  111 provisions
subdivision (j)(7)(iii) of U.S. note 52          74
subdivisions (d) and (f) of U.S. note 37          5   -- one clause, two citations
subdivision (v)(iii)(a) of U.S. note 2
```

**Options.**
- Match the prefix in the resolver, leaving `cited_text` as it was — the citation text
  would then no longer contain what it was resolved by, which is the split D-0015 exists
  to prevent.
- Match it in the extractor and normalise `cited_text` into the inline form — loses the
  fact of how the provision actually printed it.
- Match it in the extractor, keep `cited_text` verbatim, and record the path beside it.

**Decision.** The third. `rule_note` gains `cited_subdivision`, holding the path exactly as
printed — `(b)`, `(j)(7)(iii)` — and one row is written per label named, so
`subdivisions (d) and (f)` is two citations sharing one `cited_text`. The unique key becomes
`(rule_hts, cited_text, cited_subdivision)`.

Measured after: all 13 note-31 provisions now link to their own subdivision, the additive
layers on Chinese steel fall from **14 to 6**, `unresolved_note` issues from **62 to 1**,
and citations linked rise from 738 to 850.

**Tradeoff.** Only the outermost label can be looked up, because the PDF segmenter isolates
one level — `(j)(7)(iii)` resolves no further than note 52(j). That is recorded rather than
hidden; see D-0038.

**Feeds.** SUBMISSION.md §2, §4

---

## D-0038 — Fall back to the parent note, and say so in a column
**Date:** 2026-08-25 · **Area:** schema, resolver · **Status:** accepted

**Context.** D-0037 made citations name subdivisions. **277 of 977** name one that is not a
row in `note`, so they resolve to nothing. Almost all are note 2 — the IEEPA reciprocal
tariff, the most frequently applied duty in the schedule.

The cause is the segmenter, and it is not a small bug. `_split_subdivisions` accepts a
label only if it is the next in sequence or within `MAX_GAP`, which exists to stop a label
quoted inside prose from opening a subdivision. Note 2's top-level labels run
`(a)(b)(c)(j)(k)(l)(m)(s)(t)(u)(v)(x)` — a gap of six between `(c)` and `(j)` — so
everything from `(j)` on was rejected. Worse, a `(d)` **three levels down** (`2(v)(xxv)(d)`,
PDF page 209) sat exactly at `highest + 1` and was accepted as a top-level subdivision, so
the row stored as `note 2(d)` holds the wrong text.

Doing this properly means reconstructing a three-level outline whose labels are reused at
each level, from text with no indentation: verified, pypdf reports leading whitespace 0 on
every line of the notes PDF. The PDF does print the full path in a compiler's note —
`[Compiler's note: List for 2(v)(xxv)(d) may appear or continue on a subsequent page.]` —
but only on **3 pages** of 807, so it cannot carry the segmentation.

**Options.**
- Raise `MAX_GAP` — admits `(j)`, and re-admits the `(vvv)` failure D-0034 built the cap to
  stop, while leaving the mis-accepted nested `(d)` in place.
- Link nothing when the subdivision is missing — never over-reports, and strips coverage
  from 111 provisions of the reciprocal tariff, which is most of what a user asks about.
- Rebuild the nested outline today — correct, and estimated at 60–90 minutes with no
  guarantee of being right the first time, against a same-day deadline for Part 3.
- Fall back to the parent and record that the match is inexact.

**Decision.** The fourth. `rule_note.match_precision` takes one of four values, and every
consumer must read it:

```
exact            note_id is the note the citation named                 573
parent_fallback  note_id is an ancestor; coverage is WIDER than scope   277
chapter_note     names a note in another chapter's document, absent     126
unresolved       nothing matched; a parse_issue says so                   1
```

`parent_fallback` also raises a `subdivision_not_segmented` issue naming the label. Part 3
must show it on the provision — "this cites note 2(v), which was not isolated; the coverage
below is note 2 as a whole" — and link the note text and PDF page so a reader can settle it.

**Tradeoff.** 277 citations show coverage broader than the provision truly has. This is
the first place in the schema where a *wrong-but-labelled* answer is preferred to no
answer, and it is only defensible because the label is machine-readable and the UI is
required to surface it. Wrong the moment a consumer joins `rule_note` without reading
`match_precision` — which is why the column is NOT NULL with no neutral default.

**Feeds.** SUBMISSION.md §2, §4, §5

---

## D-0039 — Read codes a note names in prose, but only when it never says "not apply"
**Date:** 2026-08-25 · **Area:** parser · **Status:** accepted

**Context.** After D-0037, `9903.91.04` (+25%), `9903.91.07` (+50%) and `9903.91.08`
(+100%) still landed on Chinese steel. Their notes are classified `prose` and yielded no
codes, so the provisions kept the scope they were given before any note was read —
`by_country_all_goods` — and applied to every Chinese import. `9903.91.08` is rubber
gloves; it was adding 100 points to hot-rolled steel.

The notes do name their codes, just in running text rather than on a list page:

```
31(i)  "products of China classified in 8-digit subheading 4015.12.10"
31(e)  "facemasks of textiles, disposable, described in statistical reporting number 6307.90.9870"
31(g)  "(1) 2504.10.10 (2) 2504.10.50 (3) 2504.90.00 ..."
```

`_content_kind` calls a body prose below 20 codes, and `_add` returns early for prose, so
these were dropped. Counted across the whole PDF: **49 prose notes name codes and never say
what they do not apply to; 107 more do both in the same body.**

**Options.**
- Extract codes from every prose note — picks up all 202 codes in the clean notes and also
  1,667 from bodies that say "shall not apply to" in the same breath, inverting the meaning
  of the provision.
- Extract only from numbered items `(n) CODE` — catches 31(g), misses 31(e) and 31(i),
  which is where the 100% duty was.
- Extract behind a scoping lead-in, from notes with an affirmative statement and no
  negative one.

**Decision.** The third. A prose note is read only when it matches `applies to` / `apply to`
and does **not** match `not apply` / `shall not`; codes are then taken from numbered items
and from behind `subheading` / `statistical reporting number`. A code sitting loose in
running text does not carry which sentence it belonged to, so the 107 mixed bodies are left
alone rather than guessed at.

Measured after: additive layers on Chinese steel **6 → 3**, and the one that reaches steel
by code does so through note 31(b), which is the steel list. `mixed` notes rise 23 → 63.

**Tradeoff.** The 107 mixed-direction notes still yield nothing, so provisions citing them
stay `by_country_all_goods` and over-report — `9903.88.04` and `9903.88.09` are the two that
survive on the steel query. Reading them needs sentence-level scope, not pattern matching.
The rule is also a heuristic on wording: a note that states its scope without the words
"applies to" is not read, and one that mentions "shall not" incidentally is skipped.

**Feeds.** SUBMISSION.md §4, §5

---

## D-0040 — A note-level record takes the union of its subdivisions, not its own density
**Date:** 2026-08-25 · **Area:** parser · **Status:** accepted · extends D-0034

**Context.** After D-0037 and D-0039, 164 provisions still could not reach a base code
through the note they cite. Partitioning them by what would actually unblock each one:

```
44  cite a parent note whose own subdivisions already carry codes
54  cite a note that points at another note                          -> D-0041
48  cite a note that says both what it applies to and what it does not
27  cite a note that names no code at all -- a quota trigger price, a definition,
    an ad valorem equivalence formula. Nothing to extract, by any method.
```

The first group is `U.S. note 20` alone, cited by 38 provisions. `_add` reads a note-level
record's codes off its own body, and note 20's body is **912,964 characters** — its lists
are in there, but `_content_kind` divides code characters by body characters, the ratio
falls under the threshold, and the note was stored as prose with zero codes.

**Options.**
- Lower the density threshold — it exists to stop a sentence quoting two headings from
  becoming a list, and lowering it far enough for note 20 removes that protection entirely.
- Special-case note-level records to skip the classifier — silently makes every parent a
  list, including parents that genuinely are prose.
- Take the union of the subdivisions that were already extracted.

**Decision.** The third. When a note-level record ends with no codes and its subdivisions
have some, it inherits their union and is reclassified `mixed`. The semantics were already
the intent — the existing comment says a note record repeats its subdivisions' codes
"because a provision citing the note without a subdivision is pointing at all of them" —
this stops that intent depending on how much prose surrounds the lists.

Measured: `note_subheading` 36,896 → 48,170.

**Tradeoff.** A parent whose subdivisions were themselves mis-segmented inherits the
mistake — note 2 is exactly that case, and D-0038's `parent_fallback` is what keeps it
visible. The union is also unordered with respect to the printed page: `ordinal` becomes
the order subdivisions were parsed in, not the order the codes appear in the PDF.

**Feeds.** SUBMISSION.md §2, §4

---

## D-0041 — Follow a note's pointer to another note, but only the scoping one
**Date:** 2026-08-25 · **Area:** resolver · **Status:** accepted

**Context.** 54 of the 164 blocked provisions cite a note that lists nothing itself and
instead points at another note. Notes point at each other 224 times in this revision, and
the two directions are distinguishable by the words used:

```
'the subheadings enumerated in U.S. note X'    70 times   what the duty COVERS
'and provided for in U.S. note X'            154 times   an exclusion FROM it, and always
                                                          after a 9903 heading:
                                                          "...granted an exclusion by the
                                                          USTR and provided for in: (1)
                                                          heading 9903.88.33 and U.S. note
                                                          20(ll)..."
```

Following every pointer would file all 154 USTR exclusion lists as the *scope* of the duty
they exempt goods from — the exact inverse of what the note says.

**Options.**
- Follow every note-to-note reference — inverts the meaning on the majority of them.
- Follow none, and leave the 54 provisions unable to reach anything.
- Follow only `subheadings enumerated in`, the phrase that states coverage.

**Decision.** The third, in the resolver rather than the parser: a note pointing at another
note is interpretation, and `note_subheading` is the fact layer (D-0015). A note with no
matches of its own inherits the matches of the notes it enumerates, to a depth of 2 with a
visited set — one hop is what the data uses, and the cap is a backstop against a cycle
rather than a modelled depth.

Measured, together with D-0040: `note_base_match` 79,250 → 136,325; provisions rescoped to
`by_code` 304 → 343; `by_country_all_goods` 99 → 67.

**Tradeoff.** The phrase is a heuristic on wording. A note that states coverage in different
words is not followed, and `9903.88.04` is the visible casualty — its note 20(g) says "as
provided for in **this note**", a self-reference this does not resolve, so it stays
country-wide and over-reports. Following "this note" would hand it all of note 20's 11,000
codes, which is worse.

**Feeds.** SUBMISSION.md §2, §4, §5

---

## D-0042 — Widen country extraction on evidence, not on imagination
**Date:** 2026-08-25 · **Area:** parser · **Status:** accepted · extends D-0033

**Context.** A control query — laptops, `8471.30.01.00`, from China — returned 14 additive
provisions, among them `9903.01.15` (Canada) and `9903.02.43` (Myanmar). They were not
filtered out because they have no `rule_country` row at all, so a country filter cannot see
them. Querying for provisions whose prose names an origin and which have no row found
**21** such provisions, and they fail in three distinct ways:

```
9903.01.15  'Potash that is a product of Canada'      subject is not 'articles/products/goods'
9903.02.43  'the product of Myanmar (Burma)'          a parenthesis ends the name
9903.01.51  'the product of Cote d`Ivoire or Namibia' not ASCII; the apostrophe is a backtick
                                                       on one line and a curly quote on another
9903.02.15  'the product of Japan with an ad valorem' 'with' was not a clause terminator
```

**Options.**
- Enumerate the country names the schedule uses — a hand-written list, which D-0032
  rejected once already and which the next revision breaks.
- Widen the name character class to admit anything — the capture then runs into the rest of
  the sentence.
- Widen the class and let the terminators carry the weight, and normalise the punctuation
  before the ISO lookup.

**Decision.** The third. The subject may be any word before `that is a product of`; the name
is lazy and stops at the first punctuation or clause word, with `(`, `with` and `classified`
added to that set; and `country_code` normalises curly quotes and backticks to a straight
apostrophe before the register lookup, which resolves both spellings of Cote d'Ivoire
without an alias claiming they are different names. `area` joins `any` and `a member state`
as generic, from "the product of any country **or area** including the United States".

Measured: `rule_country` 397 → 422 links; unresolved country names 11 → 0, leaving only
`European Union`, which is correctly not a country. Additive layers on the laptop control
**14 → 8**, and every survivor either names China or is genuinely "any country" — the IEEPA
universal baseline, which does apply.

**Tradeoff.** A lazy capture bounded by terminators fails open: a name followed by a word
not in the terminator set runs on, and the result is a `parse_issue` rather than a wrong
code, because it will not match the ISO register. `unnamed_country` issues rose 13 → 36 as
the wider subject admits more generic phrasings, which is the correct direction — they are
recorded, not silently dropped.

**Feeds.** SUBMISSION.md §2, §5

---

## D-0043 — Read effectivity from the prose, and keep status apart from dates
**Date:** 2026-08-25 · **Area:** schema, parser · **Status:** accepted · settles P-i

**Context.** The steel query returned `9903.91.14 +100%` — a duty on ship-to-shore gantry
cranes that does not begin until **10 November 2026**, shown as current on 25 August 2026 —
alongside nine `9903.88.5x` provisions that ended on 31 December 2020. Presenting either as
applicable is the plain "wrong information" failure, on the first example the app shows.

Nothing in the sources states this as a field. The JSON export has no effective or expiry
column at all; the PDF marks an expired row by shading it grey, which text extraction
destroys. Two signals survive, both in the prose, and they are different in kind:

```
44  'Effective with respect to entries on or after <date>[, and through|before <date>]'
70  compiler's asides in square brackets:
      'provision terminated. See 90 Fed. Reg. 37963.'          36  -- NO DATE
      'provision terminated as of February 7, 2026.'            6
      'Duties suspended except on certain goods entered from FTZs'  23  (from a superior
                                                                        text, and it does
                                                                        govern the rows
                                                                        beneath it)
      'provision suspended. See 90 Fed. Reg. 50729.'            2
      'expired at the close of Dec. 31, 2020.'                  1
```

**Options.**
- Two date columns only — leaves the 36 dateless terminations looking current, which is the
  larger group and the one the schedule is most emphatic about.
- A single `is_active` boolean — cannot answer "in force on which date", and the whole point
  is that `9903.91.06` starts in January and `9903.91.14` in November.
- Dates plus a status plus the aside verbatim.

**Decision.** The third. `rule` gains `effective_from`, `effective_to`, `status`
(`in_force` / `terminated` / `suspended`) and `status_note`. In force on a date D is

```sql
status = 'in_force'
  AND (effective_from IS NULL OR effective_from <= D)
  AND (effective_to   IS NULL OR effective_to   >= D)
```

`effective_to` is always the **last day in force**, so `and before January 1, 2026` is stored
as `2025-12-31` and a caller compares with `<=` without knowing which word was printed.
`status_note` keeps the aside verbatim because it carries the Federal Register citation —
the only actionable thing in it, since this dataset holds the tariff line and not the legal
instrument that made it.

The extraction is anchored on `effective with respect to entries` and nothing looser. The
same descriptions carry a transit carve-out — "Except for goods loaded onto a vessel ... in
transit before 12:01 a.m. eastern daylight time on April 9, 2025" — and a pattern that
merely looked for `on or after <date>` reads one as the other on `9903.01.51` and
`9903.02.43`.

Measured: 3,028 `in_force` · 45 `terminated` · 25 `suspended`; 52 provisions carry a date.
On 2026-08-25: 3,005 in force, 26 expired, 5 not yet. The steel query's layers drop from 2
to 2 and the laptop control's from 8 to 6 — `9903.01.63` (34% on China) is *suspended, see
90 Fed. Reg. 50729*, and `9903.88.16` (§301 list 4B, 15%) likewise.

**Tradeoff.** This sees only what the prose says. The grey shading is gone, so a provision
expired by shading alone still reads `in_force`, and 3,028 of 3,098 provisions carry no
signal at all — the schedule states a window only when it is unusual. The status is also
read from ancestors, which is right for a superior text's 'Duties suspended ...' and would
be wrong if a coded parent were ever terminated while a child was not; no such case exists
in this revision, and nothing checks for one.

**Feeds.** SUBMISSION.md §2, §4, §5

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
- ~~**P-i · Effectivity.**~~ Settled by **D-0043**: `effective_from`, `effective_to`,
  `status` and `status_note` on `rule`, read from the two prose signals. The grey shading is
  still lost, and that limitation is recorded there.
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
- **P-j · Chapter 98 is outside the fetch range.** 199 base rows resolve their Special
  treatment through `See 98xx.xx.xx`, and the scraper fetches `0100-9799` plus `9900-9999`,
  so chapter 98 exists in no payload. Decide whether to add it as a fourth `Source` — the
  scraper needs one entry in `SOURCES` and nothing else — or to leave the citations
  unresolved and say so on screen. See D-0027.
- **P-k · An additive duty whose base is named, not implied.** `9903.91.12` reads "The duty
  provided in subheadings 8716.39.00, 8716.90.30 or 8716.90.50 + 100%". Every other additive
  provision modifies "the applicable subheading" — whatever the goods classified under —
  while this one names the base itself. `rate_kind` has no operator for it and it stays
  `prose`. One row today; decide whether a `rate_base_hts` column earns its place, or
  whether `rule_edge` already carries enough to reconstruct it.
