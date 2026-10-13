from conftest import add_outage


def test_create_pending_report_returns_201(client, area):
    """Regression: the route shadowed the library function of the same name, so every
    POST raised a TypeError (the agent path hid it by importing the library directly)."""
    r = client.post("/api/pending-reports", json={"phone": "+38344111000", "area": area})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert body["immediate_match"] is False
    assert body["consent_to_sms"] is True


def test_unknown_area_is_rejected(client):
    r = client.post("/api/pending-reports", json={"phone": "+38344111000", "area": "Atlantis"})
    assert r.status_code == 400


def test_report_is_matched_immediately_if_outage_is_known(client, conn, area):
    add_outage(conn, area)
    r = client.post("/api/pending-reports", json={"phone": "+38344111001", "area": area})
    assert r.status_code == 201
    assert r.json()["immediate_match"] is True
    assert r.json()["status"] == "matched"


def test_list_filters_by_area(client, area):
    client.post("/api/pending-reports", json={"phone": "+38344111002", "area": area})
    client.post("/api/pending-reports", json={"phone": "+38349111003", "area": "Prizren - Qendër"})
    rows = client.get("/api/pending-reports", params={"area": area}).json()
    assert [r["phone"] for r in rows] == ["+38344111002"]


def test_confirming_an_outage_via_api_notifies_waiting_customers(client, area):
    client.post("/api/pending-reports", json={"phone": "+38344111004", "area": area})
    r = client.post("/api/outages", json={"area": area, "status": "confirmed", "cause": "fault"})
    assert r.status_code == 201
    assert r.json()["pending_reports_notified"] == 1
