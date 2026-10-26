from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables (and .env in development)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://sentinel:sentinel@localhost:5432/sentinelai"

    jwt_secret: str = Field(default="dev-only-insecure-secret-change-me-0123456789", min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    cookie_name: str = "sentinel_session"

    cors_origins: list[str] = ["http://localhost:3000"]
    enable_docs: bool = True

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    ai_requests_per_hour: int = 20

    max_upload_mb: int = 10
    max_upload_rows: int = 100_000

    login_attempts_per_15min: int = 10

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, v: object) -> object:
        if isinstance(v, str) and not v.startswith("["):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

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


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.is_production and settings.jwt_secret.startswith("dev-only"):
        raise RuntimeError("JWT_SECRET must be set in production")
    return settings
