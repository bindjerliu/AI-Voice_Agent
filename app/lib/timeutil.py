from datetime import datetime, timedelta, timezone


def _format(dt: datetime) -> str:
    """UTC timestamp in the format SQLite's strftime('%Y-%m-%dT%H:%M:%fZ') produces,
    so python-generated and sqlite-generated timestamps compare correctly as strings."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def now_iso() -> str:
    # Read the clock exactly once so seconds and milliseconds always belong together.
    return _format(datetime.now(timezone.utc))


def hours_from_now_iso(hours: float) -> str:
    return _format(datetime.now(timezone.utc) + timedelta(hours=hours))
