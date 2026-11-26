from __future__ import annotations

import logging
from pathlib import Path

from time_manager.settings import SettingsStore
from time_manager.storage import ActivityStore
from time_manager.tracker import ActivityTracker

from .ai import AIMixin
from .ask import AskMixin
from .backup import BackupMixin
from .dashboard import DashboardMixin
from .inbox import InboxMixin
from .presets import PresetMixin
from .report import ReportMixin
from .review import ReviewMixin
from .rules import RulesMixin
from .settings import SettingsMixin
from .weekly_summary import WeeklySummaryMixin

__all__ = ["WebApi"]

_log = logging.getLogger(__name__)


class WebApi(
    DashboardMixin,
    InboxMixin,
    ReviewMixin,
    RulesMixin,
    ReportMixin,
    SettingsMixin,
    BackupMixin,
    WeeklySummaryMixin,
    AIMixin,
    AskMixin,
    PresetMixin,
):
    def __init__(
        self,
        *,
        store: ActivityStore,
        tracker: ActivityTracker,
        settings_store: SettingsStore,
        rules_path: Path,
    ) -> None:
        self.store = store
        self.tracker = tracker
        self.settings_store = settings_store
        self.settings = settings_store.load()
        self.rules_path = rules_path
        # 트레이가 있으면 창을 닫는 대신 숨기므로, 앱을 끝내는 방법을 창 쪽에서 지정
        self._quit_handler = None
        self._run_startup_tasks()
        tracker.on_new_day = self.run_daily_tasks

    def _run_startup_tasks(self) -> None:
        self._try(self._maybe_auto_backup)
        self._try(self._maybe_weekly_summary_notify)

    def run_daily_tasks(self) -> None:
        """날짜가 바뀔 때: 앱을 켜 둔 채로도 보존 기간·자동 백업·주간 요약을 처리."""
        self._try(lambda: self.store.purge_older_than(self.settings.retention_days))
        self._run_startup_tasks()

    @staticmethod
    def _try(task) -> None:
        try:
            task()
        except Exception:
            _log.exception("scheduled task failed")

    def _quit_app(self) -> None:
        if self._quit_handler:
            self._quit_handler()
            return
        import webview

        if webview.windows:
            webview.windows[0].destroy()
