# Web app

Next.js (App Router), server-rendered. It draws pages; it does not compute anything.

Every page is a Server Component that fetches from the FastAPI service in [`../api/`](../api)
and renders the object it gets back. The same object is available to a reader at
`/api/<same path>`, so any number on a page can be checked against the JSON that produced it.
That is the point of splitting the two: the reasoning lives in one place, in Python, and the
page cannot quietly compute something different.

```bash
./dev.sh                 # from the repo root -- db, hatchet, worker, api, app
```

- app  -> http://localhost:3000
- API  -> http://localhost:8000/docs  (OpenAPI, generated)

## Running it on your host instead

Smoother on macOS -- bind-mounted `node_modules` and file watching are both slower in a
container.

```bash
docker compose up -d                    # Postgres and Hatchet only
cd api && uv run uvicorn main:app --reload --port 8000
cd app && npm install && npm run dev    # -> http://localhost:3000
```

The app defaults `API_URL` to `http://localhost:8000`, so nothing needs setting.

## Layout

```
src/app/          routes. layout.tsx, page.tsx, and one directory per route.
src/lib/api.ts    the only place that knows where the API lives.
next.config.ts    rewrites /api/* to the FastAPI service, so the browser never
                  needs an API origin and there is no CORS to configure.
```

Server Components call `API_URL` directly over the compose network. The browser goes through
the rewrite. `API_URL` is deliberately not `NEXT_PUBLIC_`: `api:8000` does not resolve
outside the compose network, and a value baked into a bundle would be wrong everywhere else.

## Memory

The whole stack -- Postgres, Hatchet, Hatchet's database, the worker, the API and this app --
sits at about **1.5 GB** at rest, measured:

```
app  (next dev)  647 MB      hatchet_db  271 MB      api  157 MB
worker           249 MB      hatchet     137 MB      db    43 MB
```

Give Docker **3 GB or more**. Under that, the peaks bite rather than the resting size: `npm
install` and `next dev`'s first compile both spike well above their steady state, and on a
1.75 GB VM the app container is OOM-killed mid-compile and prints only `Killed` -- no stack,
no message. If you see that, either raise Docker's memory (Settings -> Resources) or run the
worker and the app in separate steps, which is how the parts are meant to be run anyway.
