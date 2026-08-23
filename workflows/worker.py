"""
The worker process. Registers workflows and waits for work.

    uv run python -m worker

Leave it running in one terminal; trigger runs from another. Every workflow you
write needs to be imported and listed here, or the engine will accept a run and
then hang forever waiting for someone to pick it up.
"""

from scrape import hatchet, scrape_workflow


def main() -> None:
    worker = hatchet.worker(
        "chp99-worker",
        workflows=[scrape_workflow],
    )
    worker.start()


if __name__ == "__main__":
    main()
