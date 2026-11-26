"""비공개 창, 사이트 제외, 삭제한 기록, 업데이트 검증, 일괄 삭제, 일시정지 시간, 직접 기록, 목표 요일, 집중 중 알림."""

import hashlib
import io
import json
import sqlite3
from datetime import date, datetime, timedelta
from unittest.mock import patch
from zipfile import ZipFile

import pytest

from time_manager import tracker as tracker_module
from time_manager import updater
from time_manager.models import MANUAL_APP, PRIVATE_REASON, ActiveTarget, Category, ClassifiedActivity
from time_manager.notifications import NullNotifier, RecordingNotifier
from time_manager.platforms.windows import _has_private_marker
from time_manager.rules import RuleClassifier, load_rules
from time_manager.settings import SettingsStore
from time_manager.storage import ActivityStore
from time_manager.tracker import ActivityTracker
from time_manager.webapi import WebApi

TODAY = date.today()


class Monitor:
    last_status = ""

    def __init__(self):
        self.target = ActiveTarget("notepad.exe", "memo", None)

    def get_active_target(self):
        return self.target

    def idle_seconds(self):
        return 0

    def media_playing(self, app_name):
        return False


@pytest.fixture
def api(tmp_path):
    store = ActivityStore(tmp_path / "activity.sqlite3")
    rules = tmp_path / "rules.json"
    rules.write_text("{}", encoding="utf-8")
    tracker = ActivityTracker(store=store, classifier=RuleClassifier.from_dict({}), monitor=Monitor(),
                              notifier=RecordingNotifier(NullNotifier()))
    settings = SettingsStore(tmp_path / "settings.json")
    saved = settings.load_or_create()
    saved.auto_backup_enabled = False
    saved.store_domain_only = False
    settings.save(saved)
    value = WebApi(store=store, tracker=tracker, settings_store=settings, rules_path=rules)
    yield value
    store.close()


def rows(api, include_deleted=True):
    with sqlite3.connect(api.store.db_path) as conn:
        sql = "SELECT app_name, window_title, url, category, reason, deleted_at FROM activity_events"
        return conn.execute(sql if include_deleted else sql + " WHERE deleted_at IS NULL").fetchall()


def use(api, target, ticks=3):
    api.tracker.monitor.target = target
    for _ in range(ticks):
        api.tracker._tick()


def add(api, app, title="", url=None, seconds=60, when=None, category="neutral", deleted_at=None):
    when = when or datetime(TODAY.year, TODAY.month, TODAY.day, 0, 1).astimezone()
    with api.store._connection() as conn:
        return conn.execute(
            "INSERT INTO activity_events (started_at, seconds, category, app_name, window_title, url, reason, deleted_at)"
            " VALUES (?, ?, ?, ?, ?, ?, 'r', ?)",
            (when.isoformat(timespec="seconds"), seconds, category, app, title, url, deleted_at),
        ).lastrowid


# -- 비공개 창 -------------------------------------------------------------------

@pytest.mark.parametrize("text,private", [
    ("TM browser check - [InPrivate] - Microsoft​ Edge", True),  # 실제 Edge 제목
    ("TM browser check - Chrome (시크릿 모드)", True),  # 실제 Chrome 창 안쪽 영역 이름
    ("news - Google Chrome (Incognito)", True),
    ("page — Mozilla Firefox Private Browsing", True),
    ("page — Mozilla Firefox 사생활 보호 모드", True),
    ("TM browser check - Chrome", False),
    ("InPrivate browsing explained - Microsoft Edge", False),  # 페이지 제목에 낱말만 있음
    ("Private Equity 101 - Chrome", False),
])
def test_private_windows_are_recognised_by_their_marks(text, private):
    assert _has_private_marker(text) is private


@pytest.mark.parametrize("titles", [True, False])
def test_a_private_window_keeps_only_its_time(api, titles):
    api.tracker.store_window_titles = titles
    use(api, ActiveTarget("msedge.exe", "secret page - [InPrivate] - Microsoft Edge", None, private=True))
    assert rows(api) == [("msedge.exe", "비공개 창", None, "neutral", PRIVATE_REASON, None)]
    assert sum(row.seconds for row in api.store.summary_for_day(TODAY)) == 15


def test_rules_do_not_classify_private_time(api):
    api.add_rule("앱 이름", "비생산적", "msedge.exe")
    use(api, ActiveTarget("msedge.exe", "x", None, private=True))
    assert rows(api)[0][3:5] == ("neutral", PRIVATE_REASON)
    assert api.preview_rule_reapply()["count"] == 0


# -- 사이트 제외 ------------------------------------------------------------------

