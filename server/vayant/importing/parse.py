"""Turns bank export files into rows: date, signed amount, description, optional running balance.

CSV exports have no standard layout, so this finds the header row, guesses which column is which,
and lets the caller override every guess with an explicit mapping.
"""
import csv
import html
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

# Day-first and month-first variants are both listed; guess_mapping orders them by the account's country.
DATE_FORMATS = [
    "%Y-%m-%d", "%Y/%m/%d",
    "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y",
    "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%d.%m.%Y",
    "%d %b %Y", "%d-%b-%Y", "%d-%b-%y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y", "%b %d %Y",
]
MONTH_FIRST = {"%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y"}
DAY_FIRST = {"%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%d.%m.%Y"}

# Header keywords, checked in this order so "Withdrawal Amt." is a debit, not an amount.
NAMES = {
    "debit": ("debit", "withdrawal", "paid out", "money out", "dr"),
    "credit": ("credit", "deposit", "paid in", "money in", "cr"),
    "balance": ("balance",),
    "amount": ("amount", "amt", "value"),
    "description": ("description", "narration", "details", "payee", "merchant", "particulars", "memo", "name", "transaction"),
    "date": ("transaction date", "trans date", "txn date", "date", "posted", "posting"),
}


@dataclass
class Mapping:
    header_row: int | None  # index into the file's rows; None when the file has no header
    date: int
    date_format: str
    description: int
    amount: int | None = None  # one signed column, or …
    debit: int | None = None   # … separate money-out and money-in columns
    credit: int | None = None
    balance: int | None = None
    negate: bool = False       # the file shows money out as positive (common on card exports)


@dataclass
class Row:
    line: int  # 1-based line in the file, for messages
    date: date
    amount: Decimal
    description: str
    balance: Decimal | None = None
    fitid: str | None = None  # OFX's unique transaction id


@dataclass
class Parsed:
    format: str  # csv | ofx
    rows: list[Row]
    skipped: list[tuple[int, str]] = field(default_factory=list)
    header: list[str] | None = None
    columns: int = 0
    sample: list[list[str]] = field(default_factory=list)
    mapping: Mapping | None = None
    date_formats: list[str] = field(default_factory=list)
    ledger_balance: tuple[Decimal, date] | None = None
    currency: str | None = None


# ---- Values ----

def parse_date(value: str, fmt: str) -> date | None:
    v = value.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}[T ]", v):  # ISO timestamp: keep the date part
        v = v[:10]
    try:
        return datetime.strptime(v, fmt).date()
    except ValueError:
        return None


CURRENCY = r"(?:CA\$|US\$|C\$|Rs\.?|INR|USD|CAD|[$₹€£])"
AMOUNT = re.compile(rf"(\()?\s*(-)?\s*{CURRENCY}?\s*(-)?\s*([\d,]*\.?\d+)\s*(-)?\s*(\))?", re.I)


def parse_amount(value: str | None) -> Decimal | None:
    """Accepts 1,234.56 · 1,23,456.00 · (84.20) · 84.20- · −84.20 · 84.20 DR · ₹ $ CA$ prefixes. Rejects dates."""
    if value is None:
        return None
    s = value.strip().replace("−", "-")
    neg = False
    if len(s) > 2 and s[-2:].upper() in ("DR", "CR") and not s[-3].isalpha():
        neg, s = s[-2:].upper() == "DR", s[:-2].strip()
    m = AMOUNT.fullmatch(s)
    if not m or (m.group(1) is None) != (m.group(6) is None):
        return None
    n = Decimal(m.group(4).replace(",", ""))
    return -n if neg or any(m.group(i) for i in (1, 2, 3, 5)) else n


def looks_like_date(value: str) -> bool:
    return any(parse_date(value, f) for f in DATE_FORMATS)


def matching_formats(values: list[str], country: str | None = None) -> list[str]:
    """Formats that read every value, best guess first: month-first in the US, day-first elsewhere."""
    vals = [v for v in values if v.strip()][:300]
    counts = {f: sum(1 for v in vals if parse_date(v, f)) for f in DATE_FORMATS}
    best = max(counts.values(), default=0)
    if not vals or best < 0.8 * len(vals):  # a few footer rows may sit in the date column
        return []
    fits = [f for f, c in counts.items() if c == best]
    first, second = (MONTH_FIRST, DAY_FIRST) if country == "US" else (DAY_FIRST, MONTH_FIRST)
    return sorted(fits, key=lambda f: 0 if f in first else 2 if f in second else 1)


