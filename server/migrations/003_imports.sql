-- File imports (CSV, OFX/QFX). Deleting an import removes the transactions and balances it added.
CREATE TABLE imports (
  id         serial PRIMARY KEY,
  account_id int NOT NULL REFERENCES accounts ON DELETE CASCADE,
  filename   text NOT NULL,
  format     text NOT NULL CHECK (format IN ('csv', 'ofx')),
  row_count  int NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE transactions ADD COLUMN import_id int REFERENCES imports ON DELETE CASCADE;
ALTER TABLE balance_snapshots ADD COLUMN import_id int REFERENCES imports ON DELETE CASCADE;
CREATE INDEX transactions_import_idx ON transactions (import_id);

ALTER TABLE transactions DROP CONSTRAINT transactions_source_check,
  ADD CONSTRAINT transactions_source_check CHECK (source IN ('manual', 'csv', 'ofx', 'aggregator'));

-- The column mapping last used for an account's CSV files, reused while the file's header is unchanged.
CREATE TABLE import_profiles (
  account_id int PRIMARY KEY REFERENCES accounts ON DELETE CASCADE,
  header     text[],
  mapping    jsonb NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);
