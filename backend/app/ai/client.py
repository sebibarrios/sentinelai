"""Model client. The rest of the app depends on the AIClient protocol, not on OpenAI,
so tests can swap in a fake and the provider can change without touching services."""

import logging
from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger("sentinelai.ai")
T = TypeVar("T", bound=BaseModel)


class AIUnavailable(Exception):
    """The AI service failed or returned something unusable."""


@dataclass
class Completion[T]:
    parsed: T
    model: str
    tokens_in: int | None
    tokens_out: int | None


class AIClient(Protocol):
    model: str

    def complete(self, *, instructions: str, user: str, schema: type[T]) -> Completion[T]: ...


class OpenAIClient:
    def __init__(self, api_key: str, model: str, timeout_s: float = 60.0, http_client=None):
        from openai import OpenAI

        # http_client is injectable so tests can exercise the real SDK without network.
        self._client = OpenAI(
            api_key=api_key, timeout=timeout_s, max_retries=2, http_client=http_client
        )
        self.model = model

    def complete(self, *, instructions: str, user: str, schema: type[T]) -> Completion[T]:
        try:
            response = self._client.responses.parse(
                model=self.model,
                instructions=instructions,
                input=user,
                text_format=schema,  # structured outputs: the reply must match the schema
                store=False,  # don't retain log data on the provider side
            )
        except Exception as exc:  # network, auth, rate limit, refusal...
            logger.warning("OpenAI request failed: %s", type(exc).__name__)
            raise AIUnavailable("The AI service request failed. Try again shortly.") from exc

        parsed = response.output_parsed
        if parsed is None:
            raise AIUnavailable("The AI service returned no usable analysis.")
        usage = response.usage
        return Completion(
            parsed=schema.model_validate(parsed.model_dump()),  # re-validate before trusting
            model=getattr(response, "model", self.model) or self.model,
            tokens_in=getattr(usage, "input_tokens", None),
            tokens_out=getattr(usage, "output_tokens", None),
        )


def get_ai_client() -> AIClient | None:
    """FastAPI dependency. Returns None when no API key is configured."""
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    return OpenAIClient(settings.openai_api_key, settings.openai_model)
