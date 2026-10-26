"""Exercise OpenAIClient through the real OpenAI SDK with a simulated HTTP layer.

No network and no API key: an httpx MockTransport answers like the Responses API.
This checks request shape (model, structured-output schema, store=False) and that the
SDK's parsed output flows back through our validation.
"""

import json

import httpx
import pytest

from app.ai.client import AIUnavailable, OpenAIClient
from app.ai.schemas import AlertExplanation

EXPLANATION = {
    "summary": "Twelve failed logins for admin.",
    "explanation": "Automated guessing.",
    "likely_tactics": ["Brute force"],
    "investigation_steps": [{"step": "Check for success", "rationale": "Breach?"}],
    "recommended_severity": "high",
    "confidence": "medium",
    "caveats": ["MFA status unknown."],
}


def responses_api_body(text: str) -> dict:
    return {
        "id": "resp_test",
        "object": "response",
        "created_at": 1761400000,
        "status": "completed",
        "model": "gpt-5-mini-2025-08-07",
        "output": [
            {
                "type": "message",
                "id": "msg_test",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        ],
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
        "usage": {
            "input_tokens": 812,
            "output_tokens": 164,
            "total_tokens": 976,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 64},
        },
    }


def make_client(handler) -> OpenAIClient:
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenAIClient("sk-test-not-real", "gpt-5-mini", http_client=http)


def test_structured_output_round_trip():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=responses_api_body(json.dumps(EXPLANATION)))

    result = make_client(handler).complete(
        instructions="Explain the alert.", user="<data>{}</data>", schema=AlertExplanation
    )

    assert isinstance(result.parsed, AlertExplanation)
    assert result.parsed.recommended_severity == "high"
    assert (result.model, result.tokens_in, result.tokens_out) == (
        "gpt-5-mini-2025-08-07",
        812,
        164,
    )

    body = seen["body"]
    assert seen["url"].endswith("/v1/responses")
    assert seen["auth"] == "Bearer sk-test-not-real"
    assert body["model"] == "gpt-5-mini" and body["store"] is False
    assert body["instructions"] == "Explain the alert."
    fmt = body["text"]["format"]
    assert fmt["type"] == "json_schema" and fmt["strict"] is True
    assert set(fmt["schema"]["required"]) == set(EXPLANATION)


def test_schema_violation_is_reported_not_stored():
    bad = dict(EXPLANATION, recommended_severity="apocalyptic")

    def handler(request):
        return httpx.Response(200, json=responses_api_body(json.dumps(bad)))

    with pytest.raises(AIUnavailable):
        make_client(handler).complete(instructions="x", user="y", schema=AlertExplanation)


@pytest.mark.parametrize("status", [401, 429, 500])
def test_provider_errors_become_ai_unavailable(status):
    def handler(request):
        return httpx.Response(status, json={"error": {"message": "nope", "type": "x"}})

    client = make_client(handler)
    client._client = client._client.with_options(max_retries=0)  # keep the test fast
    with pytest.raises(AIUnavailable, match="request failed"):
        client.complete(instructions="x", user="y", schema=AlertExplanation)
