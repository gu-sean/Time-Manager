import logging
import os
import sys
import threading
import time as _time
from dataclasses import dataclass, field
from datetime import date
from typing import Callable
from urllib.parse import urlparse, urlunparse

_log = logging.getLogger(__name__)
# 이 횟수만큼 연속 실패하면 기록이 안 되고 있음을 사용자에게 알림
_FAILURES_TO_REPORT = 3
# 이 앱의 다른 인스턴스 (실행 중인 자신은 프로세스 id 로 식별)
_OWN_EXECUTABLES = frozenset({"timemanager.exe", "timemanagerweb.exe"})

from time_manager.models import ActiveTarget, Category, ClassifiedActivity
from time_manager.notifications import Notifier, default_notifier
from time_manager.platforms import PlatformMonitor
from time_manager.rules import RuleClassifier, _domain_from_url
from time_manager.storage import ActivityStore


def default_monitor() -> PlatformMonitor:
    if sys.platform.startswith("win"):
        from time_manager.platforms.windows import WindowsMonitor

        return WindowsMonitor()
    raise RuntimeError(f"Windows only. Unsupported platform: {sys.platform}")


@dataclass
class ActivityTracker:
    store: ActivityStore
    classifier: RuleClassifier
    poll_seconds: int = 5
    idle_threshold_seconds: int = 5 * 60
    unproductive_alert_seconds: int = 30 * 60
    productive_alert_seconds: int = 60 * 60
    work_end_hour: int = 18
    store_domain_only: bool = False
    store_window_titles: bool = True
    monitor: PlatformMonitor = field(default_factory=default_monitor)
    notifier: Notifier = field(default_factory=default_notifier)
    on_activity: Callable[[ClassifiedActivity], None] | None = None
    on_status: Callable[[str], None] | None = None
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    _paused_event: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)
    _streak_category: Category | None = field(default=None, init=False)
    _streak_seconds: int = field(default=0, init=False)
    _last_activity: ClassifiedActivity | None = field(default=None, init=False)
    _streak_alert_sent: bool = field(default=False, init=False)
    _idle_status_sent: bool = field(default=False, init=False)
    _last_monitor_status: str = field(default="", init=False)
    _end_of_day_notified_date: str = field(default="", init=False)
    _work_end_armed: bool = field(default=False, init=False)
    _failures_in_a_row: int = field(default=0, init=False)
    _last_failure: str = field(default="", init=False)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._arm_end_of_day_notify()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="activity-tracker", daemon=True)
        self._thread.start()
        self._emit_status("실시간 기록 중")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=self.poll_seconds + 1)
        self._emit_status("기록을 중지했습니다.")

    def pause(self) -> None:
        self._paused_event.set()
        self._reset_streak()
        self._emit_status("기록을 일시정지했습니다.")

    def resume(self) -> None:
        self._paused_event.clear()
        self._emit_status("실시간 기록 중")

    def toggle_pause(self) -> None:
        if self.is_paused:
            self.resume()
        else:
            self.pause()

    @property
    def is_paused(self) -> bool:
        return self._paused_event.is_set()

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._stop_event.is_set())

    def _run(self) -> None:
        while not self._stop_event.is_set():
            # 한 번의 실패(DB 잠김, 디스크 부족, 알림 오류)로 스레드가 끝나면 안 됨
            # (알림 없이 기록이 영구 중단됨)
            try:
                self._tick()
            except Exception as exc:
                self._failures_in_a_row += 1
                self._last_failure = type(exc).__name__
                if self._failures_in_a_row in (1, _FAILURES_TO_REPORT) or self._failures_in_a_row % 100 == 0:
                    _log.exception("tracking failed (%d in a row)", self._failures_in_a_row)
            self._stop_event.wait(self.poll_seconds)

    @property
    def problem(self) -> str:
        """지금 활동이 기록되지 않는 이유. 정상이면 ""."""
        if self._failures_in_a_row < _FAILURES_TO_REPORT or self.is_paused:
            return ""
        return (
            f"활동을 기록하지 못하고 있어요 ({self._last_failure}). 디스크 공간과 데이터 폴더 권한을 확인하세요. "
            "계속 다시 시도합니다."
        )

    def _tick(self) -> None:
        if self._paused_event.is_set():
            return

        idle_seconds = self._safe_idle_seconds()
        if idle_seconds >= self.idle_threshold_seconds:
            if not self._idle_status_sent:
                self._emit_status(f"자리 비움 감지({idle_seconds // 60}분). 기록을 잠시 멈췄습니다.")
                self._idle_status_sent = True
            self._reset_streak()
            return

        if self._idle_status_sent:
            self._emit_status("활동이 다시 감지되었습니다. 실시간 기록 중")
            self._idle_status_sent = False

        target = self._safe_active_target()
        if target is None or self._should_skip_target(target):
            return
        activity = self.classifier.classify(target)
        stored_activity = self._privacy_filtered_activity(activity)
        self.store.record(stored_activity, self.poll_seconds)
        self._failures_in_a_row = 0
        self._last_activity = activity
        self._update_streak(activity)
        self._maybe_end_of_day_notify()
        if self.on_activity:
            self.on_activity(stored_activity)
        self._emit_monitor_status()

    def _safe_active_target(self) -> ActiveTarget | None:
        try:
            return self.monitor.get_active_target()
        except Exception as exc:  # 지어낸 "Unknown" 활동을 기록하면 통계가 왜곡됨
            _log.warning("get_active_target failed: %s", exc)
            return None

    def current_streak(self) -> tuple[Category | None, int]:
        return self._streak_category, self._streak_seconds

    def current_activity(self) -> ClassifiedActivity | None:
        if not self.is_running or self.is_paused:
            return None
        return self._last_activity

    def _safe_idle_seconds(self) -> int:
        try:
            return self.monitor.idle_seconds()
        except Exception as exc:
            _log.warning("idle_seconds failed: %s", exc)
            return 0

    def _update_streak(self, activity: ClassifiedActivity) -> None:
        category = activity.category
        if category != self._streak_category:
            self._streak_category = category
            self._streak_seconds = 0
            self._streak_alert_sent = False

        self._streak_seconds += self.poll_seconds
        if self._streak_alert_sent:
            return

        if category == Category.UNPRODUCTIVE and self._streak_seconds >= self.unproductive_alert_seconds:
            minutes = self.unproductive_alert_seconds // 60
            self.notifier.send(
                "집중할 시간입니다",
                f"비생산적인 활동이 {minutes}분 동안 이어졌습니다. 이제 다시 몰입해볼까요?",
            )
            self._streak_alert_sent = True
        elif category == Category.PRODUCTIVE and self._streak_seconds >= self.productive_alert_seconds:
            minutes = self.productive_alert_seconds // 60
            hours, mins = divmod(minutes, 60)
            label = f"{hours}시간" if mins == 0 else f"{hours}시간 {mins}분" if hours else f"{mins}분"
            self.notifier.send(
                "멋진 집중입니다",
                f"생산적인 시간이 {label} 동안 이어졌습니다. 잠깐 스트레칭하고 다시 가도 좋습니다.",
            )
            self._streak_alert_sent = True

    def _arm_end_of_day_notify(self) -> None:
        # 하루 마무리 알림은 work_end_hour 전부터 실행하다 그 시각을 지날 때만 허용
        # (그 시각 이후에 앱을 켠 것만으로는 알리지 않음)
        self._work_end_armed = _time.localtime().tm_hour < self.work_end_hour

    def _maybe_end_of_day_notify(self) -> None:
        if not self._work_end_armed:
            return
        today = date.today().isoformat()
        if self._end_of_day_notified_date == today:
            return
        if _time.localtime().tm_hour < self.work_end_hour:
            return
        totals = {row.category: row.seconds for row in self.store.summary_for_day(date.today())}
        productive = totals.get(Category.PRODUCTIVE, 0)
        unproductive = totals.get(Category.UNPRODUCTIVE, 0)
        focused = productive + unproductive
        score = round((productive / focused) * 100) if focused > 0 else 0
        prod_min = productive // 60
        body = f"생산 시간 {prod_min // 60}시간 {prod_min % 60}분 · 생산성 점수 {score}점"
        self.notifier.send("오늘 하루 수고했어요", body)
        self._end_of_day_notified_date = today

    def reset_end_of_day_state(self) -> None:
        self._end_of_day_notified_date = ""
        self._arm_end_of_day_notify()

    def _reset_streak(self) -> None:
        self._streak_category = None
        self._streak_seconds = 0
        self._streak_alert_sent = False
        self._last_activity = None

    def _emit_status(self, status: str) -> None:
        if self.on_status:
            self.on_status(status)

    def _emit_monitor_status(self) -> None:
        status = str(getattr(self.monitor, "last_status", "") or "")
        if status and status != self._last_monitor_status:
            self._emit_status(status)
        self._last_monitor_status = status

    def set_privacy_options(self, store_domain_only: bool, store_window_titles: bool) -> None:
        self.store_domain_only = store_domain_only
        self.store_window_titles = store_window_titles

    def _privacy_filtered_activity(self, activity: ClassifiedActivity) -> ClassifiedActivity:
        target = activity.target
        url = _domain_url(target.url) if self.store_domain_only and target.url else target.url
        title = target.window_title if self.store_window_titles else ""
        return ClassifiedActivity(
            target=ActiveTarget(app_name=target.app_name, window_title=title, url=url),
            category=activity.category,
            reason=activity.reason,
        )

    def _should_skip_target(self, target: ActiveTarget) -> bool:
        # 이 앱을 보는 시간은 기록하지 않음
        app_name = target.app_name.lower()
        if target.process_id == os.getpid() or app_name in _OWN_EXECUTABLES:
            return True
        excluded = {item.lower() for item in self.classifier.excluded_apps}
        return app_name in excluded

def _domain_url(url: str) -> str:
    domain = _domain_from_url(url)
    if domain is None:
        return url
    try:
        scheme = urlparse(url if "://" in url else f"https://{url}").scheme or "https"
    except ValueError:
        scheme = "https"
    return urlunparse((scheme, domain, "", "", "", ""))
