# Workflows

Your Hatchet workflows go here. Ships with one that does nothing useful, so you
can confirm the plumbing works before writing the scraper.

## Setup

`./dev.sh` from the repo root runs a worker for you, in a container, and restarts
it when you edit a `.py` here. Trigger a run against it from this directory:

```bash
cd workflows && uv sync
uv run python -m echo_run "hello chapter 99"
# → message='hello chapter 99' length=16
```

To run the worker on your host instead, don't use `./dev.sh` — start just the
infrastructure, then the worker yourself:

```bash
docker compose up -d        # from the repo root; wait for hatchet to be healthy
cd workflows && uv sync
uv run python -m worker     # one terminal: registers workflows, waits for work
uv run python -m echo_run "hello chapter 99"   # another
```

**Run one worker at a time.** They share the token in `.env`, so a host worker
and the container worker will both register and Hatchet will hand tasks to
whichever it picks — including the one running code you didn't just edit.

Runs show up in the Hatchet UI at http://localhost:8080 — no login, it opens
straight to the dashboard. Workflows can be triggered from the UI or
programatically.

## The worker in Docker

`./dev.sh` is the short version. For the worker alone:

```bash
docker compose --profile worker watch    # foreground, restarts on edit
docker compose --profile worker up -d    # detached, no reload
docker compose logs -f worker
```

Either bind-mounts `./workflows`. Under `watch`, editing a `.py` restarts the
worker for you; adding a dependency to `pyproject.toml` restarts it too, picking
up the new package via `uv sync`. Detached, you restart it yourself with
`docker compose restart worker`.

Either path is fine. Host-running gives you a debugger; the container gives you
one less thing to install and the reload for free. Note that from inside the
container your database is `db:5432`, not `localhost:5432` — the service reads
`DATABASE_URL` from the environment for exactly this reason.

## What's here

| File          |                                                             |
| ------------- | ----------------------------------------------------------- |
| `echo.py`     | A workflow with one task: takes an input, returns an output |
| `worker.py`   | The worker process. Register your workflows here            |
| `echo_run.py` | Triggers a run and prints the result                        |
| `.env`        | Hatchet connection settings. Committed — see below          |

## The shape of a workflow

```python
class EchoInput(BaseModel):
    message: str

class EchoOutput(BaseModel):
    message: str
    length: int

echo_workflow = hatchet.workflow(name="Echo", input_validator=EchoInput)

@echo_workflow.task()
def echo(input: EchoInput, ctx: Context) -> EchoOutput:
    return EchoOutput(message=input.message, length=len(input.message))
```

[Hatchet docs](https://docs.hatchet.run/home/setup) is a great resource for
documentation and patterns.

## Notes

**Register your workflows in `worker.py`.** If you forget, the engine will accept
a run and it'll sit queued forever with nothing to pick it up. This is the most
common way to lose ten minutes here.

**The token in `.env` is committed, and that's deliberate.** We run the Hatchet
dev image, which has auth compiled out — no login on the dashboard, and one fixed
non-expiring worker token that's the same on every auth-disabled instance. It
isn't a secret and it survives `./cleanup.sh`, so there's no setup step and
nothing to rotate. Don't copy the pattern into anything real.
