import os

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgres://postgres:postgres@localhost:5432/chp99"
)
POOL_MIN = int(os.environ.get("API_POOL_MIN", "1"))
POOL_MAX = int(os.environ.get("API_POOL_MAX", "8"))
