from app.lib.matching import match_new_pending_report, match_outage_to_pending_reports
from app.lib.reports import create_pending_report

from conftest import add_outage, add_report


def sms_phones(conn):
    rows = conn.execute("SELECT details FROM audit_log WHERE action = 'sms_simulated'").fetchall()
    return [__import__("json").loads(r["details"])["phone"] for r in rows]


def test_confirmed_outage_notifies_matching_pending_reports(conn, area):
    add_report(conn, "+38344000001", area)
    outage = add_outage(conn, area)
    matched = match_outage_to_pending_reports(conn, outage)
    assert [m["phone"] for m in matched] == ["+38344000001"]
    assert sms_phones(conn) == ["+38344000001"]


def test_customers_who_declined_sms_are_never_notified(conn, area):
    """Regression: consent_to_sms was ignored when an outage was confirmed later."""
    add_report(conn, "+38344000001", area, consent=1)
    declined = add_report(conn, "+38344000002", area, consent=0)
    outage = add_outage(conn, area)
    match_outage_to_pending_reports(conn, outage)
    assert sms_phones(conn) == ["+38344000001"]
    row = conn.execute("SELECT * FROM pending_reports WHERE id = ?", (declined,)).fetchone()
    assert row["matched_outage_id"] is None and row["notified_at"] is None


def test_reports_from_other_areas_are_not_matched(conn, area):
    add_report(conn, "+38344000003", "Prizren - Qendër")
    outage = add_outage(conn, area)
    assert match_outage_to_pending_reports(conn, outage) == []


def test_expired_reports_are_not_matched(conn, area):
    add_report(conn, "+38344000004", area, expires_at="2000-01-01T00:00:00.000Z")
    outage = add_outage(conn, area)
    assert match_outage_to_pending_reports(conn, outage) == []


def test_report_is_notified_only_once(conn, area):
    add_report(conn, "+38344000005", area)
    outage = add_outage(conn, area)
    match_outage_to_pending_reports(conn, outage)
    assert match_outage_to_pending_reports(conn, outage) == []
    assert sms_phones(conn) == ["+38344000005"]


def test_new_report_matches_immediately_when_outage_already_confirmed(conn, area):
    add_outage(conn, area)
    report, matched_outage = create_pending_report(conn, "+38344000006", area)
    assert matched_outage is not None
    assert report["matched_outage_id"] == matched_outage["id"]


def test_new_report_without_consent_is_stored_but_not_notified(conn, area):
    add_outage(conn, area)
    report, matched_outage = create_pending_report(conn, "+38344000007", area, consent_to_sms=False)
    assert matched_outage is None
    assert report["matched_outage_id"] is None
    assert sms_phones(conn) == []


def test_no_immediate_match_when_no_active_outage(conn, area):
    report = add_report(conn, "+38344000008", area)
    row = conn.execute("SELECT * FROM pending_reports WHERE id = ?", (report,)).fetchone()
    assert match_new_pending_report(conn, row) is None
