"""Fills the database with 18 months of realistic sample data across US, Canadian and Indian accounts.

    python -m scripts.seed           # refuses if accounts already exist
    python -m scripts.seed --reset   # wipes all data (categories are kept) and reseeds

Every name and number here is invented.
"""
import random
import sys
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from vayant import fx
from vayant.db import connect
from vayant.migrate import migrate

random.seed(7)
TODAY = date.today()
START = date(TODAY.year - 1, TODAY.month, 1) - timedelta(days=183)
START = START.replace(day=1)
FALLBACK_RATES = {"CAD": Decimal("1.38"), "INR": Decimal("84.0")}

# key: (institution, country, name, type, currency, mask, opening balance)
ACCOUNTS = {
    "chase":    ("Chase", "US", "Total Checking", "cash", "USD", "4821", 8200),
    "ally":     ("Ally", "US", "High-Yield Savings", "cash", "USD", "1177", 22000),
    "amex":     ("American Express", "US", "Gold Card", "credit", "USD", "1005", 1400),
    "fidelity": ("Fidelity", "US", "401(k)", "investment", "USD", "9932", None),
    "td":       ("TD", "CA", "All-Inclusive Chequing", "cash", "CAD", "3390", 6400),
    "eq":       ("EQ Bank", "CA", "Savings Plus", "cash", "CAD", "7712", 15000),
    "rbc":      ("RBC", "CA", "Avion Visa", "credit", "CAD", "2290", 450),
    "ws":       ("Wealthsimple", "CA", "TFSA", "investment", "CAD", "5501", None),
    "mortgage": ("TD", "CA", "Rental Condo Mortgage", "loan", "CAD", "8810", 318000),
    "condo":    (None, "CA", "Toronto Condo", "property", "CAD", None, 655000),
    "hdfc":     ("HDFC Bank", "IN", "Savings", "cash", "INR", "6604", 420000),
    "icici":    ("ICICI Bank", "IN", "Fixed Deposits", "investment", "INR", "0941", None),
    "zerodha":  ("Zerodha", "IN", "Demat", "investment", "INR", "ZK21", None),
}

# account: [(symbol, name, currency, asset_class, security_type, quantity, current price, monthly drift, vol, extra)]
HOLDINGS = {
    "fidelity": [
        ("FXAIX", "Fidelity 500 Index Fund", "USD", "equity", "mutual_fund", 520, 212.40, .008, .04, {}),
        ("FSPSX", "Fidelity International Index Fund", "USD", "equity", "mutual_fund", 900, 52.10, .005, .04, {}),
        ("BND", "Vanguard Total Bond Market ETF", "USD", "fixed_income", "etf", 400, 73.20, .002, .012, {}),
        ("SPAXX", "Fidelity Government Money Market", "USD", "cash", "money_market", 3200, 1.00, 0, 0, {}),
    ],
    "ws": [
        ("XEQT", "iShares Core Equity ETF Portfolio", "CAD", "equity", "etf", 1450, 36.80, .007, .035, {}),
        ("ZAG", "BMO Aggregate Bond Index ETF", "CAD", "fixed_income", "etf", 900, 14.10, .001, .012, {}),
        ("SHOP", "Shopify Inc.", "CAD", "equity", "stock", 45, 162.30, .012, .09, {}),
        (None, "Wealthsimple 1-Year GIC", "CAD", "fixed_income", "gic", 10000, 1.00, 0, 0,
         {"interest_rate": 3.85, "maturity_date": TODAY + timedelta(days=210)}),
    ],
    "zerodha": [
        ("NIFTYBEES", "Nippon India Nifty 50 BeES", "INR", "equity", "etf", 3200, 284.50, .009, .04, {}),
        ("RELIANCE", "Reliance Industries Ltd", "INR", "equity", "stock", 180, 2950.00, .007, .06, {}),
        (None, "Parag Parikh Flexi Cap Fund", "INR", "equity", "mutual_fund", 4100, 88.40, .011, .035, {}),
        (None, "HDFC Corporate Bond Fund", "INR", "fixed_income", "mutual_fund", 9500, 31.20, .006, .006, {}),
    ],
    "icici": [
        (None, "ICICI FD 7.10% (2027)", "INR", "fixed_income", "fixed_deposit", 500000, 1.00, 0, 0,
         {"interest_rate": 7.10, "maturity_date": date(TODAY.year + 1, 3, 15)}),
        (None, "ICICI FD 7.25% (2028)", "INR", "fixed_income", "fixed_deposit", 300000, 1.00, 0, 0,
         {"interest_rate": 7.25, "maturity_date": date(TODAY.year + 2, 1, 9)}),
    ],
}

