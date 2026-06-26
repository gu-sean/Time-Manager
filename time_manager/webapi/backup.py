from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from time_manager.rules import RuleClassifier

from ._shared import WebApiBase


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

    def export_csv(self, day_iso: str | None = None) -> dict[str, Any]:
        target_day = date.fromisoformat(day_iso) if day_iso else date.today()
        path = self._save_dialog(f"activity-{target_day.isoformat()}.csv", ("CSV 파일 (*.csv)",))
        if path is None:
            return {"message": ""}
        rows = self.store.export_csv_for_day(target_day, path)
        return self._csv_result(rows, single_day=True)

    def export_csv_period(self, period: str) -> dict[str, Any]:
        from time_manager.formatting import _report_period_for_label

        today = date.today()
        start_day, end_day = _report_period_for_label(period, today)
        path = self._save_dialog(
            f"activity-{start_day.isoformat()}-{end_day.isoformat()}.csv", ("CSV 파일 (*.csv)",)
        )
        if path is None:
            return {"message": ""}
        rows = self.store.export_csv_for_period(start_day, end_day, path)
        return self._csv_result(rows)

    def export_csv_range(self, start_iso: str, end_iso: str) -> dict[str, Any]:
        try:
            start_day = date.fromisoformat(start_iso)
            end_day = date.fromisoformat(end_iso)
        except ValueError:
            return {"message": "날짜 형식이 올바르지 않습니다."}
        if start_day > end_day:
            return {"message": "시작일이 종료일보다 늦을 수 없습니다."}
        path = self._save_dialog(
            f"activity-{start_day.isoformat()}-{end_day.isoformat()}.csv", ("CSV 파일 (*.csv)",)
        )
        if path is None:
            return {"message": ""}
        rows = self.store.export_csv_for_period(start_day, end_day, path)
        return self._csv_result(rows)

    def export_backup(self) -> dict[str, Any]:
        manager = self._backup_manager()
        path = self._save_dialog(
            f"time-manager-{date.today().isoformat()}.tmbak", ("Time Manager 백업 (*.tmbak)",)
        )
        if path is None:
            return {"message": ""}
        manager.export(path)
        return {"message": f"백업을 저장했습니다: {path}"}

    def restore_backup(self) -> dict[str, Any]:
        manager = self._backup_manager()
        path = self._open_dialog(("Time Manager 백업 (*.tmbak)",))
        if path is None:
            return {"message": ""}
        manager.restore(path)
        self.settings = self.settings_store.load()
        self.tracker.classifier = RuleClassifier.from_file(self.rules_path)
        self.tracker.set_exclude_self_app(self.settings.exclude_self_app)
        self.tracker.set_privacy_options(self.settings.store_domain_only, self.settings.store_window_titles)
        return {"message": "백업을 복원했습니다.", **self.get_settings()}
