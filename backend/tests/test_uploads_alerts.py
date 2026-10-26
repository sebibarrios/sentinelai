import csv
import io
import json
from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import get_settings
from app.ingest.synthetic import generate
from app.models.enums import Role

API = "/api/v1"
END = datetime.now(UTC).replace(microsecond=0)


def sample_csv(seed: int = 7) -> bytes:
    log = generate(seed=seed, end=END)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(log.rows[0]))
    writer.writeheader()
    writer.writerows(log.rows)
    return buf.getvalue().encode()


def upload(client, content: bytes, name: str = "sample.csv"):
    return client.post(f"{API}/uploads", files={"file": (name, content, "text/csv")})


@pytest.fixture
def uploaded(analyst_client):
    r = upload(analyst_client, sample_csv())
    assert r.status_code == 201, r.text
    return r.json()


def test_upload_parses_stores_and_detects(analyst_client, uploaded):
    assert uploaded["status"] == "completed"
    assert uploaded["rows_rejected"] == 0 and uploaded["rows_parsed"] > 1000
    assert uploaded["alerts_created"] == 8
    assert uploaded["uploaded_by"]["email"] == "analyst@example.com"

    alerts = analyst_client.get(f"{API}/alerts", params={"page_size": 100}).json()
    assert alerts["total"] == 8
    assert {a["rule_id"] for a in alerts["items"]} == {
        "AUTH-001",
        "AUTH-002",
        "AUTH-003",
        "AUTH-004",
        "AUTH-005",
        "IOC-001",
        "NET-001",
        "NET-002",
    }
    events = analyst_client.get(f"{API}/events", params={"page_size": 1}).json()
    assert events["total"] == uploaded["rows_parsed"]


def test_alert_detail_links_back_to_exact_evidence(analyst_client, uploaded):
    alerts = analyst_client.get(f"{API}/alerts", params={"rule_id": "AUTH-001"}).json()["items"]
    detail = analyst_client.get(f"{API}/alerts/{alerts[0]['id']}").json()
    assert detail["rule_name"] == "Brute force"
    assert detail["event_count"] == len(detail["evidence"]) == 12
    assert all(
        e["username"] == "admin" and e["outcome"] == "failure" and e["src_ip"] == "203.0.113.45"
        for e in detail["evidence"]
    )
    assert detail["ai_analysis"] is None and detail["evidence_truncated"] is False


def test_same_file_twice_is_refused(analyst_client, uploaded):
    r = upload(analyst_client, sample_csv())
    assert r.status_code == 409
    assert r.json()["error"]["details"]["upload_id"] == uploaded["id"]


def test_overlapping_data_does_not_duplicate_alerts(analyst_client, uploaded):
    # Same events, different bytes (JSON instead of CSV): alerts dedupe by rule + key.
    rows = generate(seed=7, end=END).rows
    r = upload(analyst_client, json.dumps(rows).encode(), "same-data.json")
    assert r.status_code == 201
    assert r.json()["alerts_created"] == 0
    assert analyst_client.get(f"{API}/alerts").json()["total"] == 8


def test_partial_bad_rows_are_reported(analyst_client):
    content = (
        b"timestamp,category,action,outcome,src_ip,username\n"
        b"2026-10-20T03:00:00Z,auth,login,success,10.0.0.1,amy\n"
        b"2026-10-20T03:00:00Z,auth,login,success,not-an-ip,amy\n"
    )
    r = upload(analyst_client, content)
    assert r.status_code == 201
    body = r.json()
    assert (body["rows_parsed"], body["rows_rejected"]) == (1, 1)
    assert body["rejection_samples"][0]["line"] == 3


@pytest.mark.parametrize(
    ("name", "content", "status", "code"),
    [
        ("shell.php", b"<?php system($_GET['c']); ?>", 422, "upload_rejected"),
        ("empty.csv", b"timestamp,category,action,outcome,src_ip\n", 422, "upload_rejected"),
        (
            "bad.csv",
            b"timestamp,category,action,outcome,src_ip\nx,y,z,w,v\n",
            422,
            "upload_rejected",
        ),
    ],
)
def test_invalid_uploads_rejected_and_nothing_stored(analyst_client, name, content, status, code):
    r = upload(analyst_client, content, name)
    assert r.status_code == status and r.json()["error"]["code"] == code
    assert analyst_client.get(f"{API}/uploads").json()["total"] == 0


