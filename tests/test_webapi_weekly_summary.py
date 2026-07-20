from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from time_manager.storage import WeeklyProgress
from time_manager.webapi import WebApi


class FakeNotifier:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def send(self, title: str, body: str) -> None:
        self.messages.append((title, body))


def _with_progress(api: WebApi, productive_seconds: int, previous_productive_seconds: int) -> None:
    api.store.weekly_progress = lambda *a, **k: WeeklyProgress(  # type: ignore[method-assign]
        productive_seconds=productive_seconds,
        previous_productive_seconds=previous_productive_seconds,
        achieved_days=0,
        weekly_goal_minutes=api.settings.weekly_goal_minutes,
    )


class TestWeeklySummaryNotification:
    def test_skips_on_non_monday(self, api: WebApi) -> None:
        notifier = FakeNotifier()
        api.tracker.notifier = notifier
        api.settings.last_weekly_summary_notified = ""  # fixture construction already ran this with the real date
        _with_progress(api, 3600, 1800)

        with patch("time_manager.webapi.weekly_summary.date") as mock_date:
            mock_date.today.return_value = date(2026, 7, 21)  # Tuesday
            api._maybe_weekly_summary_notify()

        assert notifier.messages == []
        assert api.settings.last_weekly_summary_notified == ""

    def test_sends_and_persists_on_monday(self, api: WebApi) -> None:
        notifier = FakeNotifier()
        api.tracker.notifier = notifier
        api.settings.last_weekly_summary_notified = ""  # fixture construction already ran this with the real date
        _with_progress(api, 7200, 3600)  # 2h last week vs 1h the week before

        with patch("time_manager.webapi.weekly_summary.date") as mock_date:
            mock_date.today.return_value = date(2026, 7, 20)  # Monday
            api._maybe_weekly_summary_notify()

        assert len(notifier.messages) == 1
        title, body = notifier.messages[0]
        assert title == "지난주 생산성 요약"
        assert "2시간" in body
        assert "▲" in body
        assert api.settings.last_weekly_summary_notified != ""
        assert api.settings_store.load().last_weekly_summary_notified == api.settings.last_weekly_summary_notified

    def test_does_not_double_notify_same_week(self, api: WebApi) -> None:
        notifier = FakeNotifier()
        api.tracker.notifier = notifier
        api.settings.last_weekly_summary_notified = ""  # fixture construction already ran this with the real date
        _with_progress(api, 7200, 3600)

        with patch("time_manager.webapi.weekly_summary.date") as mock_date:
            mock_date.today.return_value = date(2026, 7, 20)  # Monday
            api._maybe_weekly_summary_notify()
            api._maybe_weekly_summary_notify()

        assert len(notifier.messages) == 1

    def test_declining_trend_uses_down_arrow(self, api: WebApi) -> None:
        notifier = FakeNotifier()
        api.tracker.notifier = notifier
        api.settings.last_weekly_summary_notified = ""  # fixture construction already ran this with the real date
        _with_progress(api, 1800, 3600)  # productivity dropped

        with patch("time_manager.webapi.weekly_summary.date") as mock_date:
            mock_date.today.return_value = date(2026, 7, 20)
            api._maybe_weekly_summary_notify()

        body = notifier.messages[0][1]
        assert "▼" in body

    def test_no_notifier_send_does_not_crash(self, api: WebApi) -> None:
        api.tracker.notifier = SimpleNamespace()  # no .send attribute
        _with_progress(api, 3600, 1800)

        with patch("time_manager.webapi.weekly_summary.date") as mock_date:
            mock_date.today.return_value = date(2026, 7, 20)
            api._maybe_weekly_summary_notify()  # must not raise

        assert api.settings.last_weekly_summary_notified != ""
