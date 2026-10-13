"""SQLite data layer.

Prototype note: a real KEDS deployment would use Postgres (or whatever
the corporate DB standard is) behind the billing/CRM/outage systems.
SQLite is used here because it needs zero setup and the whole database
is a single inspectable file, which suits a bootcamp demo.
"""
import sqlite3
from pathlib import Path

from app.lib.constants import AREAS

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "keds.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    area TEXT NOT NULL,
    meter_number TEXT NOT NULL UNIQUE,
    balance REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS outages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    area TEXT NOT NULL,
    cause TEXT,
    status TEXT NOT NULL DEFAULT 'reported'
        CHECK (status IN ('reported', 'confirmed', 'in_progress', 'restored')),
    eta TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    confirmed_at TEXT
);

CREATE TABLE IF NOT EXISTS pending_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT NOT NULL,
    area TEXT NOT NULL,
    consent_to_sms INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    expires_at TEXT NOT NULL,
    matched_outage_id INTEGER REFERENCES outages(id),
    notified_at TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    details TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_outages_area_status ON outages(area, status);
CREATE INDEX IF NOT EXISTS idx_pending_reports_area ON pending_reports(area, matched_outage_id);
"""

SEED_CUSTOMERS = [
    # name, phone, area, meter_number, balance
    ("Arben Krasniqi", "+38344111222", "Prishtinë - Qendër", "MTR-001122", 12.50),
    ("Blerina Hoxha", "+38344222333", "Prishtinë - Qendër", "MTR-001123", -5.00),
    ("Fatmir Berisha", "+38345333444", "Prishtinë - Lakrishtë", "MTR-001124", 0.00),
    ("Vlora Gashi", "+38345444555", "Prishtinë - Lakrishtë", "MTR-001125", 34.20),
    ("Driton Morina", "+38349555666", "Prizren - Qendër", "MTR-001126", 8.75),
    ("Elmedina Rama", "+38349666777", "Prizren - Qendër", "MTR-001127", 0.00),
    ("Ilir Shala", "+38343777888", "Pejë - Kala", "MTR-001128", -12.30),
    ("Njomza Krasniqi", "+38343888999", "Pejë - Kala", "MTR-001129", 5.60),
    ("Bashkim Zeneli", "+38348999000", "Gjilan - Qendër", "MTR-001130", 0.00),
    ("Donjeta Ismaili", "+38348000111", "Gjilan - Qendër", "MTR-001131", 22.10),
    ("Agron Thaçi", "+38346111333", "Ferizaj - Stacion", "MTR-001132", 3.40),
    ("Lumnije Bytyqi", "+38346222444", "Ferizaj - Stacion", "MTR-001133", -1.00),
]


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: FastAPI's sync-dependency handling can enter/exit
    # this generator on different worker threads within a single request, which
    # sqlite3's default thread-affinity check would otherwise reject. Safe here
    # because each request gets its own connection, never shared concurrently.
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    """FastAPI dependency: one connection per request."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        _seed_if_empty(conn)
    finally:
        conn.close()


def _seed_if_empty(conn: sqlite3.Connection) -> None:
    count = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    if count > 0:
        return
    conn.executemany(
        "INSERT INTO customers (name, phone, area, meter_number, balance) "
        "VALUES (?, ?, ?, ?, ?)",
        SEED_CUSTOMERS,
    )
    conn.commit()
    assert all(c[2] in AREAS for c in SEED_CUSTOMERS), "seed customer area not in AREAS"
