from datetime import date


def add_account(db, name, type_, currency, balances):
    aid = db.execute("INSERT INTO accounts (name, type, currency) VALUES (%s,%s,%s) RETURNING id",
                     (name, type_, currency)).fetchone()["id"]
    for d, b in balances:
        db.execute("INSERT INTO balance_snapshots VALUES (%s,%s,%s)", (aid, d, b))
    return aid


def test_migrations_are_idempotent(db):
    from vayant.migrate import migrate
    assert migrate(db) == []


def test_fx_convert_goes_through_usd_and_uses_latest_rate_on_or_before(db):
    db.execute("""INSERT INTO fx_rates VALUES ('2026-01-01','CAD',1.40), ('2026-01-01','INR',84),
                                              ('2026-02-01','CAD',1.30)""")
    convert = lambda *a: float(db.execute("SELECT fx_convert(%s,%s,%s,%s) AS v", a).fetchone()["v"])
    assert convert(140, "CAD", "USD", date(2026, 1, 15)) == 100
    assert convert(100, "USD", "CAD", date(2026, 3, 1)) == 130
    assert convert(140, "CAD", "INR", date(2026, 1, 15)) == 8400
    assert convert(100, "CAD", "USD", date(2025, 6, 1)) == 100 / 1.4  # before any rate: earliest known


def test_net_worth_subtracts_liabilities_and_converts(client, db):
    db.execute("INSERT INTO fx_rates VALUES ('2026-01-01','CAD',1.25)")
    add_account(db, "Checking", "cash", "USD", [("2026-01-10", 1000)])
    add_account(db, "Visa", "credit", "CAD", [("2026-01-10", 250)])
    add_account(db, "Old", "cash", "USD", [("2026-02-10", 500)])
    db.commit()
    s = client.get("/api/net-worth", params={"start": "2026-01-01", "end": "2026-02-28"}).json()["series"]
    assert s[0] == {"date": "2026-01-31", "assets": 1000, "liabilities": 200, "net_worth": 800}
    assert s[1]["assets"] == 1500  # balances carry forward until the next snapshot
    cad = client.get("/api/net-worth", params={"currency": "CAD", "start": "2026-01-01", "end": "2026-01-31"}).json()
    assert cad["series"][0]["net_worth"] == 1000


def test_cash_flow_excludes_transfers(client, db):
    aid = add_account(db, "Checking", "cash", "USD", [])
    cat = lambda name: db.execute("SELECT id FROM categories WHERE name=%s", (name,)).fetchone()["id"]
    for amount, c in ((5000, "Salary"), (-1200, "Rent"), (-800, "Transfer")):
        db.execute("INSERT INTO transactions (account_id, date, amount, payee, category_id) VALUES (%s,'2026-03-05',%s,'x',%s)",
                   (aid, amount, cat(c)))
    db.commit()
    m = client.get("/api/cash-flow", params={"start": "2026-03-01", "end": "2026-03-31"}).json()["months"]
    assert m == [{"month": "2026-03-01", "income": 5000, "expenses": 1200, "net": 3800}]


def test_goal_progress_caps_fixed_allocations_at_balance(client, db):
    a = add_account(db, "Savings", "cash", "USD", [("2026-01-01", 3000)])
    b = add_account(db, "HYSA", "cash", "USD", [("2026-01-01", 10000)])
    gid = db.execute("INSERT INTO goals (name, currency, target_amount) VALUES ('Trip','USD',20000) RETURNING id").fetchone()["id"]
    db.execute("INSERT INTO goal_allocations VALUES (%s,%s,5000,NULL), (%s,%s,NULL,50)", (gid, a, gid, b))
    db.commit()
    [g] = client.get("/api/goals").json()
    assert (g["target"], g["current"]) == (20000, 8000)


def test_update_transaction(client, db):
    aid = add_account(db, "Checking", "cash", "USD", [])
    tid = db.execute("INSERT INTO transactions (account_id, date, amount, payee) VALUES (%s,'2026-03-05',-9,'SQ *CAFE') RETURNING id",
                     (aid,)).fetchone()["id"]
    db.commit()
    r = client.patch(f"/api/transactions/{tid}", json={"payee": "Corner Cafe", "notes": "with Sam"})
    assert (r.json()["payee"], r.json()["notes"]) == ("Corner Cafe", "with Sam")
    assert client.patch("/api/transactions/999999", json={"notes": "x"}).status_code == 404
