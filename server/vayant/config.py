import os

# Local Postgres over the Unix socket as the current OS user. Override for other setups.
DATABASE_URL = os.environ.get("VAYANT_DATABASE_URL", "postgresql:///vayant")

# Currencies net worth can be reported in.
REPORTING_CURRENCIES = ("USD", "CAD", "INR")

# The only outbound network call: daily FX rates from open.er-api.com (no key). Set to 0 to disable.
FX_AUTO_REFRESH = os.environ.get("VAYANT_FX_AUTO_REFRESH", "1") == "1"
