# Vayant

A personal finance app that runs on your own computer. It tracks transactions, income, spending, investments, net worth (in USD, CAD and INR), reserve funds and goals across accounts in several countries. Your data stays in a local PostgreSQL database; nothing is sent to a cloud service.

**Status:** MVP in progress. The UI and API run on generated sample data. Importing real data (CSV first, then an aggregator) is next.

## What it does

| Screen | Shows |
| --- | --- |
| Overview | Net worth, assets, liabilities, 12-month trend, this month's income and spending, recent transactions, goal progress |
| Accounts | Net worth over 3M–2Y, every account grouped by type, balances in the account's currency and the reporting currency |
| Transactions | Search, filter by account, category and period; edit payee, category and notes |
| Cash flow | Income vs spending by month, savings rate, category breakdown that opens the matching transactions |
| Investments | Allocation by asset class, then by security type (ETF, mutual fund, stock, bond, GIC, FD); holdings with gain since purchase |
| Goals | Savings goals and reserve funds, each funded by a share or fixed amount of one or more accounts |

Switch the reporting currency (USD, CAD, INR) from the header. Historical values convert at the exchange rate of their own date.

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

1. **MVP:** UI on sample data, then CSV import with saved column mappings per institution
2. **Aggregators:** connect accounts through Plaid, SimpleFIN or India's Account Aggregator network, one data source at a time behind a shared importer interface
3. **Local LLM:** categorisation and questions about your finances answered by a model running on this machine

## Licence

MIT
