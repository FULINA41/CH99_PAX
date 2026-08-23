# Data inventory

What the three sources actually contain, field by field, with real values from the live
data. Written before designing the schema so the design argues from evidence rather than
from the README's illustrative examples.

Every count and sample below comes from release **2026HTSRev16**, fetched 2026-08-20/21.

---

## 1. What is staged locally

`data/` is gitignored, so nothing here reaches the submission. These copies were fetched
by hand during exploration — **the Part 1 workflow does not exist yet**, and when it does
it will write this same layout itself.

```
data/
  raw/2026HTSRev16/
    ch99.json          1,992,914 B   3,336 rows   Chapter 99 provisions
    base.json         10,349,905 B  31,860 rows   Chapters 1–97 base schedule
    ch99-notes.pdf    13,969,270 B    807 pages   official chapter document + U.S. Notes
    manifest.json                                 provenance prototype: url, fetched_at, bytes, sha256
  derived/
    ch99-notes.txt     2,669,910 B                pypdf text extraction, for reading only
```

Re-fetch with:

```bash
curl -s 'https://hts.usitc.gov/reststop/currentRelease'
curl -s 'https://hts.usitc.gov/reststop/exportList?from=9900&to=9999&format=JSON&styles=false' -o ch99.json
curl -s 'https://hts.usitc.gov/reststop/exportList?from=0100&to=9799&format=JSON&styles=false' -o base.json
curl -s 'https://hts.usitc.gov/reststop/file?release=currentRelease&filename=Chapter%2099' -o ch99-notes.pdf
```

The release moved from Revision 15 to Revision 16 between the README being written
(2026-08-03) and this fetch, which is why `manifest.json` records the release name rather
than assuming one.

---

## 2. The export JSON

Both exports return the same 12-key row shape — they are the same endpoint over different
code ranges. Non-empty counts are out of 3,336 (Ch 99) and 31,860 (base).

| Field | Ch 99 | Base | What it is | Needed |
| --- | ---: | ---: | --- | --- |
| `htsno` | 3,098 | 26,246 | The code. 4, 6, 8 or 10 digits depending on depth. Empty on parent heading rows | **yes** |
| `indent` | 3,336 | 31,860 | Nesting depth as a string, `"0"`–`"5"`. The only thing that reconstructs the tree | **yes** |
| `description` | 3,336 | 31,860 | The prose. Carries the cross-references, the exclusions, the country, the note citation | **yes** |
| `superior` | 238 | 5,614 | `"true"` exactly on the rows whose `htsno` is empty — verified, the two sets match exactly in both files. Flags a parent heading row | **yes** |
| `general` | 2,220 | 11,438 | Column 1 General rate — the MFN rate, or a Chapter 99 modifier | **yes** |
| `special` | 2,372 | 7,123 | Column 1 Special — FTA / preference programs, with country codes in parentheses | maybe |
| `other` | 2,075 | 11,439 | **Column 2** — the statutory rate for countries without normal trade relations (Cuba, North Korea, Russia, Belarus) | maybe |
| `units` | 2 | 19,847 | Statistical reporting units, e.g. `['No.']`, `['kg']` | no |
| `footnotes` | 3,094 | 1,321 | Structured `{columns, marker, value, type}`. In Ch 99, 3,092 of them are the same pointer to statistical note 1. On the base side, a cross-reference — but not a reliable one, see below | trap |
| `additionalDuties` | 810 | 0 | Extra specific duty on some Ch 99 headings, e.g. `66.6¢/kg` | **yes** |
| `quotaQuantity` | 0 | 0 | Always empty in this release | no |
| `addiitionalDuties` | 0 | 0 | Misspelled duplicate key in the API's own schema. Always empty | no |

### What the fields mean in practice

The schedule is not a reference work; it is the form a customs broker fills in. Take one
real shipment — $100,000 of `2922.49.30.00`, a chemical, arriving in Los Angeles.

| Field | What it decides |
| --- | --- |
| `htsno` | The number that goes on the entry summary. Digits 1–6 are the international HS code, 7–8 are the US legal subdivision that sets the rate, 9–10 are statistical only. Misclassifying is a legal matter, not a typo |
| `indent` | How the schedule is legally read. Terms are compared against siblings at the same level, so "Other" means nothing without its parent |
| `description` | The words a classification dispute is actually fought over |
| `superior` | This row cannot be entered against. It is a heading that gives its children their scope |
| `general` | What the importer pays from a normal-trade-relations country. Here 6.5% — **$6,500** |
| `special` | The preferential rate if the goods qualify under an agreement *and* origin can be proved. Usually Free; claiming it without the paperwork is fraud |
| `other` | **Column 2**, for countries without normal trade relations — Cuba, North Korea, and Russia and Belarus since 2022. Here `15.4¢/kg + 50%`, roughly **$50,000** on the same shipment |
| `units` | The quantity that must be reported, and the basis a specific duty is computed on. `15.4¢/kg` is unanswerable without it |
| `footnotes` | A cross-reference, most often a warning that some other chapter modifies this line |
| `additionalDuties` | A further specific duty stacked on top — safeguards, over-quota volumes |
| `quotaQuantity` | A tariff-rate quota: the low rate applies up to this volume, a higher one past it |

