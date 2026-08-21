# Work journal

Chronological, append-only. One section per working session. Records what was
attempted, what broke, what was verified (with the output, not a claim), and where a
coding agent helped or misled. Feeds `SUBMISSION.md` §4 and §6, and the demo video.

---

## 2026-08-20 — Reading the sources before writing anything

**Goal.** Understand the shape of the three data sources well enough to design the
schema, before committing to any parsing approach.

**Done.**
- Read the provided docs: `README.md`, `AGENTS.md`, `parts/*.md`, `db/schema.sql`,
  `docker-compose.yaml`, the `app/` and `workflows/` scaffolds.
- Fetched two of the three sources by hand (curl, into a scratch directory outside the
  repo) and inspected them with Python. The notes PDF was **not** downloaded yet.
- Wrote `CLAUDE.md` for future agent sessions.

**Verified facts** (live API, 2026-08-20):

| Check | Result |
| --- | --- |
| `GET /reststop/currentRelease` | `2026HTSRev16` — README documented Rev 15 as of 2026-08-03 |
| Chapter 99 export rows | 3,336 |
| Base schedule (1–97) rows | 31,860 |
| Ch99 rows containing `provided for in` | 2,556 |
| Ch99 rows citing a U.S./statistical note | 595 |
| Ch99 rows with `except` / `other than` | 307 |
| Ch99 rows with an empty `htsno` (parent heading rows) | 238 |
| Base rows with an empty `general` rate | 20,446 of 31,860 |
| Base rate shapes | 4,315 `Free` · 5,863 pure ad valorem · 771 specific (`14.27¢/liter`) · 417 compound (`4.4¢/kg + 8.5%`) · ~30 prose |

**Findings that will drive the schema** (each is now a pending decision in
[`DECISIONS.md`](DECISIONS.md)):

1. Cited codes are 8-digit, base rows are 10-digit — `2922.49.30` vs `2922.49.30.00`.
   A naive join matches nothing.
2. Most base rows inherit their rate from an ancestor row through `indent`
   (`2922.49.49.10` Alanine is empty; the 4.2% lives on `2922.49.49`).
3. Additive rates are spelled two ways in the same export: `+ 25%` on `9903.01.01`,
   `plus 25%` on `9903.88.01`. 204 rows say "The duty provided in the applicable
   subheading" with no delta, i.e. no change.
4. 238 rows carry no `htsno`; they are parent headings such as
   `Described in U.S. note 15(a) to this subchapter:` — the product scope sits on the
   parent, the rate on the children. Losing the `indent` tree loses the meaning.
5. `9903.88.01` scopes itself by reference to "the subheadings enumerated in U.S. note
   20(b)". That list is not in the JSON at all — it is the reason the notes PDF is a
   required source rather than a nice-to-have.
6. `9903.88.01` excludes 17 other headings in one sentence, confirming exclusions are a
   graph traversal, not a lookup.

**Not done / open.**
- Repo is not a git repository (`git status` → *not a repository*). The submission
  requires full git history. Original `.git` needs to be recovered, or the repo
  initialized now and committed normally from here.
- Docker stack never started; `./dev.sh`, `./setup.sh` unrun. Nothing in this session
  touched Postgres or Hatchet.
- Notes PDF not fetched or inspected — its structure is still unknown, and it is the
  least predictable of the three sources.

**Agent notes.** The agent's summary of the domain was accurate against the primary
docs, and pulling the live exports turned two of the README's illustrative examples into
checkable numbers — including one that had already gone stale (Rev 15 → Rev 16). Nothing
was written to the repo except `CLAUDE.md` and these two log files, so there is no
generated code carrying unverified assumptions yet.
