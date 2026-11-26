"""지난 기록에 규칙 적용, 앱·사이트 묶기, 일간 목표."""

from datetime import date, datetime
from zipfile import ZipFile

import pytest

from time_manager.models import NO_RULE_REASON, ActiveTarget, Category, ClassifiedActivity
from time_manager.notifications import NullNotifier, RecordingNotifier
from time_manager.rules import RuleClassifier
from time_manager.settings import SettingsStore
from time_manager.storage import ActivityStore
from time_manager.tracker import ActivityTracker
from time_manager.webapi import WebApi

TODAY = date.today()


@pytest.fixture
def api(tmp_path):
    store = ActivityStore(tmp_path / "activity.sqlite3")
    rules = tmp_path / "rules.json"
    rules.write_text("{}", encoding="utf-8")
    tracker = ActivityTracker(
        store=store, classifier=RuleClassifier.from_dict({}), monitor=object(),
        notifier=RecordingNotifier(NullNotifier()),
    )
    settings = SettingsStore(tmp_path / "settings.json")
    saved = settings.load_or_create()
    saved.auto_backup_enabled = False
    settings.save(saved)
    yield WebApi(store=store, tracker=tracker, settings_store=settings, rules_path=rules)
    store.close()


def add(api, app, title="", url=None, seconds=60, category=Category.NEUTRAL, reason=NO_RULE_REASON, minute=0):
    started = datetime(TODAY.year, TODAY.month, TODAY.day, 9, minute).astimezone().isoformat(timespec="seconds")
    with api.store._connection() as conn:
        return conn.execute(
            "INSERT INTO activity_events (started_at, seconds, category, app_name, window_title, url, reason)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (started, seconds, category.value, app, title, url, reason),
        ).lastrowid


def categories(api):
    with api.store._connection() as conn:
        return dict(conn.execute("SELECT id, category FROM activity_events ORDER BY id").fetchall())


def test_preview_shows_what_would_change_without_changing_it(api):
    add(api, "notion.exe", "a", seconds=120)
    add(api, "notion.exe", "b", seconds=60)
    add(api, "chrome.exe", "v", "https://www.youtube.com/watch?v=1", seconds=600)
    api.add_rule("앱 이름", "생산적", "notion.exe")
    api.add_rule("도메인", "비생산적", "youtube.com")
    before = categories(api)

    preview = api.preview_rule_reapply()

    assert (preview["count"], preview["timeLabel"], preview["more"]) == (3, "13분", 0)
    assert preview["items"][0] == {
        "target": "youtube.com", "from": "중립", "to": "비생산적", "count": 1, "timeLabel": "10분"}
    assert preview["items"][1]["count"] == 2
    assert categories(api) == before


def test_apply_changes_only_what_a_rule_matches(api):
    matched = add(api, "notion.exe", "a")
    manual = add(api, "notion.exe", "b", category=Category.UNPRODUCTIVE, reason="manual correction")
    deleted = add(api, "notion.exe", "c")
    api.store.soft_delete_event(deleted)
    # 창 제목을 저장하지 않아 제목 규칙으로 다시 판단할 수 없는 기록
    untitled = add(api, "reader.exe", "", category=Category.PRODUCTIVE, reason="productive title keyword: 강의")
    api.add_rule("앱 이름", "생산적", "notion.exe")

    result = api.reapply_rules()

    assert result["error"] == "" and "1건" in result["message"]
    assert categories(api) == {matched: "productive", manual: "unproductive", deleted: "neutral", untitled: "productive"}
    assert api.preview_rule_reapply()["count"] == 0


def test_the_state_before_applying_is_backed_up(api, tmp_path):
    add(api, "notion.exe", "a")
    api.add_rule("앱 이름", "생산적", "notion.exe")

    api.reapply_rules()

    (backup,) = (tmp_path / "backups").glob("pre-reapply-*.tmbak")
    restored = tmp_path / "restored.sqlite3"
    with ZipFile(backup) as archive:
        restored.write_bytes(archive.read("activity.sqlite3"))
    old = ActivityStore(restored)
    assert old.recent()[0].category == Category.NEUTRAL
    old.close()


