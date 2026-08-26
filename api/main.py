from fastapi import FastAPI

from db import lifespan
from routes import meta

app = FastAPI(
    title="Chapter 99 API",
    version="0.1.0",
    description=(
        "Read-only access to the HTSUS Chapter 99 database built by the Part 1 scraper and "
        "the Part 2 parser.\n\n"
        "Every endpoint returns the same object the web app renders, so any number shown on "
        "a page can be checked here against the rows it came from. Nothing is computed in "
        "the browser."
    ),
    lifespan=lifespan,
)

app.include_router(meta.router)
