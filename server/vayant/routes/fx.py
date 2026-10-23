from fastapi import APIRouter

from .. import fx
from ..config import REPORTING_CURRENCIES
from ..schemas import FxRates
from . import DB

router = APIRouter(tags=["fx"])


@router.get("/fx", response_model=FxRates)
def latest_rates(db: DB):
    """Latest stored rate for each reporting currency, as units per 1 USD."""
    rows = db.execute("""
        SELECT DISTINCT ON (currency) currency, date, per_usd FROM fx_rates
        WHERE currency = ANY(%s) ORDER BY currency, date DESC""", (list(REPORTING_CURRENCIES),)).fetchall()
    return {"date": max((r["date"] for r in rows), default=None),
            "per_usd": {"USD": 1, **{r["currency"]: r["per_usd"] for r in rows}}}


@router.post("/fx/refresh", response_model=FxRates)
def refresh_rates(db: DB):
    fx.refresh(db, force=True)
    return latest_rates(db)
