"""Brute-force protection and session revocation."""

from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.models import RateLimitHit
from tests.conftest import PASSWORD

API = "/api/v1"


def attempt(client, email, password="wrong-password-1"):
    return client.post(f"{API}/auth/login", json={"email": email, "password": password})


# --- Account lockout -------------------------------------------------------------------


def test_account_locks_after_five_failures_even_for_the_right_password(client, make_user):
    make_user("target@example.com")
    for _ in range(5):
        assert attempt(client, "target@example.com").status_code == 401

    locked = attempt(client, "target@example.com", PASSWORD)  # correct password
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "rate_limited"
    assert "for this account" in locked.json()["error"]["message"]
    retry = int(locked.headers["retry-after"])
    assert 0 < retry <= 15 * 60


def test_lockout_expires_after_the_window(client, make_user, db):
    make_user("target@example.com")
    for _ in range(5):
        attempt(client, "target@example.com")
    assert attempt(client, "target@example.com", PASSWORD).status_code == 429

    # Age the recorded failures past the 15-minute window.
    for hit in db.query(RateLimitHit).all():
        hit.created_at -= timedelta(minutes=16)
    db.commit()
    assert attempt(client, "target@example.com", PASSWORD).status_code == 200


def test_successful_login_resets_the_failure_count(client, make_user):
    make_user("target@example.com")
    for _ in range(4):
        attempt(client, "target@example.com")
    assert attempt(client, "target@example.com", PASSWORD).status_code == 200
    for _ in range(4):
        assert attempt(client, "target@example.com").status_code == 401  # not locked yet


def test_unknown_emails_lock_the_same_way_so_lockout_reveals_nothing(client, make_user):
    make_user("real@example.com")
    for _ in range(5):
        attempt(client, "real@example.com")
        attempt(client, "ghost@example.com")
    real, ghost = attempt(client, "real@example.com"), attempt(client, "ghost@example.com")
    assert real.status_code == ghost.status_code == 429
    assert real.json() == ghost.json()


def test_email_case_variants_share_one_counter(client, make_user):
    make_user("target@example.com")
    for variant in ["TARGET@example.com", "Target@Example.com", "target@EXAMPLE.COM"] * 2:
        attempt(client, variant)
    assert attempt(client, "target@example.com", PASSWORD).status_code == 429


def test_one_ip_spraying_many_accounts_is_blocked(client, make_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "login_max_failures_per_ip", 6)
    make_user("victim@example.com")
    for i in range(6):  # one try per account: no single account reaches its limit
        assert attempt(client, f"user{i}@example.com").status_code == 401
    r = attempt(client, "victim@example.com", PASSWORD)
    assert r.status_code == 429 and "from your network" in r.json()["error"]["message"]


def test_registration_is_rate_limited_per_ip(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "register_max_per_ip_per_hour", 3)
    for i in range(3):
        r = client.post(
            f"{API}/auth/register",
            json={"email": f"n{i}@example.com", "full_name": "N", "password": "Str0ngPassw0rd"},
        )
        assert r.status_code == 201
        client.cookies.clear()
    r = client.post(
        f"{API}/auth/register",
        json={"email": "n9@example.com", "full_name": "N", "password": "Str0ngPassw0rd"},
    )
    assert r.status_code == 429


# --- Frontend-only access and trusted client IP ----------------------------------------

SECRET = "s" * 40


def _proxied(**headers):
    base = {"X-Requested-With": "pytest", "X-Sentinel-Proxy-Secret": SECRET}
    return TestClient(app, headers={**base, **headers})


def test_without_a_secret_configured_the_api_is_open_and_uses_the_socket_ip(client):
    from starlette.requests import Request

    from app.core.proxy_auth import client_ip

    assert client.get(f"{API}/alerts/rules").status_code == 401  # normal auth, not 403
    forged = {
        "type": "http",
        "client": ("testclient", 1),
        "headers": [(b"x-sentinel-client-ip", b"203.0.113.9")],
    }
    assert client_ip(Request(forged)) == "testclient"  # header ignored without a secret


def test_direct_calls_are_refused_once_a_secret_is_configured(monkeypatch, make_user):
    monkeypatch.setattr(get_settings(), "proxy_shared_secret", SECRET)
    make_user("amy@example.com")
    direct = TestClient(app, headers={"X-Requested-With": "pytest"})
    r = direct.post(f"{API}/auth/login", json={"email": "amy@example.com", "password": PASSWORD})
    assert r.status_code == 403 and r.json()["error"]["code"] == "direct_access_forbidden"
    wrong = TestClient(app, headers={"X-Sentinel-Proxy-Secret": "guess" * 8})
    assert wrong.get(f"{API}/alerts/rules").status_code == 403
    # Through the frontend it works, and the host's health check stays reachable.
    via_frontend = _proxied().post(
        f"{API}/auth/login", json={"email": "amy@example.com", "password": PASSWORD}
    )
    assert via_frontend.status_code == 200
    assert direct.get(f"{API}/health").status_code == 200


