"""정리함의 기록 하나로 만드는 "앞으로도 적용" 규칙."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from time_manager.models import Category
from time_manager.rules import RuleClassifier, load_rules
from time_manager.settings import SettingsStore
from time_manager.storage import ActivityStore
from time_manager.tracker import ActivityTracker
from time_manager.webapi import WebApi
from time_manager.webapi.report import _week_change_text


@pytest.fixture()
def api(tmp_path: Path):
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(
        json.dumps({"productive_domains": ["docs.example.com"], "unproductive_domains": ["video.example"]}),
        encoding="utf-8",
    )
    store = ActivityStore(tmp_path / "activity.sqlite3")
    tracker = ActivityTracker(store=store, classifier=RuleClassifier.from_file(rules_path))
    value = WebApi(
        store=store, tracker=tracker, settings_store=SettingsStore(tmp_path / "settings.json"), rules_path=rules_path
    )
    yield value
    store.close()


def add(api: WebApi, app: str, url: str | None, category: str, title: str = "t") -> int:
    with api.store._connection() as conn:
        return conn.execute(
            "INSERT INTO activity_events (started_at, seconds, category, app_name, window_title, url, reason)"
            " VALUES (?, 600, ?, ?, ?, ?, 'r')",
            (datetime.now().astimezone().isoformat(timespec="seconds"), category, app, title, url),
        ).lastrowid


def offered(api: WebApi, event_id: int) -> str:
    return next(row["ruleTarget"] for row in api.get_inbox()["records"] if row["id"] == event_id)


@pytest.mark.parametrize(
    "app,url,category,target",
    [
        ("chrome.exe", "https://www.news.example/a?q=1", "unproductive", "news.example"),
        ("Studio.exe", None, "productive", "Studio.exe"),
        ("chrome.exe", None, "unproductive", ""),  # 브라우저 규칙은 모든 웹 사용에 적용됨
        ("Studio.exe", None, "neutral", ""),
        ("chrome.exe", "https://video.example/1", "unproductive", ""),  # 이미 규칙대로 분류됨
    ],
)
def test_a_rule_is_offered_only_when_safe_and_useful(
    api: WebApi, app: str, url: str | None, category: str, target: str
) -> None:
    assert offered(api, add(api, app, url, category)) == target


def test_the_rule_is_added_and_used_by_the_tracker(api: WebApi) -> None:
    event = add(api, "Studio.exe", None, "productive")

    result = api.add_rule_for_event(event)

    assert result["error"] == "" and "Studio.exe" in result["message"]
    assert load_rules(api.rules_path)["productive_apps"] == ["Studio.exe"]
    assert api.tracker.classifier.productive_apps == ("Studio.exe",)
    assert offered(api, event) == ""


def test_an_opposite_rule_is_not_overwritten(api: WebApi) -> None:
    event = add(api, "chrome.exe", "https://video.example/lecture", "productive")

    result = api.add_rule_for_event(event)

    assert "추가하지 않았어요" in result["error"]
    assert load_rules(api.rules_path)["unproductive_domains"] == ["video.example"]


def test_a_rule_that_a_parent_domain_would_override_is_neither_offered_nor_added(api: WebApi) -> None:
    # 생산적 상위 도메인을 먼저 검사 → 비생산적 하위 도메인 규칙은 효과 없음
    event = add(api, "chrome.exe", "https://fun.docs.example.com/1", "unproductive")
    before = api.rules_path.read_text(encoding="utf-8")

    assert offered(api, event) == ""
    assert "추가하지 않았어요" in api.add_rule_for_event(event)["error"]
    assert api.rules_path.read_text(encoding="utf-8") == before


def test_missing_and_neutral_records_are_refused(api: WebApi) -> None:
    assert api.add_rule_for_event(9999)["error"]
    assert api.add_rule_for_event(add(api, "Studio.exe", None, "neutral"))["error"]


@pytest.mark.parametrize(
    "seconds,text",
    [(0, "지난주와 같음"), (30, "지난주와 같음"), (-14520, "지난주보다 4시간 2분 줄음"), (600, "지난주보다 10분 늘음")],
)
def test_the_weekly_change_is_readable(seconds: int, text: str) -> None:
    assert _week_change_text(seconds) == text
