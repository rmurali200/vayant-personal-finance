-- Core schema. Amounts are NUMERIC (exact decimal) in the account's own currency.
-- Balances are stored as displayed: a credit card owing 500 has balance 500;
-- whether it counts for or against net worth comes from accounts.classification.

CREATE TABLE institutions (
  id      serial PRIMARY KEY,
  name    text NOT NULL,
  country char(2) NOT NULL,
  UNIQUE (name, country)
);

CREATE TABLE accounts (
  id             serial PRIMARY KEY,
  institution_id int REFERENCES institutions,
  name           text NOT NULL,
  type           text NOT NULL CHECK (type IN
                   ('cash', 'credit', 'investment', 'loan', 'property', 'other_asset', 'other_liability')),
  classification text GENERATED ALWAYS AS (
                   CASE WHEN type IN ('credit', 'loan', 'other_liability') THEN 'liability' ELSE 'asset' END
                 ) STORED,
  currency       char(3) NOT NULL,
  mask           text,                       -- last 4 digits, for display only
  is_closed      boolean NOT NULL DEFAULT false,
  in_net_worth   boolean NOT NULL DEFAULT true,
  created_at     timestamptz NOT NULL DEFAULT now()
);

-- Daily (or less frequent) balance per account. Net worth history is derived from this.
CREATE TABLE balance_snapshots (
  account_id int NOT NULL REFERENCES accounts ON DELETE CASCADE,
  date       date NOT NULL,
  balance    numeric(19, 4) NOT NULL,
  PRIMARY KEY (account_id, date)
);

-- One tree for income, expense and transfer categories. Transfers are excluded from cash flow.
CREATE TABLE categories (
  id        serial PRIMARY KEY,
  name      text NOT NULL,
  kind      text NOT NULL CHECK (kind IN ('income', 'expense', 'transfer')),
  parent_id int REFERENCES categories,
  icon      text,
  UNIQUE NULLS NOT DISTINCT (parent_id, name)
);

CREATE TABLE transactions (
  id               bigserial PRIMARY KEY,
  account_id       int NOT NULL REFERENCES accounts ON DELETE CASCADE,
  date             date NOT NULL,
  amount           numeric(19, 4) NOT NULL,  -- negative = money out of the account
  payee            text NOT NULL,
  original_payee   text,                     -- raw statement text, kept for re-categorisation rules
  category_id      int REFERENCES categories,
  notes            text,
  transfer_pair_id bigint REFERENCES transactions ON DELETE SET NULL,
  source           text NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'csv', 'aggregator')),
  import_hash      text,                     -- dedupes re-imported rows
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (account_id, import_hash)
);
CREATE INDEX transactions_date_idx ON transactions (date DESC);
CREATE INDEX transactions_category_idx ON transactions (category_id);

-- Two independent axes, so a bond ETF is (fixed_income, etf) and a GIC is (fixed_income, gic).
CREATE TABLE securities (
  id            serial PRIMARY KEY,
  symbol        text,                        -- null for GICs, FDs and other unlisted holdings
  name          text NOT NULL,
  currency      char(3) NOT NULL,
  asset_class   text NOT NULL DEFAULT 'other' CHECK (asset_class IN
                  ('equity', 'fixed_income', 'cash', 'real_estate', 'commodity', 'crypto', 'other')),
  security_type text CHECK (security_type IN
                  ('stock', 'etf', 'mutual_fund', 'bond', 'gic', 'fixed_deposit', 'money_market', 'crypto', 'other')),
  maturity_date date,
  interest_rate numeric(7, 4),               -- percent, for GICs/FDs/bonds
  UNIQUE (symbol, currency)
);

CREATE TABLE security_prices (
  security_id int NOT NULL REFERENCES securities ON DELETE CASCADE,
  date        date NOT NULL,
  price       numeric(19, 6) NOT NULL,
  PRIMARY KEY (security_id, date)
);

-- Current position per account. Value history lives in balance_snapshots.
CREATE TABLE holdings (
  account_id  int NOT NULL REFERENCES accounts ON DELETE CASCADE,
  security_id int NOT NULL REFERENCES securities,
  quantity    numeric(24, 8) NOT NULL,
  cost_basis  numeric(19, 4),
  PRIMARY KEY (account_id, security_id)
);

-- Units of each currency per 1 USD. Any pair converts through USD.
CREATE TABLE fx_rates (
  date     date NOT NULL,
  currency char(3) NOT NULL,
  per_usd  numeric(20, 10) NOT NULL CHECK (per_usd > 0),
  PRIMARY KEY (currency, date)
);

-- A reserve fund is a goal with kind 'reserve' whose target can be N months of average expenses.
CREATE TABLE goals (
  id            serial PRIMARY KEY,
  name          text NOT NULL,
  kind          text NOT NULL DEFAULT 'savings' CHECK (kind IN ('savings', 'reserve')),
  currency      char(3) NOT NULL,
  target_amount numeric(19, 4),
  target_months numeric(5, 2),
  target_date   date,
  is_archived   boolean NOT NULL DEFAULT false,
  created_at    timestamptz NOT NULL DEFAULT now(),
  CHECK (target_amount IS NOT NULL OR target_months IS NOT NULL)
);

-- Earmarks part of an account toward a goal: a fixed amount or a share of the balance.
CREATE TABLE goal_allocations (
  goal_id    int NOT NULL REFERENCES goals ON DELETE CASCADE,
  account_id int NOT NULL REFERENCES accounts ON DELETE CASCADE,
  amount     numeric(19, 4) CHECK (amount > 0),
  percent    numeric(5, 2) CHECK (percent > 0 AND percent <= 100),
  PRIMARY KEY (goal_id, account_id),
  CHECK ((amount IS NULL) <> (percent IS NULL))
);

-- Rate for a currency on a date: latest on or before the date, else the earliest known.
CREATE FUNCTION fx_per_usd(cur char(3), d date) RETURNS numeric
LANGUAGE sql STABLE AS $$
  SELECT CASE WHEN cur = 'USD' THEN 1 ELSE COALESCE(
    (SELECT per_usd FROM fx_rates WHERE currency = cur AND date <= d ORDER BY date DESC LIMIT 1),
    (SELECT per_usd FROM fx_rates WHERE currency = cur ORDER BY date LIMIT 1)
  ) END
$$;

CREATE FUNCTION fx_convert(amount numeric, from_cur char(3), to_cur char(3), d date) RETURNS numeric
LANGUAGE sql STABLE AS $$
  SELECT CASE WHEN from_cur = to_cur THEN amount
              ELSE amount * fx_per_usd(to_cur, d) / fx_per_usd(from_cur, d) END
$$;
