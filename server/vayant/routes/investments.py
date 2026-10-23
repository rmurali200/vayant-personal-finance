from fastapi import APIRouter

from ..schemas import Holding
from . import DB, CurrencyQ

router = APIRouter(tags=["investments"])


@router.get("/holdings", response_model=list[Holding])
def list_holdings(db: DB, currency: CurrencyQ = "USD"):
    """Positions valued at each security's latest price; group by asset_class, then security_type."""
    return db.execute("""
        SELECT h.account_id, a.name AS account_name, s.id AS security_id, s.symbol, s.name,
               s.asset_class, s.security_type, s.currency, h.quantity, p.price, p.date AS price_date,
               h.quantity * p.price AS value,
               fx_convert(h.quantity * p.price, s.currency, %(cur)s, CURRENT_DATE) AS value_converted,
               h.cost_basis, s.maturity_date, s.interest_rate
        FROM holdings h
        JOIN accounts a ON a.id = h.account_id
        JOIN securities s ON s.id = h.security_id
        LEFT JOIN LATERAL (
            SELECT price, date FROM security_prices sp
            WHERE sp.security_id = s.id ORDER BY date DESC LIMIT 1) p ON true
        WHERE NOT a.is_closed
        ORDER BY value_converted DESC NULLS LAST""", {"cur": currency}).fetchall()
