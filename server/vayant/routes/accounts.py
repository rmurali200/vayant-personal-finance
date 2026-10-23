from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter

from ..schemas import Account, NetWorth
from . import DB, CurrencyQ

router = APIRouter(tags=["accounts"])


@router.get("/accounts", response_model=list[Account])
def list_accounts(db: DB, currency: CurrencyQ = "USD"):
    return db.execute("""
        SELECT a.id, a.name, a.type, a.classification, a.currency, a.mask, a.is_closed, a.in_net_worth,
               i.name AS institution, i.country, b.balance, b.date AS balance_date,
               fx_convert(b.balance, a.currency, %(cur)s, CURRENT_DATE) AS balance_converted
        FROM accounts a
        LEFT JOIN institutions i ON i.id = a.institution_id
        LEFT JOIN LATERAL (
            SELECT balance, date FROM balance_snapshots s
            WHERE s.account_id = a.id ORDER BY date DESC LIMIT 1) b ON true
        ORDER BY a.classification, a.type, a.name""", {"cur": currency}).fetchall()


@router.get("/net-worth", response_model=NetWorth)
def net_worth(
    db: DB,
    currency: CurrencyQ = "USD",
    start: date | None = None,
    end: date | None = None,
    interval: Literal["day", "week", "month"] = "month",
):
    """Assets, liabilities and net worth at the end of each interval, converted at that date's rate."""
    end = end or date.today()
    start = start or end - timedelta(days=365)
    series = db.execute("""
        WITH points AS (
            SELECT LEAST((b + ('1 ' || %(iv)s)::interval - interval '1 day')::date, %(end)s::date) AS d
            FROM generate_series(date_trunc(%(iv)s, %(start)s::date), %(end)s::date, ('1 ' || %(iv)s)::interval) b
        ), totals AS (
            SELECT p.d,
                   COALESCE(SUM(v.value) FILTER (WHERE a.classification = 'asset'), 0) AS assets,
                   COALESCE(SUM(v.value) FILTER (WHERE a.classification = 'liability'), 0) AS liabilities
            FROM points p
            CROSS JOIN accounts a
            CROSS JOIN LATERAL (
                SELECT fx_convert(s.balance, a.currency, %(cur)s, p.d) AS value
                FROM balance_snapshots s
                WHERE s.account_id = a.id AND s.date <= p.d
                ORDER BY s.date DESC LIMIT 1) v
            WHERE a.in_net_worth
            GROUP BY p.d
        )
        SELECT p.d AS date, COALESCE(t.assets, 0) AS assets, COALESCE(t.liabilities, 0) AS liabilities,
               COALESCE(t.assets - t.liabilities, 0) AS net_worth
        FROM points p LEFT JOIN totals t USING (d)
        ORDER BY p.d""", {"cur": currency, "start": start, "end": end, "iv": interval}).fetchall()
    return {"currency": currency, "series": series}
