"""Chooses the AI client for a request (kept apart from client.py to avoid an import cycle)."""

from app.ai.client import AIClient, OpenAIClient
from app.ai.fixtures import FixtureAIClient
from app.core.config import get_settings


def get_ai_client() -> AIClient | None:
    """FastAPI dependency. Returns None when no API key is configured."""
    settings = get_settings()
    if settings.ai_offline_fixtures:
        return FixtureAIClient()
    if not settings.openai_api_key:
        return None
    return OpenAIClient(settings.openai_api_key, settings.openai_model)
