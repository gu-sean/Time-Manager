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
# 연속 사용 알림: 이 시간 이하로 다른 분류를 본 것은 흐름이 이어진 것으로 봄
_STREAK_GRACE_SECONDS = 60
# 영상·회의 확인
_MEDIA_CHECK_AFTER_SECONDS = 30   # 입력이 이만큼 없을 때부터 확인
_MEDIA_HOLD_SECONDS = 2 * 60      # 말이 끊기거나 장면이 조용한 동안은 재생 중으로 봄
_MEDIA_LIMIT_SECONDS = 3 * 3600   # 입력이 이보다 오래 없으면 재생 중이어도 자리 비움
# 잠금·로그인 화면: 사용 시간이 아님
_LOCK_SCREEN_APPS = frozenset({"lockapp.exe", "logonui.exe"})
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
    record_media: bool = True
    # 자리 비움으로 판단하면, 마지막 입력 뒤에 기록한 시간을 뺌
    trim_idle_time: bool = False
    on_new_day: Callable[[], None] | None = None
    # 0 이면 목표 알림 없음
    daily_goal_seconds: int = 0
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
    # 흐름과 다른 분류가 이어진 시간, 그중 가장 최근 분류와 그 시간
    _away_seconds: int = field(default=0, init=False)
    _next_category: Category | None = field(default=None, init=False)
    _next_seconds: int = field(default=0, init=False)
    _idle_status_sent: bool = field(default=False, init=False)
    _last_monitor_status: str = field(default="", init=False)
    _end_of_day_notified_date: str = field(default="", init=False)
    _work_end_armed: bool = field(default=False, init=False)
    _goal_notified_day: date | None = field(default=None, init=False)
    _current_day: date | None = field(default=None, init=False)
    _media_app: str = field(default="", init=False)
    _quiet_seconds: int = field(default=0, init=False)
    _media_check_failed: bool = field(default=False, init=False)
    # 마지막 입력 뒤에 기록한 시간
    _unattended_seconds: int = field(default=0, init=False)
    _failures_in_a_row: int = field(default=0, init=False)
    _last_failure: str = field(default="", init=False)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._arm_end_of_day_notify()
        self._current_day = date.today()
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
        self._unattended_seconds = 0
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
        target, media = self._check_media(idle_seconds)
        if idle_seconds >= self.idle_threshold_seconds and not media:
            if not self._idle_status_sent:
                self._emit_status(f"자리 비움 감지({idle_seconds // 60}분). 기록을 잠시 멈췄습니다.")
                self._idle_status_sent = True
                self._trim_unattended()
            self._unattended_seconds = 0
            self._reset_streak()
            return

        if self._idle_status_sent:
            self._emit_status("활동이 다시 감지되었습니다. 실시간 기록 중")
            self._idle_status_sent = False

        target = target or self._safe_active_target()
        if target is None or self._should_skip_target(target):
            return
        activity = self.classifier.classify(target)
        stored_activity = self._privacy_filtered_activity(activity)
        self.store.record(stored_activity, self.poll_seconds)
        self._failures_in_a_row = 0
        # 입력도 재생도 없이 지난 시간만 셈
        if media or idle_seconds < self.poll_seconds:
            self._unattended_seconds = 0
        else:
            self._unattended_seconds += self.poll_seconds
        self._last_activity = activity
        self._update_streak(activity)
        self._maybe_start_new_day()
        self._maybe_goal_notify(activity)
        self._maybe_end_of_day_notify()
        if self.on_activity:
            self.on_activity(stored_activity)
        self._emit_monitor_status()

    def _check_media(self, idle_seconds: int) -> tuple[ActiveTarget | None, bool]:
        """(확인할 때 읽은 대상, 입력 없이도 사용 중인지)."""
        if not self.record_media or not _MEDIA_CHECK_AFTER_SECONDS <= idle_seconds < _MEDIA_LIMIT_SECONDS:
            self._media_app = ""
            return None, False
        target = self._safe_active_target()
        if target is None or self._should_skip_target(target):
            self._media_app = ""
            return target, False
        try:
            playing = self.monitor.media_playing(target.app_name)
        except Exception as exc:
            if not self._media_check_failed:
                self._media_check_failed = True
                _log.warning("media check failed: %s", type(exc).__name__)
            playing = False
        if playing:
            self._media_app, self._quiet_seconds = target.app_name, 0
        elif self._media_app == target.app_name:
            self._quiet_seconds += self.poll_seconds
        else:
            self._media_app = ""
        return target, self._media_app == target.app_name and self._quiet_seconds <= _MEDIA_HOLD_SECONDS

    def _trim_unattended(self) -> None:
        if self.trim_idle_time and self._unattended_seconds:
            self.store.remove_recent_seconds(self._unattended_seconds)

    def _maybe_start_new_day(self) -> None:
        """날짜가 바뀐 뒤 처음 기록할 때: 앱을 켜 둔 채로도 하루 단위 작업을 실행."""
        today = date.today()
        if self._current_day == today:
            return
        first = self._current_day is None
        self._current_day = today
        if first:
            return
        self._arm_end_of_day_notify()
        if self.on_new_day:
            try:
                self.on_new_day()
            except Exception:  # 정리 작업의 실패가 기록 실패로 보이지 않게 함
                _log.exception("daily tasks failed")

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
        if self._streak_category is None or category == self._streak_category:
            self._streak_category = category
            self._streak_seconds += self.poll_seconds
            self._clear_interruption()
        else:
            # 잠깐 다른 창을 본 것은 흐름을 끊지 않음. 길어지면 새 흐름으로 바꿈
            self._away_seconds += self.poll_seconds
            if category != self._next_category:
                self._next_category = category
                self._next_seconds = 0
            self._next_seconds += self.poll_seconds
            if self._away_seconds <= _STREAK_GRACE_SECONDS:
                return
            self._streak_category = category
            self._streak_seconds = self._next_seconds
            self._streak_alert_sent = False
            self._clear_interruption()

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

    def _maybe_goal_notify(self, activity: ClassifiedActivity) -> None:
        """오늘 생산 시간이 방금 목표를 넘었을 때 한 번 알림.

        - 이번 기록으로 넘은 경우만: 앱을 다시 켜도 같은 알림이 반복되지 않음
        """
        goal = self.daily_goal_seconds
        today = date.today()
        if goal <= 0 or activity.category != Category.PRODUCTIVE or self._goal_notified_day == today:
            return
        total = sum(row.seconds for row in self.store.summary_for_day(today) if row.category == Category.PRODUCTIVE)
        if not total - self.poll_seconds < goal <= total:
            return
        hours, minutes = divmod(goal // 60, 60)
        label = " ".join(part for part in (f"{hours}시간" if hours else "", f"{minutes}분" if minutes else "") if part)
        self.notifier.send("오늘 목표를 달성했어요", f"생산 시간 {label or '1분 미만'}을 채웠습니다.")
        self._goal_notified_day = today

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
        self._clear_interruption()

    def _clear_interruption(self) -> None:
        self._away_seconds = 0
        self._next_category = None
        self._next_seconds = 0

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
        # 앞에 보이는 창이 없으면 이름도 제목도 없음 (잠금 전환 중 등)
        if app_name in _LOCK_SCREEN_APPS or (app_name == "unknown" and not target.window_title):
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
