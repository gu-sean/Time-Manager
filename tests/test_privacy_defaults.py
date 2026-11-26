""""도메인만 저장": 새 설치는 켜짐, 기존 사용자의 설정은 그대로."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from time_manager.models import ActiveTarget
from time_manager.rules import RuleClassifier
from time_manager.settings import SettingsStore
from time_manager.storage import ActivityStore
from time_manager.tracker import ActivityTracker


def store_at(folder: Path, content: object = None) -> SettingsStore:
    path = folder / "settings.json"
    if content is not None:
        path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return SettingsStore(path)


def test_a_new_installation_stores_only_the_domain(tmp_path: Path) -> None:
    settings = store_at(tmp_path).load_or_create()

    assert settings.store_domain_only is True
    assert settings.store_window_titles is True  # 이 설정의 기본값은 그대로
    saved = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert saved["store_domain_only"] is True


@pytest.mark.parametrize("chosen", [True, False])
def test_a_saved_choice_is_kept(tmp_path: Path, chosen: bool) -> None:
    settings = store_at(tmp_path, {"store_domain_only": chosen, "daily_goal_minutes": 200})

    assert settings.load_or_create().store_domain_only is chosen
    settings.save(settings.load())
    assert settings.load().store_domain_only is chosen


def test_an_existing_file_without_the_key_behaves_as_before(tmp_path: Path) -> None:
    """업데이트만으로 기존 사용자의 저장 방식이 바뀌면 안 됨."""
    settings = store_at(tmp_path, {"daily_goal_minutes": 200})

    assert settings.load().store_domain_only is False


@pytest.mark.parametrize("damaged", ["{not json", "[1, 2]"])
def test_an_unreadable_file_falls_back_to_storing_less(tmp_path: Path, damaged: str) -> None:
    assert store_at(tmp_path, damaged).load().store_domain_only is True


@pytest.mark.parametrize(
    "address,stored",
    [
        ("youtube.com/watch?v=secret", "https://youtube.com"),
        ("https://www.google.com/search?q=private+words", "https://google.com"),
        ("127.0.0.1:8000/page?token=abc", "https://127.0.0.1"),
    ],
)
def test_with_the_new_default_no_path_or_query_reaches_the_database(
    tmp_path: Path, address: str, stored: str
) -> None:
    settings = store_at(tmp_path).load_or_create()
    rules = tmp_path / "rules.json"
    rules.write_text("{}", encoding="utf-8")
    store = ActivityStore(tmp_path / "activity.sqlite3")

    class Monitor:
        def idle_seconds(self) -> int:
            return 0

        def get_active_target(self) -> ActiveTarget:
            return ActiveTarget("chrome.exe", "title", address)

    tracker = ActivityTracker(
        store=store, classifier=RuleClassifier.from_file(rules), monitor=Monitor(),
        store_domain_only=settings.store_domain_only,
    )
    try:
        tracker._tick()
        with store._connection() as conn:
            assert [row[0] for row in conn.execute("SELECT url FROM activity_events")] == [stored]
    finally:
        store.close()
