from collections.abc import Iterator

import psycopg
from psycopg.rows import dict_row

from .config import DATABASE_URL


def connect(url: str = DATABASE_URL) -> psycopg.Connection:
    return psycopg.connect(url, row_factory=dict_row)


def get_db() -> Iterator[psycopg.Connection]:
    """FastAPI dependency: one connection per request, committed on success."""
    with connect() as conn:
        yield conn
