import re
from datetime import datetime, timezone
from unittest.mock import patch

from app.lib import timeutil

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def test_now_iso_matches_sqlite_format():
    assert ISO.match(timeutil.now_iso())


def test_hours_from_now_iso_is_in_the_future():
    assert timeutil.hours_from_now_iso(1) > timeutil.now_iso()


def test_now_iso_reads_the_clock_exactly_once():
    """Regression: the seconds and milliseconds used to come from two separate clock
    reads, so a timestamp could mix e.g. 12:00:00 with .001 near a second boundary."""
    first = datetime(2026, 1, 1, 12, 0, 0, 999_000, tzinfo=timezone.utc)
    second = datetime(2026, 1, 1, 12, 0, 1, 1_000, tzinfo=timezone.utc)
    with patch("app.lib.timeutil.datetime") as fake:
        fake.now.side_effect = [first, second]
        assert timeutil.now_iso() == "2026-01-01T12:00:00.999Z"