def test_only_the_latest_three_safety_backups_stay(api, tmp_path):
    manager = api._backup_manager()
    made = [manager.safety_backup("reapply") for _ in range(5)]

    assert sorted((tmp_path / "backups").glob("pre-reapply-*.tmbak")) == made[-3:]


def test_nothing_changes_when_the_backup_fails(api, monkeypatch):
    add(api, "notion.exe", "a")
    api.add_rule("앱 이름", "생산적", "notion.exe")

    def full(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("time_manager.backup.BackupManager.export", full)
    result = api.reapply_rules()

    assert result["error"]
    assert set(categories(api).values()) == {"neutral"}


def test_windows_of_one_app_and_pages_of_one_site_are_grouped(api):
    for index in range(8):
        add(api, "Code.exe", f"file{index}.py", seconds=300, minute=index)
    add(api, "chrome.exe", "a", "https://github.com/a/b", seconds=100, minute=20)
    add(api, "msedge.exe", "b", "https://www.github.com/c", seconds=100, minute=30)

    rows = api.get_dashboard()["topApps"]

    assert [(row["label"], row["time"]) for row in rows] == [("Code.exe", "40분"), ("github.com", "3분")]
    assert api.get_report()["topActivities"][0]["name"] == "Code.exe"
    assert "Code.exe" in api.get_review()["highlights"][2]["value"]


def test_the_dashboard_shows_the_daily_goal(api):
    api.settings.daily_goal_minutes = 60
    add(api, "Code.exe", seconds=45 * 60, category=Category.PRODUCTIVE, reason="r")

    goal = api.get_dashboard()["goal"]

    assert (goal["value"], goal["pct"], goal["achieved"], goal["remaining"]) == ("45분 / 1시간 0분", 75, False, "15분")


def test_a_goal_is_not_shown_as_full_before_it_is_reached(api):
    api.settings.daily_goal_minutes = 180
    add(api, "Code.exe", seconds=180 * 60 - 1, category=Category.PRODUCTIVE, reason="r")
    assert api.get_dashboard()["goal"]["pct"] == 99

    add(api, "Code.exe", seconds=3600, category=Category.PRODUCTIVE, reason="r", minute=1)
    goal = api.get_dashboard()["goal"]
    assert goal["achieved"] and goal["ratio"] == 1.0 and goal["pct"] > 100


def _goal_messages(tracker):
    return [entry for entry in tracker.notifier.recent() if entry.title == "오늘 목표를 달성했어요"]


def _work(tracker, seconds, category=Category.PRODUCTIVE):
    activity = ClassifiedActivity(ActiveTarget("Code.exe", "x", None), category, "r")
    for _ in range(seconds // tracker.poll_seconds):
        tracker.store.record(activity, tracker.poll_seconds)
        tracker._maybe_goal_notify(activity)


def test_reaching_the_goal_notifies_once(api):
    tracker = api.tracker
    tracker.daily_goal_seconds = 60
    _work(tracker, 55)
    assert _goal_messages(tracker) == []
    _work(tracker, 60)
    assert len(_goal_messages(tracker)) == 1
    assert "1분" in _goal_messages(tracker)[0].message


def test_a_restart_after_the_goal_does_not_notify_again(api):
    add(api, "Code.exe", seconds=600, category=Category.PRODUCTIVE, reason="r")
    api.tracker.daily_goal_seconds = 60

    _work(api.tracker, 60)

    assert _goal_messages(api.tracker) == []


def test_saving_the_goal_applies_to_the_running_tracker(api):
    values = {**api.get_settings(), "dailyGoalMinutes": 240, "weeklyGoalMinutes": 1200}
    api.save_settings(values)
    assert api.tracker.daily_goal_seconds == 240 * 60
