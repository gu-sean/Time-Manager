import time
import unittest
from datetime import date
from unittest.mock import patch

from time_manager.models import ActiveTarget, Category, ClassifiedActivity
from time_manager.storage import SummaryRow
from time_manager.rules import _domain_from_url
from time_manager.tracker import ActivityTracker


class FakeStore:
    def __init__(self, productive_seconds: int = 0) -> None:
        self.records: list[tuple[ClassifiedActivity, int]] = []
        self._productive_seconds = productive_seconds

    def record(self, activity: ClassifiedActivity, seconds: int) -> None:
        self.records.append((activity, seconds))

    def summary_for_day(self, day: date) -> list[SummaryRow]:
        return [SummaryRow(Category.PRODUCTIVE, self._productive_seconds)] if self._productive_seconds else []


class FakeClassifier:
    def __init__(self, category: Category) -> None:
        self.category = category
        self.excluded_apps: tuple[str, ...] = ()

    def classify(self, target: ActiveTarget) -> ClassifiedActivity:
        return ClassifiedActivity(target=target, category=self.category, reason="test")


class FakeMonitor:
    def __init__(self, idle_seconds: int = 0) -> None:
        self._idle_seconds = idle_seconds

    def get_active_target(self) -> ActiveTarget:
        return ActiveTarget(app_name="chrome.exe", window_title="YouTube", url="https://youtube.com")

    def idle_seconds(self) -> int:
        return self._idle_seconds


class StatusMonitor(FakeMonitor):
    last_status = "Browser URL unavailable: Not authorized"


class FakeNotifier:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def send(self, title: str, message: str) -> None:
        self.messages.append((title, message))


