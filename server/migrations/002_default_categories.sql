-- Starter category tree. Users can rename, add or remove any of these.
WITH groups(kind, name, children) AS (VALUES
  ('income',   'Income',            ARRAY['Salary', 'Bonus', 'Interest', 'Dividends', 'Rental Income', 'Other Income']),
  ('expense',  'Housing',           ARRAY['Rent', 'Mortgage', 'Property Tax', 'Maintenance', 'Utilities', 'Internet & Phone']),
  ('expense',  'Food & Dining',     ARRAY['Groceries', 'Restaurants', 'Coffee']),
  ('expense',  'Transportation',    ARRAY['Fuel', 'Public Transit', 'Rideshare', 'Car Payment', 'Car Insurance', 'Parking']),
  ('expense',  'Shopping',          ARRAY['Clothing', 'Electronics', 'Household']),
  ('expense',  'Health',            ARRAY['Medical', 'Pharmacy', 'Fitness', 'Health Insurance']),
  ('expense',  'Travel',            ARRAY['Flights', 'Hotels', 'Vacation']),
  ('expense',  'Lifestyle',         ARRAY['Entertainment', 'Subscriptions', 'Personal Care', 'Gifts', 'Charity']),
  ('expense',  'Family',            ARRAY['Childcare', 'Education', 'Family Support']),
  ('expense',  'Financial',         ARRAY['Taxes', 'Fees', 'Loan Interest', 'Life Insurance']),
  ('transfer', 'Transfers',         ARRAY['Transfer', 'Credit Card Payment', 'Investment Contribution', 'Remittance'])
),
parents AS (
  INSERT INTO categories (kind, name)
  SELECT kind, name FROM groups
  RETURNING id, kind, name
)
INSERT INTO categories (kind, name, parent_id)
SELECT p.kind, c, p.id
FROM parents p JOIN groups g ON g.name = p.name, unnest(g.children) AS c;
