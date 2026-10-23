"""Response models. They define the OpenAPI spec the web client's types are generated from."""
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, PlainSerializer

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
