"""The pending-outage notification loop.

This is the standout feature: a customer calls about an outage nobody
has confirmed yet -> we store a pending_report. Later, when a
technician confirms an outage in that area, every matching pending
report gets "notified" (an SMS, simulated here as a log line + audit
entry) instead of the customer having to call back.

Production equivalent: this module would call an SMS gateway (e.g.
Twilio, or KEDS's existing bulk-SMS vendor) instead of print()/logging.
"""
import sqlite3

from app.lib.audit import log
from app.lib.timeutil import now_iso


def _send_simulated_sms(conn: sqlite3.Connection, phone: str, message: str) -> None:
    print(f"[SMS SIMULATED] to={phone} | {message}")
    log(conn, actor="system", action="sms_simulated", details={"phone": phone, "message": message})


def _outage_message(outage: sqlite3.Row) -> str:
    eta = outage["eta"] or "ende pa afat të konfirmuar"
    return (
        f"KEDS: Ndërprerja e energjisë në zonën '{outage['area']}' është konfirmuar "
        f"(shkaku: {outage['cause'] or 'në verifikim'}). Kohëzgjatja e pritur: {eta}."
    )


def get_active_outage(conn: sqlite3.Connection, area: str) -> sqlite3.Row | None:
    """Most recent non-restored outage for an area, if any."""
    return conn.execute(
        "SELECT * FROM outages WHERE area = ? AND status IN ('confirmed', 'in_progress') "
        "ORDER BY confirmed_at DESC LIMIT 1",
        (area,),
    ).fetchone()


def match_outage_to_pending_reports(conn: sqlite3.Connection, outage: sqlite3.Row) -> list[sqlite3.Row]:
    """Called when an outage becomes confirmed. Matches + notifies all
    still-valid, unmatched pending reports in that area whose customer
    consented to SMS (reports without consent are never notified)."""
    candidates = conn.execute(
        "SELECT * FROM pending_reports WHERE area = ? AND matched_outage_id IS NULL "
        "AND consent_to_sms = 1 AND expires_at > ?",
        (outage["area"], now_iso()),
    ).fetchall()

    matched = []
    for report in candidates:
        ts = now_iso()
        conn.execute(
            "UPDATE pending_reports SET matched_outage_id = ?, notified_at = ? WHERE id = ?",
            (outage["id"], ts, report["id"]),
        )
        conn.commit()
        _send_simulated_sms(conn, report["phone"], _outage_message(outage))
        log(conn, actor="system", action="pending_report_matched",
            details={"pending_report_id": report["id"], "outage_id": outage["id"], "area": outage["area"]})
        matched.append(report)
    return matched


def match_new_pending_report(conn: sqlite3.Connection, report: sqlite3.Row) -> sqlite3.Row | None:
    """Called right after a pending report is created, in case an
    outage in that area is already confirmed. Returns the outage if an
    immediate match happened, else None."""
    outage = get_active_outage(conn, report["area"])
    if outage is None:
        return None
    ts = now_iso()
    conn.execute(
        "UPDATE pending_reports SET matched_outage_id = ?, notified_at = ? WHERE id = ?",
        (outage["id"], ts, report["id"]),
    )
    conn.commit()
    _send_simulated_sms(conn, report["phone"], _outage_message(outage))
    log(conn, actor="system", action="pending_report_matched_immediately",
        details={"pending_report_id": report["id"], "outage_id": outage["id"], "area": outage["area"]})
    return outage
