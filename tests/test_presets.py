import json
from pathlib import Path
from unittest.mock import patch

import pytest
from test_ai import FakeKeys, _unclassified

from time_manager.presets import MAX_PRESETS, coerce_presets
from time_manager.rules import load_rules
from time_manager.webapi import WebApi


def _options(result: dict) -> dict[str, dict]:
    return {o["label"]: o for o in result["profileOptions"]}


def _items(result: dict) -> set[tuple[str, str]]:
    return {(i["key"], i["value"]) for i in result["presetItems"]}


def _create(api: WebApi, name: str = "내 업무", source: str = "") -> str:
    result = api.create_preset(name, "🚀", source)
    assert "error" not in result, result.get("error")
    return result["profile"]


class TestCreate:
    def test_empty_preset_is_selected_and_listed(self, api: WebApi) -> None:
        result = api.create_preset("  내   업무 ", "🚀")

        assert result["presetItems"] == []
        assert _options(result)["내 업무"] == {"value": result["profile"], "label": "내 업무", "emoji": "🚀", "custom": True}

    def test_copy_of_a_builtin_keeps_the_original_untouched(self, api: WebApi) -> None:
        preset_id = _create(api, source="developer")
        api.update_preset(preset_id, "내 업무", "🚀", [{"key": "productive_domains", "value": "only.example.com"}])

        assert ("productive_domains", "github.com") in _items(api.set_profile("developer"))
        assert _items(api.set_profile(preset_id)) == {("productive_domains", "only.example.com")}

    def test_from_current_rules_leaves_out_unrelated_lists(self, api: WebApi) -> None:
        api.add_rule("도메인", "생산적", "mine.com")

        result = api.create_preset("지금 규칙", "", "current_rules")

        assert _items(result) == {("productive_domains", "mine.com")}  # 제외 앱·중립 키워드는 포함 안 함
        assert _options(result)["지금 규칙"]["emoji"] == "🧩"

    @pytest.mark.parametrize("name", ["", "   ", "가" * 31, "개발자"])
    def test_rejects_bad_names(self, api: WebApi, name: str) -> None:
        assert "error" in api.create_preset(name)
        assert api.settings.custom_presets == []

    def test_rejects_duplicates_unknown_sources_and_too_many(self, api: WebApi) -> None:
        _create(api, "Work")
        assert "error" in api.create_preset("work")
        assert "error" in api.create_preset("x", "", "nope")
        for number in range(MAX_PRESETS - 1):
            _create(api, f"p{number}")
        assert "error" in api.create_preset("one too many")


class TestUpdate:
    def test_normalizes_and_deduplicates(self, api: WebApi) -> None:
        preset_id = _create(api)

        result = api.update_preset(
            preset_id, "새 이름", "✨",
            [
                {"key": "productive_domains", "value": "https://www.Company.com/path?q=1"},
                {"key": "productive_domains", "value": "company.com"},
                {"key": "unproductive_apps", "value": "  Game.exe "},
                {"key": "productive_title_keywords", "value": "분기 보고"},
            ],
        )

        assert "error" not in result
        assert _items(result) == {
            ("productive_domains", "company.com"), ("unproductive_apps", "Game.exe"),
            ("productive_title_keywords", "분기 보고"),
        }
        assert api.settings_store.load().custom_presets[0]["name"] == "새 이름"

    @pytest.mark.parametrize(
        "items",
        [
            [{"key": "excluded_apps", "value": "a.exe"}],
            [{"key": "productive_domains", "value": "not a domain"}],
            [{"key": "productive_domains", "value": "localhost"}],
            [{"key": "productive_apps", "value": " "}],
            [{"key": "productive_domains", "value": "x.com"}, {"key": "unproductive_domains", "value": "X.com"}],
            [{"key": "productive_apps", "value": f"a{n}.exe"} for n in range(101)],
        ],
    )
    def test_invalid_input_changes_nothing(self, api: WebApi, items: list) -> None:
        preset_id = _create(api, source="developer")
        before = json.dumps(api.settings.custom_presets)

        assert "error" in api.update_preset(preset_id, "다른 이름", "🚀", items)
        assert json.dumps(api.settings.custom_presets) == before

    def test_builtins_are_read_only(self, api: WebApi) -> None:
        assert "error" in api.update_preset("developer", "x", "", [])
        assert "error" in api.delete_preset("developer")

    def test_keeping_the_same_name_is_allowed(self, api: WebApi) -> None:
        preset_id = _create(api)

        assert "error" not in api.update_preset(preset_id, "내 업무", "🚀", [])


