import dataclasses
import json
import select
import socket
import threading
import time
from collections.abc import Iterator
from unittest.mock import patch

import pytest
from test_ai import FakeKeys, _unclassified

from time_manager import ai
from time_manager.models import ActiveTarget, Category, ClassifiedActivity
from time_manager.webapi import WebApi


@pytest.fixture
def model_api(api: WebApi) -> WebApi:
    api._ai_keys = FakeKeys("sk-ant-test-key-0123456789")
    api.save_ai_settings("model", "claude", "claude-opus-5-5")
    api.store.record(_unclassified("notion.exe", "Secret roadmap"), 900)
    api.store.record(_unclassified("chrome.exe", "Private page", "https://reddit.com/r/secret"), 600)
    productive = ClassifiedActivity(
        ActiveTarget(app_name="code.exe", window_title="secret-project"), Category.PRODUCTIVE, "rule"
    )
    api.store.record(productive, 3600)
    return api


class TestPreview:
    @pytest.mark.parametrize("kind", ["suggestions", "coaching"])
    def test_matches_what_is_actually_sent(self, model_api: WebApi, kind: str) -> None:
        with patch("time_manager.ai.complete", return_value="[]") as sent:
            preview = model_api.preview_ai_request(kind, "day")
            sent.assert_not_called()  # 미리보기는 아무것도 보내지 않음
            if kind == "suggestions":
                model_api.get_ai_rule_suggestions()
            else:
                model_api.get_ai_coaching("day")

        assert preview["error"] == ""
        assert json.loads(preview["data"]) == json.loads(sent.call_args.kwargs["user"])
        assert preview["instructions"] == sent.call_args.kwargs["system"]
        assert preview["model"] == sent.call_args.kwargs["model"]
        assert preview["url"] == "https://api.anthropic.com/v1/messages"

    @pytest.mark.parametrize("kind", ["suggestions", "coaching"])
    def test_shows_no_titles_paths_or_keys(self, model_api: WebApi, kind: str) -> None:
        shown = json.dumps(model_api.preview_ai_request(kind, "day"), ensure_ascii=False)

        for secret in ("Secret roadmap", "Private page", "/r/secret", "secret-project", "sk-ant"):
            assert secret not in shown

    def test_builtin_analysis_has_nothing_to_preview(self, api: WebApi) -> None:
        result = api.preview_ai_request("suggestions")

        assert result["data"] == "" and result["error"]

    def test_says_when_nothing_would_be_sent(self, api: WebApi) -> None:
        api._ai_keys = FakeKeys()
        api.save_ai_settings("model", "ollama", "m")

        assert api.preview_ai_request("suggestions")["data"] == ""
        assert api.preview_ai_request("coaching", "day")["data"] == ""
        assert api.preview_ai_request("coaching", "year")["error"]


class TestBuiltinFallback:
    def test_failure_offers_but_never_uses_the_builtin_analysis(self, model_api: WebApi) -> None:
        with patch("time_manager.ai.complete", side_effect=ai.AIError("서버 오류")):
            suggestions = model_api.get_ai_rule_suggestions()
            coaching = model_api.get_ai_coaching("day")

        assert (suggestions["items"], suggestions["canFallback"]) == ([], True)
        assert (coaching["headline"], coaching["canFallback"]) == ("", True)

    def test_builtin_on_request_sends_nothing_and_keeps_settings(self, model_api: WebApi) -> None:
        with patch("time_manager.ai.complete") as sent:
            suggestions = model_api.get_ai_rule_suggestions("", True)
            coaching = model_api.get_ai_coaching("day", None, False, "", True)

        sent.assert_not_called()
        assert suggestions["source"] == coaching["source"] == "내장 분석"
        assert coaching["generated"] is False and coaching["error"] == ""
        assert model_api.settings.ai_provider == "model"

    def test_builtin_result_is_not_cached_as_the_model_answer(self, model_api: WebApi) -> None:
        model_api.get_ai_coaching("day", None, False, "", True)

        with patch("time_manager.ai.complete", return_value='{"headline": "model"}') as sent:
            result = model_api.get_ai_coaching("day")

        sent.assert_called_once()
        assert result["headline"] == "model"

    def test_missing_data_does_not_offer_a_fallback(self, api: WebApi) -> None:
        api._ai_keys = FakeKeys()
        api.save_ai_settings("model", "ollama", "m")

        assert api.get_ai_coaching("day")["canFallback"] is False


