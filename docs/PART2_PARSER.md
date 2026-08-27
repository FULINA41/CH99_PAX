# Part 2 — The parser

A second Hatchet workflow that reads the payloads Part 1 landed and turns prose into rows
that can be queried and computed with. It never touches the network.

Reasoning behind the choices below is in [`DECISIONS.md`](DECISIONS.md); measured
behaviour and verification output are in [`JOURNAL.md`](JOURNAL.md); every table and
column is documented in [`SCHEMA.md`](SCHEMA.md); the shape of the source data is in
[`DATA_INVENTORY.md`](DATA_INVENTORY.md).

---

## 1. Where it sits

```
   data/raw/<release>/          ← written by Part 1. The parser reads only from here
     ch99.json  base.json  ch99-notes.pdf  manifest.json
        │
        │  no HTTP client is imported anywhere in this workflow
        ▼
  ┌──────────────────────────────────────────────────────────┐
  │ ParseHTS workflow            ← Part 2, this document     │
  └──────────────────────────────────────────────────────────┘
        │
        ▼
   Postgres, 12 tables ──► App (Part 3)
```

`load_payloads` refuses to start on a directory whose manifest does not say `complete`.
That flag is the contract Part 1 offers, and honouring it is the reason the two workflows
are separate: a run that parsed two of three payloads would produce a database that looks
finished.

## 2. The four requirements

| Requirement | Where it is met |
| --- | --- |
| Extract the cross-references to base HTS codes | `rule_edge`, 14,229 rows — the code exactly as printed, no foreign key, §7 |
| Resolve them, so a provision reaches the MFN rate it modifies | `rule_base_match` (16,958) and `note_base_match` (79,087), §7 |
| Model the notes and connect them to the headings citing them | `note` (345), `rule_note` (926), `note_subheading` (36,764), §8 |
| Rates must be computable, not just displayable | `rate_kind` is an operator and three columns are its operands, §6 |

## 3. Shape of the workflow

```
                    ┌── parse_base_schedule ──┐
   load_payloads ───┤                         ├── resolve_citations ── summarize
                    └── parse_chapter99 ──── parse_us_notes
```

Four parse tasks and a summary. The edges are the real dependencies, not a pipeline drawn
for tidiness:

- `parse_base_schedule` and `parse_chapter99` run **in parallel**. Neither writes a foreign
  key into the other's tables; only the resolver needs both.
- `parse_us_notes` runs **after** `parse_chapter99`, because loading notes clears
  `rule_note.note_id`, and that column belongs to rows the Chapter 99 task writes.
- `resolve_citations` runs **last** and is the only task that reads what three others wrote.

**Every parse task raises on failure.** This is the deliberate opposite of Part 1, where
tasks report failures instead of raising so that the manifest still covers every source
(D-0007). Part 2 has no manifest to protect: a run that parsed half the data should be red.

## 4. Modules

| Module | Holds |
| --- | --- |
| `parsing/manifest.py` | Finds a release directory the parser is allowed to read, and refuses the rest |
| `parsing/db.py` | Connection, and rebuilding a missing `source_fetch` row from the manifest |
| `parsing/tree.py` | Hierarchy reconstruction and rate inheritance — shared by both schedules |
| `parsing/rates.py` | One duty-rate parser, used by base rows, Chapter 99 rates and additional duties |
| `parsing/base.py` | Chapters 1–97 → `hts_base` |
| `parsing/ch99.py` | Chapter 99 → `rule` and its five fact tables |
| `parsing/countries.py` | Country name → ISO 3166-1 alpha-2 |
| `parsing/notes.py` | The PDF → `note` and `note_subheading` |
| `parsing/resolve.py` | Citations → base-code coverage |
| `parsing/issues.py` | The one way anything unparseable is recorded |

`parse.py` is the workflow; `parse_run.py` is the CLI. Nothing under `parsing/` imports
Hatchet, so every rule in it is testable without a worker.

## 5. The data model in one line

**What a source says and what we concluded from it are different layers, and they get
different tables.**

```
FACT                                            INTERPRETATION
rule_edge.target_hts = '2922.49.30'      →      rule_base_match → hts_base rows
  as printed, 8-digit, no foreign key,          a real foreign key, rebuilt from the
  sometimes a code that no longer exists        fact layer without re-reading prose
```

Both derived tables can be dropped and rebuilt from `rule_edge` and `note_subheading` with
no payload re-read. A reviewer can audit the interpretation without trusting it, and a
resolver bug costs a re-resolve rather than a re-parse.

The full column-by-column reference is [`SCHEMA.md`](SCHEMA.md). What became of the three
tables the exercise supplied — three columns removed, one CHECK vocabulary changed, every
departure with its reason — is D-0021.

## 6. Rates, made computable

