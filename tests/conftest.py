"""Shared fixtures: every test gets its own throw-away SQLite database."""
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Make `import app...` work no matter where pytest is launched from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db as db_module  # noqa: E402
from app.routes import admin, customers, outages, pending_reports  # noqa: E402


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    """A connection to a fresh, seeded temporary database."""
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "keds-test.db")
    db_module.init_db()
    connection = db_module.get_connection()
    yield connection
    connection.close()


@pytest.fixture()
def client(conn):
    """HTTP client for every router except the LLM agent (needs an API key / engine)."""
    api = FastAPI()
    for module in (customers, outages, pending_reports, admin):
        api.include_router(module.router)
    return TestClient(api)


@pytest.fixture()
def area():
    return "Prishtinë - Qendër"


def add_report(conn, phone, area, consent=1, expires_at="2999-01-01T00:00:00.000Z"):
    cur = conn.execute(
        "INSERT INTO pending_reports (phone, area, consent_to_sms, expires_at) VALUES (?, ?, ?, ?)",
        (phone, area, consent, expires_at),
    )
    conn.commit()
    return cur.lastrowid


def add_outage(conn, area, status="confirmed"):
    cur = conn.execute(
        "INSERT INTO outages (area, cause, status, confirmed_at) VALUES (?, 'test', ?, "
        "strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
        (area, status),
    )
    conn.commit()
    return conn.execute("SELECT * FROM outages WHERE id = ?", (cur.lastrowid,)).fetchone()
