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
- **P-f · Provenance grain.** Per fetch, per file, or per parsed row? The live release
  moved from Revision 15 to Revision 16 during the exercise window, so this is real.
