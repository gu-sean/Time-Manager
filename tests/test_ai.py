import json
from unittest.mock import patch

import pytest

from time_manager import ai
from time_manager.models import ActiveTarget, Category, ClassifiedActivity
from time_manager.webapi import WebApi


class FakeKeys:
    def __init__(self, claude_key: str = "") -> None:
        self.keys: dict[str, str] = {}
        if claude_key:
            self.keys[ai.key_account("claude", "https://api.anthropic.com")] = claude_key

    def get(self, account: str) -> str:
        return self.keys.get(account, "")

    def set(self, account: str, api_key: str) -> None:
        self.keys[account] = api_key

    def delete(self, account: str) -> None:
        self.keys.pop(account, None)


def _unclassified(app: str, title: str = "", url: str | None = None) -> ClassifiedActivity:
    return ClassifiedActivity(
        target=ActiveTarget(app_name=app, window_title=title, url=url),
        category=Category.NEUTRAL,
        reason="no matching rule",
    )


@pytest.fixture
def ai_api(api: WebApi) -> WebApi:
    api._ai_keys = FakeKeys("sk-ant-test-key-0123456789")
    api.settings.ai_provider = "model"
    api.settings.ai_service = "claude"
    return api


class TestParseClassifications:
    def test_keeps_only_known_targets_and_valid_categories(self) -> None:
        text = json.dumps(
            [
                {"target": "notion.exe", "category": "productive", "reason": "문서 작성"},
                {"target": "evil.example", "category": "productive", "reason": "x"},
                {"target": "reddit.com", "category": "bogus", "reason": "x"},
                {"target": "NOTION.EXE", "category": "unproductive", "reason": "dup"},
            ]
        )

        result = ai.parse_classifications(f"```json\n{text}\n```", ["notion.exe", "reddit.com"])

        assert result == [{"target": "notion.exe", "category": "productive", "reason": "문서 작성"}]

    def test_rejects_non_json(self) -> None:
        with pytest.raises(ai.AIError):
            ai.parse_classifications("sorry, no", ["a.exe"])


class TestParseCoaching:
    def test_parses_and_limits(self) -> None:
        text = json.dumps({"headline": "좋아요", "insights": ["a", "b", "c", "d"], "actions": ["x"]})
        assert ai.parse_coaching(text) == {"headline": "좋아요", "insights": ["a", "b", "c"], "actions": ["x"]}

    def test_falls_back_to_plain_text(self) -> None:
        assert ai.parse_coaching("그냥 텍스트")["headline"] == "그냥 텍스트"