def test_per_ip_limit_uses_the_client_ip_forwarded_by_the_frontend(monkeypatch, make_user):
    monkeypatch.setattr(get_settings(), "proxy_shared_secret", SECRET)
    monkeypatch.setattr(get_settings(), "login_max_failures_per_ip", 3)
    make_user("amy@example.com")
    attacker = _proxied(**{"X-Sentinel-Client-IP": "203.0.113.66"})
    for i in range(3):
        attempt(attacker, f"user{i}@example.com")
    assert attempt(attacker, "amy@example.com", PASSWORD).status_code == 429
    # A different visitor behind the same frontend isn't blocked by the attacker.
    legit = _proxied(**{"X-Sentinel-Client-IP": "198.51.100.7"})
    assert attempt(legit, "amy@example.com", PASSWORD).status_code == 200


# --- Session revocation ----------------------------------------------------------------


def _session(email):
    c = TestClient(app, headers={"X-Requested-With": "pytest"})
    assert (
        c.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD}).status_code == 200
    )
    return c


def test_logout_revokes_a_copied_token(make_user):
    make_user("amy@example.com")
    browser = _session("amy@example.com")
    stolen = browser.cookies.get(get_settings().cookie_name)

    attacker = TestClient(app)
    attacker.cookies.set(get_settings().cookie_name, stolen)
    assert attacker.get(f"{API}/auth/me").status_code == 200

    assert browser.post(f"{API}/auth/logout").status_code == 204
    assert attacker.get(f"{API}/auth/me").status_code == 401  # copied token is dead too


def test_logout_ends_sessions_on_every_device(make_user):
    make_user("amy@example.com")
    laptop, phone = _session("amy@example.com"), _session("amy@example.com")
    laptop.post(f"{API}/auth/logout")
    assert phone.get(f"{API}/auth/me").status_code == 401


def test_password_change_signs_out_other_sessions_but_keeps_this_one(make_user):
    make_user("amy@example.com")
    here, elsewhere = _session("amy@example.com"), _session("amy@example.com")
    r = here.post(
        f"{API}/users/me/password",
        json={"current_password": PASSWORD, "new_password": "BrandNewPass99"},
    )
    assert r.status_code == 204
    assert here.get(f"{API}/auth/me").status_code == 200
    assert elsewhere.get(f"{API}/auth/me").status_code == 401


def test_deactivation_revokes_sessions_and_reactivation_does_not_restore_them(
    make_user, client, login
):
    from app.models.enums import Role

    target = make_user("amy@example.com")
    victim = _session("amy@example.com")
    make_user("admin@example.com", Role.admin)
    login("admin@example.com")

    client.patch(f"{API}/users/{target.id}", json={"is_active": False})
    client.patch(f"{API}/users/{target.id}", json={"is_active": True})
    assert victim.get(f"{API}/auth/me").status_code == 401  # old token stays dead


def test_tokens_without_a_session_version_are_rejected(make_user):
    """Tokens minted before this change (no 'sv' claim) must not be accepted."""
    from datetime import UTC, datetime

    import jwt

    user = make_user("amy@example.com")
    s = get_settings()
    now = datetime.now(UTC)
    legacy = jwt.encode(
        {
            "sub": str(user.id),
            "role": "analyst",
            "iat": now,
            "exp": now + timedelta(hours=1),
            "typ": "access",
        },
        s.jwt_secret,
        algorithm=s.jwt_algorithm,
    )
    c = TestClient(app)
    c.cookies.set(s.cookie_name, legacy)
    assert c.get(f"{API}/auth/me").status_code == 401


def test_forged_algorithm_none_token_is_rejected(make_user):
    import base64
    import json

    user = make_user("amy@example.com")
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()  # noqa: E731
    header = enc({"alg": "none", "typ": "JWT"})
    claims = enc({"sub": str(user.id), "sv": 0, "typ": "access", "iat": 1, "exp": 9999999999})
    forged = f"{header}.{claims}."
    c = TestClient(app)
    c.cookies.set(get_settings().cookie_name, forged)
    assert c.get(f"{API}/auth/me").status_code == 401
