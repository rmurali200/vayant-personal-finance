from fastapi import APIRouter

from ..schemas import Goal
from . import DB

router = APIRouter(tags=["goals"])

# Full months of spending averaged for a reserve goal measured in months.
EXPENSE_LOOKBACK_MONTHS = 6


@router.get("/goals", response_model=list[Goal])
def list_goals(db: DB):
    goals = db.execute("""
        SELECT id, name, kind, currency, target_amount, target_months, target_date
        FROM goals WHERE NOT is_archived
        ORDER BY kind = 'reserve' DESC, target_date NULLS LAST, id""").fetchall()
    allocations = db.execute("""
        SELECT ga.goal_id, ga.account_id, a.name AS account_name, a.currency AS account_currency,
               ga.amount, ga.percent, n.native AS contributed_native,
               fx_convert(n.native, a.currency, g.currency, CURRENT_DATE) AS contributed
        FROM goal_allocations ga
        JOIN goals g ON g.id = ga.goal_id
        JOIN accounts a ON a.id = ga.account_id
        CROSS JOIN LATERAL (
            SELECT COALESCE((SELECT balance FROM balance_snapshots s
                             WHERE s.account_id = a.id ORDER BY date DESC LIMIT 1), 0) AS balance) b
        CROSS JOIN LATERAL (
            SELECT CASE WHEN ga.amount IS NOT NULL THEN LEAST(ga.amount, GREATEST(b.balance, 0))
                        ELSE GREATEST(b.balance, 0) * ga.percent / 100 END AS native) n
        ORDER BY contributed DESC""").fetchall()
    for g in goals:
        g["allocations"] = [a for a in allocations if a["goal_id"] == g["id"]]
        g["current"] = sum((a["contributed"] for a in g["allocations"]), 0)
        g["target"] = g["target_amount"] if g["target_amount"] is not None else (
            g["target_months"] * monthly_expenses(db, g["currency"]))
    return goals


def monthly_expenses(db: DB, currency: str) -> float:
    return db.execute("""
        SELECT COALESCE(-SUM(fx_convert(t.amount, a.currency, %(cur)s, t.date)), 0) / %(n)s AS avg
        FROM transactions t
        JOIN accounts a ON a.id = t.account_id
        JOIN categories c ON c.id = t.category_id
        WHERE c.kind = 'expense'
          AND t.date >= date_trunc('month', CURRENT_DATE) - make_interval(months => %(n)s)
          AND t.date < date_trunc('month', CURRENT_DATE)""",
        {"cur": currency, "n": EXPENSE_LOOKBACK_MONTHS}).fetchone()["avg"]
