# Submission

<!--
Fill this in as you go, not at the end. The headings below are the six things
the README asks for; delete this comment and write under each one.
-->

## 1. How to run it

<!--
The command for each part, in order, from a fresh clone and an empty database.
We will follow these literally, so include the setup steps you'd otherwise do
from memory. Say what we should see when each one works.
-->

## 2. The data model, and why

<!--
The section we read most carefully. Walk us through how you decided to
represent Chapter 99's relationship to the rest of the schedule.
-->

## 3. Part 3: what you built, and why that

<!--
What you decided was worth understanding about this data, what you left out,
and how your storage layer is shaped to serve it.
-->

## 4. What you'd do with another week

<!--
Known bugs, shortcuts, the thing that's held together with tape. Be blunt.
-->

## 5. Assumptions

<!--
Where the data was ambiguous and you had to pick. What you picked, and why.
-->

### The revision: every number here is Revision 16, and you will see Revision 17

**Read this before comparing any count in this repository against your own run.**

All figures in `docs/SCHEMA.md`, `docs/PART3_APP.md`, `docs/DECISIONS.md` and
`docs/JOURNAL.md` were measured against **2026HTSRev16**. As of 2026-08-27 the USITC serves
**2026HTSRev17**, and `data/` is gitignored — so Part 1 on a fresh clone fetches Revision 17
and your counts will differ from ours.

**Pinning does not recover it, and that is the part worth knowing.** The scraper takes
`--release`, but only the notes PDF has a stable per-revision URL; the two JSON exports are
served for the current release only:

```
uv run python -m scrape_run --release 2026HTSRev16
  base       skipped     endpoint cannot serve a past release
  ch99       skipped     endpoint cannot serve a past release
  notes_pdf  unchanged   13,969,270 B
```

With nothing already on disk those two carry no sha256, `build_manifest` therefore writes
`"complete": false`, and Part 2 refuses to start on the directory — deliberately (D-0007: a run
that parsed two of three payloads would produce a database that looks finished). So **Revision
16 is not reachable from a cold clone at all.** We kept the documented figures at Revision 16
rather than re-baselining, because the write-up, the decisions and the journal are a record of
what was measured when, and rewriting a dated measurement is worse than explaining it.

**This is a documentation gap, not a defect, and it was checked rather than assumed.** We
fetched Revision 17 and parsed it on 2026-08-27. It parses cleanly, the `api/audit.py`
invariants hold over 8,000 queries, and every worked example on the site returns the same
answer. What moves is five new provisions and five new notes:

| | Rev 16 | Rev 17 |
| --- | ---: | ---: |
| `hts_base` | 26,246 | 26,246 |
| `rule` | 3,098 | 3,103 |
| `note` | 345 | 350 |
| `rule_note` | 977 | 982 |
| `note_subheading` | 48,053 | 50,359 |
| `note_base_match` | 136,325 | 141,656 |
| `rule_country` | 503 | 507 |
| `rule_coverage` | 2,825 | 2,829 |
| `rule_base_match`, `rule_edge`, `rule_identifier`, `rule_condition` | 16,958 · 14,229 · 1,229 · 31 | unchanged |
| `parse_issue` | 848 | 869 |

`parse_issue` moves by 21 of which 18 are a pre-existing category, so the parsers did not lose
ground on the new revision — which is the thing a reviewer would actually want to know.

If you want to reproduce our figures exactly, the payloads are reproducible only from a copy of
`data/raw/2026HTSRev16/`; ask us for it rather than trying to fetch it.

## 6. Where you used AI tools

<!--
Including anything you shipped without fully verifying.
-->
