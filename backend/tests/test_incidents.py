from app.models.enums import Role

API = "/api/v1/incidents"


def _create(client, **overrides):
    payload = {"title": "Suspicious login burst", "severity": "high", "description": "Initial"}
    payload.update(overrides)
    r = client.post(API, json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_and_get_incident(analyst_client):
    inc = _create(analyst_client)
    assert inc["reference"] == "INC-0001"
    assert inc["status"] == "open"
    assert inc["created_by"]["email"] == "analyst@example.com"

    r = analyst_client.get(f"{API}/{inc['id']}")
    assert r.status_code == 200
    assert r.json()["notes"] == []


def test_viewer_can_read_but_not_write(client, make_user, login):
    make_user("analyst2@example.com", Role.analyst)
    login("analyst2@example.com")
    inc = _create(client)

    make_user("viewer@example.com", Role.viewer)
    login("viewer@example.com")
    assert client.get(f"{API}/{inc['id']}").status_code == 200
    assert client.post(API, json={"title": "Nope", "severity": "low"}).status_code == 403
    assert client.patch(f"{API}/{inc['id']}", json={"status": "closed"}).status_code == 403


def test_status_change_sets_closed_at_and_reopen_clears_it(analyst_client):
    inc = _create(analyst_client)
    r = analyst_client.patch(f"{API}/{inc['id']}", json={"status": "resolved"})
    assert r.json()["closed_at"] is not None
    r = analyst_client.patch(f"{API}/{inc['id']}", json={"status": "investigating"})
    assert r.json()["closed_at"] is None


def test_every_change_is_audited(analyst_client):
    inc = _create(analyst_client)
    analyst_client.patch(
        f"{API}/{inc['id']}", json={"severity": "critical", "status": "investigating"}
    )
    analyst_client.post(f"{API}/{inc['id']}/notes", json={"body": "Blocked IP at firewall"})

    history = analyst_client.get(f"{API}/{inc['id']}/history").json()
    actions = [(h["action"], h["field"], h["old_value"], h["new_value"]) for h in history]
    assert actions == [
        ("created", None, None, "INC-0001"),
        ("status_changed", "status", "open", "investigating"),
        ("updated", "severity", "high", "critical"),
        ("note_added", None, None, None),
    ]


def test_patch_without_changes_writes_no_history(analyst_client):
    inc = _create(analyst_client)
    analyst_client.patch(f"{API}/{inc['id']}", json={"severity": "high"})
    assert len(analyst_client.get(f"{API}/{inc['id']}/history").json()) == 1


def test_assign_only_to_analysts_or_admins(client, make_user, login):
    analyst = make_user("a@example.com", Role.analyst, full_name="Ana Lyst")
    viewer = make_user("v@example.com", Role.viewer)
    login("a@example.com")
    inc = _create(client)

    r = client.patch(f"{API}/{inc['id']}", json={"assignee_id": str(viewer.id)})
    assert r.status_code == 400

    r = client.patch(f"{API}/{inc['id']}", json={"assignee_id": str(analyst.id)})
    assert r.status_code == 200
    assert r.json()["assignee"]["full_name"] == "Ana Lyst"


def test_notes_appear_on_detail_in_order(analyst_client):
    inc = _create(analyst_client)
    for body in ("first", "second"):
        analyst_client.post(f"{API}/{inc['id']}/notes", json={"body": body})
    notes = analyst_client.get(f"{API}/{inc['id']}").json()["notes"]
    assert [n["body"] for n in notes] == ["first", "second"]


def test_list_filters_search_and_pagination(analyst_client):
    for i in range(30):
        _create(analyst_client, title=f"Incident {i}", severity="low" if i % 2 else "critical")
    _create(analyst_client, title="Port scan from 203.0.113.9", severity="medium")

    page1 = analyst_client.get(API, params={"page_size": 10}).json()
    assert page1["total"] == 31 and len(page1["items"]) == 10

    crit = analyst_client.get(API, params={"severity": "critical", "page_size": 100}).json()
    assert crit["total"] == 15

    found = analyst_client.get(API, params={"q": "port scan"}).json()
    assert found["total"] == 1

    # SQL wildcards in search input are treated literally.
    assert analyst_client.get(API, params={"q": "%"}).json()["total"] == 0


def test_validation_and_not_found(analyst_client):
    assert analyst_client.post(API, json={"title": "x", "severity": "high"}).status_code == 422
    assert (
        analyst_client.post(API, json={"title": "Okay", "severity": "extreme"}).status_code == 422
    )
    missing = "00000000-0000-0000-0000-000000000000"
    r = analyst_client.get(f"{API}/{missing}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_dashboard_summary(analyst_client):
    _create(analyst_client, severity="critical")
    inc = _create(analyst_client, severity="low")
    analyst_client.patch(f"{API}/{inc['id']}", json={"status": "closed"})

    s = analyst_client.get("/api/v1/dashboard/summary", params={"range": "24h"}).json()
    assert s["open_incidents"] == 1
    assert s["critical_open_incidents"] == 1
    assert s["incidents_in_range"] == 2
    assert s["incidents_by_status"]["closed"] == 1
    assert len(s["recent_incidents"]) == 2
