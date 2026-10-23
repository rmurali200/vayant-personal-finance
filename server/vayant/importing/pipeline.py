"""From parsed rows to stored transactions: duplicate checks, category suggestions, balances.

Preview and commit both re-read the file, so nothing is held between the two requests.
"""
import hashlib
import re
from collections import Counter
from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal

from psycopg import Connection
from psycopg.types.json import Jsonb

from .parse import Mapping, Parsed, Row, is_ofx, parse_csv, parse_ofx


def load_account(db: Connection, account_id: int) -> dict | None:
    return db.execute("""
        SELECT a.id, a.name, a.type, a.classification, a.currency, i.country
        FROM accounts a LEFT JOIN institutions i ON i.id = a.institution_id WHERE a.id = %s""", (account_id,)).fetchone()


def parse_file(db: Connection, account: dict, filename: str, content: str, mapping: Mapping | None) -> tuple[Parsed, bool]:
    """Parses with, in order: the caller's mapping, the account's saved mapping if the header still matches, a guess.
    Returns the result and whether the saved mapping was used."""
    if is_ofx(filename, content):
        return parse_ofx(content), False
    if mapping is None:
        profile = db.execute("SELECT header, mapping FROM import_profiles WHERE account_id = %s", (account["id"],)).fetchone()
        if profile:
            saved = Mapping(**profile["mapping"])
            parsed = parse_csv(content, account["type"], account["country"], saved)
            if parsed.header == profile["header"] and parsed.rows:
                return parsed, True
    return parse_csv(content, account["type"], account["country"], mapping), False


# Card-processor prefixes that come before the merchant's name: "SQ *BLUE BOTTLE", "TST* NOPA".
PROCESSORS = re.compile(r"^(sq|tst|sp|pp|paypal|py|pos|ckc|dd)\s*\*\s*")
# Payment-rail prefixes on bank narrations: "UPI-SWIGGY-...", "NEFT CR-ACME", "ACH DEBIT ...".
RAILS = re.compile(r"^(upi|neft|imps|rtgs|nach|ach|pos|eft)(\s+(cr|dr|debit|credit))?\s*[-/:]\s*")


def payee_key(text: str) -> str:
    """Groups statement text that names the same payee: 'SQ *BLUE BOTTLE 0412' ~ 'Blue Bottle'."""
    t = RAILS.sub("", PROCESSORS.sub("", text.lower().strip()))
    t = re.sub(r"\d{3,}|[#*]", " ", t)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z&' ]", " ", t)).strip()[:32]


def suggest(history: dict[str, int], key: str) -> int | None:
    """Category of the same payee seen before; failing that, of one whose name starts with the same whole words
    ('uber trip' ~ 'uber', 'swiggy payment' ~ 'swiggy')."""
    if key in history:
        return history[key]
    if len(key) < 3:
        return None
    matches = [k for k in history if len(k) >= 3 and (key.startswith(k + " ") or k.startswith(key + " "))]
    return history[max(matches, key=len)] if matches else None


def fingerprints(rows: list[Row]) -> list[str]:
    """Stable per-row ids. OFX rows use the bank's id; CSV rows hash their content, numbering identical rows
    (two $6.50 coffees the same day) so each still gets its own id."""
    seen: Counter = Counter()
    out = []
    for r in rows:
        if r.fitid:
            out.append(f"ofx:{r.fitid}")
            continue
        key = f"{r.date}|{r.amount.quantize(Decimal('0.01'))}|{re.sub(r'\s+', ' ', r.description.lower())}"
        seen[key] += 1
        out.append(hashlib.sha256(f"{key}|{seen[key]}".encode()).hexdigest()[:32])
    return out


def review(db: Connection, account: dict, parsed: Parsed) -> list[dict]:
    """Each row with its id, status and suggested category.

    status: new · duplicate (this exact row was imported before) · possible_duplicate (the account already has a
    transaction with the same date and amount, e.g. entered by hand or imported from another file format).
    """
    rows = parsed.rows
    hashes = fingerprints(rows)
    if not rows:
        return []
    existing = {r["import_hash"] for r in db.execute(
        "SELECT import_hash FROM transactions WHERE account_id = %s AND import_hash = ANY(%s)", (account["id"], hashes))}
    lo, hi = min(r.date for r in rows), max(r.date for r in rows)
    same_day = Counter({(r["date"], r["amount"]): r["n"] for r in db.execute("""
        SELECT date, amount, count(*) AS n FROM transactions
        WHERE account_id = %s AND date BETWEEN %s AND %s AND (import_hash IS NULL OR NOT (import_hash = ANY(%s)))
        GROUP BY date, amount""", (account["id"], lo, hi, hashes))})
    history = {}
    for r in db.execute("""
            SELECT DISTINCT ON (payee) payee, original_payee, category_id FROM transactions
            WHERE category_id IS NOT NULL ORDER BY payee, date DESC"""):
        for text in (r["payee"], r["original_payee"]):
            if text:
                history.setdefault(payee_key(text), r["category_id"])

    out = []
    for r, h in zip(rows, hashes):
        key = (r.date, r.amount.quantize(Decimal("0.0001")))
        if h in existing:
            status = "duplicate"
        elif same_day[key] > 0:
            same_day[key] -= 1
            status = "possible_duplicate"
        else:
            status = "new"
        out.append({"hash": h, "line": r.line, "date": r.date, "amount": r.amount, "description": r.description,
                    "balance": r.balance, "status": status, "category_id": suggest(history, payee_key(r.description))})
    return out


