"""Model clients. The rest of the app depends on the AIClient and EmbeddingClient
protocols, not on a vendor, so tests can swap in fakes and the provider is one setting.

- OpenAIClient: OpenAI's Responses API with structured outputs and store=False.
- ChatCompletionsClient: any OpenAI-compatible chat-completions endpoint with
  structured outputs. Used for Gemini, whose OpenAI-compatible API has no Responses API.
- OpenAICompatibleEmbedder: embeddings through the same SDK, for OpenAI or Gemini.
- HashingEmbedder: deterministic, offline embeddings for tests and keyless demos.
"""

import hashlib
import logging
import math
import re
from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel

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

    def complete(self, *, instructions: str, user: str, schema: type[T]) -> Completion[T]:
        """Return the model's answer parsed into `schema`; raise AIUnavailable on failure."""


class EmbeddingClient(Protocol):
    model: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one unit-length vector per text; raise AIUnavailable on failure."""


def _sdk(api_key: str, base_url: str | None, timeout_s: float, http_client):
    from openai import OpenAI

    # http_client is injectable so tests can exercise the real SDK without network.
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout_s,
        max_retries=2,
        http_client=http_client,
    )


def _unit(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    return [x / norm for x in vector] if norm else vector


class OpenAIClient:
    def __init__(self, api_key: str, model: str, timeout_s: float = 60.0, http_client=None):
        self._client = _sdk(api_key, None, timeout_s, http_client)
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


class ChatCompletionsClient:
    """Structured output through an OpenAI-compatible chat-completions endpoint."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        provider: str,
        timeout_s: float = 60.0,
        http_client=None,
    ):
        self._client = _sdk(api_key, base_url, timeout_s, http_client)
        self.model = model
        self._provider = provider

    def complete(self, *, instructions: str, user: str, schema: type[T]) -> Completion[T]:
        try:
            response = self._client.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": user},
                ],
                response_format=schema,  # structured outputs: the reply must match the schema
            )
        except Exception as exc:
            logger.warning("%s request failed: %s", self._provider, type(exc).__name__)
            raise AIUnavailable("The AI service request failed. Try again shortly.") from exc

        message = response.choices[0].message if response.choices else None
        parsed = message.parsed if message else None
        if parsed is None:
            raise AIUnavailable("The AI service returned no usable analysis.")
        usage = response.usage
        return Completion(
            parsed=schema.model_validate(parsed.model_dump()),  # re-validate before trusting
            model=getattr(response, "model", None) or self.model,
            tokens_in=getattr(usage, "prompt_tokens", None),
            tokens_out=getattr(usage, "completion_tokens", None),
        )


class OpenAICompatibleEmbedder:
    """Embeddings from OpenAI or Gemini (OpenAI-compatible), shortened to `dimensions`."""

    def __init__(
        self,
        api_key: str,
        model: str,
        dimensions: int,
        base_url: str | None = None,
        timeout_s: float = 60.0,
        http_client=None,
    ):
        self._client = _sdk(api_key, base_url, timeout_s, http_client)
        self.model = model
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            response = self._client.embeddings.create(
                model=self.model, input=texts, dimensions=self.dimensions
            )
        except Exception as exc:
            logger.warning("Embedding request failed: %s", type(exc).__name__)
            raise AIUnavailable("The embedding service request failed.") from exc
        vectors = [item.embedding for item in sorted(response.data, key=lambda d: d.index)]
        if len(vectors) != len(texts) or any(len(v) != self.dimensions for v in vectors):
            raise AIUnavailable("The embedding service returned vectors of the wrong shape.")
        # Shortened embeddings aren't unit length; normalize so scores are comparable.
        return [_unit(v) for v in vectors]


_TOKEN = re.compile(r"[a-z0-9]+(?:[.\-][a-z0-9]+)*")


class HashingEmbedder:
    """Deterministic bag-of-words embeddings via feature hashing. No network, no key.

    Not semantic: it matches shared words, not meaning. It exists so retrieval code
    and its tests run offline in CI with predictable results; it's labeled as such
    wherever it's used.
    """

    model = "hashing-test-embedder (not a real model)"

    def __init__(self, dimensions: int):
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for token in _TOKEN.findall(text.lower()):
                digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
                bucket = int.from_bytes(digest[:4], "big") % self.dimensions
                sign = 1.0 if digest[4] & 1 else -1.0
                vector[bucket] += sign
            out.append(_unit(vector))
        return out
