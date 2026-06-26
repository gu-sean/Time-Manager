from __future__ import annotations

from pathlib import Path

from time_manager.settings import SettingsStore
from time_manager.storage import ActivityStore
from time_manager.tracker import ActivityTracker

from .backup import BackupMixin
from .dashboard import DashboardMixin
from .inbox import InboxMixin
from .report import ReportMixin
from .review import ReviewMixin
from .rules import RulesMixin
from .settings import SettingsMixin

__all__ = ["WebApi"]


class WebApi(DashboardMixin, InboxMixin, ReviewMixin, RulesMixin, ReportMixin, SettingsMixin, BackupMixin):
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
        try:
            self._maybe_auto_backup()
        except Exception:
            pass
