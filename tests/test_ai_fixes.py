"""복원 안전성, 오래된 코칭, 약한 근거, 숨긴 추천, 전송 제외, 기록."""
import json
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from test_ai import FakeKeys, _unclassified

from time_manager import ai
from time_manager.local_model import LocalClassifier, Signature
from time_manager.models import ActiveTarget, Category, ClassifiedActivity
from time_manager.webapi import WebApi

P, U = Category.PRODUCTIVE, Category.UNPRODUCTIVE


def _work(app: str, category: Category = P) -> ClassifiedActivity:
    return ClassifiedActivity(ActiveTarget(app_name=app, window_title="t"), category, "rule")


@pytest.fixture
def model_api(api: WebApi) -> WebApi:
    api._ai_keys = FakeKeys()
    assert "error" not in api.save_ai_settings("model", "ollama", "m")
    return api


# -- 1. 복원한 백업이 데이터 전송처를 정하면 안 됨 -------------------------------

class TestRestore:
    @staticmethod
    def _backup_with(api: WebApi, tmp_path: Path, **changes: object) -> Path:
        """ "다른 PC"에서 만든 백업: 이 PC의 파일에 AI 설정만 다름."""
        original = api.settings_store.path.read_text(encoding="utf-8") if api.settings_store.path.exists() else None
        for key, value in changes.items():
            setattr(api.settings, key, value)
        api.settings_store.save(api.settings)
        archive = api._backup_manager().export(tmp_path / "foreign.tmbak")
        if original is None:
            api.settings_store.path.unlink()
        else:
            api.settings_store.path.write_text(original, encoding="utf-8")
        api.settings = api.settings_store.load()
        return archive

    def _restore(self, api: WebApi, archive: Path) -> dict:
        with patch.object(WebApi, "_open_dialog", return_value=archive):
            return api.restore_backup()

    def test_never_turns_on_sending_or_imports_a_server(self, api: WebApi, tmp_path: Path) -> None:
        api._ai_keys = FakeKeys()
        archive = self._backup_with(
            api, tmp_path, ai_provider="model", ai_service="custom",
            ai_service_configs={"custom": {"model": "m", "base_url": "https://other.example/v1"}},
        )

        result = self._restore(api, archive)

        assert result["aiProvider"] == "local"
        assert api.settings.ai_service_configs == {}
        assert "other.example" not in api.settings_store.path.read_text(encoding="utf-8")
        assert "내장 분석" in result["message"]

    def test_keeps_this_pcs_setup_and_merges_the_never_send_list(self, model_api: WebApi, tmp_path: Path) -> None:
        model_api.add_ai_exclusion("mine.com")
        archive = self._backup_with(
            model_api, tmp_path, ai_service_configs={}, ai_excluded_targets=["theirs.com"]
        )

        self._restore(model_api, archive)

        assert model_api.settings.ai_provider == "local"
        assert model_api.settings.ai_service_configs["ollama"]["model"] == "m"
        assert model_api.settings.ai_excluded_targets == ["mine.com", "theirs.com"]

    def test_quiet_when_no_model_was_involved(self, api: WebApi, tmp_path: Path) -> None:
        api.settings_store.save(api.settings)
        archive = api._backup_manager().export(tmp_path / "plain.tmbak")

        assert self._restore(api, archive)["message"] == "백업을 복원했습니다."

    def test_older_backup_without_history_table_still_works(self, api: WebApi, tmp_path: Path) -> None:
        with api.store._connection() as conn:
            conn.execute("DROP TABLE coaching_history")
        api.settings_store.save(api.settings)
        archive = api._backup_manager().export(tmp_path / "old.tmbak")
        api.store.ensure_schema()

        self._restore(api, archive)

        assert api.get_coaching_history() == []


# -- 2. 저장된 답은 완전히 같은 요청에만 재사용 ----------------------------------