class ActivityTrackerTests(unittest.TestCase):
    def test_unproductive_alert_only_fires_once_per_streak(self) -> None:
        notifier = FakeNotifier()
        tracker = ActivityTracker(
            store=FakeStore(),
            classifier=FakeClassifier(Category.UNPRODUCTIVE),
            monitor=FakeMonitor(),
            notifier=notifier,
            poll_seconds=5,
            unproductive_alert_seconds=10,
        )
        activity = ClassifiedActivity(ActiveTarget("chrome.exe", "YouTube", "https://youtube.com"), Category.UNPRODUCTIVE, "test")

        tracker._update_streak(activity)
        tracker._update_streak(activity)
        tracker._update_streak(activity)

        self.assertEqual(1, len(notifier.messages))
        self.assertEqual("집중할 시간입니다", notifier.messages[0][0])

    def test_productive_alert_uses_korean_message(self) -> None:
        notifier = FakeNotifier()
        tracker = ActivityTracker(
            store=FakeStore(),
            classifier=FakeClassifier(Category.PRODUCTIVE),
            monitor=FakeMonitor(),
            notifier=notifier,
            poll_seconds=5,
            productive_alert_seconds=10,
        )
        activity = ClassifiedActivity(ActiveTarget("Code.exe", "main.py", None), Category.PRODUCTIVE, "test")

        tracker._update_streak(activity)
        tracker._update_streak(activity)

        self.assertEqual("멋진 집중입니다", notifier.messages[0][0])

    def test_idle_state_skips_recording(self) -> None:
        store = FakeStore()
        tracker = ActivityTracker(
            store=store,
            classifier=FakeClassifier(Category.UNPRODUCTIVE),
            monitor=FakeMonitor(idle_seconds=999),
            notifier=FakeNotifier(),
            poll_seconds=0.01,
            idle_threshold_seconds=1,
        )

        tracker.start()
        time.sleep(0.03)
        tracker.stop()

        self.assertEqual([], store.records)

    def test_excluded_app_is_not_recorded(self) -> None:
        store = FakeStore()
        classifier = FakeClassifier(Category.NEUTRAL)
        classifier.excluded_apps = ("TimeManager.exe",)
        tracker = ActivityTracker(
            store=store,
            classifier=classifier,
            monitor=FakeMonitor(),
            notifier=FakeNotifier(),
        )

        self.assertTrue(tracker._should_skip_target(ActiveTarget("TimeManager.exe", "시간 관리 매니저", None)))

    def test_active_target_failure_does_not_crash_tracking(self) -> None:
        class ExplodingMonitor(FakeMonitor):
            def get_active_target(self) -> ActiveTarget:
                raise RuntimeError("foreground API failed")

        tracker = ActivityTracker(
            store=FakeStore(),
            classifier=FakeClassifier(Category.NEUTRAL),
            monitor=ExplodingMonitor(),
            notifier=FakeNotifier(),
        )

        target = tracker._safe_active_target()
        self.assertEqual("Unknown", target.app_name)
        self.assertIn("Monitor error", target.window_title)

    def test_idle_failure_falls_back_to_zero(self) -> None:
        class ExplodingMonitor(FakeMonitor):
            def idle_seconds(self) -> int:
                raise RuntimeError("idle API failed")

        tracker = ActivityTracker(
            store=FakeStore(),
            classifier=FakeClassifier(Category.NEUTRAL),
            monitor=ExplodingMonitor(),
            notifier=FakeNotifier(),
        )

        self.assertEqual(0, tracker._safe_idle_seconds())

    def test_tracker_has_no_focus_session_api(self) -> None:
        tracker = ActivityTracker(
            store=FakeStore(),
            classifier=FakeClassifier(Category.UNPRODUCTIVE),
            monitor=FakeMonitor(),
            notifier=FakeNotifier(),
        )

        self.assertFalse(hasattr(tracker, "set_focus_mode"))
        self.assertFalse(hasattr(tracker, "focus_mode_active"))
        self.assertFalse(hasattr(tracker, "set_focus_allowlist"))
        self.assertFalse(hasattr(tracker, "allow_focus_target_for_session"))
        self.assertFalse(hasattr(tracker, "focus_distraction_count"))

    def test_privacy_filter_stores_domain_only_and_hides_window_title(self) -> None:
        tracker = ActivityTracker(
            store=FakeStore(),
            classifier=FakeClassifier(Category.PRODUCTIVE),
            monitor=FakeMonitor(),
            notifier=FakeNotifier(),
            store_domain_only=True,
            store_window_titles=False,
        )
        activity = ClassifiedActivity(
            ActiveTarget("chrome.exe", "Private project - Google Chrome", "https://docs.python.org/3/library/pathlib.html"),
            Category.PRODUCTIVE,
            "productive site",
        )

        filtered = tracker._privacy_filtered_activity(activity)

        self.assertEqual("https://docs.python.org", filtered.target.url)
        self.assertEqual("", filtered.target.window_title)
        self.assertEqual(Category.PRODUCTIVE, filtered.category)

    def test_privacy_filter_keeps_invalid_url_unchanged(self) -> None:
        tracker = ActivityTracker(
            store=FakeStore(),
            classifier=FakeClassifier(Category.PRODUCTIVE),
            monitor=FakeMonitor(),
            notifier=FakeNotifier(),
            store_domain_only=True,
        )
        activity = ClassifiedActivity(
            ActiveTarget("HShow.exe", "Presentation", "http://[broken"),
            Category.PRODUCTIVE,
            "test",
        )

        filtered = tracker._privacy_filtered_activity(activity)

        self.assertEqual("http://[broken", filtered.target.url)

    def test_localhost_urls_are_supported_for_rules_and_privacy(self) -> None:
        self.assertEqual("localhost", _domain_from_url("http://localhost:3000/dashboard"))
        self.assertEqual("127.0.0.1", _domain_from_url("http://127.0.0.1:8000/docs"))

    def test_monitor_status_is_emitted_after_activity(self) -> None:
        statuses: list[str] = []
        tracker = ActivityTracker(
            store=FakeStore(),
            classifier=FakeClassifier(Category.PRODUCTIVE),
            monitor=StatusMonitor(),
            notifier=FakeNotifier(),
            on_status=statuses.append,
        )
        activity = ClassifiedActivity(ActiveTarget("chrome.exe", "Docs", "https://docs.python.org"), Category.PRODUCTIVE, "test")

        tracker._emit_monitor_status()

        self.assertEqual(["Browser URL unavailable: Not authorized"], statuses)


