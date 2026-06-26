from __future__ import annotations

import platform
from typing import Any

from time_manager import __version__
from time_manager.diagnostics import run_diagnostics as _run_diagnostics
from time_manager.rules import PROFILE_PRESETS, apply_profile_preset
from time_manager.startup import disable as _startup_disable
from time_manager.startup import enable as _startup_enable
from time_manager.startup import is_enabled as _startup_is_enabled

from ._shared import WebApiBase


class SettingsMixin(WebApiBase):
    PROFILE_LABELS = {
        "": "선택 안 함",
        "developer": "개발자",
        "student": "학생",
        "office": "사무직",
        "creator": "크리에이터",
        "researcher": "연구자",
        "designer": "디자이너",
        "marketer": "마케터",
        "finance": "재무/투자",
        "manager": "매니저",
    }

    def get_settings(self) -> dict[str, Any]:
        profile = self.settings.onboarding_profile
        preset_items = [
            {"key": key, "value": value}
            for key, values in PROFILE_PRESETS.get(profile, {}).items()
            for value in values
        ]
        return {
            "dailyGoalMinutes": self.settings.daily_goal_minutes,
            "startupEnabled": _startup_is_enabled(),
            "weeklyGoalMinutes": self.settings.weekly_goal_minutes,
            "unproductiveLimitMinutes": self.settings.unproductive_limit_minutes,
            "workStartHour": self.settings.work_start_hour,
            "workEndHour": self.settings.work_end_hour,
            "profile": profile,
            "profileOptions": [{"value": k, "label": v} for k, v in self.PROFILE_LABELS.items()],
            "presetItems": preset_items,
            "excludeSelf": self.settings.exclude_self_app,
            "notificationsEnabled": self.settings.notifications_enabled,
            "autoBackupEnabled": self.settings.auto_backup_enabled,
            "storeDomainOnly": self.settings.store_domain_only,
            "storeWindowTitles": self.settings.store_window_titles,
            "retentionDays": self.settings.retention_days,
            "theme": self.settings.theme,
            "notificationStatus": self._notification_status_text(),
            "diagnosticInfo": self._diagnostic_info_text(),
            "diagnosticResults": "",
        }

    def _notification_status_text(self) -> str:
        if not self.settings.notifications_enabled:
            return "앱 알림이 꺼져 있습니다."
        notifier = getattr(self.tracker, "notifier", None)
        if notifier and hasattr(notifier, "status"):
            status = notifier.status()
            message = status.get("message") if isinstance(status, dict) else None
            if message:
                return str(message)
        return "앱 알림이 켜져 있습니다. 표시되지 않으면 Windows 알림 설정을 확인하세요."

    def _diagnostic_info_text(self) -> str:
        settings_path = self.settings_store.path if self.settings_store else "없음"
        environment = f"v{__version__} · {platform.system()} {platform.release()}"
        log_path = self.store.db_path.parent / "time-manager.log"
        return "\n".join(
            (
                f"환경: {environment}",
                f"데이터: {self.store.db_path}",
                f"규칙: {self.rules_path}",
                f"설정: {settings_path}",
                f"로그: {log_path}",
            )
        )

    def save_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            daily_goal = int(payload["dailyGoalMinutes"])
            weekly_goal = int(payload["weeklyGoalMinutes"])
            unproductive_limit = int(payload["unproductiveLimitMinutes"])
            start_hour = int(payload["workStartHour"])
            end_hour = int(payload["workEndHour"])
            retention_days = int(payload["retentionDays"])
        except (ValueError, TypeError, KeyError):
            return {**self.get_settings(), "error": "값을 숫자로 입력해주세요."}
        if min(daily_goal, weekly_goal, unproductive_limit) < 1:
            return {**self.get_settings(), "error": "목표와 상한은 1분 이상이어야 합니다."}
        if weekly_goal < daily_goal:
            return {**self.get_settings(), "error": "주간 생산 목표는 일간 목표 이상으로 설정해주세요."}
        if not 0 <= start_hour <= 23 or not 1 <= end_hour <= 24 or start_hour >= end_hour:
            return {**self.get_settings(), "error": "근무 시간을 0~24 사이로, 종료가 시작보다 늦게 입력해주세요."}
        if retention_days < 0:
            return {**self.get_settings(), "error": "데이터 보존 기간은 0 이상이어야 합니다."}

        self.settings.daily_goal_minutes = daily_goal
        self.settings.weekly_goal_minutes = weekly_goal
        self.settings.unproductive_limit_minutes = unproductive_limit
        self.settings.work_start_hour = start_hour
        self.settings.work_end_hour = end_hour
        self.settings.retention_days = retention_days
        self.settings.store_domain_only = bool(payload.get("storeDomainOnly", self.settings.store_domain_only))
        self.settings.store_window_titles = bool(payload.get("storeWindowTitles", self.settings.store_window_titles))
        theme = str(payload.get("theme", self.settings.theme))
        self.settings.theme = theme if theme in {"light", "dark"} else self.settings.theme
        self.settings_store.save(self.settings)
        self.tracker.set_privacy_options(self.settings.store_domain_only, self.settings.store_window_titles)
        self.tracker.unproductive_alert_seconds = self.settings.unproductive_limit_minutes * 60
        if self.tracker.work_end_hour != self.settings.work_end_hour:
            self.tracker.work_end_hour = self.settings.work_end_hour
            self.tracker.reset_end_of_day_state()
        return self.get_settings()

    def set_theme(self, theme: str) -> dict[str, Any]:
        self.settings.theme = theme if theme in {"light", "dark"} else "light"
        self.settings_store.save(self.settings)
        return self.get_settings()

    def toggle_exclude_self(self, enabled: bool) -> dict[str, Any]:
        self.settings.exclude_self_app = bool(enabled)
        self.tracker.set_exclude_self_app(self.settings.exclude_self_app)
        self.settings_store.save(self.settings)
        return self.get_settings()

    def toggle_startup(self, enabled: bool) -> dict[str, Any]:
        try:
            if enabled:
                _startup_enable()
            else:
                _startup_disable()
        except Exception as exc:
            return {**self.get_settings(), "error": f"자동 시작 설정 실패: {exc}"}
        return self.get_settings()

    def toggle_auto_backup(self, enabled: bool) -> dict[str, Any]:
        self.settings.auto_backup_enabled = bool(enabled)
        self.settings_store.save(self.settings)
        if self.settings.auto_backup_enabled:
            self._maybe_auto_backup()
        return self.get_settings()

    def set_profile(self, profile: str) -> dict[str, Any]:
        self.settings.onboarding_profile = profile
        self.settings_store.save(self.settings)
        return self.get_settings()

    def apply_preset(self) -> dict[str, Any]:
        if self.settings.onboarding_profile:
            self.tracker.classifier = apply_profile_preset(self.rules_path, self.settings.onboarding_profile)
        return self.get_settings()

    def export_logs(self) -> dict[str, str]:
        import shutil
        from datetime import datetime
        from pathlib import Path

        log_path = self.store.db_path.parent / "time-manager.log"
        if not log_path.exists():
            return {"message": "로그 파일이 없습니다."}
        desktop = Path.home() / "Desktop"
        if not desktop.exists():
            desktop = Path.home() / "Documents"
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = desktop / f"time-manager-log-{stamp}.txt"
        try:
            shutil.copy2(log_path, dest)
            return {"message": f"로그를 저장했습니다: {dest.name}"}
        except OSError as exc:
            return {"message": f"로그 내보내기 실패: {exc}"}

    def check_update(self) -> dict[str, Any]:
        from time_manager.updater import check_for_update
        return check_for_update()

    def run_diagnostics(self) -> dict[str, Any]:
        settings_path = self.settings_store.path if self.settings_store else self.store.db_path.parent / "settings.json"
        results = _run_diagnostics(
            data_dir=self.store.db_path.parent,
            db_path=self.store.db_path,
            rules_path=self.rules_path,
            settings_path=settings_path,
            log_path=self.store.db_path.parent / "time-manager.log",
        )
        lines = []
        for result in results:
            lines.append(f"[{result.status.value.upper()}] {result.name}: {result.message}")
            lines.append(f"    {result.path}")
        return {**self.get_settings(), "diagnosticResults": "\n".join(lines) if lines else "문제가 없습니다."}
