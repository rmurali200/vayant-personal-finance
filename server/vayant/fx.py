"""Daily exchange rates from open.er-api.com (free, keyless, updated about once a day)."""
import json
import logging
import urllib.request
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import psycopg

URL = "https://open.er-api.com/v6/latest/USD"
log = logging.getLogger(__name__)


def fetch() -> tuple[date, dict[str, Decimal]]:
    with urllib.request.urlopen(URL, timeout=10) as r:
        data = json.load(r, parse_float=Decimal)
    if data.get("result") != "success":
        raise RuntimeError(f"FX API error: {data.get('error-type', 'unknown')}")
    day = datetime.fromtimestamp(data["time_last_update_unix"], UTC).date()
    return day, {c: Decimal(r) for c, r in data["rates"].items() if c != "USD"}


def store(conn: psycopg.Connection, day: date, rates: dict[str, Decimal]) -> None:
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO fx_rates (date, currency, per_usd) VALUES (%s, %s, %s)
               ON CONFLICT (currency, date) DO UPDATE SET per_usd = EXCLUDED.per_usd""",
            [(day, c, r) for c, r in rates.items()],
        )


def refresh(conn: psycopg.Connection, force: bool = False) -> date | None:
    """Fetches today's rates unless we already have rates from the last day. Returns the rate date."""
    latest = conn.execute("SELECT max(date) AS d FROM fx_rates").fetchone()["d"]
    if not force and latest and latest >= date.today() - timedelta(days=1):
        return None
    day, rates = fetch()
    store(conn, day, rates)
    conn.commit()
    log.info("Stored %d FX rates for %s", len(rates), day)
    return day