class TestCoachingFreshness:
    def test_changed_records_goals_or_model_ask_again(self, model_api: WebApi) -> None:
        model_api.store.record(_work("code.exe"), 3600)
        with patch("time_manager.ai.complete", return_value='{"headline": "h"}') as llm:
            model_api.get_ai_coaching("day")
            assert model_api.get_ai_coaching("day")["reused"] is True
            assert llm.call_count == 1

            model_api.reclassify_event(model_api.get_inbox()["records"][0]["id"], "unproductive")
            assert model_api.get_ai_coaching("day")["reused"] is False
            model_api.settings.daily_goal_minutes = 10
            assert model_api.get_ai_coaching("day")["reused"] is False
            model_api.save_ai_settings("model", "ollama", "another")
            assert model_api.get_ai_coaching("day")["reused"] is False

        assert llm.call_count == 4

    def test_saved_answer_survives_a_restart(self, model_api: WebApi) -> None:
        model_api.store.record(_work("code.exe"), 3600)
        with patch("time_manager.ai.complete", return_value='{"headline": "h"}'):
            model_api.get_ai_coaching("day")
        restarted = WebApi(
            store=model_api.store, tracker=model_api.tracker,
            settings_store=model_api.settings_store, rules_path=model_api.rules_path,
        )
        restarted._ai_keys = FakeKeys()

        with patch("time_manager.ai.complete") as llm:
            result = restarted.get_ai_coaching("day")

        llm.assert_not_called()
        assert (result["headline"], result["reused"]) == ("h", True)


class TestCoachingHistory:
    def test_keeps_one_entry_per_period_and_source(self, model_api: WebApi) -> None:
        model_api.store.record(_work("code.exe"), 3600)
        with patch("time_manager.ai.complete", side_effect=['{"headline": "a"}', '{"headline": "b"}']):
            model_api.get_ai_coaching("day")
            model_api.get_ai_coaching("day", None, True)
        for _ in range(3):
            model_api.get_ai_coaching("day", None, False, "", True)
        model_api.get_ai_coaching("week", None, False, "", True)

        history = model_api.get_coaching_history()

        assert len(history) == 3
        assert {(h["scope"], h["source"], h["generated"]) for h in history} == {
            ("day", "Ollama · m", True), ("day", "내장 분석", False), ("week", "내장 분석", False)
        }
        assert next(h for h in history if h["generated"])["headline"] == "b"

    def test_delete_and_clear(self, api: WebApi) -> None:
        api.store.record(_work("code.exe"), 3600)
        api.get_ai_coaching("day")
        api.get_ai_coaching("week")
        first = api.get_coaching_history()[0]["id"]

        assert len(api.delete_coaching_history(first)) == 1
        assert api.clear_coaching_history() == []

    def test_failures_are_not_saved(self, model_api: WebApi) -> None:
        model_api.store.record(_work("code.exe"), 3600)
        with patch("time_manager.ai.complete", side_effect=ai.AIError("x")):
            model_api.get_ai_coaching("day")

        assert model_api.get_coaching_history() == []

    def test_follows_data_retention(self, api: WebApi) -> None:
        api.store.record(_work("code.exe"), 3600)
        api.get_ai_coaching("day")

        api.store.purge_older_than(30, reference_day=date.today() + timedelta(days=10))
        assert len(api.get_coaching_history()) == 1
        api.store.purge_older_than(5, reference_day=date.today() + timedelta(days=10))
        assert api.get_coaching_history() == []


# -- 3. 근거는 서로 다른 앱·사이트 수로 계산 -------------------------------------

def _titles(app: str, word: str, category: Category, count: int = 5) -> list[Signature]:
    return [Signature(app, "", f"{word} item{i}x", category, "manual correction", 600) for i in range(count)]


class TestEvidence:
    def test_many_titles_of_one_app_per_class_are_not_enough(self) -> None:
        model = LocalClassifier.train(_titles("solo.exe", "alpha", P) + _titles("fun.exe", "beta", U))

        assert model.predict("new.exe", {"alpha": 60}) is None

    def test_three_apps_per_class_are_enough(self) -> None:
        history = [s for n in range(3) for s in _titles(f"work{n}.exe", "alpha", P, 2)]
        history += [s for n in range(3) for s in _titles(f"play{n}.exe", "beta", U, 2)]

        result = LocalClassifier.train(history).predict("new.exe", {"alpha": 60})

        assert result is not None and result.category == P

    def test_an_app_the_user_listed_in_rules_still_matches(self) -> None:
        model = LocalClassifier.train([], rules={"productive_apps": ["Code.exe"]})

        assert model.predict("code.exe") is not None