class TestAISettings:
    def test_default_provider_is_builtin(self, api: WebApi) -> None:
        api._ai_keys = FakeKeys()

        result = api.get_settings()

        assert result["aiProvider"] == "local"
        assert [p["value"] for p in result["aiProviderOptions"]] == ["local", "model"]
        assert [s["value"] for s in result["aiServices"]] == ["claude", "openai", "ollama", "lmstudio", "custom"]

    @pytest.mark.parametrize("service,model", [("claude", "claude-opus-5-5"), ("openai", "some-gpt")])
    def test_hosted_services_need_a_key(self, api: WebApi, service: str, model: str) -> None:
        api._ai_keys = FakeKeys()

        result = api.save_ai_settings("model", service, model)

        assert "error" in result
        assert api.settings.ai_provider == "local"

    @pytest.mark.parametrize("service", ["ollama", "lmstudio"])
    def test_local_servers_need_no_key(self, api: WebApi, service: str) -> None:
        api._ai_keys = FakeKeys()

        result = api.save_ai_settings("model", service, "my-model")

        assert "error" not in result
        assert api.settings.ai_service == service

    def test_key_is_never_returned(self, api: WebApi) -> None:
        api._ai_keys = FakeKeys()

        result = api.set_ai_api_key("claude", "sk-ant-secret-key-0123456789")

        assert next(x for x in result["aiServices"] if x["value"] == "claude")["hasKey"] is True
        assert "sk-ant-secret" not in json.dumps(result)

    def test_rejects_malformed_key(self, api: WebApi) -> None:
        api._ai_keys = FakeKeys()
        assert "error" in api.set_ai_api_key("claude", "short")
        assert "error" in api.set_ai_api_key("openai", "has space")

    def test_rejects_unknown_provider_service_and_empty_model(self, ai_api: WebApi) -> None:
        assert "error" in ai_api.save_ai_settings("other")
        assert "error" in ai_api.save_ai_settings("model", "nope", "m")
        assert "error" in ai_api.save_ai_settings("model", "claude", "  ")
        assert "error" in ai_api.save_ai_settings("model", "custom", "m", "")

    def test_fixed_service_ignores_a_supplied_address(self, ai_api: WebApi) -> None:
        ai_api.set_ai_api_key("openai", "sk-openai", "https://evil.example/v1")
        ai_api.save_ai_settings("model", "openai", "some-gpt", "https://evil.example/v1")

        with patch("time_manager.ai.complete", return_value="OK") as fake:
            ai_api.test_ai_connection()

        assert fake.call_args.kwargs["base_url"] == "https://api.openai.com/v1"

    def test_each_service_gets_only_its_own_key(self, ai_api: WebApi) -> None:
        ai_api.set_ai_api_key("openai", "sk-openai")
        sent: dict[str, str] = {}
        for service, model in [("claude", "claude-opus-5-5"), ("openai", "some-gpt"), ("ollama", "llama")]:
            ai_api.save_ai_settings("model", service, model)
            with patch("time_manager.ai.complete", return_value="OK") as fake:
                ai_api.test_ai_connection()
            sent[service] = fake.call_args.kwargs["api_key"]

        assert sent == {"claude": "sk-ant-test-key-0123456789", "openai": "sk-openai", "ollama": ""}

    def test_custom_key_is_not_reused_for_another_server(self, ai_api: WebApi) -> None:
        ai_api.set_ai_api_key("custom", "secret-one", "https://one.example/v1")
        ai_api.save_ai_settings("model", "custom", "m", "https://one.example/v1")

        ai_api.save_ai_settings("model", "custom", "m", "https://two.example/v1")

        with patch("time_manager.ai.complete", return_value="OK") as fake:
            ai_api.test_ai_connection()
        assert fake.call_args.kwargs["api_key"] == ""

    def test_saving_a_key_does_not_redirect_the_model_in_use(self, ai_api: WebApi) -> None:
        ai_api.save_ai_settings("model", "custom", "m", "https://one.example/v1")

        result = ai_api.set_ai_api_key("custom", "secret", "https://two.example/v1")

        assert "error" in result
        assert ai_api.settings.ai_service_configs["custom"]["base_url"] == "https://one.example/v1"

    def test_clearing_a_required_key_returns_to_builtin(self, ai_api: WebApi) -> None:
        ai_api.save_ai_settings("model", "claude", "claude-opus-5-5")

        result = ai_api.clear_ai_api_key("claude")

        assert result["aiProvider"] == "local"

    def test_each_service_keeps_its_setup(self, ai_api: WebApi) -> None:
        ai_api.save_ai_settings("model", "ollama", "llama", "http://127.0.0.1:9999/v1/")
        ai_api.save_ai_settings("model", "claude", "claude-haiku-5-5")
        ai_api.save_ai_settings("local")

        reloaded = ai_api.settings_store.load()
        assert reloaded.ai_provider == "local"
        assert reloaded.ai_service == "claude"
        assert reloaded.ai_service_configs == {
            "ollama": {"model": "llama", "base_url": "http://127.0.0.1:9999/v1"},
            "claude": {"model": "claude-haiku-5-5", "base_url": "https://api.anthropic.com"},
        }


class TestListModels:
    def test_requires_the_key_for_hosted_services(self, api: WebApi) -> None:
        api._ai_keys = FakeKeys()

        with patch("time_manager.ai.list_models") as fake:
            result = api.list_ai_models("openai")

        fake.assert_not_called()
        assert result["error"]

    def test_returns_models(self, api: WebApi) -> None:
        api._ai_keys = FakeKeys()

        with patch("time_manager.ai.list_models", return_value=["a", "b"]):
            assert api.list_ai_models("ollama") == {"models": ["a", "b"], "error": ""}