def test_a_site_can_be_excluded(api):
    result = api.add_rule("도메인", "기록 제외", "mybank.com")
    assert [(i["ruleType"], i["key"]) for i in result["items"]] == [("도메인", "excluded_domains")]
    use(api, ActiveTarget("chrome.exe", "account", "https://www.mybank.com/account?no=1"))
    use(api, ActiveTarget("chrome.exe", "login", "https://login.mybank.com/"))
    use(api, ActiveTarget("chrome.exe", "news", "https://news.example.com/"))
    assert [row[2] for row in rows(api)] == ["https://news.example.com/"]


def test_title_keywords_cannot_exclude(api):
    assert api.add_rule("창 제목 키워드", "기록 제외", "bank")["error"]
    assert load_rules(api.rules_path) == {}


def test_sites_saved_as_apps_by_the_old_version_are_moved(api):
    api.rules_path.write_text(json.dumps({"excluded_apps": ["mybank.com", "KakaoTalk.exe"]}), encoding="utf-8")
    rules = load_rules(api.rules_path)
    assert (rules["excluded_apps"], rules["excluded_domains"]) == (["KakaoTalk.exe"], ["mybank.com"])
    assert RuleClassifier.from_dict(rules).excluded_domains == ("mybank.com",)


def test_an_excluded_site_conflicts_with_the_same_site_as_productive(api):
    api.add_rule("도메인", "기록 제외", "mybank.com")
    assert api.add_rule("도메인", "생산적", "mybank.com")["error"]


# -- 삭제한 기록 ------------------------------------------------------------------

def test_deleted_records_can_be_restored_for_a_day_then_are_gone(api):
    event = add(api, "chrome.exe", "private title", "https://x.example/secret")
    api.delete_event(event)
    assert rows(api)[0][5]  # 아직 복원 가능
    assert api.store.purge_deleted(now=datetime.now().astimezone() + timedelta(hours=25)) == 1
    assert rows(api) == []


def test_deleting_clears_older_deleted_records(api):
    old = (datetime.now().astimezone() - timedelta(days=3)).isoformat(timespec="seconds")
    add(api, "a.exe", "old secret", deleted_at=old)
    api.delete_event(add(api, "b.exe", "new"))
    assert [row[1] for row in rows(api)] == ["new"]


def test_backups_never_contain_deleted_records(api, tmp_path):
    keep = add(api, "a.exe", "keep me")
    api.delete_event(add(api, "b.exe", "deleted title"))
    out = tmp_path / "b.tmbak"
    api._backup_manager().export(out)
    copy = tmp_path / "copy.sqlite3"
    with ZipFile(out) as archive:
        copy.write_bytes(archive.read("activity.sqlite3"))
    with sqlite3.connect(copy) as conn:
        assert conn.execute("SELECT id, window_title FROM activity_events").fetchall() == [(keep, "keep me")]
    assert b"deleted title" not in copy.read_bytes()


def test_deleted_text_does_not_stay_in_the_file(api):
    api.store.delete_target("app", add(api, "zz.exe", "UNIQUE-SECRET-TEXT") and "zz.exe")
    api.store.close()
    assert b"UNIQUE-SECRET-TEXT" not in api.store.db_path.read_bytes()


# -- 업데이트 파일 확인 -------------------------------------------------------------

def _release(digest):
    asset = {"name": "TimeManager-Setup-99.0.0.exe", "browser_download_url": "https://example.invalid/s.exe"}
    if digest:
        asset["digest"] = digest
    response = io.BytesIO(json.dumps({"tag_name": "v99.0.0", "assets": [asset]}).encode())
    response.__enter__ = lambda self=response: self
    response.__exit__ = lambda *a: False
    return response


@pytest.fixture
def no_launch(monkeypatch, tmp_path):
    updater._expected_sha256.clear()
    started = []
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(updater.subprocess, "Popen", lambda *a, **k: started.append(a))
    yield started
    updater._expected_sha256.clear()


def _download(payload):
    return patch.object(updater.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(payload))


def test_the_installer_runs_only_when_it_matches_the_release(no_launch):
    good = b"real installer"
    with patch.object(updater.urllib.request, "urlopen", lambda *a, **k: _release("sha256:" + hashlib.sha256(good).hexdigest())):
        assert updater.check_for_update()["assetUrl"] == "https://example.invalid/s.exe"
    with _download(b"tampered"):
        result = updater.download_and_launch_installer("https://example.invalid/s.exe")
    assert not result["started"] and "달라" in result["error"] and no_launch == []
    with _download(good):
        assert updater.download_and_launch_installer("https://example.invalid/s.exe")["started"]
    assert len(no_launch) == 1


