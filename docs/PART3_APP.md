# Part 3 — The app

A full-stack app over the parsed database. It answers one question — *what does Chapter 99
do to this good from this country, and how do you know* — and it answers it with the
working shown.

Reasoning behind the choices below is in [`DECISIONS.md`](DECISIONS.md); measured behaviour
and verification output are in [`JOURNAL.md`](JOURNAL.md); every table and column is in
[`SCHEMA.md`](SCHEMA.md).

---

## 1. What it is for

The brief says: *build something that explains how tariffs work to a novice*, and *think of
yourself as the primary user*.

So this is **not a duty calculator**. A calculator would have to be right about a number,
and the number cannot be got right from these three sources: stacking order lives in CBP's
filing instructions, free-trade eligibility lives in the General Notes, and whether a
shipment is on an exclusion list is a question about the goods. An app that produced a
confident total would be wrong in a way its user could not detect.

It is a **teaching instrument built out of real provisions**. The measure of a screen here
is not whether it produced a figure but whether a reader who has never opened a tariff
schedule can say, afterwards, *why* that figure and *where it came from*. Three consequences
run through everything below:

1. **Money is optional.** Supply a declared value and the layers carry dollars; leave it out
   and the page still explains the mechanism. Nothing is guessed to fill a column.
2. **Worked examples are the front door**, not decoration. A novice does not know a code to
   type, and "search for your product" is a worse first instruction than "look at what
   happens to steel".
3. **What the data cannot settle is a first-class section**, not a footer. Every entry says
   why these sources cannot answer, and names a specific place that can.

## 2. Where it sits

```
   Postgres, 15 tables  ← written by Part 2, read-only from here on
        │
        ▼
  ┌────────────────────────────────────────────────────────┐
  │ api   FastAPI :8000     the duty computation lives here │
  │   duty/applicable.py   which provisions reach this good │
  │   duty/compute.py      rate_kind as an operator         │
  │   duty/explain.py      sorts them into what they are    │
  │   reference/           the two editorial additions      │
  └────────────────────────────────────────────────────────┘
        │  HTTP, server-side
        ▼
  ┌────────────────────────────────────────────────────────┐
  │ app   Next.js :3000     draws pages, computes nothing   │
  └────────────────────────────────────────────────────────┘
```

**The computation exists once.** `/duty/7208.51.00.30?country=CN` returns the same object
the page renders, so every number on screen can be checked against JSON without reading the
UI's source. That is the strongest form the promise "the reasoning is transparent" can take:
the human view and the machine view are the same view.

The frontend holds no domain logic — no rate arithmetic, no filtering by date, no deciding
what an exclusion means. It renders. `src/lib/api.ts` is the only file that knows where the
API is, and `src/lib/types.ts` mirrors `api/models.py` by hand, because the OpenAPI document
at `/docs` is the contract and one file of types is cheaper to read than a generator in the
build (D-0048).

## 3. The five screens

| Route | What it is |
| --- | --- |
| `/` | The three worked examples, each with a sentence saying what it teaches |
| `/search?q=` | Keyword → candidate base codes, with how many trade programmes reach each |
| `/duty/[hts]` | **The main screen.** The formula, then one card per term |
| `/rule/[hts]` | One provision: text, rate, dates, coverage by both paths, both directions of its exclusion edges |
| `/note/[id]` | One U.S. note: text, the codes it lists, its siblings, and every provision citing it |

Every link on a duty page resolves. A provision number opens the provision; a cited note
opens the note with its PDF page; an exclusion group opens the note that granted it.

## 4. The formula, and the cards under it

`rate_kind` is an operator and the columns beside it are its operands (D-0013). The screen
carries that shape unchanged:

```
  6.5%       + 25%          ± 0            =  31.5%
  ────────     ──────────     ──────────       ────────
  Column 1     9903.91.01     19 exclusions    $31,500
  inherited    Section 301    could remove
  from 7208.51 — China        one of these
```

| Operator | Mark | Colour | From |
| --- | --- | --- | --- |
| adds to the base rate | `+` | red | `rate_kind = 'additive'` |
| stands in for it | `→` | green | `replace`, `free` |
| changes nothing by itself | `±` | grey | `no_change` — the exclusions |
| stated in words | `?` | amber | `prose` |

**The mark and the colour always travel together.** `+ → ± ?` distinguish the four operators
on their own, so nothing is lost when the colours are not seen.

Three honesty constraints the formula is not allowed to break:

- **A total may be an expression rather than a number.** `25% + 46.3¢/kg` is written as
  that. Percentages and per-unit duties are never collapsed into one figure.
- **The assumption sits beside the equals sign**, not in a footer, and it says *maximum
  exposure*, never *what you owe*. It no longer claims the schedule is silent on stacking:
  it is not, and §6 says what it does state.
- **Expired, not-yet-effective and non-computable terms are not in the formula.** They are
  below it with their dates.

