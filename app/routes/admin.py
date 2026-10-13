"""Dashboard/demo support endpoints - audit trail, areas list, and a
manual cleanup trigger (so you don't have to wait 24h to see expiry
in a demo)."""
import sqlite3

from fastapi import APIRouter, Depends, Query

from app.db import get_db
from app.lib.cleanup import expire_pending_reports
from app.lib.constants import AREAS

router = APIRouter(prefix="/api", tags=["admin"])


@router.get("/areas")
def list_areas():
    return AREAS


@router.get("/audit-log")
def get_audit_log(limit: int = Query(default=50, le=500), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute(
        "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [
        {
            "id": r["id"],
            "actor": r["actor"],
            "action": r["action"],
            "details": r["details"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


@router.post("/admin/run-cleanup")
def run_cleanup(conn: sqlite3.Connection = Depends(get_db)):
    expired_count = expire_pending_reports(conn)
    return {"expired": expired_count}