@pytest.mark.parametrize("digest", ["", "md5:abc"])
def test_without_a_checksum_nothing_is_downloaded(no_launch, digest):
    with patch.object(updater.urllib.request, "urlopen", lambda *a, **k: _release(digest)):
        updater.check_for_update()
    with patch.object(updater.urllib.request, "urlopen", side_effect=AssertionError("must not download")):
        result = updater.download_and_launch_installer("https://example.invalid/s.exe")
    assert not result["started"] and result["error"] and no_launch == []


# -- 한꺼번에 삭제 ----------------------------------------------------------------

def test_all_records_of_a_site_can_be_deleted(api):
    first = add(api, "chrome.exe", "a", "https://www.example.com/a", seconds=120)
    add(api, "msedge.exe", "b", "https://shop.example.com/b", seconds=60)
    add(api, "chrome.exe", "c", "https://other.org/", seconds=30)
    preview = api.preview_delete_target(first)
    assert (preview["target"], preview["kindLabel"], preview["count"], preview["timeLabel"]) == ("example.com", "사이트", 2, "3분")
    assert "2건" in api.delete_target_records(first)["message"]
    assert [row[2] for row in rows(api)] == ["https://other.org/"]


def test_deleting_an_app_keeps_its_web_pages(api):
    first = add(api, "Code.exe", "a.py")
    add(api, "Code.exe", "b.py")
    add(api, "Code.exe", "docs", "https://code.visualstudio.com/")
    assert api.preview_delete_target(first)["count"] == 2
    api.delete_target_records(first)
    assert [row[1] for row in rows(api)] == ["docs"]


def test_a_period_can_be_deleted(api):
    day = TODAY - timedelta(days=3)
    for offset in range(3):
        moment = datetime(day.year, day.month, day.day, 10).astimezone() + timedelta(days=offset)
        add(api, "a.exe", f"day{offset}", when=moment)
    start, end = day.isoformat(), (day + timedelta(days=1)).isoformat()
    assert api.preview_delete_period(start, end)["count"] == 2
    assert "2건" in api.delete_period(start, end)["message"]
    assert [row[1] for row in rows(api)] == ["day2"]
    assert api.delete_period(end, start)["error"]


# -- 시간을 정한 일시정지 -----------------------------------------------------------

def test_a_timed_pause_ends_by_itself(api, monkeypatch):
    clock = [1_000_000.0]
    monkeypatch.setattr(tracker_module._time, "time", lambda: clock[0])
    api.tracker._thread = type("Alive", (), {"is_alive": lambda self: True})()
    api.tracker.pause(15)
    assert api.tracker.paused_until == clock[0] + 900
    use(api, ActiveTarget("notepad.exe", "memo", None))
    assert rows(api) == []
    clock[0] += 901
    use(api, ActiveTarget("notepad.exe", "memo", None), ticks=1)
    assert not api.tracker.is_paused and len(rows(api)) == 1


def test_the_dashboard_shows_when_a_pause_ends(api, monkeypatch):
    monkeypatch.setattr(api.tracker, "start", lambda: None)
    monkeypatch.setattr(type(api.tracker), "is_running", property(lambda self: True))
    data = api.pause_tracking(60)
    expected = datetime.fromtimestamp(api.tracker.paused_until)
    assert data["pausedUntil"].endswith(f"{expected:%H:%M}") and not data["tracking"]
    assert api.pause_tracking("abc")["pausedUntil"] == ""  # 잘못된 값: 다시 켤 때까지


# -- 직접 기록 --------------------------------------------------------------------

def _yesterday(api, start="10:00", minutes=30, label="팀 회의", category="productive"):
    day = (TODAY - timedelta(days=1)).isoformat()
    return api.add_manual_entry(day, start, minutes, label, category)


def test_time_away_from_the_pc_can_be_added(api):
    result = _yesterday(api)
    assert result["error"] == "" and "30분" in result["message"]
    yesterday = TODAY - timedelta(days=1)
    assert rows(api) == [(MANUAL_APP, "팀 회의", None, "productive", "manual entry", None)]
    assert sum(r.productive_seconds for r in api.store.summaries_between(yesterday, yesterday)) == 1800


@pytest.mark.parametrize("kwargs,error", [
    ({"label": " "}, "입력"), ({"minutes": 0}, "1~"), ({"minutes": 721}, "1~"), ({"category": "x"}, "분류"),
    ({"start": "25:00"}, "시각"), ({"label": "가" * 81}, "80자"), ({"start": "23:50", "minutes": 20}, "자정"),
])
def test_wrong_manual_entries_are_refused(api, kwargs, error):
    assert error in _yesterday(api, **kwargs)["error"]
    assert rows(api) == []