Each formula cell links to a card, and the cards run in derivation order. A card carries
three things: the provision's own sentence, *why this is in your answer*, and the metadata
that supports it — dates, countries named, CAS numbers, reach, carve-outs.

## 5. Three ways a provision reaches your goods

The single most important query in the app, and the one easiest to get wrong:

```
A  it names the code itself          rule_base_match
B  it cites a note whose list        note_base_match ⋈ rule_note        ← easy to forget
   contains the code
C  it names the country and          rule.scope = 'by_country_all_goods'
   limits no goods                     ⋈ rule_country
```

Path B is most of subchapter III. `9903.91.01` writes down no product code at all and
reaches steel only through U.S. note 31(b) — a list of 349 codes printed in a PDF. Querying
`rule_base_match` alone under-reports by nearly everything a user came for (D-0036).

The country test is a **veto, not a fourth path**: a provision that names China is not an
answer about a Vietnamese shipment however well its codes match. It reads `rule.origin_scope`
rather than the presence of country rows, because *"any country"* and *"a member state of the
European Union"* both leave `rule_country` empty and mean opposite things — reading that
silence as permission replaced a Chinese T-shirt's 16.5% base rate with an EU-only 10% (D-0056).

**A provision can also rule itself out.** 31 state a condition on the base rate of the goods
they cover — *"with an ad valorem rate of duty under column 1 less than 10 percent"* — and one
that fails is shown under *Ruled out by their own wording*, quoting the sentence that removed
it, in neither the floor nor the ceiling (D-0057).

**A provision that arrived on path C is listed but not summed** (D-0049). It names the
country and describes its goods in words the parser could not turn into codes, so it reaches
*every* import from that origin — `9903.85.67` reads "Aluminum articles that are the product
of Russia" and matches a steel shipment. The total therefore reports a floor and a ceiling,
and says which provisions the gap is made of:

```
7208.51.00.30 from China     25%   ..  up to 50%
7208.51.00.30 from Russia    20%   ..  up to 220%
7208.51.00.30 from Germany   Free              (nothing origin-scoped, so no range)
```

## 6. The order the duties are applied in

The schedule states this, in three layers, and the app reads it rather than picking a
convention:

```
U.S. note 1 to subchapter III   a Chapter 99 rate applies "IN LIEU OF the rate provided
                                therefor in chapters 1 to 98"           -> the default
U.S. note 1 to subchapter I     "CUMULATIVE duties which apply IN ADDITION TO the duties,
                                if any, otherwise imposed"
31 notes override the default   "NOTWITHSTANDING U.S. note 1 to this subchapter ... shall
                                ALSO be subject to the general rates of duty imposed under
                                subheadings in chapters 1 to 97"
```

Each operator names what it acts on, so the order is derived: an *in lieu* rate stands in for
the **base**, never for another Chapter 99 duty; a cumulative rate applies to *"the duties
otherwise imposed"*, which includes whatever replaced the base. Replacements resolve first,
additions go on top, and addition commutes — so nothing below that depends on order.

This was measured, not assumed. Applying provisions in heading order left **346 of 2,160
sampled queries order-dependent**; sorting by operator leaves **none**.

Two consequences worth stating:

- **`rate_kind` and `cumulation` are two readings of the same fact**, one from the rate text
  and one from the note that governs it, and the engine composes the operator from both. 18
  provisions print a bare rate — `9903.05.39`'s `10%` — that reads as a replacement and is
  charged on top, because U.S. note 52(a) says the heading imposes an *additional* duty. Read
  from the rate alone, that 10% replaced a 16.5% base.
- **Two provisions cannot both stand in lieu of the same base rate.** `9903.45.01` (14%,
  in-quota) and `9903.45.02` (30%, over-quota) are a tariff-rate quota's two halves, told apart
  by how much has been imported this year — which is in no source here. The lowest stays in the
  figure, the rest go to the ceiling with an unknown (D-0058).

## 7. What is precomputed, and how it is kept true

The brief asks what is worth storing. The answer here is **one thing**, and it was chosen by
measuring the query the application actually runs.

`rule_coverage` holds how many base codes each provision reaches. Counting that for *one*
provision takes 4 ms, which is why an earlier decision concluded no table was needed
(D-0044). But a duty page never asks for one: a laptop from China matches 88 provisions, and
counting all 88 in a single query took **1,568 ms of a 2,034 ms response** — everything else
on that page ran under 6 ms. Materialising it took the page to 70 ms (D-0047).

That mistake is the point worth keeping: **measuring a query the application never runs
looks exactly like measuring.**

Deliberately *not* precomputed, and why:

| Not built | Why |
| --- | --- |
| `(base_hts × rule_hts)` flattened | 4.7 million rows, nearly all of them the same note expansion written again (D-0036). The live union runs in 0.19 s |
| A transitive exclusion closure | The graph is 859 edges at depth 1 and 23 at depth 2, and contains a cycle. One hop covers it (D-0044) |
| A per-code profile table for search | Live count is 3.8 ms for a page of 30 codes. The difference from the case above is cardinality |

