"""The 'we don't know yet, we'll text you' loop.

Production equivalent: this would write to a lightweight queue/table
that the OMS integration polls or subscribes to, and the SMS send
would go through KEDS's SMS gateway with real opt-in/consent tracking.
"""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import get_db
from app.lib.constants import AREAS
from app.lib.reports import create_pending_report as create_report
from app.lib.timeutil import now_iso
from app.schemas import PendingReportCreate

router = APIRouter(prefix="/api/pending-reports", tags=["pending-reports"])


def _report_to_dict(row: sqlite3.Row) -> dict:
    if row["matched_outage_id"] is not None:
        status = "matched"
    elif row["expires_at"] <= now_iso():
        status = "expired"
    else:
        status = "pending"
    return {
        "id": row["id"],
        "phone": row["phone"],
        "area": row["area"],
        "consent_to_sms": bool(row["consent_to_sms"]),
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
        "matched_outage_id": row["matched_outage_id"],
        "notified_at": row["notified_at"],
        "status": status,
    }


@router.post("", status_code=201)
def create_pending_report(payload: PendingReportCreate, conn: sqlite3.Connection = Depends(get_db)):
    if payload.area not in AREAS:
        raise HTTPException(status_code=400, detail=f"Unknown area. Valid areas: {AREAS}")

    report, matched_outage = create_report(
        conn, payload.phone, payload.area, payload.consent_to_sms, payload.ttl_hours
    )

    result = _report_to_dict(report)
    result["immediate_match"] = matched_outage is not None
    return result


@router.get("")
def list_pending_reports(area: str | None = Query(default=None), conn: sqlite3.Connection = Depends(get_db)):
    if area:
        rows = conn.execute(
            "SELECT * FROM pending_reports WHERE area = ? ORDER BY created_at DESC", (area,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM pending_reports ORDER BY created_at DESC").fetchall()
    return [_report_to_dict(r) for r in rows]
