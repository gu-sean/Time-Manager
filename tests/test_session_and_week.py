"""집중 구간은 긴 공백에서 끊기고, 지난주 비교는 같은 시점까지만 계산."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from time_manager.storage import ActivityStore

MONDAY = date(2026, 11, 23)
TUESDAY = MONDAY + timedelta(days=1)


@pytest.fixture()
def store(tmp_path: Path):
    value = ActivityStore(tmp_path / "activity.sqlite3")
    yield value
    value.close()


def add(store: ActivityStore, day: date, clock: str, seconds: int, category: str = "productive") -> None:
    zone = datetime.now().astimezone().isoformat(timespec="seconds")[-6:]
    with store._connection() as conn:
        conn.execute(
            "INSERT INTO activity_events (started_at, seconds, category, app_name, window_title, url, reason)"
            " VALUES (?, ?, ?, 'a.exe', 't', NULL, 'r')",
            (f"{day.isoformat()}T{clock}{zone}", seconds, category),
        )


def spans(store: ActivityStore) -> list[tuple[str, str, int]]:
    return [(s.started_at, s.ended_at, s.seconds // 60) for s in store.day_flow(MONDAY).sessions]


# -- 집중 구간 ---------------------------------------------------------------------

def test_blocks_hours_apart_are_not_one_focus_session(store: ActivityStore) -> None:
    add(store, MONDAY, "09:00:00", 13 * 60)
    add(store, MONDAY, "14:00:00", 13 * 60)

    assert spans(store) == [("09:00", "09:13", 13), ("14:00", "14:13", 13)]
    assert store.day_flow(MONDAY).focus_sessions() == ()


@pytest.mark.parametrize("second_start,expected", [("09:18:00", 1), ("09:18:01", 2)])
def test_a_break_of_more_than_five_minutes_ends_a_session(
    store: ActivityStore, second_start: str, expected: int
) -> None:
    add(store, MONDAY, "09:00:00", 13 * 60)
    add(store, MONDAY, second_start, 13 * 60)

    assert len(store.day_flow(MONDAY).sessions) == expected


def test_short_breaks_keep_the_session_and_are_not_counted(store: ActivityStore) -> None:
    for clock in ("09:00:00", "09:13:00", "09:23:00"):  # 쉬는 시간 3분, 0분
        add(store, MONDAY, clock, 10 * 60)

    assert spans(store) == [("09:00", "09:33", 30)]
    assert len(store.day_flow(MONDAY).focus_sessions()) == 1


def test_a_row_inside_a_longer_one_does_not_move_the_end_back(store: ActivityStore) -> None:
    add(store, MONDAY, "09:00:00", 30 * 60)
    add(store, MONDAY, "09:05:00", 60)  # 겹치는 행 (시계 변경 등)
    add(store, MONDAY, "09:32:00", 10 * 60)

    assert len(store.day_flow(MONDAY).sessions) == 1


def test_switch_counts_do_not_depend_on_breaks(store: ActivityStore) -> None:
    add(store, MONDAY, "09:00:00", 600)
    add(store, MONDAY, "14:00:00", 600)
    add(store, MONDAY, "14:10:00", 600, "unproductive")

    flow = store.day_flow(MONDAY)
    assert (flow.category_switches, len(flow.sessions)) == (1, 3)


# -- 지난주 비교 --------------------------------------------------------------------

def week(store: ActivityStore, now: datetime, reference_day: date | None = None) -> tuple[int, int]:
    progress = store.weekly_progress(900, 180, reference_day=reference_day, now=now)
    return progress.productive_seconds // 60, progress.previous_productive_seconds // 60


def same_pace(store: ActivityStore, until: date) -> None:
    """지난주 월요일부터 ``until`` 까지 매일 09:00-10:00, 14:00-15:00."""
    day = MONDAY - timedelta(days=7)
    while day <= until:
        add(store, day, "09:00:00", 3600)
        add(store, day, "14:00:00", 3600)
        day += timedelta(days=1)


def test_the_same_pace_compares_as_equal_after_the_day_is_done(store: ActivityStore) -> None:
    same_pace(store, TUESDAY)

    assert week(store, datetime(2026, 11, 24, 18, 0)) == (240, 240)


def test_last_week_is_cut_at_the_same_time_of_day(store: ActivityStore) -> None:
    same_pace(store, MONDAY)  # 지난주 화요일(09시, 14시 각 1시간) 포함
    add(store, TUESDAY, "09:00:00", 30 * 60)  # 오늘 09:30 까지 사용

    # 지난주: 월요일 2시간 + 화요일 09:00-09:30
    assert week(store, datetime(2026, 11, 24, 9, 30)) == (150, 150)


def test_monday_morning_is_not_compared_with_all_of_last_monday(store: ActivityStore) -> None:
    same_pace(store, MONDAY - timedelta(days=1))

    assert week(store, datetime(2026, 11, 23, 8, 0)) == (0, 0)


def test_a_finished_week_is_compared_in_full(store: ActivityStore) -> None:
    """월요일 알림: 일요일 기준이면 지난 두 주 전체를 비교."""
    same_pace(store, MONDAY - timedelta(days=1))  # 11/16-11/22
    add(store, date(2026, 11, 9), "23:00:00", 3600)
    add(store, date(2026, 11, 15), "23:00:00", 3600)

    sunday = date(2026, 11, 22)
    assert week(store, datetime(2026, 11, 23, 8, 0), reference_day=sunday) == (14 * 60, 120)