def test_oversized_upload_rejected(analyst_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)
    r = upload(analyst_client, b"timestamp,category\n" + b"x" * (2 * 1024 * 1024))
    assert r.status_code == 413


def test_viewer_cannot_upload_or_change_alerts(client, make_user, login, uploaded):
    make_user("viewer@example.com", Role.viewer)
    login("viewer@example.com")
    assert upload(client, sample_csv(seed=99)).status_code == 403
    alert_id = client.get(f"{API}/alerts").json()["items"][0]["id"]
    assert client.patch(f"{API}/alerts/{alert_id}", json={"status": "dismissed"}).status_code == 403
    assert client.post(f"{API}/alerts/{alert_id}/promote").status_code == 403
    assert client.get(f"{API}/alerts/{alert_id}").status_code == 200  # can still read


def test_alert_filters(analyst_client, uploaded):
    get = lambda **p: analyst_client.get(f"{API}/alerts", params=p).json()["total"]  # noqa: E731
    assert get(severity="critical") == 1
    assert get(src_ip="192.0.2.77") == 2  # port scan + denied burst
    assert get(q="jdoe") == 2  # spray success + new IP
    assert get(**{"from": (END + timedelta(days=1)).isoformat()}) == 0
    assert analyst_client.get(f"{API}/alerts", params={"src_ip": "nope"}).status_code == 422


def test_status_change_and_promote_to_incident(analyst_client, uploaded):
    alert = analyst_client.get(f"{API}/alerts", params={"rule_id": "AUTH-003"}).json()["items"][0]

    r = analyst_client.patch(f"{API}/alerts/{alert['id']}", json={"status": "acknowledged"})
    assert r.json()["status"] == "acknowledged"

    r = analyst_client.post(f"{API}/alerts/{alert['id']}/promote")
    assert r.status_code == 201
    incident_id = r.json()["incident_id"]

    incident = analyst_client.get(f"{API}/incidents/{incident_id}").json()
    assert incident["severity"] == "critical"
    assert "Verified facts from detection" in incident["description"]
    assert incident["assignee"]["email"] == "analyst@example.com"
    history = analyst_client.get(f"{API}/incidents/{incident_id}/history").json()
    assert [h["action"] for h in history] == ["created", "alert_linked"]

    after = analyst_client.get(f"{API}/alerts/{alert['id']}").json()
    assert after["status"] == "escalated" and after["incident_id"] == incident_id

    linked = analyst_client.get(f"{API}/alerts", params={"incident_id": incident_id}).json()
    assert [a["id"] for a in linked["items"]] == [alert["id"]]

    assert analyst_client.post(f"{API}/alerts/{alert['id']}/promote").status_code == 409
    r = analyst_client.patch(f"{API}/alerts/{alert['id']}", json={"status": "dismissed"})
    assert r.status_code == 400  # managed through the incident now


def test_dashboard_includes_alert_metrics(analyst_client, uploaded):
    s = analyst_client.get(f"{API}/dashboard/summary", params={"range": "24h"}).json()
    assert s["open_alerts"] == 8 and s["alerts_in_range"] == 8
    assert s["open_alerts_by_severity"] == {"low": 1, "medium": 2, "high": 4, "critical": 1}
    assert s["events_in_range"] == uploaded["rows_parsed"]
    assert len(s["alert_timeline"]) in (24, 25)
    assert sum(p["low"] + p["medium"] + p["high"] + p["critical"] for p in s["alert_timeline"]) == 8
    # The spray IP has 3 alerts (spray, success-after-failures, new IP); the scanner has 2.
    assert s["top_sources"][:2] == [
        {"ip": "198.51.100.23", "alerts": 3, "max_severity": "critical"},
        {"ip": "192.0.2.77", "alerts": 2, "max_severity": "high"},
    ]
    assert len(s["recent_alerts"]) == 6


def test_rules_catalog(analyst_client):
    rules = analyst_client.get(f"{API}/alerts/rules").json()
    assert len(rules) == 8 and rules[0] == {
        "id": "AUTH-001",
        "name": "Brute force",
        "description": "Repeated failed logins for one account from one IP",
        "severity": "high",
    }
