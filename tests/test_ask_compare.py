"""두 기간 비교, 하루 중 시간대를 묻는 질문."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from time_manager.ask import QuestionError, parse_local, parse_model_spec, run_query
from time_manager.models import Category
from time_manager.storage import ActivityStore

TODAY = date(2026, 11, 26)  # 목요일
NAMES = ["Code.exe", "youtube.com"]
LAST_WEEK = (date(2026, 11, 16), date(2026, 11, 22))
THIS_WEEK = (date(2026, 11, 23), TODAY)
YESTERDAY = date(2026, 11, 25)


@pytest.mark.parametrize(
    "question",
    [
        "지난주랑 이번 주 비교해줘", "이번 주랑 지난주 비교", "지난주보다 이번 주에 더 많이 썼어?",
        "지난주 대비 이번 주 늘었어?", "지난주와 이번 주 차이", "이번 주는 지난주보다 줄었나요",
    ],
)
def test_comparisons_put_the_earlier_period_first(question: str) -> None:
    spec = parse_local(question, NAMES, TODAY)
    assert (spec.compare, (spec.start, spec.end), spec.group_by) == (LAST_WEEK, THIS_WEEK, "none")


def test_comparison_keeps_the_target_and_category() -> None:
    spec = parse_local("어제랑 오늘 유튜브 비교해줘", NAMES, TODAY)
    assert (spec.compare, spec.targets) == ((YESTERDAY, YESTERDAY), ("youtube.com",))
    assert parse_local("지난주랑 이번 주 생산 시간 비교", NAMES, TODAY).category == Category.PRODUCTIVE


@pytest.mark.parametrize(
    "question",
    ["유튜브 언제 가장 많이 봤어?", "오늘 시간대별 사용 시간", "어제 몇 시에 많이 썼어", "지난주 어느 시간대에 가장 많이 했어"],
)
def test_time_of_day_questions(question: str) -> None:
    assert parse_local(question, NAMES, TODAY).group_by == "hour"


def test_how_many_hours_is_not_a_time_of_day_question() -> None:
    assert parse_local("어제 몇 시간 했어", NAMES, TODAY).group_by == "none"
    assert parse_local("지난주 무슨 요일에 가장 많이 썼어", NAMES, TODAY).group_by == "day"


def _model(**changes: object) -> dict:
    data = {"answerable": True, "start": "2026-11-23", "end": "2026-11-26", "category": None,
            "targets": None, "groupBy": "none", "compareStart": None, "compareEnd": None}
    return {**data, **changes}


def test_a_model_comparison_is_ordered_by_date() -> None:
    spec = parse_model_spec(
        _model(start="2026-11-16", end="2026-11-22", compareStart="2026-11-23", compareEnd="2026-11-26"), NAMES, TODAY
    )
    assert (spec.compare, (spec.start, spec.end)) == (LAST_WEEK, THIS_WEEK)


@pytest.mark.parametrize(
    "changes",
    [
        {"compareStart": "2026-11-16"},  # 기간의 절반만 있음
        {"compareStart": "2026-11-20", "compareEnd": "2026-11-24"},  # 기간 겹침
        {"compareStart": "2026-11-16", "compareEnd": "2026-11-22", "groupBy": "day"},
        {"compareStart": "never", "compareEnd": "2026-11-22"},
    ],
)
def test_a_bad_model_comparison_is_refused(changes: dict) -> None:
    with pytest.raises(QuestionError):
        parse_model_spec(_model(**changes), NAMES, TODAY)


@pytest.fixture()
def store(tmp_path: Path):
    value = ActivityStore(tmp_path / "activity.sqlite3")
    zone = datetime.now().astimezone().isoformat(timespec="seconds")[-6:]
    rows = [
        # 지난주: 7일 동안 유튜브 7시간
        ("2026-11-17T20:00:00", 7 * 3600, "unproductive", "chrome.exe", "https://youtube.com/watch"),
        # 이번 주(현재 4일): 유튜브 2시간
        ("2026-11-24T21:30:00", 2 * 3600, "unproductive", "chrome.exe", "https://youtube.com/watch"),
        ("2026-11-24T09:00:00", 3600, "productive", "Code.exe", None),
    ]
    with value._connection() as conn:
        for started, seconds, category, app, url in rows:
            conn.execute(
                "INSERT INTO activity_events (started_at, seconds, category, app_name, window_title, url, reason)"
                " VALUES (?, ?, ?, ?, 't', ?, 'r')",
                (started + zone, seconds, category, app, url),
            )
    yield value
    value.close()


def test_periods_of_different_length_are_compared_per_day(store: ActivityStore) -> None:
    result = run_query(store, parse_local("지난주랑 이번 주 유튜브 비교", NAMES, TODAY), TODAY)
    # 7시간 / 7일 = 하루 1시간, 2시간 / 4일 = 하루 30분 (합계 차이는 5시간)
    assert "하루 평균: 1시간 → 30분, 30분 줄었어요." in result["answer"]
    assert "7일과 4일" in result["answer"] and "오늘은 아직 끝나지 않았어요" in result["answer"]
    # 막대도 평균을 표시: "줄었다"는 쪽의 막대가 더 길면 안 됨
    assert [(row["time"], row["ratio"]) for row in result["rows"]] == [("1시간", 1.0), ("30분", 0.5)]
    assert result["rows"][0]["label"].endswith("하루 평균 (합계 7시간)")
    assert result["interpretation"].startswith("비교 2026-11-16~2026-11-22 → 2026-11-23~2026-11-26")


def test_equal_periods_are_compared_by_total(store: ActivityStore) -> None:
    result = run_query(store, parse_model_spec(
        _model(start="2026-11-24", end="2026-11-24", compareStart="2026-11-17", compareEnd="2026-11-17"), NAMES, TODAY
    ), TODAY)
    assert result["answer"] == "사용 시간: 7시간 → 3시간, 4시간 줄었어요."


def test_the_difference_matches_the_numbers_shown(store: ActivityStore) -> None:
    zone = datetime.now().astimezone().isoformat(timespec="seconds")[-6:]
    with store._connection() as conn:
        conn.execute("DELETE FROM activity_events")
        for day, seconds in (("2026-11-17", 54 * 60 + 50), ("2026-11-24", 87 * 60 + 5)):
            conn.execute(
                "INSERT INTO activity_events (started_at, seconds, category, app_name, window_title, url, reason)"
                " VALUES (?, ?, 'productive', 'Code.exe', 't', NULL, 'r')",
                (f"{day}T09:00:00{zone}", seconds),
            )
    spec = parse_model_spec(
        _model(start="2026-11-24", end="2026-11-24", compareStart="2026-11-17", compareEnd="2026-11-17"), NAMES, TODAY
    )
    assert "54분 → 1시간 27분, 33분 늘었어요" in run_query(store, spec, TODAY)["answer"]


def test_hours_follow_the_clock(store: ActivityStore) -> None:
    result = run_query(store, parse_local("이번 주 유튜브 언제 많이 봤어", NAMES, TODAY), TODAY)
    assert [(row["label"], row["time"]) for row in result["rows"]] == [
        ("21시–22시", "30분"), ("22시–23시", "1시간"), ("23시–24시", "30분"),
    ]
    assert "가장 많이 쓴 시간대는 22시–23시" in result["answer"]


def test_the_busiest_day_is_named(store: ActivityStore) -> None:
    result = run_query(store, parse_local("최근 14일 무슨 요일에 가장 많이 썼어", NAMES, TODAY), TODAY)
    assert "가장 많이 쓴 날은 2026-11-17 (7시간)" in result["answer"]


def test_no_records_says_so(store: ActivityStore) -> None:
    result = run_query(store, parse_local("지난달이랑 어제 비교", NAMES, TODAY), TODAY)
    assert result["answer"] == "두 기간 모두 이 조건에 해당하는 활동 기록이 없어요." and result["rows"] == []
