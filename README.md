# Vayant

A personal finance app that runs on your own computer. It tracks transactions, income, spending, investments, net worth (in USD, CAD and INR), reserve funds and goals across accounts in several countries. Your data stays in a local PostgreSQL database; nothing is sent to a cloud service.

**Status:** MVP in progress. Runs on generated sample data; real transactions come in through CSV or OFX/QFX import. Connecting an aggregator is next.

## What it does

| Screen | Shows |
| --- | --- |
| Overview | Net worth, assets, liabilities, 12-month trend, this month's income and spending, recent transactions, goal progress |
| Accounts | Net worth over 3M–2Y; one section per currency with that currency's assets, liabilities and net |
| Transactions | One tab per account currency; search, filter by account, category and period; edit payee, category and notes |
| Cash flow | Income vs spending by month, savings rate, category breakdown that opens the matching transactions |
| Investments | Allocation by asset class, then by security type (ETF, mutual fund, stock, bond, GIC, FD); holdings in one table per currency, with gain since purchase |
| Goals | Savings goals and reserve funds, each funded by a share or fixed amount of one or more accounts |
| Import (from Accounts) | CSV or OFX/QFX files from any bank: column mapping remembered per account, duplicate detection, suggested categories, review before saving, undo per import |

Lists never mix currencies: accounts, holdings and transactions each get a section or tab per currency and show amounts in that currency only. Totals and charts that combine currencies (net worth, cash flow, allocation) use the reporting currency (USD, CAD or INR), switched from the header; historical values convert at the exchange rate of their own date.

## Stack

- **Server:** Python 3.12+, FastAPI, psycopg 3 with plain SQL (no ORM), PostgreSQL 17
- **Web:** React 19, TypeScript, Vite. No UI kit, state library or chart library: charts are hand-written SVG
- **Design:** the Vayant design system. `web/design/tokens.json` generates `web/src/styles/tokens.css`; components are ported in `web/src/ui/components.tsx`
- **API types:** generated from FastAPI's OpenAPI spec into `web/src/lib/api-types.ts`

Runtime dependencies: `fastapi`, `uvicorn`, `psycopg` on the server; `react`, `react-dom` in the browser.

## Setup (macOS)

```sh
brew install postgresql@17 && brew services start postgresql@17
createdb vayant

cd server
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m scripts.seed          # sample data; --reset to start over

cd ../web
npm install
```

## Run

Development, with hot reload (two terminals):

```sh
cd server && .venv/bin/python -m vayant   # API on http://127.0.0.1:8600
cd web && npm run dev                     # app on http://localhost:5173
```

Everyday use, one process:

```sh
cd web && npm run build
cd ../server && .venv/bin/python -m vayant   # app and API on http://127.0.0.1:8600
```

The server listens on 127.0.0.1 only.

## Tests

```sh
createdb vayant_test
cd server && .venv/bin/python -m pytest
cd web && npx tsc --noEmit
```

## Configuration

Environment variables, all optional:

| Variable | Default | Purpose |
| --- | --- | --- |
| `VAYANT_DATABASE_URL` | `postgresql:///vayant` | Database connection |
| `VAYANT_FX_AUTO_REFRESH` | `1` | Set to `0` to stop the daily exchange-rate fetch |

The repository holds no credentials or keys. Anything account-specific is entered after installation and lives only in your database.

## Network use

The app makes one outbound request: once a day it fetches exchange rates from [open.er-api.com](https://www.exchangerate-api.com/docs/free) (free, no key). If that fails it keeps using the last stored rates. Fonts are self-hosted.

## Importing transactions

Banks have no common CSV layout, so the importer works it out per file and lets you correct it:

- **Finding the data:** skips preamble and summary lines, finds the header (or works without one), and detects the delimiter and date format. Day-first vs month-first is settled from the dates themselves, or asked when every date fits both.
- **Columns:** guesses date, description, and either one signed amount or separate money-out/money-in columns, plus an optional running balance. Amounts like `1,23,456.00`, `(84.20)`, `84.20 DR` and `₹`/`CA$` prefixes are understood. Card exports that show charges as positive are flipped. The mapping is saved per account and reused while the file's header stays the same.
- **OFX/QFX:** read directly (SGML 1.x and XML 2.x), using the bank's transaction ids and reported balance.
- **Duplicates:** each row gets a fingerprint, so re-importing an overlapping date range adds nothing twice. Rows matching an existing transaction's date and amount (for example one entered by hand) are flagged and left out unless ticked.
- **Categories:** suggested from earlier transactions with the same payee, ignoring card-processor and payment-rail prefixes (`SQ *`, `UPI-`, `NEFT CR-`).
- **Balances:** taken from the file's balance column or OFX balance; otherwise enter one known balance and earlier daily balances are worked out from the transactions.
- **Undo:** each import can be removed as a unit, with the transactions and balances it added.

Files are read and processed on your machine.

## Data model

- Amounts are `NUMERIC` in the account's own currency. Balances are stored as displayed (a card owing 500 has balance 500); `accounts.classification` decides whether an account adds to or subtracts from net worth.
- `balance_snapshots` holds each account's balance over time. Net worth history is computed from it, converting each balance at the rate for that date (`fx_convert` in `001_init.sql`).
- `fx_rates` stores units per USD; any pair converts through USD.
- Securities carry two independent labels, `asset_class` and `security_type`, so a bond ETF is fixed income and an ETF.
- A goal is funded by `goal_allocations`: a percentage or a fixed amount of an account's balance. A reserve fund is a goal whose target is N months of average spending.
- Schema changes go in new numbered files in `server/migrations/`, applied on startup.

## Layout

```
server/
  migrations/      numbered .sql files
  vayant/          FastAPI app: routes/, schemas.py, fx.py, migrate.py
  scripts/seed.py  sample data
  tests/
web/
  design/          tokens.json from the design system
  scripts/         token → CSS generator
  src/
    lib/           API client and generated types, formatting, settings, router
    ui/            design-system components, icons
    charts/        SVG line, column and stacked-bar charts
    pages/         one file per screen
```

## Roadmap

1. **MVP:** UI on sample data and CSV/OFX import (done); next, transfer matching across accounts and categorisation rules
2. **Aggregators:** connect accounts through Plaid, SimpleFIN or India's Account Aggregator network, one data source at a time behind a shared importer interface
3. **Local LLM:** categorisation and questions about your finances answered by a model running on this machine

## Licence

MIT