# category path -> (payees, monthly count range, amount range) for variable card spending
SPEND = {
    "amex": {
        "Food & Dining/Groceries": (["Whole Foods Market", "Trader Joe's", "Safeway"], (6, 9), (35, 190)),
        "Food & Dining/Restaurants": (["Chipotle", "Sweetgreen", "Tartine", "Nopa"], (4, 8), (18, 120)),
        "Food & Dining/Coffee": (["Blue Bottle Coffee", "Philz Coffee"], (5, 10), (5, 9)),
        "Transportation/Rideshare": (["Uber", "Lyft"], (2, 5), (12, 48)),
        "Transportation/Fuel": (["Shell", "Chevron"], (1, 3), (40, 75)),
        "Shopping/Household": (["Target", "Amazon"], (2, 4), (20, 160)),
        "Shopping/Clothing": (["Uniqlo", "Patagonia"], (0, 2), (40, 180)),
        "Health/Pharmacy": (["CVS Pharmacy", "Walgreens"], (0, 2), (8, 45)),
        "Lifestyle/Entertainment": (["AMC Theatres", "Ticketmaster"], (0, 2), (25, 140)),
        "Lifestyle/Personal Care": (["Supercuts", "Sephora"], (0, 2), (25, 90)),
    },
    "rbc": {
        "Food & Dining/Groceries": (["Loblaws", "Metro"], (1, 3), (30, 110)),
        "Food & Dining/Coffee": (["Tim Hortons"], (0, 3), (3, 8)),
        "Housing/Maintenance": (["Home Depot"], (0, 1), (40, 300)),
    },
    "hdfc": {
        "Food & Dining/Restaurants": (["Swiggy", "Zomato"], (1, 4), (300, 1400)),
        "Shopping/Household": (["Amazon.in", "BigBasket"], (1, 3), (500, 4000)),
    },
}

FIXED = [  # (account, day, category, payee, amount or (low, high))
    ("chase", 15, "Income/Salary", "Acme Corp Payroll", 4650),
    ("chase", 28, "Income/Salary", "Acme Corp Payroll", 4650),
    ("chase", 1, "Housing/Rent", "Parkside Apartments", -3100),
    ("chase", 6, "Housing/Utilities", "PG&E", (-95, -180)),
    ("chase", 9, "Housing/Internet & Phone", "Comcast Xfinity", -79.99),
    ("chase", 12, "Housing/Internet & Phone", "T-Mobile", -65),
    ("amex", 3, "Lifestyle/Subscriptions", "Netflix", -15.49),
    ("amex", 8, "Lifestyle/Subscriptions", "Spotify", -11.99),
    ("amex", 2, "Health/Fitness", "Equinox", -245),
    ("td", 1, "Income/Rental Income", "Tenant e-Transfer", 3200),
    ("td", 3, "Housing/Mortgage", "TD Mortgage Payment", -1960),
    ("td", 5, "Housing/Maintenance", "Condo Corp #1342 Fees", -485),
    ("td", 18, "Financial/Life Insurance", "Sun Life", -42),
    ("hdfc", 5, "Family/Family Support", "Monthly Support - Parents", -25000),
    ("hdfc", 10, "Housing/Utilities", "BESCOM", (-1800, -3600)),
    ("hdfc", 12, "Housing/Internet & Phone", "Airtel", -999),
]

TRANSFERS = [  # (from, to, day, category, amount in the "from" currency)
    ("chase", "ally", 16, "Transfers/Transfer", 500),
    ("chase", "hdfc", 20, "Transfers/Remittance", 1200),
    ("hdfc", "zerodha", 7, "Transfers/Investment Contribution", 50000),
    ("td", "eq", 4, "Transfers/Transfer", 200),
]


def month_starts():
    d = START
    while d <= TODAY:
        yield d
        d = (d + timedelta(days=32)).replace(day=1)


