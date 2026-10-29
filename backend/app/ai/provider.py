"""Chooses the AI clients for a request (kept apart from client.py to avoid an import cycle).

AI_PROVIDER selects the vendor (openai or gemini). With no key for that vendor, AI is
off and these return None. AI_OFFLINE_FIXTURES swaps in deterministic offline clients
for tests and keyless demos (refused in production).
"""

from app.ai.client import (
    AIClient,
    ChatCompletionsClient,
    EmbeddingClient,
    HashingEmbedder,
    OpenAIClient,
    OpenAICompatibleEmbedder,
)
from app.ai.fixtures import FIXTURE_MODEL, FixtureAIClient
from app.core.config import Settings, get_settings

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def _key(settings: Settings) -> str | None:
    if settings.ai_provider == "gemini":
        return settings.gemini_api_key
    return settings.openai_api_key


def get_ai_client() -> AIClient | None:
    """FastAPI dependency: the chat model client, or None when AI is off."""
    settings = get_settings()
    if settings.ai_offline_fixtures:
        return FixtureAIClient()
    key = _key(settings)
    if not key:
        return None
    if settings.ai_provider == "gemini":
        return ChatCompletionsClient(
            key, settings.gemini_model, base_url=GEMINI_BASE_URL, provider="Gemini"
        )
    return OpenAIClient(key, settings.openai_model)


def get_embedding_client() -> EmbeddingClient | None:
    """The embedding client, or None when AI is off."""
    settings = get_settings()
    if settings.ai_offline_fixtures:
        return HashingEmbedder(settings.embedding_dimensions)
    key = _key(settings)
    if not key:
        return None
    if settings.ai_provider == "gemini":
        return OpenAICompatibleEmbedder(
            key,
            settings.gemini_embedding_model,
            settings.embedding_dimensions,
            base_url=GEMINI_BASE_URL,
        )
    return OpenAICompatibleEmbedder(
        key, settings.openai_embedding_model, settings.embedding_dimensions
    )


def ai_status() -> dict:
    """What the UI may know about AI: on or off, provider and model. Never the key."""
    settings = get_settings()
    if settings.ai_offline_fixtures:
        return {"enabled": True, "provider": "offline-fixture", "model": FIXTURE_MODEL}
    model = settings.gemini_model if settings.ai_provider == "gemini" else settings.openai_model
    return {"enabled": bool(_key(settings)), "provider": settings.ai_provider, "model": model}
