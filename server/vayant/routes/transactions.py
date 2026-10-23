from datetime import date

from fastapi import APIRouter, HTTPException, Query

from ..schemas import CashFlow, Category, Transaction, TransactionPage, TransactionUpdate
from . import DB, CurrencyQ

router = APIRouter(tags=["transactions"])

TXN_SELECT = """
    SELECT t.id, t.account_id, a.name AS account_name, t.date, t.amount, a.currency, t.payee,
           t.category_id, c.name AS category_name, p.name AS category_group, c.kind AS category_kind,
           t.notes, t.transfer_pair_id
    FROM transactions t
    JOIN accounts a ON a.id = t.account_id
    LEFT JOIN categories c ON c.id = t.category_id
    LEFT JOIN categories p ON p.id = c.parent_id"""


@router.get("/categories", response_model=list[Category])
def list_categories(db: DB):
    return db.execute(
        "SELECT id, name, kind, parent_id, icon FROM categories ORDER BY kind, parent_id NULLS FIRST, name"
    ).fetchall()


@router.get("/transactions", response_model=TransactionPage)
def list_transactions(
    db: DB,
    account_id: int | None = None,
    category_id: int | None = Query(None, description="Includes the category's children"),
    start: date | None = None,
    end: date | None = None,
    q: str | None = Query(None, description="Search payee and notes"),
    limit: int = Query(50, le=500),
    offset: int = 0,
):
    where, params = [], {}
    if account_id is not None:
        where.append("t.account_id = %(account_id)s")
        params["account_id"] = account_id
    if category_id is not None:
        where.append("(c.id = %(category_id)s OR c.parent_id = %(category_id)s)")
        params["category_id"] = category_id
    if start:
        where.append("t.date >= %(start)s")
        params["start"] = start
    if end:
        where.append("t.date <= %(end)s")
        params["end"] = end
    if q:
        where.append("(t.payee ILIKE %(q)s OR t.notes ILIKE %(q)s)")
        params["q"] = f"%{q}%"
    sql = TXN_SELECT + (" WHERE " + " AND ".join(where) if where else "")
    total = db.execute(f"SELECT count(*) AS n FROM ({sql}) x", params).fetchone()["n"]
    items = db.execute(
        sql + " ORDER BY t.date DESC, t.id DESC LIMIT %(limit)s OFFSET %(offset)s",
        params | {"limit": limit, "offset": offset},
    ).fetchall()
    return {"total": total, "items": items}


@router.patch("/transactions/{txn_id}", response_model=Transaction)
def update_transaction(txn_id: int, body: TransactionUpdate, db: DB):
    changes = body.model_dump(exclude_unset=True)
    if changes:
        sets = ", ".join(f"{k} = %({k})s" for k in changes)  # keys come from the model, not the client
        if not db.execute(f"UPDATE transactions SET {sets} WHERE id = %(id)s", changes | {"id": txn_id}).rowcount:
            raise HTTPException(404, "Transaction not found")
    row = db.execute(TXN_SELECT + " WHERE t.id = %s", (txn_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Transaction not found")
    return row


@router.get("/cash-flow", response_model=CashFlow)
def cash_flow(db: DB, start: date, end: date, currency: CurrencyQ = "USD"):
    """Income and expenses per month and per category. Transfers are excluded."""
    base = """
        WITH t AS (
            SELECT t.date, c.id AS category_id, c.name, p.name AS grp,
                   COALESCE(c.kind, CASE WHEN t.amount > 0 THEN 'income' ELSE 'expense' END) AS kind,
                   fx_convert(t.amount, a.currency, %(cur)s, t.date) AS amount
            FROM transactions t
            JOIN accounts a ON a.id = t.account_id
            LEFT JOIN categories c ON c.id = t.category_id
            LEFT JOIN categories p ON p.id = c.parent_id
            WHERE t.date BETWEEN %(start)s AND %(end)s AND c.kind IS DISTINCT FROM 'transfer'
        )"""
    params = {"cur": currency, "start": start, "end": end}
    months = db.execute(base + """
        SELECT date_trunc('month', date)::date AS month,
               COALESCE(SUM(amount) FILTER (WHERE kind = 'income'), 0) AS income,
               COALESCE(-SUM(amount) FILTER (WHERE kind = 'expense'), 0) AS expenses,
               SUM(amount) AS net
        FROM t GROUP BY 1 ORDER BY 1""", params).fetchall()
    categories = db.execute(base + """
        SELECT category_id, COALESCE(name, 'Uncategorised') AS name, grp AS "group", kind,
               CASE WHEN kind = 'expense' THEN -SUM(amount) ELSE SUM(amount) END AS total
        FROM t GROUP BY category_id, name, grp, kind ORDER BY kind, total DESC""", params).fetchall()
    return {"currency": currency, "months": months, "categories": categories}
