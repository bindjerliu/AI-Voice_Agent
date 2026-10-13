import asyncio
import contextlib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.lib.cleanup import cleanup_loop
from app.routes import admin, agent, customers, outages, pending_reports


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = asyncio.create_task(cleanup_loop())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


PUBLIC_DIR = Path(__file__).resolve().parent.parent / "public"

app = FastAPI(title="KEDS Voice Agent Prototype", lifespan=lifespan)

app.include_router(customers.router)
app.include_router(outages.router)
app.include_router(pending_reports.router)
app.include_router(admin.router)
app.include_router(agent.router)

app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="public")
