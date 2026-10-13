"""Shared pending-report creation.

Extracted so both the REST route (technician/dispatch side) and the
voice agent's tool call go through identical logic — create the
pending report, audit it, and immediately match it if an outage in
that area is already confirmed.
"""
import sqlite3

from app.lib.audit import log
from app.lib.matching import match_new_pending_report
from app.lib.timeutil import hours_from_now_iso


def create_pending_report(
    conn: sqlite3.Connection,
    phone: str,
    area: str,
    consent_to_sms: bool = True,
    ttl_hours: float = 24,
    actor: str = "ivr",
) -> tuple[sqlite3.Row, sqlite3.Row | None]:
    """Returns (report_row, matched_outage_or_None)."""
    expires_at = hours_from_now_iso(ttl_hours)
    cur = conn.execute(
        "INSERT INTO pending_reports (phone, area, consent_to_sms, expires_at) VALUES (?, ?, ?, ?)",
        (phone, area, int(consent_to_sms), expires_at),
    )
    conn.commit()
    report = conn.execute("SELECT * FROM pending_reports WHERE id = ?", (cur.lastrowid,)).fetchone()

    log(conn, actor=actor, action="pending_report_created",
        details={"pending_report_id": report["id"], "phone": phone, "area": area})

    matched_outage = match_new_pending_report(conn, report) if consent_to_sms else None
    report = conn.execute("SELECT * FROM pending_reports WHERE id = ?", (report["id"],)).fetchone()
    return report, matched_outage