`rate_kind` is an **operator**; the three columns beside it are its **operands** (D-0013).
A single numeric could not hold what the schedule prints: 5,863 pure ad valorem rates, 771
specific duties, 417 compound ones and about 30 that are English sentences.

| printed | `rate_kind` | pct | amount | unit |
| --- | --- | ---: | ---: | --- |
| `Free` | `free` | 0 | | |
| `2.5%` | `replace` | 2.5 | | |
| `14.27¢/liter` | `replace` | | 0.1427 | `liter` |
| `4.4¢/kg + 8.5%` | `replace` | 8.5 | 0.044 | `kg` |
| `The duty provided in the applicable subheading + 25%` | `additive` | 25 | | |
| `The rate applicable to each garment in the set` | `prose` | | | |

Two decisions make the numbers usable rather than merely present:

- **Amounts are always dollars.** `46.3¢/kg` is stored as `0.463`, so it multiplies without
  anyone re-reading `rate_text` to find out which symbol was printed (D-0024).
- **A qualified basis stays in the unit.** `7.4¢/kg on drained weight` keeps
  `'kg on drained weight'`, because it is not plain kg and a calculator handed plain kg
  would overcharge.

What stays `prose` is chosen, not left over: a rate with three or more terms
(`8.8¢/kg on copper content + 3.3¢/kg on lead content + …`) would have to be truncated to
the two operand slots, so it is not parsed at all (D-0026). 305 of 22,829 base rate strings
(1.3%) end up here, each with a `parse_issue` row.

Inheritance is materialised: 20,446 of 31,860 base rows print no rate and take one from an
ancestor, and `rate_inherited_from` names which (D-0014). Column 2 inherits on its own
chain, which differs from Column 1 on exactly one row in 26,246 — `9006.59.15.20` states
its own Column 2 while inheriting Column 1 (D-0028).

## 7. Cross-references, resolved

A Chapter 99 provision reaches base codes two ways, and the second one multiplies.

**By naming them.** `rule_edge` stores the string as printed — 8-digit where `hts_base` is
8 or 10, so it matches nothing directly, and 226 cited codes resolve to nothing at all.
`rule_base_match` holds the resolution: 16,958 rows, prefix-matched **anchored at a
separator**, because a bare prefix test would let `2922.49.3` reach `2922.49.30`.

**Through a note that lists them.** Expanded once per note into `note_base_match` —
79,087 rows. Doing it per provision was measured first and came to roughly **4.7 million
rows**, ~98% of them the same expansion repeated: note 52 lists 4,166 codes and is cited by
98 provisions (D-0036).

The consequence is stated here because it is easy to get wrong: **a provision's coverage is
the union of two queries**, and so is a shipment's exposure.

```sql
-- what reaches this base code
SELECT rule_hts FROM rule_base_match WHERE base_hts = $1
UNION
SELECT n.rule_hts FROM rule_note n JOIN note_base_match m ON m.note_id = n.note_id
 WHERE m.base_hts = $1;

-- and, separately, what reaches every good from this country
SELECT r.hts FROM rule r JOIN rule_country c ON c.rule_hts = r.hts
 WHERE r.scope = 'by_country_all_goods' AND c.country_code = $2;
```

That second query exists because **102 provisions name a country and no product at all**
(D-0018). `9903.01.01` covers every good from Mexico. Materialising it against 26,246 base
rows would cost millions of rows per provision; omitting it loses the most frequently
applied duties in the schedule. Forgetting it understates the duty on Chinese goods by 25
points.

`rule.scope` is finalised by the resolver, not the Chapter 99 parser: **306 provisions**
were filed as `by_country_all_goods` or `unknown` and became `by_code` once their note
turned out to be a list. Whether a note is a list is not knowable until the PDF is parsed.

## 8. Notes

`rule_note` records **926 citations**. Many of them are how a provision gets its scope:
`9903.88.01` — Section 301 — covers "the subheadings enumerated in U.S. note 20(b)", a list
that exists only in the PDF.

pypdf returns 807 pages with every trace of layout gone. What survives is that the schedule
prints **in order**, so segmentation rests on three ordering rules rather than on layout
(D-0034):

| Rule | What it prevents |
| --- | --- |
| A note opens only if its number exceeds the last, and the period is followed by whitespace | `44.5 percent` opening "note 44", which once blocked note 52 — cited 98 times — from ever starting |
| A subdivision label may be at most two places ahead in the sequence a…z, aa…zz, aaa…zzz | `(vvv)`, quoted inside note 20's prose, being accepted after `(a)` and hiding the real `(b)` and its 874 codes |
| Codes are read by a scan accepting a match at a non-digit **or where the previous ended** | Reading one code out of `0201.10.500201.10.10`, which pypdf prints with no separator |

350 note records across 9 subchapters, 50,359 listed codes. `rule_note` keeps `cited_text`
as the description wrote it and a nullable `note_id`, so an unresolved citation keeps its
text and gets an issue rather than vanishing.

