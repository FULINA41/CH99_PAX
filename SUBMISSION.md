# Submission

Full reasoning lives in `docs/DECISIONS.md` (one entry per decision, cited below as `D-000x`)
and `docs/JOURNAL.md` (what was run and what it printed). This file is the map to those, not
a restatement of them.

**Demo video:** https://www.loom.com/share/2799e879970441aeba013863e3005292

## 1. How to run it

```bash
git clone <repo> && cd chp99-takehome
./dev.sh                       # stack up: db, hatchet, worker, api, app — leave running
./setup.sh                     # apply db/schema.sql; prints \dt with empty tables

cd workflows && uv sync
uv run python -m scrape_run    # Part 1 — fetches 3 sources into data/raw/<release>/
uv run python -m parse_run     # Part 2 — reads that directory, no network, fills Postgres
```

Each prints a reconciliation table. Scrape ends `3 fetched → /data/raw/<release>/`; parse
ends with row counts per table and a `parse_issue` breakdown — nonzero is expected (§5).
Run either again and the counts don't move; scrape reports `unchanged`, parse reproduces
every table exactly, because both stages reload from a `TRUNCATE`/full-COPY (D-0004, D-0025).

**Part 3 has no separate start command** — `./dev.sh` already launched `api` and `app`
alongside the database, and both are read-only over whatever Part 2 last wrote, so they
just need Part 2 to have finished. Once it has: `localhost:3000` is the app (open it on
the first worked example on `/`), `localhost:8000/docs` is the API, `localhost:8080` is the
Hatchet UI. `./cleanup.sh` tears everything down to nothing.

```bash
cd workflows && uv run pytest          # 134 tests, no db/network
cd api       && uv run pytest          # 24 tests, no db/network
docker compose exec -T app npx vitest run     # 6 component tests
cd api       && uv run python -m audit --codes 2000   # 20,000 queries against a live db
```

## 2. The data model, and why

**The big picture.** 15 tables in three layers over the three source payloads:

```
   SOURCE                    FACT LAYER                    INTERPRETATION LAYER

   base.json        →   hts_base (26,246)
   ch99.json        →   rule (3,103), rule_edge,      →   rule_base_match (16,958)
                         rule_country, rule_identifier
   ch99-notes.pdf   →   note (350), note_subheading,  →   note_base_match (141,656)
                         rule_note

   parse_issue (869)  ←──  everything that fit none of the above
```

Plus three small tables outside that grid: `source_fetch` (provenance — which download and
release each row came from), `rule_coverage` (one precomputed aggregate, §3), and
`trade_programme` (the one editorial table — "Section 301" is a label we added, the schedule
itself never names a statute, D-0045).

