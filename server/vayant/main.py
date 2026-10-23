import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import fx
from .config import FX_AUTO_REFRESH
from .db import connect
from .migrate import migrate
from .routes import accounts, fx as fx_routes, goals, investments, transactions

log = logging.getLogger("vayant")
WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"
FX_CHECK_SECONDS = 6 * 3600


def refresh_fx():
    with connect() as conn:
        fx.refresh(conn)


async def fx_loop():
    while True:
        try:
            await asyncio.to_thread(refresh_fx)
        except Exception as e:  # offline or API down: keep the last stored rates
            log.warning("FX refresh failed: %s", e)
        await asyncio.sleep(FX_CHECK_SECONDS)


@asynccontextmanager
async def lifespan(_: FastAPI):
    with connect() as conn:
        migrate(conn)
    task = asyncio.create_task(fx_loop()) if FX_AUTO_REFRESH else None
    yield
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="Vayant", lifespan=lifespan)
for r in (accounts, transactions, investments, goals, fx_routes):
    app.include_router(r.router, prefix="/api")

# In production the built web app is served from here; in development Vite serves it and proxies /api.
if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