The same shipment, four outcomes:

```
from Germany                6.5%              →  $6,500
qualifying under an FTA     Free              →  $0
from Cuba (Column 2)        15.4¢/kg + 50%    →  $50,000+
claiming 9902.04.06         Free              →  $0     ← Chapter 99
```

Chapter 99 does not change the fact that these goods are `2922.49.30.00`. It changes what
they cost. `9903.01.01` works the other way: same classification, 25% added.

Three consequences for the schema. The gap between `general` and `other` is eightfold, so
the country of origin decides which column applies and cannot be an afterthought. The
country codes inside `special` are a *second*, unrelated origin dimension — one grants
relief, the other imposes it, and a shipment can hit both. And "rates must be computable"
runs aground on `15.4¢/kg` unless `units` is carried alongside.

Neither the Column 2 country list nor the meaning of the FTA codes (`AU`, `KR`, `A+`, …)
appears in any of the three sources. Both live in the HTS General Notes. They have to be
hardcoded with a citation, or the answer has to say a human is needed.

### Field notes that matter for the schema

**`footnotes` is not an index of Chapter 99 coverage, and reading it as one loses 72% of
the modifications.** Of the 975 base codes cited by Chapter 99 that resolve against the
export, only **272** carry a footnote on the base side; **703 do not**. `2922.49.30.00` has
`footnotes: []` while `9902.04.06` names it explicitly.

Where footnotes do exist they point at 9903 (773) and 9904 (372), and they can be narrower
than they look. `7208.51.00` — steel — carries `See 9903.90.09.` scoped to
`columns: ['other']`, the Column 2 rate alone. That the same line is hit by Section 232 and
Section 301 goes unmentioned.

The reason it cannot work is structural: a Chapter 99 line reaches base codes either by
naming them in its description, or through a U.S. note listing them — and note 20(b) alone
covers well over a thousand codes. No footnoting convention could carry that. The 703
figure counts only the first path, so the real shortfall is larger.

Consequence: **coverage has to be derived from the Chapter 99 side and indexed backwards.**
Footnotes are worth parsing as a supplementary hint, and worth labelling as unreliable
wherever they are stored, because the next person will otherwise trust them.

**`superior` is the hierarchy flag, and it is reliable.** In Chapter 99, `superior="true"`
holds on exactly 238 rows and `htsno` is empty on exactly 238 rows — the same rows. In the
base schedule the number is 5,614 both ways. The tree does not have to be inferred from
`indent` alone.

Real example — the product scope lives on the parent, the rate on the children:

```
htsno=''            indent=0  superior=true  "Sugars, syrups and molasses provided for in
                                               subheading 1701.12.10, 1701.91.10, …"
htsno=''            indent=1  superior=true  "Described in U.S. note 15(a) to this subchapter:"
htsno='9903.17.01'  indent=2                 "Eligible to be imported under the first quota period…"
htsno='9903.17.02'  indent=2                 "…second quota period…"
```

Read `9903.17.01` on its own and it means nothing. It only means "sugar, under note 15(a),
first quota period" once the two ancestors are attached.

**`general` is empty on 20,446 of 31,860 base rows.** The rate is inherited from the
nearest ancestor that has one:

```
2922.49.49     indent=5  general='4.2%'   "Other amino acids"
2922.49.49.10  indent=6  general=''       "Alanine"          → 4.2%
2922.49.49.50  indent=6  general=''       "Other"            → 4.2%
```

**`other` is a different rate, not a duplicate.** Column 2 applies to non-NTR countries:

| htsno | general | other |
| --- | --- | --- |
| `0101.29.00` | Free | 20% |
| `0101.30.00.00` | 6.8% | 15% |
| `0102.29.20` | Free | 6.6¢/kg |

The rate explainer takes a country as input, so it has to decide which column applies.
Column 2 countries are a short list and are not in this data.

**Rate strings are not numbers.** Across the base schedule:

| Shape | Count | Example |
| --- | ---: | --- |
| empty (inherited) | 20,446 | — |
| pure ad valorem | 5,863 | `2.5%` |
| free | 4,315 | `Free` |
| specific | 771 | `14.27¢/ liter` |
| compound | 417 | `4.4¢/kg + 8.5%` |
| prose | ~30 | `The rate applicable to each garment in the set` |

And in Chapter 99, the modifier forms:

| Form | Count | Meaning |
| --- | ---: | --- |
| `Free` | 1,364 | replaces the base rate with zero |
| `The duty provided in the applicable subheading` | 204 | no change |
| `…applicable subheading + 25%` | 47 | additive |
| `…applicable subheading + 15%` | 44 | additive |
| `…applicable subheading plus 25%` | — | additive, **different spelling** (`9903.88.01`) |
| `100%`, `15%`, `2.5%` … | many | replaces with a flat rate |

**Cross-reference granularity does not match.** Chapter 99 cites 8-digit subheadings; the
base export's rate-bearing rows are 8 or 10 digit:

```
Ch 99:  "(provided for in subheading 2922.49.30)"
Base:   2922.49.30.00   general='6.5%'      ← the cited code + ".00"
```

An equality join returns zero rows. 2,556 of 3,336 Chapter 99 rows contain
`provided for in`, so this affects most of the dataset.

---

## 3. The notes PDF

807 pages. 463 of them carry a `U.S. Notes` header — the notes and the tariff table
alternate rather than sitting in one block. Three levels: chapter notes, then per-subchapter
U.S. Notes, then Statistical Notes.

**547 of 3,336 rows cite a U.S. note, across 33 distinct note numbers.** Most cited:

| Note | Cited by | Subject |
| --- | ---: | --- |
| 2 | 161 | IEEPA — Mexico, Canada |
| 52 | 98 | reciprocal tariffs, headings 9903.05.20–9903.05.84 |
| 20 | 72 | Section 301 — China |
| 33 | 51 | Section 232 — automobiles |
| 16 | 30 | Section 232 — steel, aluminum, copper |

### Seven kinds of note, and what each is for

**① Default semantics — note 1 to subchapter III.** The rule everything else is stated
against:

> "any article described in the provisions of this subchapter … is subject to duty at the
> rate set forth herein **in lieu of** the rate provided therefor in chapters 1 to 98."

The default is **replacement**, not addition. Additive treatment is an explicit exception,
which is why note 2(a) opens with "Notwithstanding U.S. note 1 to this subchapter".

**② Scope and definition prose — note 2(a), cited 161 times.**

> "products of Mexico … including both goods of Mexico under the rules set forth in
> **part 102, title 19 of the Code of Federal Regulations** … as well as goods for which
> Mexico was the **last country of substantial transformation**"

This is what makes "country of origin = Mexico" a legally defined input rather than a
label. It also states the additive behaviour explicitly.

**③ Bulk country ranges — note 52, cited 98 times.** One note governs a whole block of
headings:

> "headings **9903.05.20–9903.05.84** impose additional ad valorem rates of duty on
> imports of all products of the countries provided for in these headings"

**④ Subheading lists — note 20(b).** Pages of bare 8-digit codes defining what Section 301
List 1 covers. pypdf flattens the four-column table into runs of fixed-width codes:

```
2845.90.012845.40.002845.30.002845.20.00
8401.20.008401.10.004012.13.004011.30.00
```

Each code is exactly 10 characters, so `\d{4}\.\d{2}\.\d{2}` splits them cleanly. These
pages are almost pure code — no interleaved prose to confuse a parser.

**⑤ Mutual exclusion — note 16(a).** A stacking constraint that *is* in the data:

> "These headings are **mutually exclusive**, such that an imported article will be subject
> to **no more than one** of these headings."

So an explainer that lists two of `9903.82.02`–`9903.82.26` together is wrong.

**⑥ Quota structure — note 15(a).** Explains why ten sibling rows differ only by
"first / second / third … quota period", tied to `9903.17.01`–`9903.17.10`.

**⑦ Computation caveats — subdivisions (c), (d), (t) of various notes.**

> "For heading **9802.00.80**, the additional duties apply to the value of the article
> **less the cost or value of such products of the United States**"

> "the ad valorem duty … shall only apply to the declared value of the **aluminum content**"

These cannot be computed without entry-level data the dataset does not have. They belong
in the UI as flagged caveats, not as silent omissions.

---

## 4. How Chapter 99 reaches the base schedule

Three different mechanisms, not one. Of the 3,098 Chapter 99 rows that carry a code:

| Path | Rows | Key |
| --- | ---: | --- |
| Cites a base code in its own description | 2,203 | `(provided for in subheading 2922.49.30)` |
| Points at a U.S. note that lists the codes | 558 | `as provided for in U.S. note 20(b)` — the list is in the PDF |
| Names a country and no product at all | 211 | `articles the product of Mexico` |