# -- 4. 숨긴 추천은 계속 숨김 ----------------------------------------------------

class TestDismissedSuggestions:
    def test_stays_hidden_after_a_restart_and_can_come_back(self, api: WebApi) -> None:
        api.store.record(_unclassified("explorer.exe", "files"), 600)

        assert api.dismiss_rule_suggestion("Explorer.exe") == ["explorer.exe"]
        assert api.get_rule_suggestions() == []
        assert api.settings_store.load().dismissed_suggestions == ["explorer.exe"]

        assert api.restore_rule_suggestion("explorer.exe") == []
        assert [s["target"] for s in api.get_rule_suggestions()] == ["explorer.exe"]

    def test_is_not_sent_to_a_model(self, model_api: WebApi) -> None:
        model_api.store.record(_unclassified("explorer.exe", "files"), 600)
        model_api.dismiss_rule_suggestion("explorer.exe")

        with patch("time_manager.ai.complete") as llm:
            model_api.get_ai_rule_suggestions()

        llm.assert_not_called()


# -- 전송 제외 목록 ------------------------------------------------------------------

class TestExclusions:
    @pytest.mark.parametrize(
        "entered,stored",
        [(" Slack.EXE ", "slack.exe"), ("https://www.Corp.com/a/b?c=1", "corp.com"), ("www.corp.com", "corp.com"),
         ("git.corp.com/path", "git.corp.com")],
    )
    def test_normalizes_input(self, api: WebApi, entered: str, stored: str) -> None:
        assert api.add_ai_exclusion(entered)["aiExcludedTargets"] == [stored]

    def test_rejects_empty_input(self, api: WebApi) -> None:
        assert "error" in api.add_ai_exclusion("  ")

    @pytest.mark.parametrize(
        "name,excluded",
        [("corp.com", True), ("git.corp.com", True), ("notcorp.com", False), ("corp.com.evil.net", False),
         ("slack.exe", True), ("Slack.exe", True), ("slacker.exe", False)],
    )
    def test_matching(self, name: str, excluded: bool) -> None:
        assert ai.is_excluded(name, ["corp.com", "slack"]) is excluded

    @pytest.fixture
    def seeded(self, model_api: WebApi) -> WebApi:
        model_api.store.record(_unclassified("chrome.exe", "t", "https://wiki.corp.com/x"), 900)
        model_api.store.record(_unclassified("notion.exe", "t"), 600)
        model_api.store.record(_work("secretapp.exe"), 3600)
        model_api.add_ai_exclusion("corp.com")
        model_api.add_ai_exclusion("secretapp.exe")
        return model_api

    @pytest.mark.parametrize("kind", ["suggestions", "coaching", "question"])
    def test_excluded_names_are_in_no_request_or_preview(self, seeded: WebApi, kind: str) -> None:
        reply = '{"answerable": false}' if kind == "question" else "[]"
        with patch("time_manager.ai.complete", return_value=reply) as llm:
            preview = seeded.preview_ai_request(kind, "day", None, "오늘 뭐 했어")
            if kind == "suggestions":
                seeded.get_ai_rule_suggestions()
            elif kind == "coaching":
                seeded.get_ai_coaching("day")
            else:
                seeded.ask_activity("오늘 뭐 했어")

        sent = llm.call_args.kwargs["user"]
        for text in (sent, preview["data"]):
            assert "corp.com" not in text and "secretapp" not in text
        assert json.loads(sent) == json.loads(preview["data"])

    def test_totals_keep_the_minutes_without_the_name(self, seeded: WebApi) -> None:
        data = json.loads(seeded.preview_ai_request("coaching", "day")["data"])

        assert data["daily"][0]["productiveMin"] == 60

    def test_builtin_analysis_still_sees_everything(self, seeded: WebApi) -> None:
        coaching = seeded.get_ai_coaching("day", None, False, "", True)

        assert any("secretapp.exe" in line for line in coaching["insights"])

    def test_nothing_is_sent_when_everything_is_excluded(self, seeded: WebApi) -> None:
        seeded.add_ai_exclusion("notion.exe")

        with patch("time_manager.ai.complete") as llm:
            result = seeded.get_ai_rule_suggestions()

        llm.assert_not_called()
        assert (result["excluded"], result["items"]) == (2, [])
