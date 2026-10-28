"""Settings parse the way the docs and .env.example say they do."""

from pathlib import Path

import pytest
from sqlalchemy import text

from app.core.config import Settings, validate_for_production
from app.db.session import engine

ROOT = Path(__file__).resolve().parents[2]


def test_env_example_loads(monkeypatch):
    """Copying .env.example to .env (as the README says) must produce a valid config."""
    for key in ("JWT_SECRET", "CORS_ORIGINS", "OPENAI_API_KEY", "ENVIRONMENT", "DATABASE_URL"):
        monkeypatch.delenv(key, raising=False)
    s = Settings(_env_file=ROOT / ".env.example")
    assert s.cors_origins == ["http://localhost:3000"]
    assert s.openai_api_key is None  # blank key means AI disabled, not an empty-string key
    assert s.docs_enabled is True


def test_comma_separated_cors_origins(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example, https://b.example")
    assert Settings(_env_file=None).cors_origins == ["https://a.example", "https://b.example"]


@pytest.mark.parametrize(
    "url",
    ["postgres://u:p@h:5432/db", "postgresql://u:p@h:5432/db"],
)
def test_provider_database_urls_get_a_driver(monkeypatch, url):
    monkeypatch.setenv("DATABASE_URL", url)
    assert Settings(_env_file=None).database_url == "postgresql+psycopg://u:p@h:5432/db"


@pytest.mark.parametrize(
    "secret",
    [
        "dev-only-insecure-secret-change-me-0123456789",
        "change-me-to-a-long-random-value-before-deploying",
    ],
)
def test_production_refuses_placeholder_secrets(monkeypatch, secret):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", secret)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        validate_for_production(Settings(_env_file=None))


def test_production_defaults_docs_off(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "x" * 48)
    monkeypatch.setenv("PROXY_SHARED_SECRET", "p" * 40)
    s = Settings(_env_file=None)
    validate_for_production(s)  # real secrets pass
    assert s.docs_enabled is False


@pytest.mark.parametrize("proxy_secret", [None, "too-short"])
def test_production_requires_a_strong_proxy_secret(monkeypatch, proxy_secret):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "x" * 48)
    if proxy_secret:
        monkeypatch.setenv("PROXY_SHARED_SECRET", proxy_secret)
    else:
        monkeypatch.delenv("PROXY_SHARED_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="PROXY_SHARED_SECRET"):
        validate_for_production(Settings(_env_file=None))


def test_database_sessions_use_utc():
    with engine.connect() as conn:
        assert conn.execute(text("SHOW TIME ZONE")).scalar() == "UTC"
