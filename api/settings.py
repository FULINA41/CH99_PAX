import os

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgres://postgres:postgres@localhost:5432/chp99"
)
# Read-only over a database a Hatchet workflow owns, so the pool stays small: nothing here
# competes with the parser for connections, and the parser's loaders take exclusive locks.
POOL_MIN = int(os.environ.get("API_POOL_MIN", "1"))
POOL_MAX = int(os.environ.get("API_POOL_MAX", "8"))
