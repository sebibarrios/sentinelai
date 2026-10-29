"""Provider switch: Gemini (OpenAI-compatible chat completions + embeddings) and OpenAI.

The real OpenAI SDK runs against an httpx MockTransport, so these check the exact
requests sent and how replies are validated, with no network and no API key.
"""

import json
import math

import httpx
import pytest

from app.ai import provider
from app.ai.client import (
    AIUnavailable,
    ChatCompletionsClient,
    HashingEmbedder,
    OpenAIClient,
    OpenAICompatibleEmbedder,
)
from app.ai.schemas import AlertExplanation
from app.core.config import get_settings

EXPLANATION = {
    "summary": "Twelve failed logins for admin.",
    "explanation": "Automated guessing.",
    "likely_tactics": ["Brute force"],
    "investigation_steps": [{"step": "Check for success", "rationale": "Breach?"}],
    "recommended_severity": "high",
    "confidence": "medium",
    "caveats": ["MFA status unknown."],
}


def chat_body(content: str | None) -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1761400000,
        "model": "gemini-flash-latest",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": content},
            }
        ],
        "usage": {"prompt_tokens": 700, "completion_tokens": 120, "total_tokens": 820},
    }


def http(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def gemini_chat(handler) -> ChatCompletionsClient:
    return ChatCompletionsClient(
        "test-key-not-real",
        "gemini-flash-latest",
        base_url=provider.GEMINI_BASE_URL,
        provider="Gemini",
        http_client=http(handler),
    )


def test_gemini_structured_output_request_and_validated_reply():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=chat_body(json.dumps(EXPLANATION)))

    out = gemini_chat(handler).complete(
        instructions="You are a SOC analyst.", user="<data>…</data>", schema=AlertExplanation
    )

    assert seen["url"] == provider.GEMINI_BASE_URL + "chat/completions"
    assert seen["auth"] == "Bearer test-key-not-real"
    body = seen["body"]
    assert body["model"] == "gemini-flash-latest"
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert isinstance(out.parsed, AlertExplanation)
    assert out.parsed.recommended_severity == "high"
    assert (out.tokens_in, out.tokens_out) == (700, 120)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(429, json={"error": {"message": "quota"}}),
        httpx.Response(200, json=chat_body('{"summary": "missing every other field"}')),
        httpx.Response(200, json=chat_body(None)),
    ],
    ids=["quota-error", "schema-violation", "empty-reply"],
)
def test_gemini_failures_become_ai_unavailable(response):
    client = gemini_chat(lambda request: response)
    with pytest.raises(AIUnavailable):
        client.complete(instructions="x", user="y", schema=AlertExplanation)


def embeddings_body(vectors: list[list[float]], order: list[int]) -> dict:
    return {
        "object": "list",
        "model": "gemini-embedding-001",
        "data": [{"object": "embedding", "index": i, "embedding": vectors[i]} for i in order],
        "usage": {"prompt_tokens": 9, "total_tokens": 9},
    }


def test_embeddings_request_shortened_vectors_and_normalize_them_in_input_order():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        # Out of order on purpose: results must be matched to inputs by index.
        return httpx.Response(200, json=embeddings_body([[3.0, 4.0], [0.0, 2.0]], [1, 0]))

    embedder = OpenAICompatibleEmbedder(
        "test-key-not-real",
        "gemini-embedding-001",
        dimensions=2,
        base_url=provider.GEMINI_BASE_URL,
        http_client=http(handler),
    )
    vectors = embedder.embed(["first", "second"])

    assert seen["url"] == provider.GEMINI_BASE_URL + "embeddings"
    assert seen["body"]["dimensions"] == 2
    assert seen["body"]["input"] == ["first", "second"]
    assert vectors == [[0.6, 0.8], [0.0, 1.0]]


def test_embeddings_of_the_wrong_size_are_refused():
    embedder = OpenAICompatibleEmbedder(
        "k",
        "m",
        dimensions=3,
        http_client=http(lambda r: httpx.Response(200, json=embeddings_body([[1.0, 0.0]], [0]))),
    )
    with pytest.raises(AIUnavailable):
        embedder.embed(["text"])


def test_hashing_embedder_is_deterministic_unit_length_and_word_sensitive():
    e = HashingEmbedder(256)
    a, b, c = e.embed(
        [
            "failed logon brute force event 4625",
            "brute force failed logon 4625",
            "dns tunneling long subdomain",
        ]
    )
    assert e.embed(["failed logon brute force event 4625"])[0] == a
    assert math.isclose(sum(x * x for x in a), 1.0)
    similarity = lambda u, v: sum(x * y for x, y in zip(u, v, strict=True))  # noqa: E731
    assert similarity(a, b) > 0.8 > similarity(a, c)


@pytest.fixture
def settings(monkeypatch):
    s = get_settings()
    for name in ("ai_offline_fixtures",):
        monkeypatch.setattr(s, name, False)
    return s


def test_provider_setting_selects_the_client_and_ai_is_off_without_a_key(settings, monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", None)
    monkeypatch.setattr(settings, "openai_api_key", "sk-openai-only")
    # The OpenAI key doesn't switch Gemini on: each provider needs its own key.
    assert provider.get_ai_client() is None and provider.get_embedding_client() is None
    assert provider.ai_status()["enabled"] is False

    monkeypatch.setattr(settings, "gemini_api_key", "gemini-key-not-real")
    assert isinstance(provider.get_ai_client(), ChatCompletionsClient)
    embedder = provider.get_embedding_client()
    assert isinstance(embedder, OpenAICompatibleEmbedder)
    assert embedder.dimensions == settings.embedding_dimensions
    status = provider.ai_status()
    assert status == {"enabled": True, "provider": "gemini", "model": settings.gemini_model}
    assert "gemini-key-not-real" not in json.dumps(status)

    monkeypatch.setattr(settings, "ai_provider", "openai")
    assert isinstance(provider.get_ai_client(), OpenAIClient)
    assert provider.ai_status()["provider"] == "openai"


def test_offline_fixtures_use_deterministic_embeddings(settings, monkeypatch):
    monkeypatch.setattr(settings, "ai_offline_fixtures", True)
    assert isinstance(provider.get_embedding_client(), HashingEmbedder)
