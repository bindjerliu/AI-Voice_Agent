"""Audit logging.

Production equivalent: writes to KEDS's compliance/audit trail (who
looked up which customer's data, when an outage was confirmed, etc.),
likely shipped to a SIEM. Here it's just a table we can render on the
dashboard.
"""
import json
import sqlite3


def log(conn: sqlite3.Connection, actor: str, action: str, details: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO audit_log (actor, action, details) VALUES (?, ?, ?)",
        (actor, action, json.dumps(details or {})),
    )
    conn.commit()
