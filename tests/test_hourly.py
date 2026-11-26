"""시간은 기록이 시작한 시각이 아니라 실제로 사용한 시각에 계산."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from time_manager.models import Category
from time_manager.storage import ActivityStore

DAY = date(2026, 11, 24)  # 화요일


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
            " VALUES (?, ?, ?, 'Code.exe', 'x', NULL, 'r')",
            (f"{day.isoformat()}T{clock}{zone}", seconds, category),
        )


def minutes_by_hour(store: ActivityStore, day: date) -> dict[int, int]:
    return {
        row.hour: row.productive_seconds // 60
        for row in store.hourly_summaries_between(day, day)
        if row.productive_seconds
    }


def test_a_long_row_is_divided_between_the_hours_it_covers(store: ActivityStore) -> None:
    add(store, DAY, "09:30:00", 2 * 3600)
    assert minutes_by_hour(store, DAY) == {9: 30, 10: 60, 11: 30}


def test_a_row_that_ends_on_the_hour_adds_nothing_to_the_next(store: ActivityStore) -> None:
    add(store, DAY, "09:45:00", 15 * 60)
    assert minutes_by_hour(store, DAY) == {9: 15}


def test_time_after_midnight_belongs_to_the_next_day(store: ActivityStore) -> None:
    add(store, DAY, "23:40:00", 60 * 60)
    assert minutes_by_hour(store, DAY) == {23: 20}
    assert minutes_by_hour(store, DAY + timedelta(days=1)) == {0: 40}


def test_the_heatmap_uses_the_same_division(store: ActivityStore) -> None:
    add(store, DAY, "23:40:00", 60 * 60)
    grid = store.weekday_hour_totals_between(DAY, DAY + timedelta(days=1))
    assert (grid[1][23], grid[2][0]) == (20 * 60, 40 * 60)
    assert sum(map(sum, grid)) == 60 * 60


def test_categories_stay_apart_and_nothing_is_lost(store: ActivityStore) -> None:
    add(store, DAY, "13:50:00", 1200, "unproductive")
    add(store, DAY, "14:20:00", 600, "neutral")
    rows = store.hourly_summaries_between(DAY, DAY)
    assert (rows[13].unproductive_seconds, rows[14].unproductive_seconds, rows[14].neutral_seconds) == (600, 600, 600)

def test_several_rows_in_one_hour_are_added_up(store: ActivityStore) -> None:
    add(store, DAY, "09:00:00", 600)
    add(store, DAY, "09:15:00", 900)
    add(store, DAY, "09:45:00", 60)
    assert minutes_by_hour(store, DAY) == {9: 26}


def test_the_hourly_total_equals_the_day_total_with_many_rows(store: ActivityStore) -> None:
    for index in range(90):
        add(store, DAY, f"{8 + index // 30:02d}:{(index % 30) * 2:02d}:00", 70)
    hourly = sum(row.productive_seconds for row in store.hourly_summaries_between(DAY, DAY))
    assert hourly == sum(row.seconds for row in store.summary_for_day(DAY)) == 90 * 70
