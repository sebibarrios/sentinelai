from app.core.config import get_settings
from app.models.enums import Role
from tests.conftest import PASSWORD

API = "/api/v1"


def test_health(client):
    r = client.get(f"{API}/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


def test_register_creates_viewer_and_sets_httponly_cookie(client):
    r = client.post(
        f"{API}/auth/register",
        json={"email": "New@Example.com", "full_name": "New User", "password": "Str0ngPassw0rd"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["role"] == "viewer"  # least privilege by default
    assert "password_hash" not in body
    cookie_header = r.headers["set-cookie"]
    assert get_settings().cookie_name in cookie_header
    assert "HttpOnly" in cookie_header
    assert "samesite=lax" in cookie_header.lower()

    me = client.get(f"{API}/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "new@example.com"


def test_register_rejects_weak_password(client):
    r = client.post(
        f"{API}/auth/register",
        json={"email": "a@example.com", "full_name": "A", "password": "short"},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_register_duplicate_email_is_case_insensitive(client, make_user):
    make_user("taken@example.com")
    r = client.post(
        f"{API}/auth/register",
        json={"email": "TAKEN@example.com", "full_name": "X", "password": "Str0ngPassw0rd"},
    )
    assert r.status_code == 409


def test_login_wrong_password_and_unknown_user_give_same_error(client, make_user):
    make_user("real@example.com")
    wrong = client.post(f"{API}/auth/login", json={"email": "real@example.com", "password": "nope"})
    unknown = client.post(
        f"{API}/auth/login", json={"email": "ghost@example.com", "password": "nope"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()  # no user enumeration


def test_inactive_user_cannot_login(client, make_user):
    make_user("off@example.com", is_active=False)
    r = client.post(f"{API}/auth/login", json={"email": "off@example.com", "password": PASSWORD})
    assert r.status_code == 401


def test_protected_route_requires_auth(client):
    r = client.get(f"{API}/incidents")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_tampered_cookie_is_rejected(client):
    client.cookies.set(get_settings().cookie_name, "not-a-real-token")
    assert client.get(f"{API}/auth/me").status_code == 401


def test_logout_clears_session(analyst_client):
    assert analyst_client.post(f"{API}/auth/logout").status_code == 204
    assert analyst_client.get(f"{API}/auth/me").status_code == 401


def test_deactivation_takes_effect_immediately(analyst_client, db):
    from app.models import User

    user = db.query(User).filter_by(email="analyst@example.com").one()
    user.is_active = False
    db.commit()
    # Token is still cryptographically valid, but the user is re-checked on each request.
    assert analyst_client.get(f"{API}/auth/me").status_code == 401


def test_change_password(analyst_client):
    r = analyst_client.post(
        f"{API}/users/me/password",
        json={"current_password": PASSWORD, "new_password": "BrandNewPass99"},
    )
    assert r.status_code == 204
    r = analyst_client.post(
        f"{API}/users/me/password",
        json={"current_password": PASSWORD, "new_password": "AnotherPass99"},
    )
    assert r.status_code == 401


def test_admin_can_promote_user_but_not_demote_self(client, make_user, login):
    admin = make_user("admin@example.com", Role.admin)
    viewer = make_user("viewer@example.com", Role.viewer)
    login("admin@example.com")

    r = client.patch(f"{API}/users/{viewer.id}", json={"role": "analyst"})
    assert r.status_code == 200
    assert r.json()["role"] == "analyst"

    r = client.patch(f"{API}/users/{admin.id}", json={"role": "viewer"})
    assert r.status_code == 400


def test_non_admin_cannot_list_users(analyst_client):
    r = analyst_client.get(f"{API}/users")
    assert r.status_code == 403
