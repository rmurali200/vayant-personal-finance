from typing import Annotated

from fastapi import Depends, Query
from psycopg import Connection

from ..db import get_db

DB = Annotated[Connection, Depends(get_db)]
CurrencyQ = Annotated[str, Query(pattern="^[A-Z]{3}$", description="Currency to report in")]
