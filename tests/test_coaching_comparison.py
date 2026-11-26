from datetime import date, datetime, timedelta

from time_manager.webapi import WebApi


def _add(api: WebApi, days_ago: int, minutes: int) -> None:
    started = datetime.combine(date.today() - timedelta(days=days_ago), datetime.min.time()).astimezone()
    with api.store._connection() as conn:
        conn.execute(
            "INSERT INTO activity_events (started_at, seconds, category, app_name, window_title, reason)"
            " VALUES (?, ?, 'productive', 'code.exe', 't', 'rule')",
            (started.replace(hour=9).isoformat(timespec="seconds"), minutes * 60),
        )


def _comparison(api: WebApi, scope: str, days_ago: int = 0) -> dict | None:
    anchor = date.today() - timedelta(days=days_ago)
    start = anchor - timedelta(days=6 if scope == "week" else 0)
    return api._coaching_payload(scope, start, anchor)["comparison"]


def test_new_user_gets_no_weekly_comparison(api: WebApi) -> None:
    for days_ago in range(10):
        _add(api, days_ago, 60)

    assert _comparison(api, "week") is None


def test_week_compares_full_days_only(api: WebApi) -> None:
    for days_ago in range(1, 20):
        _add(api, days_ago, 60 if days_ago <= 6 else 30)
    _add(api, 0, 500)  # unfinished today must not count

    assert _comparison(api, "week") == {
        "comparedDays": 6,
        "currentProductiveMin": 360,
        "previousProductiveMin": 180,
    }


def test_no_comparison_when_recorded_days_differ_too_much(api: WebApi) -> None:
    for days_ago in [*range(1, 7), 8, 20]:
        _add(api, days_ago, 60)

    assert _comparison(api, "week") is None


def test_today_is_never_compared_with_yesterday(api: WebApi) -> None:
    for days_ago in range(5):
        _add(api, days_ago, 60)

    assert _comparison(api, "day") is None


def test_past_day_is_compared_with_the_day_before(api: WebApi) -> None:
    for days_ago in range(1, 5):
        _add(api, days_ago, days_ago * 10)

    assert _comparison(api, "day", days_ago=1) == {
        "comparedDays": 1,
        "currentProductiveMin": 10,
        "previousProductiveMin": 20,
    }
