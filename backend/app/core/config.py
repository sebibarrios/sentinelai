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

    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    ai_requests_per_hour: int = 20

    max_upload_mb: int = 10
    max_upload_rows: int = 100_000

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator("openai_api_key", mode="before")
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
    if settings.is_production and settings.jwt_secret.startswith(_PLACEHOLDER_PREFIXES):
        raise RuntimeError("JWT_SECRET must be set to a long random value in production")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    validate_for_production(settings)
    return settings