class HangingServer:
    """요청을 받기만 하고 답하지 않으며, 클라이언트 연결 종료를 기록."""

    def __init__(self) -> None:
        self.socket = socket.socket()
        self.socket.bind(("127.0.0.1", 0))
        self.socket.listen()
        self.url = f"http://127.0.0.1:{self.socket.getsockname()[1]}"
        self.received = threading.Event()
        self.disconnected = threading.Event()
        self.closing = False
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        try:
            connection, _ = self.socket.accept()
        except OSError:
            return
        with connection:
            connection.recv(65536)
            self.received.set()
            while not self.closing:
                if select.select([connection], [], [], 0.05)[0]:
                    try:
                        if not connection.recv(65536):
                            break
                    except OSError:
                        break
            if not self.closing:
                self.disconnected.set()


@pytest.fixture
def hanging() -> Iterator[HangingServer]:
    server = HangingServer()
    yield server
    server.closing = True
    server.socket.close()


def _use_hanging_model(api: WebApi, service: str, server: HangingServer, monkeypatch: pytest.MonkeyPatch) -> None:
    api._ai_keys = FakeKeys("sk-ant-test-key-0123456789")
    if service == "claude":  # 주소가 고정이므로 서비스 자체를 테스트 서버로 지정
        monkeypatch.setitem(ai.SERVICES, "claude", dataclasses.replace(ai.SERVICES["claude"], base_url=server.url))
        assert "error" not in api.save_ai_settings("model", "claude", "claude-haiku-4-5")
    else:
        assert "error" not in api.save_ai_settings("model", "ollama", "m", f"{server.url}/v1")
    api.store.record(_unclassified("notion.exe", "Notion"), 900)


class TestCancel:
    @pytest.mark.parametrize("service", ["ollama", "claude"])
    def test_stops_a_waiting_request_and_closes_the_connection(
        self, api: WebApi, hanging: HangingServer, monkeypatch: pytest.MonkeyPatch, service: str
    ) -> None:
        _use_hanging_model(api, service, hanging, monkeypatch)
        result: dict = {}
        worker = threading.Thread(
            target=lambda: result.update(api.get_ai_rule_suggestions("request-1")), daemon=True
        )
        worker.start()
        assert hanging.received.wait(10)

        started = time.monotonic()
        api.cancel_ai_request("request-1")
        worker.join(10)

        assert not worker.is_alive()
        assert time.monotonic() - started < 3
        assert result["error"] == "분석을 취소했어요."
        assert hanging.disconnected.wait(3)

    def test_cancel_that_arrives_first_sends_nothing(
        self, api: WebApi, hanging: HangingServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _use_hanging_model(api, "ollama", hanging, monkeypatch)
        api.cancel_ai_request("request-1")

        result = api.get_ai_rule_suggestions("request-1")

        assert result["error"] == "분석을 취소했어요."
        assert not hanging.received.wait(0.5)

    def test_cancel_does_not_affect_the_next_request(self, model_api: WebApi) -> None:
        model_api.cancel_ai_request("old")

        with patch("time_manager.ai.complete", return_value="[]"):
            assert model_api.get_ai_rule_suggestions("new")["error"] == ""

    def test_late_cancels_do_not_pile_up(self, api: WebApi) -> None:
        for number in range(500):
            api.cancel_ai_request(f"late-{number}")

        assert len(api.__dict__["_ai_tokens"]) <= 50

    def test_cancelled_coaching_is_not_cached(self, model_api: WebApi) -> None:
        def cancelled_midway(**kwargs: object) -> str:
            raise ai.AICancelled()

        with patch("time_manager.ai.complete", side_effect=cancelled_midway):
            model_api.get_ai_coaching("day", None, False, "r1")

        assert model_api.get_coaching_history() == []