**The core relationship.** A `rule` row (a Chapter 99 line) doesn't classify a good — it
modifies the duty on a good already classified in `hts_base`, and it says so three different
ways: naming a base code directly, naming a `note` that lists codes, or naming a country and
no code at all. The scaffold's three starter tables had no way to express any of that, which
is why the interpretation layer exists and why it outgrew the fact layer roughly ten to one
(`note_base_match` at 141,656 rows against `note`'s 350) — resolving "what does this note
actually cover" is where most of the real work went. The reasoning behind each shape:

- **`hts_base` and `rule` hold only coded rows** (26,246 / 3,103) — heading rows carry no
  rate, but their prose scopes every descendant, so it's folded into `full_description`
  before any extraction runs. Cross-references are read from the folded text, which is how
  the schedule is read legally. (D-0012)
- **`rate_kind` is an operator, not a label** — `free | replace | additive | no_change |
  prose | none`, with the operand(s) beside it (`rate_ad_valorem_pct`,
  `rate_specific_amount`, `rate_specific_unit`). A compound duty like `4.4¢/kg + 8.5%` fills
  both operand groups; "in lieu of" vs. cumulative is a second column (`cumulation`), read
  from the note, not guessed from the rate string. (D-0013, D-0058)
- **A citation is stored twice, once as fact and once as interpretation** — `rule_edge` keeps
  the code exactly as printed, unresolved, no foreign key, so a dead or noisy citation is
  recorded rather than silently dropped; `rule_base_match` is the resolved join, with how it
  was reached (`exact` / `prefix`, `description` / `note`). Same split for notes:
  `note_subheading` is the note's own printed list, `note_base_match` its base-code
  expansion — kept as one row per note rather than once per citing provision, because the
  naive version was ~4.7M rows of the same expansion repeated. (D-0015, D-0016, D-0036)
- **A provision's scope can be a country with no code at all** — `rule.scope` distinguishes
  `by_code` from `by_country_all_goods`; the latter has no `rule_base_match` rows by design
  and is applied through `rule_country` alone. Materialising it against all 26,246 base rows
  was measured and rejected — it's the same blow-up as the note-expansion problem, one level
  up. (D-0018)
- **Goods identity is its own table** — 44% of cited base codes are cited by more than one
  provision (`3808.92.15` by 34), and the code alone doesn't choose between them; where the
  schedule gives a CAS number, `rule_identifier` makes that choice exact instead of fuzzy.
  (D-0019)
- **Nothing unparseable is discarded** — `parse_issue` is a first-class table, not a log
  file; an empty one after a full run would mean the parser stopped checking, not that the
  data is clean. (D-0017)

Full column-by-column reference: `docs/SCHEMA.md`. Every shape above was revised at least
once against a real measurement rather than a first guess — the note-expansion blow-up
(D-0036) and the coverage-materialisation reversal (D-0044 → D-0047) are the two largest;
`docs/DECISIONS.md` has both, including the wrong number that drove the first version.

## 3. Part 3: what you built, and why that

**Not a duty calculator — a teaching instrument over real provisions.** A calculator has to
be right about a number, and the number can't be got right from these three sources: stacking
order lives in CBP filing instructions, FTA eligibility lives in the General Notes, exclusion
membership is a question about the goods. What the site optimizes for instead: *can a reader
who's never opened a tariff schedule say, after one screen, why this figure and where it came
from.* Three consequences:

1. **Money is optional** — supply a value and layers carry dollars; leave it out and the
   mechanism still explains itself. Nothing is guessed to fill a column.
2. **Three worked examples are the front door**, not decoration — a novice has no code to
   type. Each is picked to teach one mechanism: multi-layer stacking with exclusions
   (Chinese steel), choosing between competing candidates by CAS number, and a clean zero-hit
   control (the same steel code from Germany).
3. **"What this can't tell you" is a first-class section**, not a footer — every entry says
   why these sources can't answer and names a specific external source that can.

**Storage layer**: `api/duty/` is the one place the computation exists — the page and
`GET /duty/{hts}?country=` return the same object, so any number on screen can be checked
against JSON directly (D-0048's no-ORM choice serves the same transparency goal: raw SQL a
reviewer can read next to the schema, Pydantic only on the way out). The frontend computes
nothing; `src/lib/api.ts` is the only file that knows where the API lives.

**Precomputed, and why**: only `rule_coverage` (2,829 rows, one per provision, rebuilt by a
`materialize` Hatchet task after `resolve_citations` in the same Part 2 run — never a stale
window). Two more derived tables were designed, measured against the loaded database, and
*not* built: an exclusion closure table (the graph has no depth to close — 859 edges at
depth 1, 23 at depth 2, then a cycle), and a per-base-code profile (the number carries no
information — the reciprocal-tariff action genuinely covers almost everything). `D-0044`
records the measurements that killed both; `D-0047` records the one that brought coverage
back after the first version of that decision measured the wrong query shape.

**Left out**, deliberately: no LLM anywhere (an earlier build-time summary layer was removed
— D-0055, §6), no classification (search matches the schedule's wording, says so), no
natural-language querying, no agent. `docs/PART3_APP.md` §11 has the full list with reasons.

## 4. What you'd do with another week

- **Three residues in `parse_issue` are visible but unfixed**: 280 rows where a citation
  named a subdivision the PDF segmenter couldn't isolate (`subdivision_not_segmented`,
  D-0038 — the citation falls back to the parent note, which is wider than the text asked
  for); 226 cited codes that resolve to no row in this revision (`unresolved_code`); and
  1 note citation matching no note at all. (Of `rule_note`'s 982 citations, 127 are
  unlinked — 126 of those correctly point at another chapter's note, out of scope by
  design, leaving that 1 genuine miss.)
- **`special` (Column 1 preferential rates) is stored as printed and never interpreted**
  (D-0027) — needs the HTS General Notes' SPI table and rules of origin, none of which are in
  these three sources. Every FTA-eligible query currently under-states what a qualifying
  importer could actually pay.
- **Stacking order between simultaneous §232/§301 actions is asserted, not sourced** past
  what a governing note states explicitly (D-0058) — where two provisions are both
  uncertain replacements, the site reports a range rather than picking one, which is honest
  but not an answer.
- **Frontend has thin test coverage** — `vitest` covers one component (`FormulaStrip`,
  D-0070, added after a dead anchor link shipped for two commits undetected); the page
  components themselves fetch and are untested, because there's no request fixture yet.
- **Contrast was checked with a hand-rolled oklch→sRGB script**, not a browser audit tool,
  and the `*-soft` chip backgrounds were never measured (§6).
- **One resident revision** (D-0020) — re-parsing overwrites in place; historical payloads
  survive on disk in `data/raw/` but aren't queryable without a re-parse.
- **Expired provisions aren't marked** — the PDF signals expiry with grey shading, which
  text extraction destroys, and the JSON export has no date field; only provisions that state
  a date in their own prose are dated (D-0043).

## 5. Assumptions

Where the sources were ambiguous, the reading is recorded in `docs/DECISIONS.md` and the
provision that forced it is cited there. The ones that change an answer on screen:

| Assumption | Why | Where |
| --- | --- | --- |
| Chapter 99 rates replace the ordinary rate unless a note says otherwise | U.S. note 1 to subchapter III says *"in lieu of"*; 31 notes override with *"Notwithstanding U.S. note 1"*. The note is read per provision, not assumed | D-0058 |
| A provision that names countries reaches no others | The schedule states the origin in prose only. Provisions naming a bloc (*"a member state of the European Union"*) are expanded to members | D-0056 |
| A provision with no date is in force | Expiry is marked by grey shading in the PDF, which text extraction destroys. Only dates written into the description are read | D-0043 |
| Column 2 applies to Cuba, North Korea, Russia, Belarus | General Note 3(b) is in none of the three sources. This list is **editorial**, and the UI says so | D-0054 |
| "Section 301" / "Section 232" are our labels | The schedule never names a statute — across 350 U.S. notes the only one mentioned is *section 201*. The mapping is one small editorial table | D-0045 |
| Exclusions are reported, not applied | Whether an exclusion covers a shipment depends on the goods, not the code. They are listed and counted; they never move the number | D-0069 |

Two things the site therefore does not claim. It does not give **one** rate when the sources
don't determine one — competing replacements are shown as a range, and `api/audit.py` checks
that property over 20,000 queries. And it does not classify goods: search matches the
schedule's wording, not your shipment.

**Release.** All figures in this repository were measured against **2026HTSRev17**, the
release current on 2026-08-27. The HTSUS is revised several times a year and `data/` is
gitignored, so a later clone fetches whatever is current then and counts will differ.
`source_fetch` records the release every row came from, and the UI footer shows it.

## 6. Where you used AI tools

Built with Claude Code (agentic, in this repo) throughout — scraper, parser, schema, API,
frontend, and this document. Two things worth stating plainly rather than leaving implicit:

**An LLM layer was built into Part 3, then removed entirely.** A build-time step generated
one-sentence plain-language summaries of each provision (Haiku, committed as a versioned
JSON artifact, never called at request time) so a novice reader wasn't facing raw statutory
prose. Audited against its source text before removal and found no factual errors, but judged
low-value against its complexity — the structured page already said what the summary said,
just less pleasantly — and cut (D-0055). The finished app calls no model at runtime or build
time; `api/` and `app/`'s only dependencies are FastAPI, uvicorn, psycopg, pycountry, and
Next.js itself.

**Shipped without full verification, stated plainly rather than glossed over:**

- Contrast ratios for body/label text (§4) were computed with a hand-rolled oklch→sRGB
  script, not a browser accessibility auditor; the `*-soft` chip backgrounds specifically
  were never measured.
- Two SQL fixes (a `DISTINCT ON` dedup, an ellipsis truncation) have no unit test — `api/tests`
  has no database fixture — and were checked against the live database only, once.
- Page-level frontend components (as opposed to the one tested presentational component,
  `FormulaStrip`) have no test coverage; every UI claim about them rests on rendering the
  page and reading it.

**Where the agent got something wrong that mattered**, per `docs/JOURNAL.md`: an origin veto
that read "no country rows" as "no restriction" instead of a `scope` column, undercounting a
real duty stack by two layers before a user-reported case caught it (D-0056); a `float`
rate column that printed `$0.009000000000000001/each` on 625 rows before being read as
`Decimal` (D-0060); two invariant violations in the worst-case ceiling calculation, both
found by the audit harness rather than by review (D-0059); and two claims in this project's
own reasoning that had to be reversed after stopping at the nearest evidence instead of the
governing note — documented in the journal as a named recurring failure mode, not smoothed
over.
