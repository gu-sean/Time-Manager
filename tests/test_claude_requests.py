"""Claude goes through the official SDK; these check the request without any network."""
import json
from collections.abc import Callable

import anthropic
import httpx
import pytest

from time_manager import ai


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[httpx.Request]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/v1/models":
            models = [{"type": "model", "id": "claude-x", "display_name": "X", "created_at": "2026-01-01T00:00:00Z"}]
            return httpx.Response(200, json={"data": models, "has_more": False, "first_id": "claude-x", "last_id": "claude-x"})
        return httpx.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": "m",
            "content": [{"type": "text", "text": "OK"}], "stop_reason": "end_turn",
            "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1},
        })

    original: Callable = anthropic.Anthropic
    monkeypatch.setattr(
        anthropic, "Anthropic",
        lambda **kwargs: original(http_client=httpx.Client(transport=httpx.MockTransport(handler)), **kwargs),
    )
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://elsewhere.example")
    return requests


def _ask(model: str) -> str:
    return ai.complete(
        service_id="claude", base_url="https://api.anthropic.com", model=model,
        api_key="sk-ant-test-key-0123456789", system="s", user="u",
    )


def test_key_only_goes_to_anthropic(sent: list[httpx.Request]) -> None:
    assert _ask("claude-opus-5-5") == "OK"
    assert sent[0].url.host == "api.anthropic.com"


def test_current_model_gets_effort_and_fallbacks(sent: list[httpx.Request]) -> None:
    _ask("claude-opus-5-5")

    body = json.loads(sent[0].content)
    assert body["output_config"] == {"effort": "low"}
    assert body["fallbacks"] == "default"


def test_other_models_get_a_plain_request(sent: list[httpx.Request]) -> None:
    _ask("claude-haiku-4-5")

    body = json.loads(sent[0].content)
    assert "output_config" not in body and "fallbacks" not in body
    assert "anthropic-beta" not in sent[0].headers


def test_lists_claude_models(sent: list[httpx.Request]) -> None:
    assert ai.list_models(service_id="claude", base_url="", api_key="sk-ant-test") == ["claude-x"]
