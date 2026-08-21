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
