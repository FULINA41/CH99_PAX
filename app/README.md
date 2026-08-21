# Scaffold

A starting point for Part 3, not a foundation.

`./dev.sh` from the repo root runs this for you, in a container, at
http://localhost:3000. To run it on your host instead:

```bash
docker compose up -d     # just Postgres and Hatchet — Postgres on :5432
cd app && bun dev        # → http://localhost:3000
```

You should get a page listing whatever relations exist in `chp99`. If the database
is empty, it says so; that's expected until you've run Part 2.

## What's here

`server.ts` — one route, one query, no dependencies. It uses `Bun.serve` and
`Bun.sql` because they ship with Bun, not because you should use them.

That's the whole scaffold. There is no router, no ORM, no component library, no
opinion about how you fetch data or where you draw the server/client line. Those
are the decisions we're interested in, so we've left them to you.

## Use something else if you want

This is a suggestion with a working DB connection attached, and no more than that.
Replace it with Next, Vite, FastAPI, Django, Rails, htmx, or a stack we haven't
thought of. Delete this directory entirely if it's in your way. Nothing else in
the repo imports from it.

If you go a different direction, the only thing we ask is that your `SUBMISSION.md`
tells us how to run what you built. It should be runnable from a single command.

## Connecting

Defaults are in `.env.example`, and match the compose file:

| From                               | Host        | Port   |
| ---------------------------------- | ----------- | ------ |
| Your machine                       | `localhost` | `5432` |
| A container on the compose network | `db`        | `5432` |

Credentials are `postgres` / `postgres`, database `chp99`.

## Running it in Docker instead

There's an `app` service in `docker-compose.yaml`. `./dev.sh` starts it; on its
own it's behind the `app` profile. Either way it bind-mounts this directory and
runs the same `bun dev`:

```bash
docker compose --profile app up -d
```

Host-running is the smoother path on macOS — bind-mounted `node_modules` and file
watching are both slower in a container. Run `docker compose up -d` for just
Postgres and Hatchet, then `bun dev` here.
