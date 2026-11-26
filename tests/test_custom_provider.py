import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from time_manager import ai


class Handler(BaseHTTPRequestHandler):
    requests: list[dict] = []

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        Handler.requests.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
        if self.path.startswith("/redirect/"):
            self.send_response(302)
            self.send_header("Location", "/v1/chat/completions")
            self.end_headers()
        elif self.path.startswith("/denied/"):
            self._reply(401, b"{}")
        elif self.path.startswith("/badmodel/"):
            message = "model does not support chat (key sk-echoed-secret)"
            self._reply(400, json.dumps({"error": {"message": message}}).encode())
        elif self.path.startswith("/garbage/"):
            self._reply(200, b"<html>")
        else:
            content = "<think>hidden</think> OK"
            self._reply(200, json.dumps({"choices": [{"message": {"content": content}}]}).encode())

    def do_GET(self) -> None:
        Handler.requests.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": None})
        if self.path == "/v1/models":
            self._reply(200, json.dumps({"data": [{"id": "zeta"}, {"id": "alpha"}]}).encode())
        elif self.path == "/empty/models":
            self._reply(200, b'{"data": []}')
        else:
            self._reply(200, b"{}")

    def _reply(self, status: int, data: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def server() -> Iterator[str]:
    Handler.requests = []
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    httpd.server_close()


def _call(base_url: str, api_key: str = "") -> str:
    return ai.complete_openai_compatible(
        base_url=base_url, model="my-model", api_key=api_key, system="s", user="u", timeout=5
    )


def test_sends_openai_compatible_request(server: str) -> None:
    assert _call(f"{server}/v1/", "local-key") == "OK"

    sent = Handler.requests[0]
    assert sent["path"] == "/v1/chat/completions"
    assert sent["auth"] == "Bearer local-key"
    assert sent["body"]["model"] == "my-model"
    assert [m["role"] for m in sent["body"]["messages"]] == ["system", "user"]


def test_no_auth_header_without_key(server: str) -> None:
    _call(f"{server}/v1")

    assert Handler.requests[0]["auth"] is None


def test_does_not_follow_redirects(server: str) -> None:
    with pytest.raises(ai.AIError):
        _call(f"{server}/redirect", "local-key")

    assert len(Handler.requests) == 1


@pytest.mark.parametrize("path", ["denied", "garbage"])
def test_server_errors_become_user_messages(server: str, path: str) -> None:
    with pytest.raises(ai.AIError):
        _call(f"{server}/{path}")


@pytest.mark.parametrize(
    "url",
    ["ftp://localhost/v1", "http://example.com/v1", "http://192.168.0.5/v1", "https://u:p@example.com/v1",
     "https://example.com/v1?key=1", "localhost:11434/v1", "http://localhost:bad/v1", ""],
)
def test_rejects_unsafe_base_urls(url: str) -> None:
    with pytest.raises(ai.AIError):
        ai.validate_base_url(url)


@pytest.mark.parametrize("url", ["http://localhost:11434/v1", "http://127.0.0.1:1234/v1", "https://api.example.com/v1"])
def test_accepts_safe_base_urls(url: str) -> None:
    assert ai.validate_base_url(url) == url


@pytest.mark.parametrize("service", ["openai", "ollama", "lmstudio", "custom"])
def test_openai_compatible_services_use_chat_completions(server: str, service: str) -> None:
    text = ai.complete(
        service_id=service, base_url=f"{server}/v1", model="m", api_key="", system="s", user="u"
    )

    assert text == "OK"
    assert Handler.requests[0]["path"] == "/v1/chat/completions"


def test_lists_models_sorted(server: str) -> None:
    assert ai.list_models(service_id="ollama", base_url=f"{server}/v1", api_key="k") == ["alpha", "zeta"]
    assert Handler.requests[0]["auth"] == "Bearer k"


@pytest.mark.parametrize("path", ["empty", "nothing"])
def test_unusable_model_list_is_an_error(server: str, path: str) -> None:
    with pytest.raises(ai.AIError):
        ai.list_models(service_id="custom", base_url=f"{server}/{path}", api_key="")


def test_server_explanation_is_shown_without_the_key(server: str) -> None:
    with pytest.raises(ai.AIError) as error:
        _call(f"{server}/badmodel", "sk-echoed-secret")

    assert "does not support chat" in str(error.value)
    assert "sk-echoed-secret" not in str(error.value)