# ---- CSV ----

def read_table(text: str) -> list[list[str]]:
    text = text.lstrip("﻿")
    try:
        dialect = csv.Sniffer().sniff(text[:20000], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = []
    for r in csv.reader(io.StringIO(text), dialect):
        cells = [c.strip() for c in r]
        while cells and not cells[-1]:
            cells.pop()
        rows.append(cells)
    return rows


def find_header(rows: list[list[str]]) -> int | None:
    """The first row of three or more text cells that is followed by a row containing a date."""
    for i, r in enumerate(rows[:40]):
        cells = [c for c in r if c]
        if len(cells) < 3 or any(parse_amount(c) is not None or looks_like_date(c) for c in cells):
            continue
        nxt = next((n for n in rows[i + 1:i + 4] if any(n)), [])
        if any(looks_like_date(c) for c in nxt):
            return i
    return None


def data_rows(rows: list[list[str]], header_row: int | None) -> list[tuple[int, list[str]]]:
    start = 0 if header_row is None else header_row + 1
    if header_row is None:  # skip anything above the first row that carries a date
        start = next((i for i, r in enumerate(rows) if len([c for c in r if c]) >= 2 and any(looks_like_date(c) for c in r)), len(rows))
    return [(i + 1, r) for i, r in enumerate(rows) if i >= start and any(r)]


def _column(rows: list[list[str]], i: int) -> list[str]:
    return [r[i] if i < len(r) else "" for _, r in rows]


def guess_mapping(rows: list[list[str]], account_type: str, country: str | None) -> tuple[Mapping | None, list[str]]:
    header_row = find_header(rows)
    # Rows carrying a date: leaves out summary lines that statements put above and below the transactions.
    body = [(n, r) for n, r in data_rows(rows, header_row) if any(looks_like_date(c) for c in r)][:300]
    if not body:
        return None, []
    width = max(len(r) for _, r in body)
    names = [c.lower() for c in rows[header_row]] if header_row is not None else [""] * width
    names += [""] * (width - len(names))

    def by_name(role: str, taken: set[int], test=None) -> int | None:
        for kw in NAMES[role]:
            for i, n in enumerate(names):
                if i in taken or not n or not (re.search(rf"\b{re.escape(kw)}\b", n) if len(kw) <= 3 else kw in n):
                    continue
                if test is None or share(i, test) >= 0.8:
                    return i
        return None

    def share(i: int, test) -> float:
        vals = [v for v in _column(body, i) if v]
        return sum(1 for v in vals if test(v)) / len(vals) if vals else 0

    date_col = by_name("date", set(), looks_like_date)
    if date_col is None:
        date_col = next((i for i in range(width) if share(i, looks_like_date) >= 0.8), None)
    if date_col is None:
        return None, []
    formats = matching_formats(_column(body, date_col), country)
    if not formats:
        return None, []

    taken = {date_col}
    roles: dict[str, int | None] = {}
    for role in ("debit", "credit", "balance", "amount"):
        i = by_name(role, taken, lambda v: parse_amount(v) is not None)
        if i is not None:
            roles[role] = i
            taken.add(i)

    numeric = [i for i in range(width) if i not in taken and share(i, lambda v: parse_amount(v) is not None) >= 0.9]
    if not any(k in roles for k in ("amount", "debit", "credit")):
        if header_row is not None:
            numeric = [i for i in numeric if not names[i]] or numeric
        pair = next(((a, b) for a in numeric for b in numeric if a < b and _exclusive(body, a, b)), None)
        if pair:
            roles["debit"], roles["credit"] = pair
            rest = [i for i in numeric if i not in pair]
        elif numeric:
            roles["amount"], rest = numeric[0], numeric[1:]
        else:
            return None, formats
        if "balance" not in roles and rest:
            roles["balance"] = rest[-1]
        taken |= {i for i in roles.values() if i is not None}

    desc = by_name("description", taken)
    if desc is None:
        text_cols = [i for i in range(width) if i not in taken]
        desc = max(text_cols, key=lambda i: sum(len(v) for v in _column(body, i)), default=None)
    if desc is None:
        return None, formats

    m = Mapping(header_row=header_row, date=date_col, date_format=formats[0], description=desc,
                amount=roles.get("amount"), debit=roles.get("debit"), credit=roles.get("credit"), balance=roles.get("balance"))
    if account_type == "credit" and m.amount is not None:
        # On card exports, most rows are charges. If most amounts are positive, charges are shown positive.
        amounts = [a for a in (parse_amount(v) for v in _column(body, m.amount)) if a is not None]
        m.negate = bool(amounts) and sum(1 for a in amounts if a > 0) > len(amounts) * 0.6
    return m, formats


def _exclusive(body: list[tuple[int, list[str]]], a: int, b: int) -> bool:
    """True when, row by row, exactly one of the two columns has a value: a money-out / money-in pair."""
    pairs = [(bool(r[a]) if a < len(r) else False, bool(r[b]) if b < len(r) else False) for _, r in body]
    return len(pairs) > 1 and all(x != y for x, y in pairs)


def apply_mapping(rows: list[list[str]], m: Mapping) -> tuple[list[Row], list[tuple[int, str]]]:
    out, skipped = [], []
    cell = lambda r, i: r[i] if i is not None and i < len(r) else ""
    for line, r in data_rows(rows, m.header_row):
        d = parse_date(cell(r, m.date), m.date_format)
        if d is None:
            skipped.append((line, "No date in the date column"))
            continue
        if m.amount is not None:
            amount = parse_amount(cell(r, m.amount))
        else:
            out_, in_ = parse_amount(cell(r, m.debit)), parse_amount(cell(r, m.credit))
            amount = None if out_ is None and in_ is None else abs(in_ or 0) - abs(out_ or 0)
        if amount is None:
            skipped.append((line, "No amount"))
            continue
        out.append(Row(line=line, date=d, amount=-amount if m.negate else amount,
                       description=re.sub(r"\s+", " ", cell(r, m.description)) or "(no description)",
                       balance=parse_amount(cell(r, m.balance)) if m.balance is not None else None))
    return out, skipped


def parse_csv(text: str, account_type: str, country: str | None, mapping: Mapping | None = None) -> Parsed:
    rows = read_table(text)
    guessed, formats = guess_mapping(rows, account_type, country)
    m = mapping or guessed
    if m and not formats:
        formats = matching_formats(_column(data_rows(rows, m.header_row), m.date), country)
    header = rows[m.header_row] if m and m.header_row is not None else None
    body = data_rows(rows, m.header_row if m else find_header(rows))
    parsed = Parsed(format="csv", rows=[], header=header, mapping=m, date_formats=formats,
                    columns=max((len(r) for _, r in body), default=0), sample=[r for _, r in body[:8]])
    if m:
        parsed.rows, parsed.skipped = apply_mapping(rows, m)
    return parsed


# ---- OFX / QFX (SGML 1.x and XML 2.x) ----

def _tag(block: str, tag: str) -> str | None:
    m = re.search(rf"<{tag}>([^<\r\n]*)", block, re.I)
    return html.unescape(m.group(1).strip()) if m and m.group(1).strip() else None


def parse_ofx(text: str) -> Parsed:
    body = text[max(text.upper().find("<OFX>"), 0):]
    rows, skipped = [], []
    for n, m in enumerate(re.finditer(r"<STMTTRN>(.*?)</STMTTRN>", body, re.S | re.I), start=1):
        b = m.group(1)
        posted = _tag(b, "DTPOSTED") or ""
        d = parse_date(posted[:8], "%Y%m%d")
        amount = parse_amount(_tag(b, "TRNAMT"))
        if d is None or amount is None:
            skipped.append((n, "Missing date or amount"))
            continue
        name, memo = _tag(b, "NAME") or _tag(b, "PAYEE"), _tag(b, "MEMO")
        rows.append(Row(line=n, date=d, amount=amount, description=name or memo or "(no description)", fitid=_tag(b, "FITID")))
    ledger = None
    if (lm := re.search(r"<LEDGERBAL>(.*?)(</LEDGERBAL>|<AVAILBAL>|</STMTRS>|</CCSTMTRS>)", body, re.S | re.I)):
        amt, asof = parse_amount(_tag(lm.group(1), "BALAMT")), parse_date((_tag(lm.group(1), "DTASOF") or "")[:8], "%Y%m%d")
        if amt is not None and asof:
            ledger = (amt, asof)
    return Parsed(format="ofx", rows=rows, skipped=skipped, ledger_balance=ledger, currency=_tag(body, "CURDEF"))


def is_ofx(filename: str, text: str) -> bool:
    return filename.lower().endswith((".ofx", ".qfx")) or "<OFX>" in text[:5000].upper()
