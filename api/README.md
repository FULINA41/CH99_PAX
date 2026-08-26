# API

FastAPI over the parsed database, read-only. **The duty computation lives here and nowhere
else** — the page at `:3000` and the JSON at `:8000` are two renderings of one object, so any
figure on screen can be checked against the JSON that produced it.

```bash
./dev.sh                          # from the repo root
# -> http://localhost:8000/docs   OpenAPI, generated
```

Needs Part 2 to have run. Against an empty database the endpoints answer 404 rather than
failing.

## What's here

| Path | |
| --- | --- |
| `duty/applicable.py` | Which Chapter 99 provisions reach a good from an origin — the three-path union, and why each one matched |
| `duty/compute.py` | `rate_kind` as an operator: `additive` adds, `replace` stands in, `no_change` is an exclusion, `prose` is not computable |
| `duty/explain.py` | Sorts the matches into what they actually are — duties, reductions, exclusions, origin-scoped, not in force — and assembles the answer |
| `duty/queries.py` | Every read behind a duty answer, in one file, written to be read |
| `reference/` | The two additions that are **not** in any source: the four Column 2 countries (D-0054) and the catalogue of what this data cannot settle |
| `routes/` | Thin adapters. No logic below a route that is not in `duty/` |

## Two things worth knowing before editing

**No ORM, and that is a decision** (D-0048). The interesting queries here are recursive CTEs,
three-way unions and window functions; an ORM would be a layer to fight rather than a layer
to use. Responses are Pydantic models, so the boundary is typed even though the reads are
not.

**`reference/sources.py` is the only place a hedge may be written.** Every "this cannot tell
you" on any page comes from that catalogue, each entry naming why these sources cannot
answer and a specific place that can. A page that invents its own disclaimer is a bug.

## Tests

```bash
cd api && uv run pytest      # 15 tests, no database and no network
```

They cover the arithmetic and the date logic — the two places a wrong answer would be
invisible: that a specific duty with no quantity is left uncomputed rather than zeroed, that
a percentage and a per-unit rate are never collapsed into one figure, and that a provision is
judged against the date asked about rather than today.