class TestAiRuleSuggestions:
    def test_builtin_provider_never_calls_external_services(self, api: WebApi) -> None:
        api._ai_keys = FakeKeys("sk-ant-test-key-0123456789")
        api.settings.onboarding_profile = "developer"
        api.store.record(_unclassified("Code.exe", "main.py"), 600)
        api.store.record(_unclassified("mystery.exe", "zzz"), 600)

        with patch("time_manager.ai.complete") as external:
            result = api.get_ai_rule_suggestions()

        external.assert_not_called()
        assert [(i["target"], i["category"]) for i in result["items"]] == [("Code.exe", "productive")]
        assert result["skipped"] == 1
        assert result["source"] == "내장 분석"

    def test_sends_only_apps_and_domains_never_titles_or_paths(self, ai_api: WebApi) -> None:
        ai_api.store.record(_unclassified("notion.exe", "Secret roadmap - Notion"), 600)
        ai_api.store.record(_unclassified("chrome.exe", "Private page", "https://reddit.com/r/secret/path?q=1"), 300)
        captured: dict[str, str] = {}

        def fake_complete(**kwargs: str) -> str:
            captured.update(kwargs)
            return json.dumps(
                [
                    {"target": "notion.exe", "category": "productive", "reason": "업무 문서"},
                    {"target": "reddit.com", "category": "unproductive", "reason": "소셜 피드"},
                ]
            )

        with patch("time_manager.ai.complete", side_effect=fake_complete):
            result = ai_api.get_ai_rule_suggestions()

        sent = captured["user"]
        assert "Secret roadmap" not in sent
        assert "Private page" not in sent
        assert "/r/secret" not in sent
        assert "sk-ant" not in sent
        assert result["error"] == ""
        assert [(i["target"], i["category"]) for i in result["items"]] == [
            ("notion.exe", "productive"),
            ("reddit.com", "unproductive"),
        ]

    def test_skips_targets_that_already_have_rules(self, ai_api: WebApi) -> None:
        ai_api.apply_rule_suggestion("notion.exe", "productive")
        ai_api.store.record(_unclassified("notion.exe", "Notion"), 600)

        with patch("time_manager.ai.complete") as fake:
            result = ai_api.get_ai_rule_suggestions()

        fake.assert_not_called()
        assert result["items"] == []

    def test_api_error_is_returned_not_raised(self, ai_api: WebApi) -> None:
        ai_api.store.record(_unclassified("notion.exe", "Notion"), 600)

        with patch("time_manager.ai.complete", side_effect=ai.AIError("API 키가 올바르지 않습니다.")):
            result = ai_api.get_ai_rule_suggestions()

        assert result["items"] == []
        assert result["error"] == "API 키가 올바르지 않습니다."


class TestAiCoaching:
    def test_not_enough_data(self, ai_api: WebApi) -> None:
        with patch("time_manager.ai.complete") as fake:
            result = ai_api.get_ai_coaching("week")

        fake.assert_not_called()
        assert result["error"]

    def test_generates_and_caches(self, ai_api: WebApi) -> None:
        productive = ClassifiedActivity(
            ActiveTarget(app_name="code.exe", window_title="secret-project main.py"),
            Category.PRODUCTIVE,
            "rule",
        )
        ai_api.store.record(productive, 3600)
        reply = json.dumps({"headline": "집중 좋아요", "insights": ["code.exe 60분"], "actions": ["오전 집중"]})

        with patch("time_manager.ai.complete", return_value=reply) as fake:
            first = ai_api.get_ai_coaching("week")
            second = ai_api.get_ai_coaching("week")
            ai_api.get_ai_coaching("week", refresh=True)

        assert first["headline"] == "집중 좋아요"
        assert first["error"] == ""
        assert (first["reused"], second["reused"]) == (False, True)
        assert second["headline"] == first["headline"]
        assert fake.call_count == 2  # 최초 + 새로 고침. 가운데 호출은 캐시 사용
        assert "secret-project" not in fake.call_args.kwargs["user"]
        assert "code.exe" in fake.call_args.kwargs["user"]

    def test_invalid_scope(self, ai_api: WebApi) -> None:
        assert ai_api.get_ai_coaching("year")["error"]

    def test_builtin_coaching_needs_no_key_or_network(self, api: WebApi) -> None:
        api._ai_keys = FakeKeys()
        productive = ClassifiedActivity(
            ActiveTarget(app_name="code.exe", window_title="main.py"), Category.PRODUCTIVE, "rule"
        )
        api.store.record(productive, 3600)

        with patch("time_manager.ai.complete") as claude:
            result = api.get_ai_coaching("day")

        claude.assert_not_called()
        assert result["error"] == ""
        assert result["generated"] is False
        assert "1시간" in result["headline"]
        assert any("code.exe" in line for line in result["insights"])