The acceptance test is not a row count but whether the citations can find their notes:
**855 of the 856 in-PDF citations resolve**. A further 126 name `additional U.S. note N to
chapter N`, which belongs to another chapter's document and is correctly absent.

## 9. Idempotency and failure

The database holds exactly one revision. Each task opens a transaction, replaces the tables
it owns, and commits, so a crash before COMMIT leaves the previous contents intact
(D-0020).

Replacement is `TRUNCATE` where nothing else references the table and `DELETE` where
something does. That is not stylistic: `DELETE FROM hts_base` took **10.4 seconds** against
0.00s truncated, because `parent_hts` and `rate_inherited_from` reference the table with
`ON DELETE SET NULL` and Postgres nulls ~26,000 references one at a time (D-0025). The
truncate statements **name their tables instead of using CASCADE**, so a table added later
fails loudly with its name in the message — which it did, once, and cost one line.

Nothing unparseable is discarded. `parse_issue` carries 869 rows:

| stage | kind | rows |
| --- | --- | ---: |
| base | `unparsed_rate` | 305 |
| resolve | `subdivision_not_segmented` | 280 |
| resolve | `unresolved_code` | 226 |
| ch99 | `unnamed_country` | 36 |
| resolve | `rate_silent_note_decides` | 18 |
| ch99 | `unparsed_rate` | 3 |
| resolve | `unresolved_note` | 1 |

An empty `parse_issue` after a full run would mean the parser is not checking, not that the
data is clean (D-0017).

## 10. Running it

```bash
./dev.sh                                   # stack up
./setup.sh                                 # schema from empty
cd workflows && uv run python -m scrape_run   # Part 1, once
uv run python -m parse_run                    # Part 2
uv run python -m parse_run --release 2026HTSRev17   # or pin a release
```

`parse_run` prints a reconciliation table per stage. With no `--release` the parser picks
the most recently resolved directory whose manifest says `complete` — chosen from what the
scraper recorded, because with the network unplugged there is nothing to ask.

`uv run pytest` runs 134 tests. None needs a worker, a database or a network.

## 11. What it deliberately does not do

| Not done | Why |
| --- | --- |
| Keep more than one revision | One resident revision (D-0020). `data/raw/` keeps every payload, so history is recoverable by re-parsing — just not queryable |
| Decide stacking order between §232 and §301 | Not stated anywhere in the HTSUS; CBP publishes it in CSMS messages |
| Mark expired provisions | The PDF marks expiry by grey shading, which text extraction destroys; the JSON has no date field (P-i) |
| Decode `special` (`A+`, `KR`, `AU`) | Needs the HTS General Notes, in none of the three sources |
| Populate `rule_country.relation = 'excluded'` | Four phrasings of a country carve-out were searched for and every one returned zero: reciprocal-tariff headings carve out *headings*, not countries |

## 12. Verification

Run from an empty database (`./setup.sh`, `hts_base` at 0 rows) straight through:

```
hts_base   26,246 rows      11,779 / 11,778 rates inherited      305 uncomputable
rule        3,103 rows      13,370 references   859 exclusions   507 countries
note          350 records   50,359 listed codes
resolved   16,958 provision -> base matches (cited directly)
          141,656 note -> base matches (once per note)
              855 citations linked to a note
              347 provisions rescoped once their note was read
          cumulation 798 cumulative  624 in_lieu  1,681 unstated
          scope now  2,918 by_code  67 by_country_all_goods  118 unknown
```

**Idempotent end to end**, not only per task: a second run reproduces every figure above,
and `md5(string_agg(t::text, '|' ORDER BY hts))` over all of `hts_base` is identical across
runs.

Spot checks that pin behaviour rather than shape:

```
2922.49.49.10  Alanine        4.2%  replace  inherited from 2922.49.49
0402.99.90.00  46.3¢/kg + 14.9%  →  pct 14.9, amount 0.463, unit kg
2922.49.30.00  Column 1 6.5%  vs  Column 2 '15.4¢/kg + 50%'
9903.01.01     additive 25%, scope by_country_all_goods, Mexico, 4 exclusions
9903.88.01     'plus 25%' spelling → additive 25; cites note 20(a) and 20(b)
2922.49.30     cited by 9902.04.04/.05/.06/.07, each with its own CAS number
U.S. note 20(b)  subheading_list, PDF pages 261–265, 874 codes
```

The flagship, steel `7208.51.00.30` from China: base duty Free (inherited), 14 provisions
reaching it through U.S. notes 30(d) and 31 — Section 232 — and 63 provisions naming China
on the country path. `9903.88.01` correctly does **not** appear among the first group: it
was rescoped to `by_code` once note 20(b) was read, and 7208 is not in that list, because
Section 301 List 1 is machinery and electronics.
