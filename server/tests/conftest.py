import os

os.environ.setdefault("VAYANT_DATABASE_URL", "postgresql:///vayant_test")
os.environ["VAYANT_FX_AUTO_REFRESH"] = "0"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from vayant.db import connect  # noqa: E402
from vayant.main import app  # noqa: E402
from vayant.migrate import migrate  # noqa: E402


@pytest.fixture
def db():
    """A freshly migrated, empty database for each test."""
    with connect() as conn:
        conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
        migrate(conn)
        yield conn


@pytest.fixture
def client(db):
    db.commit()
    with TestClient(app) as c:
        yield c
