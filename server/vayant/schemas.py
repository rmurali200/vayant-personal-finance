"""Response models. They define the OpenAPI spec the web client's types are generated from."""
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, PlainSerializer

# Exact Decimal on the server; a JSON number for the client, which only displays it.
Money = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
Currency = Annotated[str, "ISO 4217 code"]


class Account(BaseModel):
    id: int
    name: str
    type: str
    classification: Literal["asset", "liability"]
    currency: Currency
    mask: str | None
    institution: str | None
    country: str | None
    is_closed: bool
    in_net_worth: bool
    balance: Money | None
    balance_date: date | None
    balance_converted: Money | None


class Category(BaseModel):
    id: int
    name: str
    kind: Literal["income", "expense", "transfer"]
    parent_id: int | None
    icon: str | None


class Transaction(BaseModel):
    id: int
    account_id: int
    account_name: str
    date: date
    amount: Money
    currency: Currency
    payee: str
    category_id: int | None
    category_name: str | None
    category_group: str | None
    category_kind: str | None
    notes: str | None
    transfer_pair_id: int | None


class TransactionPage(BaseModel):
    total: int
    by_currency: dict[str, int]  # matches per account currency, ignoring the currency filter
    items: list[Transaction]


class TransactionUpdate(BaseModel):
    payee: str | None = None
    category_id: int | None = None
    notes: str | None = None


class NetWorthPoint(BaseModel):
    date: date
    assets: Money
    liabilities: Money
    net_worth: Money


class NetWorth(BaseModel):
    currency: Currency
    series: list[NetWorthPoint]


class CashFlowMonth(BaseModel):
    month: date
    income: Money
    expenses: Money
    net: Money


class CashFlowCategory(BaseModel):
    category_id: int | None  # None = uncategorised
    name: str
    group: str | None
    kind: Literal["income", "expense"]
    total: Money


class CashFlow(BaseModel):
    currency: Currency
    months: list[CashFlowMonth]
    categories: list[CashFlowCategory]


class Holding(BaseModel):
    account_id: int
    account_name: str
    security_id: int
    symbol: str | None
    name: str
    asset_class: str
    security_type: str | None
    currency: Currency
    quantity: Decimal
    price: Money | None
    price_date: date | None
    value: Money | None
    value_converted: Money | None
    cost_basis: Money | None
    maturity_date: date | None
    interest_rate: Decimal | None


class GoalAllocation(BaseModel):
    account_id: int
    account_name: str
    account_currency: Currency
    amount: Money | None
    percent: Decimal | None
    contributed_native: Money  # in the account's currency
    contributed: Money  # in the goal's currency


class Goal(BaseModel):
    id: int
    name: str
    kind: Literal["savings", "reserve"]
    currency: Currency
    target: Money
    target_months: Decimal | None
    target_date: date | None
    current: Money
    allocations: list[GoalAllocation]


class FxRates(BaseModel):
    date: date | None
    per_usd: dict[str, Money]


class ImportMapping(BaseModel):
    header_row: int | None
    date: int
    date_format: str
    description: int
    amount: int | None = None
    debit: int | None = None
    credit: int | None = None
    balance: int | None = None
    negate: bool = False


class ImportFile(BaseModel):
    account_id: int
    filename: str
    content: str = Field(max_length=10_000_000)
    mapping: ImportMapping | None = None


class RowChoice(BaseModel):
    hash: str
    include: bool
    category_id: int | None


class KnownBalance(BaseModel):
    amount: Money
    as_of: date


class ImportCommit(ImportFile):
    choices: list[RowChoice] = []
    balance: KnownBalance | None = None


class ImportRow(BaseModel):
    hash: str
    line: int
    date: date
    amount: Money
    description: str
    balance: Money | None
    status: Literal["new", "duplicate", "possible_duplicate"]
    category_id: int | None


class SkippedRow(BaseModel):
    line: int
    reason: str


class ImportPreview(BaseModel):
    format: Literal["csv", "ofx"]
    header: list[str] | None
    columns: int
    sample: list[list[str]]
    mapping: ImportMapping | None
    date_formats: list[str]
    profile_used: bool
    rows: list[ImportRow]
    skipped: list[SkippedRow]
    ledger_balance: KnownBalance | None
    file_currency: str | None


class ImportResult(BaseModel):
    id: int
    inserted: int
    duplicates_skipped: int
    balances: int


class ImportRecord(BaseModel):
    id: int
    account_id: int
    account_name: str
    filename: str
    format: str
    row_count: int
    created_at: datetime
