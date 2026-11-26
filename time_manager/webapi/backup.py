from __future__ import annotations

import logging
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from time_manager import ai as _ai
from time_manager.rules import RuleClassifier
from time_manager.settings import AppSettings

from ._shared import WebApiBase, _clamp_day, _parse_day

_log = logging.getLogger(__name__)


class BackupMixin(WebApiBase):
    def _backup_manager(self):
        from time_manager.backup import BackupManager

        return BackupManager(
            activity_path=self.store.db_path,
            rules_path=self.rules_path,
            settings_path=self.settings_store.path,
            backup_dir=self.store.db_path.parent / "backups",
        )

    def _maybe_auto_backup(self) -> None:
        try:
            from time_manager.backup import should_auto_backup

            if not should_auto_backup(
                self.settings.auto_backup_enabled, self.settings.last_auto_backup, date.today()
            ):
                return
            self._backup_manager().auto_backup(date.today())
        except Exception:
            return
        self.settings.last_auto_backup = date.today().isoformat()
        self.settings_store.save(self.settings)

    def _save_dialog(self, filename: str, file_types: tuple[str, ...]) -> Path | None:
        import webview

        windows = webview.windows
        if not windows:
            return None
        output = windows[0].create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=filename,
            file_types=file_types,
        )
        if not output:
            return None
        return Path(output if isinstance(output, str) else output[0])

    def _open_dialog(self, file_types: tuple[str, ...]) -> Path | None:
        import webview

        windows = webview.windows
        if not windows:
            return None
        source = windows[0].create_file_dialog(webview.OPEN_DIALOG, file_types=file_types)
        if not source:
            return None
        entry = source[0] if isinstance(source, (list, tuple)) else source
        return Path(entry)

    def _csv_result(self, rows: int, *, single_day: bool = False) -> dict[str, Any]:
        if rows:
            return {"message": f"{rows}건의 기록을 CSV로 내보냈습니다."}
        label = "해당 날짜에" if single_day else "해당 기간에"
        return {"message": f"{label} 내보낼 기록이 없습니다."}

    @staticmethod
    def _write_failed(what: str, error: Exception) -> dict[str, Any]:
        _log.warning("%s export failed: %s", what, type(error).__name__)
        return {
            "message": f"{what}을 저장하지 못했습니다. 같은 파일이 다른 프로그램(예: Excel)에서 열려 있는지, "
            "저장할 폴더에 쓸 수 있는지, 디스크 공간이 남았는지 확인하세요."
        }

    def _export_csv_file(self, start_day: date, end_day: date, filename: str, *, single_day: bool = False) -> dict[str, Any]:
        path = self._save_dialog(filename, ("CSV 파일 (*.csv)",))
        if path is None:
            return {"message": ""}
        try:
            rows = self.store.export_csv_for_period(start_day, end_day, path)
        except (OSError, sqlite3.Error) as exc:
            return self._write_failed("CSV 파일", exc)
        return self._csv_result(rows, single_day=single_day)

    def export_csv(self, day_iso: str | None = None) -> dict[str, Any]:
        target_day = _parse_day(day_iso)
        return self._export_csv_file(
            target_day, target_day, f"activity-{target_day.isoformat()}.csv", single_day=True
        )

    def export_csv_period(self, period: str) -> dict[str, Any]:
        from time_manager.formatting import _report_period_for_label

        today = date.today()
        start_day, end_day = _report_period_for_label(period, today)
        return self._export_csv_file(start_day, end_day, f"activity-{start_day.isoformat()}-{end_day.isoformat()}.csv")

    def export_csv_range(self, start_iso: str, end_iso: str) -> dict[str, Any]:
        try:
            start_day = _clamp_day(date.fromisoformat(start_iso))
            end_day = _clamp_day(date.fromisoformat(end_iso))
        except (TypeError, ValueError):
            return {"message": "날짜 형식이 올바르지 않습니다."}
        if start_day > end_day:
            return {"message": "시작일이 종료일보다 늦을 수 없습니다."}
        return self._export_csv_file(start_day, end_day, f"activity-{start_day.isoformat()}-{end_day.isoformat()}.csv")

    def export_backup(self) -> dict[str, Any]:
        manager = self._backup_manager()
        path = self._save_dialog(
            f"time-manager-{date.today().isoformat()}.tmbak", ("Time Manager 백업 (*.tmbak)",)
        )
        if path is None:
            return {"message": ""}
        try:
            manager.export(path)
        except (OSError, sqlite3.Error) as exc:
            return self._write_failed("백업 파일", exc)
        return {"message": f"백업을 저장했습니다: {path}"}

    def restore_backup(self) -> dict[str, Any]:
        manager = self._backup_manager()
        path = self._open_dialog(("Time Manager 백업 (*.tmbak)",))
        if path is None:
            return {"message": ""}
        previous = self.settings
        try:
            manager.restore(path)
        except ValueError as exc:
            return {"message": f"백업을 복원하지 못했습니다. {exc}"}
        except OSError as exc:
            return {"message": f"백업을 복원하지 못했습니다. 파일을 쓸 수 없습니다 ({exc.strerror or exc})."}
        self.store.ensure_schema()
        self.settings = self.settings_store.load()
        notice = self._keep_ai_settings_after_restore(previous)
        self.tracker.classifier = RuleClassifier.from_file(self.rules_path)
        self.tracker.set_privacy_options(self.settings.store_domain_only, self.settings.store_window_titles)
        self._apply_alert_settings()
        self._apply_tracking_options()
        return {"message": f"백업을 복원했습니다.{notice}", **self.get_settings()}

    def _apply_alert_settings(self) -> None:
        """복원한 알림 설정은 앱을 다시 켜지 않아도 적용."""
        self.tracker.unproductive_alert_seconds = self.settings.unproductive_limit_minutes * 60
        self.tracker.daily_goal_seconds = self.settings.daily_goal_minutes * 60
        if self.tracker.work_end_hour != self.settings.work_end_hour:
            self.tracker.work_end_hour = self.settings.work_end_hour
            self.tracker.reset_end_of_day_state()
        notifier = getattr(self.tracker, "notifier", None)
        if hasattr(notifier, "set_enabled"):
            notifier.set_enabled(self.settings.notifications_enabled)

    def _keep_ai_settings_after_restore(self, previous: AppSettings) -> str:
        """백업 파일이 데이터 전송처를 정하면 안 됨.

        - 이 PC의 연결 설정은 유지
        - 분석 방식은 내장 분석으로 되돌림
        - 전송 제외 목록은 양쪽을 합침
        """
        wanted_model = _ai.PROVIDER_MODEL in (previous.ai_provider, self.settings.ai_provider)
        self.settings.ai_provider = _ai.PROVIDER_LOCAL
        self.settings.ai_service = previous.ai_service
        self.settings.ai_service_configs = previous.ai_service_configs
        self.settings.ai_excluded_targets = list(
            dict.fromkeys([*previous.ai_excluded_targets, *self.settings.ai_excluded_targets])
        )
        self.settings_store.save(self.settings)
        return " 분석 방식은 '내장 분석'으로 두었어요. 개인 모델은 설정에서 다시 켜세요." if wanted_model else ""
