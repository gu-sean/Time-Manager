"""자정 분리, 비교 기준, 잠깐의 창 전환, 정리함 조회 범위."""

from datetime import date, datetime, timedelta

import pytest

from time_manager import storage
from time_manager.models import ActiveTarget, Category, ClassifiedActivity
from time_manager.notifications import NullNotifier, RecordingNotifier
from time_manager.rules import RuleClassifier
from time_manager.settings import SettingsStore
from time_manager.storage import ActivityStore
from time_manager.tracker import ActivityTracker
from time_manager.webapi import WebApi
from time_manager.webapi._shared import _delta_text, _delta_tone

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


def _activity(category=Category.PRODUCTIVE, app="Code.exe", title="main.py"):
    return ClassifiedActivity(ActiveTarget(app, title, None), category, "test")


def _at(day, hour, minute=0, second=0):
    return datetime(day.year, day.month, day.day, hour, minute, second).astimezone().isoformat(timespec="seconds")


def _insert(store, started_at, seconds, category=Category.PRODUCTIVE, deleted_at=None):
    with store._connection() as conn:
        conn.execute(
            "INSERT INTO activity_events (started_at, seconds, category, app_name, window_title, url, reason, deleted_at)"
            " VALUES (?, ?, ?, 'Code.exe', 'main.py', NULL, 'test', ?)",
            (started_at, seconds, category.value, deleted_at),
        )


def _rows(store):
    with store._connection() as conn:
        return conn.execute(
            "SELECT started_at, seconds, deleted_at FROM activity_events ORDER BY started_at"
        ).fetchall()


def _total(store, day):
    return sum(row.seconds for row in store.summary_for_day(day))


@pytest.fixture
def store(tmp_path):
    value = ActivityStore(tmp_path / "activity.sqlite3")
    yield value
    value.close()