**How it stays true.** Everything derived is rebuilt by a `materialize` task at the end of
the same parse run that rewrites the tables under it — full rebuild, `TRUNCATE` then
`INSERT ... SELECT`, no incremental path. There is no window in which the derived tables
describe a set of provisions that no longer exists. And because a new table with a foreign
key into `rule` makes the parser's `TRUNCATE` fail loudly, a derived table that someone
forgets to register cannot silently survive a run (D-0025 — it has now caught two).

## 8. What the app refuses to answer

Every duty page ends with **"What this can't tell you"**, listing only the entries this
query actually raised. Each says why these sources cannot settle it and names somewhere that
can, with what to search for. The catalogue is one file, `api/reference/sources.py`, so no
page can invent a hedge of its own, and every entry maps to a recorded decision.

| Cannot settle | Because | Goes to |
| --- | --- | --- |
| Do these duties apply at once, in what order | The HTSUS never states stacking order | CBP CSMS, by 9903 heading |
| Is my product on this exclusion list | An exclusion describes goods, not codes | The note text here, then the USTR notice |
| Can I claim a free-trade rate | Needs the SPI table, rules of origin, the importer's claim and chapter 98 — none of them in these sources (D-0027) | HTSUS General Notes |
| Which of several 9902 reductions is mine | They are told apart by CAS number, not by code (D-0019) | Your supplier's specification sheet |
| Is this the right code for my product | This site does not classify goods | CBP CROSS rulings |
| Column 1 or Column 2 | General Note 3(b) is in none of the sources; the four-country list here is editorial | HTSUS General Note 3(b) |
| Is this provision still in force | Expiry is grey shading in the PDF, destroyed by text extraction (D-0043) | The current revision, and the Federal Register |
| What law created this duty | The dataset has the tariff line, not the instrument | Federal Register |

Two additions to the data are **editorial and labelled as such on every surface that shows
them**: the seven trade-programme names (D-0045 — the schedule never writes "Section 301"),
and the four Column 2 countries (D-0026 — without it a Russian query reports Free, which is
wrong).

## 9. Running it

```bash
./dev.sh                  # whole stack, foreground → :3000, :8000/docs
```

or, piecewise:

```bash
docker compose --profile app up -d
docker compose logs -f api
```

Both `api` and `app` read `DATABASE_URL` / `API_URL` from the environment. `API_URL` is
deliberately **not** `NEXT_PUBLIC_` — pages are server-rendered and the browser never learns
the API's address; `next.config.mjs` rewrites `/api/*` for anyone who wants the JSON.

The app needs Part 2 to have run. Against an empty database it renders and reports nothing
found, rather than failing.

## 10. Verification

| Check | Result |
| --- | --- |
| Every route answers | `/`, `/search`, `/duty`, `/rule`, `/note` all 200; unknown code and unknown note both 404 |
| Page and JSON agree | Every figure on `/duty/7208.51.00.30?country=CN` matches `/api/duty/…` field for field |
| The control group is empty | Same steel code from Germany: no Chapter 99 layer, formula degrades to `Free = Free`, two unknowns raised rather than eight |
| Compound units do not collapse | A code with a `¢/kg` component and no quantity reports the specific term uncomputed, not zero |
| Coverage is fast | Duty page 70 ms after materialising, from 2,034 ms |
| No total depends on heading order | 2,160 sampled queries swept: 346 order-dependent before, 0 after |
| Tests | 133 in `workflows`, 18 in `api`, neither needing a database or the network; `tsc --noEmit` clean |
| Zero client JavaScript for interaction | Disclosure, filtering and navigation are `<details>`, `<select>` and GET forms |

**Nothing on any of these screens was written by a language model.** A machine-written
layer — a paraphrase of each provision and a label on each prose note — was built, measured
and removed: it restated what the formula strip and the evidence lines had already said.
D-0055 records what it cost and what was learned; `JOURNAL.md` has the measurements.

## 11. What it deliberately does not do

- **No natural-language question answering.** Text-to-SQL over this schema demos well and is
  the highest-risk thing that could be built on it. Recorded as future work instead.
- **No LLM anywhere.** Not in the request path, not in the build. `api/` and `app/` contain
  no model client and the API's runtime dependencies are FastAPI, uvicorn, psycopg and
  pycountry. The stack is structured data, and letting a model restate its numbers is the
  single most expensive place misinformation could enter (D-0053, D-0055).
- **No classification.** Search matches the schedule's wording, which is not the wording
  anyone uses for a product, and it says so on the results page.
- **No agent.** The question this app answers is deterministic and auditable end to end; an
  agent would add a layer whose reasoning cannot be shown on the page (D-0053).
