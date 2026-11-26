from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from time_manager.fileio import atomic_write_bytes

AUTO_BACKUP_INTERVAL_DAYS = 7
_SQLITE_HEADER = b"SQLite format 3\x00"
_INVALID_DATABASE = "백업의 활동 기록 파일이 손상되었거나 이 앱의 데이터가 아닙니다."


def should_auto_backup(
    enabled: bool,
    last_backup_iso: str,
    today: date,
    interval_days: int = AUTO_BACKUP_INTERVAL_DAYS,
) -> bool:
    # last_backup_iso 가 없거나 해석 불가 → 백업한 적 없음으로 보고 즉시 백업
    if not enabled:
        return False
    if not last_backup_iso:
        return True
    try:
        last = date.fromisoformat(last_backup_iso)
    except ValueError:
        return True
    return (today - last).days >= interval_days


def _require_json_object(name: str, data: bytes) -> None:
    try:
        valid = isinstance(json.loads(data.decode("utf-8-sig")), dict)
    except ValueError:  # 디코딩 오류 포함
        valid = False
    if not valid:
        raise ValueError(f"백업의 {name} 파일이 손상되었습니다.")


def _require_activity_database(path: Path) -> None:
    with path.open("rb") as handle:
        if handle.read(len(_SQLITE_HEADER)) != _SQLITE_HEADER:
            raise ValueError(_INVALID_DATABASE)
    try:
        connection = sqlite3.connect(path)
        try:
            healthy = connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            has_activity = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'activity_events'"
            ).fetchone()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise ValueError(_INVALID_DATABASE) from exc
    if not healthy or not has_activity:
        raise ValueError(_INVALID_DATABASE)


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

    # 압축 폭탄 방지용 상한. 오래 쓴 앱의 백업은 복원할 수 있어야 함
    _MAX_RESTORE_BYTES = 1024 * 1024 * 1024  # 1 GB

    def restore(self, input_path: Path) -> Path:
        """현재 데이터를 백업 내용으로 교체. 교체 전 데이터의 안전 사본 경로를 반환.

        - 변경 전에 백업 내용을 모두 검사
        - ``ValueError`` 발생 시 현재 데이터는 그대로
        """
        contents = self._read_backup(input_path)
        for name in ("rules.json", "settings.json"):
            _require_json_object(name, contents[name])
        with TemporaryDirectory() as folder:
            snapshot = Path(folder) / "activity.sqlite3"
            snapshot.write_bytes(contents["activity.sqlite3"])
            _require_activity_database(snapshot)

            safety_path = self.backup_dir / f"pre-restore-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.tmbak"
            self.export(safety_path)
            self._replace_database(snapshot)
        for target, archive_name in self._managed_files():
            if archive_name != "activity.sqlite3":
                target.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_bytes(target, contents[archive_name])
        return safety_path

    def _read_backup(self, input_path: Path) -> dict[str, bytes]:
        required = [archive_name for _source, archive_name in self._managed_files()]
        try:
            with ZipFile(input_path) as archive:
                names = set(archive.namelist())
                if not names.issuperset(required):
                    raise ValueError("백업 파일에 필요한 데이터가 없습니다.")
                total_size = sum(archive.getinfo(name).file_size for name in names)
                if total_size > self._MAX_RESTORE_BYTES:
                    raise ValueError(f"백업 파일이 너무 큽니다 ({total_size // (1024 * 1024)} MB). 올바른 백업 파일인지 확인하세요.")
                return {name: archive.read(name) for name in required}
        except (BadZipFile, OSError) as exc:
            raise ValueError("백업 파일을 읽을 수 없습니다.") from exc

    def _replace_database(self, snapshot: Path) -> None:
        # 파일 덮어쓰기 금지: 남은 WAL 이나 열린 연결이 이전 데이터를 되살림
        # → SQLite backup API 로 실행 중인 DB 에 한 트랜잭션으로 복사
        self.activity_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            source = sqlite3.connect(snapshot)
            try:
                target = sqlite3.connect(self.activity_path, timeout=10)
                try:
                    source.backup(target)
                finally:
                    target.close()
            finally:
                source.close()
        except sqlite3.Error as exc:
            raise ValueError(f"활동 기록을 되돌리지 못했습니다 ({exc}).") from exc

    def safety_backup(self, label: str, keep: int = 3) -> Path:
        """기록을 한꺼번에 바꾸기 전 상태. 종류별 최근 ``keep`` 개 유지."""
        output = self.backup_dir / f"pre-{label}-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.tmbak"
        self.export(output)
        for old in sorted(self.backup_dir.glob(f"pre-{label}-*.tmbak"))[:-keep]:
            try:
                old.unlink()
            except OSError:
                pass
        return output

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
                # 사용자가 지운 기록은 백업에 넣지 않음
                columns = {row[1] for row in target.execute("PRAGMA table_info(activity_events)")}
                if "deleted_at" in columns:
                    target.execute("DELETE FROM activity_events WHERE deleted_at IS NOT NULL")
                    target.commit()
                    target.execute("VACUUM")
            finally:
                target.close()
                original.close()
            archive.write(snapshot, archive_name)
        finally:
            snapshot.unlink(missing_ok=True)
