from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Values that must never reach production. The dev default lets the app start locally.
_DEV_JWT_SECRET = "dev-only-insecure-secret-change-me-0123456789"  # noqa: S105
_PLACEHOLDER_PREFIXES = ("dev-only", "change-me", "replace-me")


class Settings(BaseSettings):
    """Application settings, loaded from environment variables (and .env in development)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://sentinel:sentinel@localhost:5432/sentinelai"

    jwt_secret: str = Field(default=_DEV_JWT_SECRET, min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    cookie_name: str = "sentinel_session"

    # NoDecode: accept a plain comma-separated string (CORS_ORIGINS=http://a,http://b)
    # instead of requiring JSON, which pydantic-settings would otherwise attempt.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    # None means "on in development, off in production" unless set explicitly.
    enable_docs: bool | None = None

    # AI provider. Both are called through the OpenAI SDK (Gemini via its
    # OpenAI-compatible endpoint). With no key for the chosen provider, AI is off.
    ai_provider: Literal["openai", "gemini"] = "openai"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-flash-latest"
    gemini_embedding_model: str = "gemini-embedding-001"
    # Vectors are stored at this size (pgvector column); both providers can shorten theirs.
    embedding_dimensions: int = 768
    ai_requests_per_hour: int = 20  # per user; cached answers don't count
    # Site-wide cap on new AI requests per 24 hours, so a public demo stays inside a
    # provider's free tier no matter how many accounts visitors create.
    ai_requests_per_day_site_wide: int = 250

    max_upload_mb: int = 10
    max_upload_rows: int = 100_000

    # Brute-force protection. Failed logins are counted per account and per client IP;
    # reaching either limit blocks sign-in (even with the right password) until the
    # oldest counted failure is older than the lockout window.
    login_max_failures_per_account: int = 5
    login_max_failures_per_ip: int = 20
    login_lockout_minutes: int = 15
    register_max_per_ip_per_hour: int = 10
    # Shared with the Next.js frontend. When set, the API only accepts requests that
    # carry it, so it can't be called directly, and it trusts the client IP the
    # frontend forwards (used for per-IP rate limits). Unset in local development.
    proxy_shared_secret: str | None = None

    # Deterministic offline AI responses for end-to-end tests and keyless demos.
    # Refused in production.
    ai_offline_fixtures: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator("openai_api_key", "gemini_api_key", "proxy_shared_secret", mode="before")
    @classmethod
    def blank_key_is_none(cls, v: object) -> object:
        return None if isinstance(v, str) and not v.strip() else v

    @field_validator("database_url")
    @classmethod
    def normalize_db_url(cls, v: str) -> str:
        # Hosting providers hand out postgres:// URLs; SQLAlchemy needs an explicit driver.
        if v.startswith("postgres://"):
            v = "postgresql://" + v.removeprefix("postgres://")
        if v.startswith("postgresql://"):
            v = "postgresql+psycopg://" + v.removeprefix("postgresql://")
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def docs_enabled(self) -> bool:
        return self.enable_docs if self.enable_docs is not None else not self.is_production


def validate_for_production(settings: Settings) -> None:
    if not settings.is_production:
        return
    if settings.jwt_secret.startswith(_PLACEHOLDER_PREFIXES):
        raise RuntimeError("JWT_SECRET must be set to a long random value in production")
    if settings.ai_offline_fixtures:
        raise RuntimeError("AI_OFFLINE_FIXTURES must not be enabled in production")
    if not settings.proxy_shared_secret or len(settings.proxy_shared_secret) < 32:
        raise RuntimeError("PROXY_SHARED_SECRET must be set (32+ characters) in production")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    validate_for_production(settings)
    return settings