class TestApplyAndDelete:
    def test_apply_adds_rules_and_classifies(self, api: WebApi) -> None:
        preset_id = _create(api)
        api.update_preset(preset_id, "내 업무", "🚀", [{"key": "productive_apps", "value": "Tool.exe"}])

        result = api.apply_preset()

        assert "1개를 추가" in result["notice"]
        assert "Tool.exe" in load_rules(api.rules_path)["productive_apps"]
        assert "Tool.exe" in api.tracker.classifier.productive_apps

    def test_existing_rules_win_over_the_preset(self, api: WebApi) -> None:
        api.add_rule("도메인", "생산적", "youtube.com")
        api.set_profile("developer")  # youtube.com 을 비생산적으로 포함

        result = api.apply_preset()

        rules = load_rules(api.rules_path)
        assert "youtube.com" in rules["productive_domains"]
        assert "youtube.com" not in rules.get("unproductive_domains", [])
        assert "1개는 이미 다른 분류" in result["notice"]
        assert "0개를 추가" in api.apply_preset()["notice"]  # 다시 적용하면 추가 없음

    def test_delete_keeps_applied_rules_and_clears_the_selection(self, api: WebApi) -> None:
        preset_id = _create(api, source="developer")
        api.apply_preset()

        result = api.delete_preset(preset_id)

        assert result["profile"] == "" and "내 업무" not in _options(result)
        assert "github.com" in load_rules(api.rules_path)["productive_domains"]

    def test_unknown_selection_is_rejected(self, api: WebApi) -> None:
        assert "error" in api.set_profile("custom:missing")


class TestWithAnalysis:
    def test_builtin_recommendations_learn_from_a_custom_preset(self, api: WebApi) -> None:
        preset_id = _create(api)
        api.update_preset(preset_id, "내 업무", "🚀", [{"key": "productive_apps", "value": "Tool.exe"}])
        api.store.record(_unclassified("Tool.exe", "t"), 600)

        result = api.get_ai_rule_suggestions()

        assert [(i["target"], i["category"]) for i in result["items"]] == [("Tool.exe", "productive")]

    @pytest.mark.parametrize("source,role", [("developer", "developer"), ("", "unspecified")])
    def test_the_typed_name_is_never_sent(self, api: WebApi, source: str, role: str) -> None:
        api._ai_keys = FakeKeys()
        api.save_ai_settings("model", "ollama", "m")
        _create(api, "비밀 프로젝트 담당", source)
        api.store.record(_unclassified("notion.exe", "t"), 900)

        with patch("time_manager.ai.complete", return_value="[]") as llm:
            api.get_ai_rule_suggestions()
            sent = llm.call_args.kwargs["user"]
        coaching = api.preview_ai_request("coaching", "day")["data"]

        for text in (sent, coaching):
            assert "비밀" not in text and "custom:" not in text
        assert json.loads(coaching)["userProfile"] == role


class TestStorage:
    def test_survives_restart_and_backup_restore(self, api: WebApi, tmp_path: Path) -> None:
        preset_id = _create(api, source="developer")
        archive = api._backup_manager().export(tmp_path / "b.tmbak")
        api.delete_preset(preset_id)

        with patch.object(WebApi, "_open_dialog", return_value=archive):
            result = api.restore_backup()

        assert result["profile"] == preset_id
        assert _options(result)["내 업무"]["custom"] is True

    def test_damaged_entries_are_dropped_not_fatal(self) -> None:
        good = {"id": "custom:1", "name": "ok", "rules": {"productive_apps": ["a.exe", 3, " "], "bad": ["x"]}}

        presets = coerce_presets([good, good, {"id": "developer", "name": "x", "rules": {}}, "junk",
                                  {"id": "custom:2", "name": "", "rules": {}}, {"id": "custom:3", "name": "n"}])

        assert presets == [
            {"id": "custom:1", "name": "ok", "emoji": "🧩", "base": "", "rules": {"productive_apps": ["a.exe"]}}
        ]
        assert coerce_presets(None) == []
