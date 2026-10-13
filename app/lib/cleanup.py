"""Expiry of stale pending reports.

If nobody confirms an outage in that area within the report's TTL
(default 24h), we stop holding the customer's number for it. Production
equivalent: a scheduled job (cron / Cloud Scheduler / Celery beat)
hitting a cleanup endpoint or task queue.
"""
import asyncio
import logging
import sqlite3

from app.db import get_connection
from app.lib.audit import log
from app.lib.timeutil import now_iso

CLEANUP_INTERVAL_SECONDS = 60

logger = logging.getLogger(__name__)


def expire_pending_reports(conn: sqlite3.Connection) -> int:
    expired = conn.execute(
        "SELECT * FROM pending_reports WHERE matched_outage_id IS NULL AND expires_at <= ?",
        (now_iso(),),
    ).fetchall()

    for report in expired:
        conn.execute("DELETE FROM pending_reports WHERE id = ?", (report["id"],))
        log(conn, actor="system", action="pending_report_expired",
            details={"pending_report_id": report["id"], "phone": report["phone"], "area": report["area"]})
    conn.commit()
    return len(expired)


def _cleanup_once() -> None:
    conn = get_connection()
    try:
        expire_pending_reports(conn)
    finally:
        conn.close()


async def cleanup_loop() -> None:
    """Runs forever. A failed sweep (e.g. a locked database) is logged and retried on the
    next cycle instead of silently killing the background task."""
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        try:
            # SQLite is blocking, so keep it off the event loop.
            await asyncio.to_thread(_cleanup_once)
        except Exception:
            logger.exception("Pending-report cleanup failed; will retry next cycle")