class EndOfDayNotificationTests(unittest.TestCase):
    def _tracker(self, work_end_hour: int = 18) -> tuple[ActivityTracker, FakeNotifier]:
        notifier = FakeNotifier()
        tracker = ActivityTracker(
            store=FakeStore(productive_seconds=5400),
            classifier=FakeClassifier(Category.PRODUCTIVE),
            monitor=FakeMonitor(),
            notifier=notifier,
            work_end_hour=work_end_hour,
        )
        return tracker, notifier

    def test_end_of_day_notification_fires_when_armed_and_hour_crossed(self) -> None:
        tracker, notifier = self._tracker(work_end_hour=18)
        with patch("time_manager.tracker._time") as mock_time:
            mock_time.localtime.return_value.tm_hour = 9
            tracker._arm_end_of_day_notify()  # session started before work_end_hour
            mock_time.localtime.return_value.tm_hour = 19
            tracker._maybe_end_of_day_notify()
        self.assertEqual(1, len(notifier.messages))
        self.assertEqual("오늘 하루 수고했어요", notifier.messages[0][0])

    def test_end_of_day_does_not_fire_when_app_launched_after_work_end_hour(self) -> None:
        # Regression test: launching the app for the first time after work_end_hour
        # has already passed must not immediately fire the summary notification.
        tracker, notifier = self._tracker(work_end_hour=18)
        with patch("time_manager.tracker._time") as mock_time:
            mock_time.localtime.return_value.tm_hour = 21
            tracker._arm_end_of_day_notify()
            tracker._maybe_end_of_day_notify()
        self.assertEqual(0, len(notifier.messages))

    def test_end_of_day_notification_fires_only_once_per_day(self) -> None:
        tracker, notifier = self._tracker(work_end_hour=18)
        with patch("time_manager.tracker._time") as mock_time:
            mock_time.localtime.return_value.tm_hour = 9
            tracker._arm_end_of_day_notify()
            mock_time.localtime.return_value.tm_hour = 19
            tracker._maybe_end_of_day_notify()
            tracker._maybe_end_of_day_notify()
        self.assertEqual(1, len(notifier.messages))

    def test_end_of_day_skipped_before_work_end_hour(self) -> None:
        tracker, notifier = self._tracker(work_end_hour=23)
        with patch("time_manager.tracker._time") as mock_time:
            mock_time.localtime.return_value.tm_hour = 10
            tracker._arm_end_of_day_notify()
            tracker._maybe_end_of_day_notify()
        self.assertEqual(0, len(notifier.messages))

    def test_end_of_day_resets_and_rearms_when_work_end_hour_changes(self) -> None:
        tracker, notifier = self._tracker(work_end_hour=18)
        with patch("time_manager.tracker._time") as mock_time:
            mock_time.localtime.return_value.tm_hour = 9
            tracker._arm_end_of_day_notify()
            mock_time.localtime.return_value.tm_hour = 19
            tracker._maybe_end_of_day_notify()
            self.assertEqual(1, len(notifier.messages))

            # User lowers work_end_hour mid-session; settings flow calls this.
            mock_time.localtime.return_value.tm_hour = 15
            tracker.work_end_hour = 20
            tracker.reset_end_of_day_state()
            mock_time.localtime.return_value.tm_hour = 21
            tracker._maybe_end_of_day_notify()
        self.assertEqual(2, len(notifier.messages))

    def test_end_of_day_body_contains_productive_time_and_score(self) -> None:
        tracker, notifier = self._tracker(work_end_hour=18)
        with patch("time_manager.tracker._time") as mock_time:
            mock_time.localtime.return_value.tm_hour = 9
            tracker._arm_end_of_day_notify()
            mock_time.localtime.return_value.tm_hour = 19
            tracker._maybe_end_of_day_notify()
        body = notifier.messages[0][1]
        self.assertIn("1시간", body)
        self.assertIn("점", body)


if __name__ == "__main__":
    unittest.main()