def commit(db: Connection, account: dict, filename: str, parsed: Parsed, choices: dict[str, dict],
           balance: tuple[Decimal, date] | None) -> dict:
    """Stores the chosen rows and the balances they imply, as one import that can be undone as a unit."""
    reviewed = review(db, account, parsed)
    picked = [r for r in reviewed if r["status"] != "duplicate"
              and choices.get(r["hash"], {}).get("include", r["status"] == "new")]
    with db.transaction():
        import_id = db.execute(
            "INSERT INTO imports (account_id, filename, format, row_count) VALUES (%s,%s,%s,%s) RETURNING id",
            (account["id"], filename, parsed.format, len(picked))).fetchone()["id"]
        with db.cursor() as cur:
            cur.executemany("""
                INSERT INTO transactions (account_id, date, amount, payee, original_payee, category_id, source, import_hash, import_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (account_id, import_hash) DO NOTHING""",
                [(account["id"], r["date"], r["amount"], r["description"], r["description"],
                  choices.get(r["hash"], {}).get("category_id", r["category_id"]), parsed.format, r["hash"], import_id)
                 for r in picked])
        snapshots = balances(db, account, parsed, balance)
        with db.cursor() as cur:
            cur.executemany("""
                INSERT INTO balance_snapshots (account_id, date, balance, import_id) VALUES (%s,%s,%s,%s)
                ON CONFLICT (account_id, date) DO UPDATE SET balance = EXCLUDED.balance, import_id = EXCLUDED.import_id""",
                [(account["id"], d, b, import_id) for d, b in snapshots.items()])
        if parsed.format == "csv" and parsed.mapping:
            db.execute("""
                INSERT INTO import_profiles (account_id, header, mapping) VALUES (%s,%s,%s)
                ON CONFLICT (account_id) DO UPDATE SET header = EXCLUDED.header, mapping = EXCLUDED.mapping, updated_at = now()""",
                (account["id"], parsed.header, Jsonb(asdict(parsed.mapping))))
    return {"id": import_id, "inserted": len(picked),
            "duplicates_skipped": sum(1 for r in reviewed if r["status"] == "duplicate"), "balances": len(snapshots)}


def balances(db: Connection, account: dict, parsed: Parsed, given: tuple[Decimal, date] | None) -> dict[date, Decimal]:
    """End-of-day balances, from the file's balance column, else from one known balance worked backwards."""
    liability = account["classification"] == "liability"
    with_balance = [r for r in parsed.rows if r.balance is not None]
    if with_balance and given is None:
        rows = with_balance if with_balance[0].date <= with_balance[-1].date else with_balance[::-1]  # oldest first
        out = {}
        for r in rows:  # within a day, the last row in time order carries the closing balance
            out[r.date] = abs(r.balance) if liability else r.balance
        return out
    known = given or parsed.ledger_balance
    if not known or not parsed.rows:
        return {}
    amount, as_of = known
    amount = abs(amount) if liability else amount
    start = min(r.date for r in parsed.rows)
    # Walk back from the known balance through every stored transaction, so earlier imports count too.
    txns = db.execute("""
        SELECT date, SUM(amount) AS total FROM transactions
        WHERE account_id = %s AND date > %s - 1 AND date <= %s GROUP BY date ORDER BY date DESC""",
        (account["id"], start, as_of)).fetchall()
    out, running = {as_of: amount}, amount
    for t in txns:
        # Balance at the end of the previous day = this day's closing balance minus (plus, for debts) its activity.
        prev = t["date"] - timedelta(days=1)
        running = running + t["total"] if liability else running - t["total"]
        if prev >= start - timedelta(days=1):
            out.setdefault(prev, running)
    return out
