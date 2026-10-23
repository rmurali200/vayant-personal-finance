from datetime import date
from decimal import Decimal
from pathlib import Path

from vayant.importing.parse import parse_csv, parse_ofx

FIX = Path(__file__).parent / "fixtures"
read = lambda name: (FIX / name).read_text()


def test_signed_amount_with_header_and_balance():
    p = parse_csv(read("checking_signed.csv"), "cash", "US")
    m = p.mapping
    assert (m.header_row, m.date, m.description, m.amount, m.balance, m.date_format) == (0, 0, 1, 2, 3, "%m/%d/%Y")
    assert not m.negate and len(p.rows) == 6
    assert p.rows[0].amount == Decimal("-1739.21") and p.rows[0].date == date(2026, 10, 22)


def test_card_export_with_positive_charges_is_flipped():
    p = parse_csv(read("card_positive_charges.csv"), "credit", "US")
    assert p.mapping.negate
    assert [r.amount for r in p.rows][:1] == [Decimal("-84.20")] and p.rows[3].amount == Decimal("1200.00")


def test_statement_with_preamble_footer_and_withdrawal_deposit_columns():
    p = parse_csv(read("india_savings.csv"), "cash", "IN")
    m = p.mapping
    assert (m.header_row, m.date_format, m.debit, m.credit, m.balance, m.description) == (4, "%d/%m/%y", 4, 5, 6, 1)
    assert [r.amount for r in p.rows] == [Decimal("-1250.00"), Decimal("113878.35"), Decimal("-2840.00"), Decimal("-25000.00")]
    assert p.rows[0].balance == Decimal("418750.00") and p.rows[0].date == date(2026, 9, 5)
    assert len(p.skipped) == 2  # the two summary lines at the bottom


def test_headerless_file_finds_debit_credit_pair_and_balance():
    p = parse_csv(read("no_header_debit_credit.csv"), "cash", "CA")
    m = p.mapping
    assert (m.header_row, m.date_format, m.debit, m.credit, m.balance) == (None, "%m/%d/%Y", 2, 3, 4)
    assert p.rows[1].amount == Decimal("3200.00") and p.rows[0].amount == Decimal("-84.31")


def test_ofx_sgml():
    p = parse_ofx(read("card_statement.ofx"))
    assert [(r.date, r.amount, r.fitid) for r in p.rows][0] == (date(2026, 10, 21), Decimal("-84.20"), "2026102101")
    assert p.rows[0].description == "WHOLE FOODS MARKET & CAFE"
    assert p.ledger_balance == (Decimal("-1907.30"), date(2026, 10, 23)) and p.currency == "USD"


# ---- API ----

def account(db, type_="cash", currency="USD", country="US"):
    inst = db.execute("INSERT INTO institutions (name, country) VALUES ('Bank', %s) RETURNING id", (country,)).fetchone()["id"]
    return db.execute("INSERT INTO accounts (institution_id, name, type, currency) VALUES (%s,'Acct',%s,%s) RETURNING id",
                      (inst, type_, currency)).fetchone()["id"]


def test_import_dedupes_on_reimport_and_records_balances(client, db):
    aid = account(db)
    db.commit()
    body = {"account_id": aid, "filename": "checking.csv", "content": read("checking_signed.csv")}
    prev = client.post("/api/imports/preview", json=body).json()
    assert [r["status"] for r in prev["rows"]] == ["new"] * 6
    assert len({r["hash"] for r in prev["rows"]}) == 6  # the two identical coffees stay distinct

    res = client.post("/api/imports", json=body).json()
    assert res["inserted"] == 6 and res["balances"] == 4
    snap = db.execute("SELECT balance FROM balance_snapshots WHERE account_id=%s AND date='2026-10-15'", (aid,)).fetchone()
    assert snap["balance"] == Decimal("57067.70")  # closing balance of the day, not the first row's

    again = client.post("/api/imports/preview", json=body).json()
    assert {r["status"] for r in again["rows"]} == {"duplicate"} and again["profile_used"]
    assert client.post("/api/imports", json=body).json()["inserted"] == 0


def test_possible_duplicate_of_a_manual_entry_is_left_out_by_default(client, db):
    aid = account(db, "credit")
    db.execute("INSERT INTO transactions (account_id, date, amount, payee) VALUES (%s,'2026-10-19',-23.10,'Uber')", (aid,))
    db.commit()
    body = {"account_id": aid, "filename": "card.csv", "content": read("card_positive_charges.csv")}
    rows = client.post("/api/imports/preview", json=body).json()["rows"]
    assert [r["status"] for r in rows].count("possible_duplicate") == 1
    assert client.post("/api/imports", json=body).json()["inserted"] == 4


def test_category_suggested_from_history_and_choices_override(client, db):
    aid = account(db)
    groceries = db.execute("SELECT id FROM categories WHERE name='Groceries'").fetchone()["id"]
    rent = db.execute("SELECT id FROM categories WHERE name='Rent'").fetchone()["id"]
    db.execute("INSERT INTO transactions (account_id, date, amount, payee, category_id) VALUES (%s,'2026-01-01',-1,'Blue Bottle 0101',%s)",
               (aid, groceries))
    db.commit()
    body = {"account_id": aid, "filename": "c.csv", "content": read("checking_signed.csv")}
    rows = client.post("/api/imports/preview", json=body).json()["rows"]
    coffee = [r for r in rows if "BLUE BOTTLE" in r["description"]]
    assert {r["category_id"] for r in coffee} == {groceries}
    rent_row = next(r for r in rows if "RENT" in r["description"])
    choices = [{"hash": rent_row["hash"], "include": True, "category_id": rent}, {"hash": coffee[0]["hash"], "include": False, "category_id": None}]
    assert client.post("/api/imports", json=body | {"choices": choices}).json()["inserted"] == 5
    assert db.execute("SELECT category_id FROM transactions WHERE payee LIKE '%%RENT%%'").fetchone()["category_id"] == rent


def test_ofx_liability_balance_walks_back_and_undo_removes_everything(client, db):
    aid = account(db, "credit")
    db.commit()
    body = {"account_id": aid, "filename": "card.ofx", "content": read("card_statement.ofx")}
    prev = client.post("/api/imports/preview", json=body).json()
    assert prev["format"] == "ofx" and prev["ledger_balance"]["amount"] == -1907.30
    res = client.post("/api/imports", json=body).json()
    owed = {r["date"].isoformat(): r["balance"] for r in db.execute(
        "SELECT date, balance FROM balance_snapshots WHERE account_id=%s", (aid,))}
    assert owed["2026-10-23"] == Decimal("1907.30")
    assert owed["2026-10-20"] == Decimal("1823.10")  # before the 84.20 charge on the 21st
    assert owed["2026-10-11"] == Decimal("3000.00")  # before the 23.10 charge and the 1,200 payment

    assert client.delete(f"/api/imports/{res['id']}").status_code == 204
    assert db.execute("SELECT count(*) AS n FROM transactions WHERE account_id=%s", (aid,)).fetchone()["n"] == 0
    assert db.execute("SELECT count(*) AS n FROM balance_snapshots WHERE account_id=%s", (aid,)).fetchone()["n"] == 0


def test_explicit_mapping_is_validated(client, db):
    aid = account(db)
    db.commit()
    bad = {"header_row": 0, "date": 0, "date_format": "%s", "description": 1, "amount": 2}
    body = {"account_id": aid, "filename": "c.csv", "content": read("checking_signed.csv"), "mapping": bad}
    assert client.post("/api/imports/preview", json=body).status_code == 422
