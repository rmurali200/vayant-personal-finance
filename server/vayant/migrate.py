"""Applies server/migrations/*.sql in name order, once each. Run: python -m vayant.migrate"""
from pathlib import Path

import psycopg

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"


def migrate(conn: psycopg.Connection) -> list[str]:
    conn.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
        name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())""")
    done = {r["name"] for r in conn.execute("SELECT name FROM schema_migrations")}
    applied = []
    for f in sorted(MIGRATIONS.glob("*.sql")):
        if f.name in done:
            continue
        with conn.transaction():
            conn.execute(f.read_text())
            conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (f.name,))
        applied.append(f.name)
    conn.commit()
    return applied


if __name__ == "__main__":
    from .db import connect

    with connect() as c:
        print("\n".join(migrate(c)) or "Up to date")