def test_recording_across_midnight_starts_a_new_row(store, monkeypatch):
    clock = [datetime.combine(YESTERDAY, datetime.min.time()) + timedelta(hours=23, minutes=59)]

    class FakeNow(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls.fromtimestamp(clock[0].timestamp(), tz)

    monkeypatch.setattr(storage, "datetime", FakeNow)
    for _ in range(24):  # 23:59:00 ~ 00:01:00
        store.record(_activity(), 5)
        clock[0] += timedelta(seconds=5)

    assert (_total(store, YESTERDAY), _total(store, TODAY)) == (60, 60)
    assert len(_rows(store)) == 2


def test_rows_saved_across_midnight_are_split_once_and_keep_totals(tmp_path):
    path = tmp_path / "activity.sqlite3"
    first = ActivityStore(path)
    _insert(first, _at(YESTERDAY, 23, 30), 3600)
    _insert(first, _at(YESTERDAY, 23, 50), 900, deleted_at=_at(TODAY, 8))
    _insert(first, _at(YESTERDAY, 22), 7200)  # 정확히 자정에 끝남 → 그대로
    first.close()

    for _ in range(2):  # 두 번 열어도 같음
        reopened = ActivityStore(path)
        rows = _rows(reopened)
        assert sum(seconds for _, seconds, _ in rows) == 3600 + 900 + 7200
        assert (_total(reopened, YESTERDAY), _total(reopened, TODAY)) == (1800 + 7200, 1800)
        assert len(rows) == 5
        # 삭제한 기록의 두 조각은 모두 삭제 상태
        assert sum(1 for _, _, deleted in rows if deleted) == 2
        hourly = reopened.hourly_summaries_between(YESTERDAY, YESTERDAY)
        assert sum(row.productive_seconds for row in hourly) == _total(reopened, YESTERDAY)
        reopened.close()


def test_a_row_longer_than_a_day_is_split_by_each_day(tmp_path):
    path = tmp_path / "activity.sqlite3"
    first = ActivityStore(path)
    start = TODAY - timedelta(days=2)
    _insert(first, _at(start, 23), 3600 + 86400 + 600)
    first.close()

    reopened = ActivityStore(path)
    assert [_total(reopened, start + timedelta(days=n)) for n in range(3)] == [3600, 86400, 600]
    reopened.close()


def test_newest_records_come_first_even_when_a_split_row_was_added_later(store):
    _insert(store, _at(TODAY, 9), 60)
    _insert(store, _at(TODAY, 0), 60)  # 나중에 추가됐지만 더 이른 기록

    assert [row.started_at for row in store.recent_for_day(TODAY, limit=None)] == [_at(TODAY, 9), _at(TODAY, 0)]


@pytest.mark.parametrize("delta,expected", [(0, "변화 없음"), (60, "▲ 1분"), (-3600, "▼ 1시간")])
def test_changes_are_short(delta, expected):
    assert _delta_text(delta) == expected


@pytest.mark.parametrize(
    "key,delta,tone",
    [("productive", 60, "good"), ("productive", -60, "bad"), ("unproductive", -60, "good"),
     ("unproductive", 60, "bad"), ("score", 3, "good"), ("neutral", -60, "neutral"), ("total", 60, "neutral"),
     ("unproductive", 0, "neutral")],
)
def test_the_colour_follows_whether_the_change_is_good(key, delta, tone):
    assert _delta_tone(key, delta) == tone


def _api(tmp_path, store):
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
    return WebApi(store=store, tracker=tracker, settings_store=settings, rules_path=rules)


def test_today_is_compared_with_yesterday_up_to_the_same_time(tmp_path, store):
    _insert(store, _at(YESTERDAY, 0), 30)
    _insert(store, _at(YESTERDAY, 23, 59, 59), 1)  # 지금보다 늦은 시각 (자정 직전 제외)

    data = _api(tmp_path, store).get_dashboard()
    stats = {item["key"]: item["delta"] for item in data["stats"]}

    if datetime.now().strftime("%H:%M:%S") < "00:01:00":
        pytest.skip("자정 직후에는 어제 같은 시각까지의 합이 30초보다 작음")
    assert (stats["total"], data["comparedWith"]) == ("▼ 30초", "어제 같은 시각")


def test_a_past_day_is_compared_with_the_whole_day_before(tmp_path, store):
    day = TODAY - timedelta(days=3)
    _insert(store, _at(day - timedelta(days=1), 23, 0), 120)
    _insert(store, _at(day, 9), 60)

    data = _api(tmp_path, store).get_dashboard(day.isoformat())

    assert ({item["key"]: item["delta"] for item in data["stats"]}["total"], data["comparedWith"]) == ("▼ 1분", "전날")


def test_report_of_a_past_period_does_not_say_yesterday(tmp_path, store):
    end = TODAY - timedelta(days=30)
    _insert(store, _at(end, 9), 600)

    report = _api(tmp_path, store).get_report_range((end - timedelta(days=6)).isoformat(), end.isoformat())

    assert report["insightSub"].startswith(f"{end.month}월 {end.day}일은 전날보다 생산 시간 +10분")
    assert "어제" not in report["insightSub"]


def test_report_including_today_compares_the_same_time_of_yesterday(tmp_path, store):
    assert _api(tmp_path, store).get_report()["insightSub"].startswith("어제 같은 시각보다")


def _streak_tracker(limit_seconds=600):
    notifier = RecordingNotifier(NullNotifier())
    tracker = ActivityTracker(
        store=object(), classifier=RuleClassifier.from_dict({}), monitor=object(), notifier=notifier,
        unproductive_alert_seconds=limit_seconds,
    )

    def use(category, seconds):
        for _ in range(seconds // tracker.poll_seconds):
            tracker._update_streak(_activity(category))

    return tracker, notifier, use


def test_a_short_glance_does_not_end_the_streak():
    tracker, notifier, use = _streak_tracker()
    for _ in range(2):
        use(Category.UNPRODUCTIVE, 300)
        use(Category.NEUTRAL, 60)  # 허용 시간까지
    assert tracker.current_streak() == (Category.UNPRODUCTIVE, 600)
    assert len(notifier.recent()) == 1


def test_a_long_switch_ends_the_streak_and_counts_the_new_one_from_its_start():
    tracker, notifier, use = _streak_tracker()
    use(Category.UNPRODUCTIVE, 590)
    use(Category.PRODUCTIVE, 90)

    assert tracker.current_streak() == (Category.PRODUCTIVE, 90)
    use(Category.UNPRODUCTIVE, 70)
    assert tracker.current_streak() == (Category.UNPRODUCTIVE, 70)
    assert notifier.recent() == []


def test_pausing_forgets_the_interruption():
    tracker, _, use = _streak_tracker()
    use(Category.UNPRODUCTIVE, 100)
    use(Category.NEUTRAL, 30)
    tracker.pause()
    tracker.resume()
    use(Category.NEUTRAL, 5)

    assert tracker.current_streak() == (Category.NEUTRAL, 5)


def test_inbox_lists_every_record_of_the_day(tmp_path, store):
    for index in range(120):
        _insert(store, _at(TODAY, index // 60, index % 60), 30)

    data = _api(tmp_path, store).get_inbox("", None, TODAY.isoformat())

    assert len(data["records"]) == 120
    assert data["truncated"] is False


def test_search_says_when_results_were_cut(tmp_path, store):
    for index in range(501):
        _insert(store, _at(TODAY, index // 60, index % 60), 30)

    data = _api(tmp_path, store).get_inbox("main", None)

    assert (len(data["records"]), data["truncated"]) == (500, True)