def on_day(month: date, day: int) -> date | None:
    try:
        d = month.replace(day=day)
    except ValueError:
        d = (month + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    return d if START <= d <= TODAY else None


def money(x) -> Decimal:
    return Decimal(str(round(x, 2)))


def walk_back(current: float, drift: float, vol: float, months: int) -> list[float]:
    """Monthly prices ending at `current`, oldest first."""
    prices = [current]
    for _ in range(months):
        prices.append(prices[-1] / (1 + drift + random.gauss(0, vol)))
    return prices[::-1]


def seed(conn):
    cats = {r["path"]: r["id"] for r in conn.execute(
        "SELECT c.id, p.name || '/' || c.name AS path FROM categories c JOIN categories p ON p.id = c.parent_id")}

    # FX: a random walk ending at today's real rate when reachable, so history joins live data cleanly.
    try:
        _, live = fx.fetch()
    except Exception:
        live = {}
    days = (TODAY - START).days
    rates: dict[str, dict[date, Decimal]] = {}
    for cur, fallback in FALLBACK_RATES.items():
        r, series = float(live.get(cur, fallback)), {}
        for i in range(days + 1):
            series[TODAY - timedelta(days=i)] = Decimal(str(round(r, 6)))
            r *= 1 + random.gauss(0, 0.002)
        rates[cur] = series
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO fx_rates (date, currency, per_usd) VALUES (%s, %s, %s)",
                        [(d, c, r) for c, s in rates.items() for d, r in s.items()])
    if live:
        fx.store(conn, TODAY, {c: r for c, r in live.items() if c not in FALLBACK_RATES})

    def convert(amount: float, frm: str, to: str, d: date) -> float:
        per = lambda c: 1.0 if c == "USD" else float(rates[c][d])
        return amount * per(to) / per(frm)

    ids = {}
    for key, (inst, country, name, typ, ccy, mask, _) in ACCOUNTS.items():
        inst_id = None
        if inst:
            inst_id = conn.execute(
                """INSERT INTO institutions (name, country) VALUES (%s, %s)
                   ON CONFLICT (name, country) DO UPDATE SET name = EXCLUDED.name RETURNING id""",
                (inst, country)).fetchone()["id"]
        ids[key] = conn.execute(
            "INSERT INTO accounts (institution_id, name, type, currency, mask) VALUES (%s,%s,%s,%s,%s) RETURNING id",
            (inst_id, name, typ, ccy, mask)).fetchone()["id"]

    txns = []  # (account, date, amount, payee, category, pair_index)

    def add(acct, d, amount, payee, cat, pair=None):
        txns.append([acct, d, money(amount), payee, cat, pair])
        return len(txns) - 1

    card_spend = defaultdict(float)  # (card, month) -> total charged
    for m in month_starts():
        for acct, day, cat, payee, amt in FIXED:
            if d := on_day(m, day):
                add(acct, d, random.uniform(*amt) if isinstance(amt, tuple) else amt, payee, cat)
        for acct, cats_ in SPEND.items():
            for cat, (payees, (lo, hi), (amin, amax)) in cats_.items():
                for _ in range(random.randint(lo, hi)):
                    if d := on_day(m, random.randint(1, 28)):
                        amt = random.uniform(amin, amax)
                        add(acct, d, -amt, random.choice(payees), cat)
                        if acct in ("amex", "rbc"):
                            card_spend[(acct, m)] += amt
        if m.month in (3, 7, 12) and (d := on_day(m, 14)):
            add("amex", d, -random.uniform(650, 1400), random.choice(["United Airlines", "Air Canada"]), "Travel/Flights")
            card_spend[("amex", m)] += float(-txns[-1][2])
        if m.month == 3 and (d := on_day(m, 15)):
            add("chase", d, 12500, "Acme Corp Bonus", "Income/Bonus")
        if m.month in (2, 5, 8, 11) and (d := on_day(m, 1)):
            add("td", d, -1140, "City of Toronto", "Housing/Property Tax")
        if d := on_day(m, 27):  # savings interest
            add("ally", d, 22000 * 0.042 / 12, "Interest Paid", "Income/Interest")
            add("eq", d, 18000 * 0.03 / 12, "Interest Earned", "Income/Interest")
        if m.month in (3, 6, 9, 12) and (d := on_day(m, 30)):
            add("hdfc", d, random.uniform(2800, 3600), "Savings Interest", "Income/Interest")

        for frm, to, day, cat, amt in TRANSFERS:
            if d := on_day(m, day):
                i = add(frm, d, -amt, f"Transfer to {ACCOUNTS[to][2]}", cat)
                j = add(to, d, convert(amt, ACCOUNTS[frm][4], ACCOUNTS[to][4], d), f"Transfer from {ACCOUNTS[frm][2]}", cat, i)
                txns[i][5] = j
        # Pay last month's card statement in full.
        prev = (m - timedelta(days=1)).replace(day=1)
        for card, bank, day in (("amex", "chase", 22), ("rbc", "td", 20)):
            if (amt := card_spend.get((card, prev))) and (d := on_day(m, day)):
                i = add(bank, d, -amt, f"{ACCOUNTS[card][0]} Payment", "Transfers/Credit Card Payment")
                txns[i][5] = add(card, d, amt, "Payment — Thank You", "Transfers/Credit Card Payment", i)

    db_ids = {}
    for idx, (acct, d, amt, payee, cat, _) in sorted(enumerate(txns), key=lambda x: x[1][1]):
        db_ids[idx] = conn.execute(
            "INSERT INTO transactions (account_id, date, amount, payee, category_id) VALUES (%s,%s,%s,%s,%s) RETURNING id",
            (ids[acct], d, amt, payee, cats[cat])).fetchone()["id"]
    conn.cursor().executemany(
        "UPDATE transactions SET transfer_pair_id = %s WHERE id = %s",
        [(db_ids[t[5]], db_ids[i]) for i, t in enumerate(txns) if t[5] is not None])

    # Balances: cash and cards from running totals; loan, property and investments monthly.
    snaps = []
    running = {k: float(v[6]) for k, v in ACCOUNTS.items() if v[6] is not None}
    by_day = defaultdict(float)
    for acct, d, amt, *_ in txns:
        by_day[(acct, d)] += float(amt)
    for key, (_, _, _, typ, *_rest) in ACCOUNTS.items():
        if typ in ("cash", "credit"):
            snaps.append((ids[key], START - timedelta(days=1), money(running[key])))
            sign = -1 if typ == "credit" else 1  # a card's balance is what you owe
            for (acct, d), amt in sorted(by_day.items(), key=lambda x: x[0][1]):
                if acct == key:
                    running[key] += sign * amt
                    snaps.append((ids[key], d, money(running[key])))

    months = list(month_starts())
    month_ends = [min((m + timedelta(days=32)).replace(day=1) - timedelta(days=1), TODAY) for m in months]
    loan, home = running["mortgage"], running["condo"]
    for d in month_ends:
        loan -= 1960 - loan * 0.0489 / 12
        home *= 1 + random.gauss(0.002, 0.006)
        snaps += [(ids["mortgage"], d, money(loan)), (ids["condo"], d, money(home))]

    totals = defaultdict(float)  # (account, month index) -> market value
    for acct, positions in HOLDINGS.items():
        for symbol, name, ccy, cls, typ, qty, price, drift, vol, extra in positions:
            sec = conn.execute(
                """INSERT INTO securities (symbol, name, currency, asset_class, security_type, maturity_date, interest_rate)
                   VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (symbol, name, ccy, cls, typ, extra.get("maturity_date"), extra.get("interest_rate"))).fetchone()["id"]
            prices = walk_back(price, drift, vol, len(month_ends) - 1)
            conn.cursor().executemany(
                "INSERT INTO security_prices (security_id, date, price) VALUES (%s,%s,%s)",
                [(sec, d, Decimal(str(round(p, 4)))) for d, p in zip(month_ends, prices)])
            conn.execute("INSERT INTO holdings (account_id, security_id, quantity, cost_basis) VALUES (%s,%s,%s,%s)",
                         (ids[acct], sec, qty, money(qty * prices[0])))
            for i, p in enumerate(prices):
                totals[(acct, i)] += qty * p
    snaps += [(ids[a], month_ends[i], money(v)) for (a, i), v in totals.items()]

    conn.cursor().executemany(
        "INSERT INTO balance_snapshots (account_id, date, balance) VALUES (%s,%s,%s) "
        "ON CONFLICT (account_id, date) DO UPDATE SET balance = EXCLUDED.balance", snaps)

    goals = [
        ("Emergency reserve", "reserve", "USD", None, 6, None,
         [("ally", None, 100), ("eq", None, 50), ("hdfc", 200000, None)]),
        ("House down payment", "savings", "CAD", 150000, None, date(TODAY.year + 2, 6, 1),
         [("ws", None, 60), ("td", 3000, None)]),
        ("Kids' education", "savings", "INR", 2500000, None, date(TODAY.year + 8, 6, 1),
         [("icici", None, 100), ("zerodha", None, 40)]),
    ]
    for name, kind, ccy, target, months_, by, allocs in goals:
        gid = conn.execute(
            """INSERT INTO goals (name, kind, currency, target_amount, target_months, target_date)
               VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""", (name, kind, ccy, target, months_, by)).fetchone()["id"]
        conn.cursor().executemany(
            "INSERT INTO goal_allocations (goal_id, account_id, amount, percent) VALUES (%s,%s,%s,%s)",
            [(gid, ids[a], amt, pct) for a, amt, pct in allocs])
    return len(txns), len(snaps)


def main():
    with connect() as conn:
        migrate(conn)
        if "--reset" in sys.argv:
            conn.execute("""TRUNCATE institutions, accounts, balance_snapshots, transactions, securities,
                            security_prices, holdings, fx_rates, goals, goal_allocations, imports, import_profiles
                            RESTART IDENTITY CASCADE""")
        elif conn.execute("SELECT 1 FROM accounts LIMIT 1").fetchone():
            sys.exit("Database already has accounts. Use --reset to replace everything with sample data.")
        n_txn, n_snap = seed(conn)
    print(f"Seeded {len(ACCOUNTS)} accounts, {n_txn} transactions, {n_snap} balance snapshots.")


if __name__ == "__main__":
    main()
