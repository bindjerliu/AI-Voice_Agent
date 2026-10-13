"""Outage reporting/status.

Production equivalent: outage *status* (reported/confirmed/in_progress/
restored) would come from KEDS's SCADA/OMS (outage management system)
and dispatcher workflow, not free-form technician entry. Here a
technician app stands in for that feed.
"""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import get_db
from app.lib.audit import log
from app.lib.constants import AREAS, OUTAGE_STATUSES
from app.lib.matching import match_outage_to_pending_reports
from app.lib.timeutil import now_iso
from app.schemas import OutageCreate, OutageUpdate

router = APIRouter(prefix="/api/outages", tags=["outages"])


def _outage_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "area": row["area"],
        "cause": row["cause"],
        "status": row["status"],
        "eta": row["eta"],
        "created_at": row["created_at"],
        "confirmed_at": row["confirmed_at"],
    }


@router.get("")
def list_outages(area: str | None = Query(default=None), conn: sqlite3.Connection = Depends(get_db)):
    if area:
        rows = conn.execute(
            "SELECT * FROM outages WHERE area = ? ORDER BY created_at DESC", (area,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM outages ORDER BY created_at DESC").fetchall()
    return [_outage_to_dict(r) for r in rows]


@router.get("/{outage_id}")
def get_outage(outage_id: int, conn: sqlite3.Connection = Depends(get_db)):
    row = conn.execute("SELECT * FROM outages WHERE id = ?", (outage_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Outage not found")
    return _outage_to_dict(row)


@router.post("", status_code=201)
def create_outage(payload: OutageCreate, conn: sqlite3.Connection = Depends(get_db)):
    if payload.area not in AREAS:
        raise HTTPException(status_code=400, detail=f"Unknown area. Valid areas: {AREAS}")
    if payload.status not in OUTAGE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Valid: {OUTAGE_STATUSES}")

    confirmed_at = now_iso() if payload.status in ("confirmed", "in_progress") else None
    cur = conn.execute(
        "INSERT INTO outages (area, cause, status, eta, confirmed_at) VALUES (?, ?, ?, ?, ?)",
        (payload.area, payload.cause, payload.status, payload.eta, confirmed_at),
    )
    conn.commit()
    outage = conn.execute("SELECT * FROM outages WHERE id = ?", (cur.lastrowid,)).fetchone()

    log(conn, actor="technician", action="outage_created",
        details={"outage_id": outage["id"], "area": outage["area"], "status": outage["status"]})

    matched = []
    if outage["status"] in ("confirmed", "in_progress"):
        matched = match_outage_to_pending_reports(conn, outage)

    return {**_outage_to_dict(outage), "pending_reports_notified": len(matched)}


@router.patch("/{outage_id}")
def update_outage(outage_id: int, payload: OutageUpdate, conn: sqlite3.Connection = Depends(get_db)):
    outage = conn.execute("SELECT * FROM outages WHERE id = ?", (outage_id,)).fetchone()
    if outage is None:
        raise HTTPException(status_code=404, detail="Outage not found")

    new_status = payload.status if payload.status is not None else outage["status"]
    if new_status not in OUTAGE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Valid: {OUTAGE_STATUSES}")

    was_active = outage["status"] in ("confirmed", "in_progress")
    becomes_active = new_status in ("confirmed", "in_progress")
    confirmed_at = outage["confirmed_at"]
    if becomes_active and not was_active:
        confirmed_at = now_iso()

    conn.execute(
        "UPDATE outages SET status = ?, cause = ?, eta = ?, confirmed_at = ? WHERE id = ?",
        (
            new_status,
            payload.cause if payload.cause is not None else outage["cause"],
            payload.eta if payload.eta is not None else outage["eta"],
            confirmed_at,
            outage_id,
        ),
    )
    conn.commit()
    outage = conn.execute("SELECT * FROM outages WHERE id = ?", (outage_id,)).fetchone()

    log(conn, actor="technician", action="outage_updated",
        details={"outage_id": outage_id, "status": new_status})

    matched = []
    if becomes_active and not was_active:
        matched = match_outage_to_pending_reports(conn, outage)

    return {**_outage_to_dict(outage), "pending_reports_notified": len(matched)}
