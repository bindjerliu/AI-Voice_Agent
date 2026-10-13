import asyncio
from unittest.mock import patch

from app.lib import cleanup

from conftest import add_report


def test_expire_removes_only_expired_unmatched_reports(conn, area):
    expired = add_report(conn, "+38344222001", area, expires_at="2000-01-01T00:00:00.000Z")
    fresh = add_report(conn, "+38344222002", area)
    assert cleanup.expire_pending_reports(conn) == 1
    ids = [r["id"] for r in conn.execute("SELECT id FROM pending_reports")]
    assert expired not in ids and fresh in ids


def test_cleanup_loop_survives_an_exception():
    """Regression: one failing sweep used to kill the background task silently."""
    calls = []

    def flaky(_conn):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("database is locked")
        return 0

    async def run():
        task = asyncio.create_task(cleanup.cleanup_loop())
        for _ in range(200):
            if len(calls) >= 2:
                break
            await asyncio.sleep(0.01)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    with patch.object(cleanup, "CLEANUP_INTERVAL_SECONDS", 0), \
         patch.object(cleanup, "expire_pending_reports", side_effect=flaky), \
         patch.object(cleanup, "get_connection") as get_conn:
        get_conn.return_value.close.return_value = None
        asyncio.run(run())
    assert len(calls) >= 2