def test_a_manual_entry_may_not_overlap_recorded_time(api):
    yesterday = TODAY - timedelta(days=1)
    add(api, "Code.exe", "a.py", seconds=600, when=datetime(yesterday.year, yesterday.month, yesterday.day, 10, 20).astimezone())
    assert "10:20" in _yesterday(api)["error"]
    assert _yesterday(api, start="10:30", minutes=30)["error"] == ""


def test_the_future_cannot_be_added(api):
    future = (datetime.now() + timedelta(hours=2))
    if future.date() != TODAY:
        pytest.skip("near midnight")
    assert "지나지 않은" in api.add_manual_entry(TODAY.isoformat(), f"{future:%H:%M}", 10, "x", "productive")["error"]


def test_rules_never_reclassify_manual_entries(api):
    _yesterday(api, label="youtube 편집", category="productive")
    api.add_rule("창 제목 키워드", "비생산적", "youtube")
    assert api.preview_rule_reapply()["count"] == 0


# -- 목표 요일 --------------------------------------------------------------------

def test_a_day_without_a_goal(api):
    weekday = TODAY.weekday()
    values = {**api.get_settings(), "goalWeekdays": [day for day in range(7) if day != weekday]}
    assert not api.save_settings(values).get("error")
    assert api.get_dashboard()["goal"]["offDay"]
    assert weekday not in api.tracker.goal_weekdays
    assert api.save_settings({**api.get_settings(), "goalWeekdays": []})["error"]
    assert api.save_settings({**api.get_settings(), "goalWeekdays": [7]})["error"]


def test_no_goal_notice_on_a_day_off(api):
    api.tracker.daily_goal_seconds = 60
    api.tracker.goal_weekdays = frozenset(day for day in range(7) if day != TODAY.weekday())
    activity = ClassifiedActivity(ActiveTarget("Code.exe", "x", None), Category.PRODUCTIVE, "r")
    for _ in range(20):
        api.store.record(activity, 5)
        api.tracker._maybe_goal_notify(activity)
    assert api.tracker.notifier.recent() == []


def test_the_weekly_count_skips_days_without_a_goal(api):
    monday = TODAY - timedelta(days=TODAY.weekday())
    for offset in range(TODAY.weekday() + 1):
        day = monday + timedelta(days=offset)
        add(api, "Code.exe", "x", seconds=4 * 3600, category="productive",
            when=datetime(day.year, day.month, day.day, 0, 1).astimezone())
    every = api.store.weekly_progress(900, 180, reference_day=TODAY)
    only_monday = api.store.weekly_progress(900, 180, reference_day=TODAY, goal_weekdays={0})
    assert (every.achieved_days, only_monday.achieved_days) == (TODAY.weekday() + 1, 1)


# -- 집중 중 방해 알림 ---------------------------------------------------------------

def _focus(api, category, seconds, app="chrome.exe", url="https://video.example/watch?v=1"):
    activity = ClassifiedActivity(ActiveTarget(app, "secret title", url), category, "r")
    for _ in range(seconds // 5):
        api.tracker._maybe_focus_alert(activity)


def _alerts(api):
    return [entry for entry in api.tracker.notifier.recent() if entry.title == "집중하는 중이에요"]


def test_distraction_during_focus_is_noticed_once(api):
    api.set_focus_session((datetime.now().timestamp() + 600) * 1000)
    _focus(api, Category.UNPRODUCTIVE, 10)
    assert _alerts(api) == []  # 잠깐 지나친 것은 알리지 않음
    _focus(api, Category.UNPRODUCTIVE, 60)
    assert len(_alerts(api)) == 1
    assert "video.example" in _alerts(api)[0].message and "secret" not in _alerts(api)[0].message
    _focus(api, Category.PRODUCTIVE, 5)
    _focus(api, Category.UNPRODUCTIVE, 20)
    assert len(_alerts(api)) == 2  # 돌아갔다가 다시 딴짓


def test_no_distraction_notice_outside_focus_or_when_turned_off(api):
    _focus(api, Category.UNPRODUCTIVE, 60)
    api.set_focus_session((datetime.now().timestamp() - 1) * 1000)
    _focus(api, Category.UNPRODUCTIVE, 60)
    api.save_tracking_options({"focusAlert": False})
    api.set_focus_session((datetime.now().timestamp() + 600) * 1000)
    _focus(api, Category.UNPRODUCTIVE, 60)
    assert _alerts(api) == [] and api.get_settings()["focusAlert"] is False


def test_the_alert_ignores_the_notification_switch(api):
    api.tracker.notifier.set_enabled(False)  # 타이머처럼 사용자가 시작한 일
    api.set_focus_session((datetime.now().timestamp() + 600) * 1000)
    _focus(api, Category.UNPRODUCTIVE, 30)
    assert len(_alerts(api)) == 1
