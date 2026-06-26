from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile

AUTO_BACKUP_INTERVAL_DAYS = 7


def should_auto_backup(
    enabled: bool,
    last_backup_iso: str,
    today: date,
    interval_days: int = AUTO_BACKUP_INTERVAL_DAYS,
) -> bool:
    # last_backup_iso가 없거나 파싱 불가면 "한 번도 안 한 것"으로 간주해 즉시 백업
    if not enabled:
        return False
    if not last_backup_iso:
        return True
    try:
        last = date.fromisoformat(last_backup_iso)
    except ValueError:
        return True
    return (today - last).days >= interval_days


class BackupManager:
    def __init__(self, activity_path: Path, rules_path: Path, settings_path: Path, backup_dir: Path) -> None:
        self.activity_path = activity_path
        self.rules_path = rules_path
        self.settings_path = settings_path
        self.backup_dir = backup_dir

    def export(self, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as archive:
            for source, archive_name in self._managed_files():
                if source.exists():
                    if archive_name == "activity.sqlite3":
                        self._write_database_snapshot(archive, source, archive_name)
                    else:
                        archive.write(source, archive_name)
        return output_path

    _MAX_RESTORE_BYTES = 200 * 1024 * 1024  # 200 MB

    def restore(self, input_path: Path) -> Path:
        safety_path = self.backup_dir / f"pre-restore-{datetime.now().strftime('%Y%m%d-%H%M%S')}.tmbak"
        self.export(safety_path)
        with ZipFile(input_path) as archive:
            names = set(archive.namelist())
            required = {archive_name for _source, archive_name in self._managed_files()}
            if not required.issubset(names):
                raise ValueError("백업 파일에 필요한 데이터가 없습니다.")
            total_size = sum(archive.getinfo(name).file_size for name in names)
            if total_size > self._MAX_RESTORE_BYTES:
                raise ValueError(f"백업 파일이 너무 큽니다 ({total_size // (1024 * 1024)} MB). 올바른 백업 파일인지 확인하세요.")
            for target, archive_name in self._managed_files():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(archive_name))
        return safety_path

    def auto_backup(self, today: date | None = None, keep: int = 4) -> Path:
        stamp = (today or date.today()).isoformat()
        output = self.backup_dir / f"auto-{stamp}.tmbak"
        self.export(output)
        self._prune_auto_backups(keep=keep)
        return output

    def _prune_auto_backups(self, keep: int = 4) -> None:
        files = sorted(self.backup_dir.glob("auto-*.tmbak"))
        for old in files[:-keep] if keep > 0 else []:
            try:
                old.unlink()
            except OSError:
                pass

    def _managed_files(self) -> tuple[tuple[Path, str], ...]:
        return (
            (self.activity_path, "activity.sqlite3"),
            (self.rules_path, "rules.json"),
            (self.settings_path, "settings.json"),
        )

    def _write_database_snapshot(self, archive: ZipFile, source: Path, archive_name: str) -> None:
        with source.open("rb") as handle:
            if handle.read(16) != b"SQLite format 3\x00":
                archive.write(source, archive_name)
                return
        with NamedTemporaryFile(suffix=".sqlite3", delete=False) as temporary:
            snapshot = Path(temporary.name)
        try:
            original = sqlite3.connect(source)
            target = sqlite3.connect(snapshot)
            try:
                original.backup(target)
            finally:
                target.close()
                original.close()
            archive.write(snapshot, archive_name)
        finally:
            snapshot.unlink(missing_ok=True)