The third path has **no join key to the base schedule**. `9903.01.01` covers every good from
Mexico; so does each of `9903.05.20`–`9903.05.84` for its own country. A resolver that only
follows code citations silently loses them, and with them the most commonly applied duties
in the current schedule. The `rule` table therefore needs a `scope` — whether the rule is
limited by code or applies to all goods from a country.

**Citations are 8-digit, base rows are 10.** Matching is prefix matching on the dotted
string, anchored at a separator (`x == c or x.startswith(c + '.')`) — a bare `startswith`
would let `2922.49.3` match `2922.49.30`. The expansion factor varies by three orders of
magnitude, which is why it is materialised rather than computed per query:

```
2922.49.30   →    1 base row
7208.51      →    4
4202         →  108      a 4-digit heading covers a whole product family
```

### A base code usually has more than one rule

Of the 994 base codes cited, **439 — 44% — are cited by more than one Chapter 99 rule**.
`3808.92.15` is cited by 34.

This is not messy data. The base code is a bucket, and a 9902 provision picks one substance
out of it. Four rules cite `2922.49.30`, whose own description is "Products described in
additional U.S. note 3 to section VI":

```
9902.04.04  4-Chlorophenylglycine           CAS 6212-33-5    → 0.5%
9902.04.05  2-Amino-5-sulfobenzoic acid     CAS 3577-63-7    → Free
9902.04.06  3,4-Diaminobenzoic acid         CAS 619-05-6     → Free
9902.04.07  Methyl 2-amino-3-chlorobenzoate CAS 77820-58-7   → Free
```

**The classification does not decide which one applies — the identity of the goods does**,
and that identity exists only in the Chapter 99 description. A query keyed on
`base_hts + country` therefore returns candidates, not an answer.

**1,009 rules carry a CAS number**, which is an exact, globally unique substance
identifier. Extracting them turns a third of Chapter 99 into a deterministic lookup for
anyone who knows what they are importing.

### Alternatives or stacking

The two must not be confused:

| Case | Relationship | Basis |
| --- | --- | --- |
| Several 9902 rules on one base code | **Alternatives** — a shipment is one substance | Inferred from the descriptions being disjoint; **nothing in the data says so** |
| A 9902 reduction and a 9903 additional duty | **Both apply** | Stated in note 20(a) |
| Several 9903 rules (§232 and §301) | Both apply; order unknown | Order is not in the dataset |

The middle case is explicit in the notes and easy to get wrong:

> "Products of China … that are eligible for temporary duty exemptions or reductions under
> subchapter II to chapter 99, **shall be subject to** the additional 25 percent ad valorem
> rate of duty imposed by heading 9903.88.01."

A duty suspension does not exempt goods from Section 301. Treating it as if it did
understates the duty on Chinese goods by 25 points.

## 5. What the rate explainer needs that the data does not contain

| Gap | Consequence |
| --- | --- |
| **Country of origin as a field.** It exists only inside prose: "articles the product of Mexico" | Must be extracted into its own dimension. The starter `rule` table has no country column |
| **Cross-measure stacking order.** Whether §232 or §301 applies first when both hit | Not stated anywhere in the HTSUS; CBP publishes it in CSMS messages. The UI must say so rather than guess |
| **Column 2 country list.** Which countries get the `other` rate | Short and stable; would have to be hardcoded with a citation |
| **Effective and expiry dates.** The PDF marks expired provisions by shading, which text extraction loses | Cannot tell an expired provision from a live one from the JSON alone |
| **The legal instrument.** Which proclamation or USTR notice created a heading | Federal Register has it; nothing in this dataset links to it |

---

## 6. Optional external sources

Ranked by join quality, not by interest.

| Source | Join key | Adds | Cost |
| --- | --- | --- | --- |
| **CBP CROSS** | `tariffs[]` array contains both base and 9903 codes — a real key | A real product CBP actually classified this way | Low. JSON API, no key |
| **Federal Register** | none; heading numbers appear in document text | The legal instrument behind a heading | Medium. Free API, but text matching gives false positives |
| **CBP CSMS** | none | Stacking order — the one thing that cannot be derived | High. JS-rendered, no clean API. Cite, do not scrape |
| **USITC DataWeb** | HTS code | Trade volume affected by a rule | Needs an account and key |
| **eCFR Title 19** | none | Regulatory background | No direct value to the explainer |

---

## 7. What this inventory does not settle

The open modelling questions are tracked as `P-a` … `P-f` in [`DECISIONS.md`](DECISIONS.md).
This document supplies the evidence; the decisions are made there.