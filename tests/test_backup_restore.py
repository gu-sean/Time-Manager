"""앱이 DB 를 열어 둔 상태에서도 복원은 데이터를 실제로 되살려야 함."""
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import pytest

from time_manager.models import ActiveTarget, Category, ClassifiedActivity
from time_manager.webapi import WebApi


def _record(api: WebApi, name: str) -> None:
    api.store.record(ClassifiedActivity(ActiveTarget(name, name), Category.PRODUCTIVE, "rule"), 60)


def _apps(api: WebApi) -> list[str]:
    """새 연결에서 보이는 내용 = 디스크의 실제 상태."""
    connection = sqlite3.connect(api.store.db_path)
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        rows = connection.execute("SELECT app_name FROM activity_events WHERE deleted_at IS NULL ORDER BY id")
        return [row[0] for row in rows]
    finally:
        connection.close()


@pytest.fixture
def backup(api: WebApi, tmp_path: Path) -> Path:
    api.settings.daily_goal_minutes = 111
    api.settings_store.save(api.settings)
    for number in range(3):
        _record(api, f"in-backup-{number}.exe")
    archive = api._backup_manager().export(tmp_path / "backup.tmbak")
    api.settings.daily_goal_minutes = 222
    api.settings_store.save(api.settings)
    return archive


IN_BACKUP = [f"in-backup-{number}.exe" for number in range(3)]


def _restore(api: WebApi, archive: Path) -> dict:
    with patch.object(WebApi, "_open_dialog", return_value=archive):
        return api.restore_backup()


@contextmanager
def _open_elsewhere(api: WebApi) -> Iterator[None]:
    """다른 스레드(추적기 등)는 자기 연결을 계속 열어 둠."""
    opened, release = threading.Event(), threading.Event()

    def hold() -> None:
        _record(api, "from-tracker.exe")
        opened.set()
        release.wait(30)
        api.store.close()

    thread = threading.Thread(target=hold)
    thread.start()
    assert opened.wait(10)
    try:
        yield
    finally:
        release.set()
        thread.join(10)


@pytest.mark.parametrize("later_records", [1, 300])
def test_records_return_to_the_backup(api: WebApi, backup: Path, later_records: int) -> None:
    for number in range(later_records):
        _record(api, f"later-{number}.exe")

    result = _restore(api, backup)

    assert "복원했습니다" in result["message"]
    assert _apps(api) == IN_BACKUP
    assert [row["label"] for row in api.get_inbox()["records"]] != []
    assert result["dailyGoalMinutes"] == 111


def test_works_while_another_thread_has_the_database_open(api: WebApi, backup: Path) -> None:
    with _open_elsewhere(api):
        _record(api, "later.exe")
        _restore(api, backup)
        assert _apps(api) == IN_BACKUP

    assert _apps(api) == IN_BACKUP  # 다른 연결을 닫아도 이전 데이터가 되살아나면 안 됨


def test_app_keeps_working_after_restore(api: WebApi, backup: Path) -> None:
    _restore(api, backup)

    _record(api, "after-restore.exe")

    assert _apps(api) == [*IN_BACKUP, "after-restore.exe"]


def test_deleted_database_is_recreated(api: WebApi, backup: Path) -> None:
    api.store.close()
    for suffix in ("", "-wal", "-shm"):
        Path(f"{api.store.db_path}{suffix}").unlink(missing_ok=True)

    _restore(api, backup)

    assert _apps(api) == IN_BACKUP


def test_safety_copy_holds_the_data_from_before(api: WebApi, backup: Path, tmp_path: Path) -> None:
    _record(api, "later.exe")
    _restore(api, backup)
    [safety] = (api.store.db_path.parent / "backups").glob("pre-restore-*.tmbak")

    _restore(api, safety)

    assert _apps(api) == [*IN_BACKUP, "later.exe"]


def test_restored_alert_settings_apply_without_a_restart(api: WebApi, tmp_path: Path) -> None:
    api.settings.unproductive_limit_minutes = 45
    api.settings.work_end_hour = 21
    api.settings.notifications_enabled = False
    api.settings_store.save(api.settings)
    archive = api._backup_manager().export(tmp_path / "alerts.tmbak")
    enabled: list[bool] = []
    api.tracker.notifier.set_enabled = enabled.append  # type: ignore[attr-defined]

    _restore(api, archive)

    assert (api.tracker.unproductive_alert_seconds, api.tracker.work_end_hour) == (45 * 60, 21)
    assert enabled == [False]


def _tampered(source: Path, target: Path, **replaced: bytes | None) -> Path:
    names = {"db": "activity.sqlite3", "rules": "rules.json", "settings": "settings.json"}
    changes = {names[key]: value for key, value in replaced.items()}
    with ZipFile(source) as original, ZipFile(target, "w") as copy:
        for name in original.namelist():
            data = changes.get(name, original.read(name))
            if data is not None:
                copy.writestr(name, data)
    return target


def _empty_database(tmp_path: Path) -> bytes:
    path = tmp_path / "other.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE something (x)")
    connection.commit()
    connection.close()
    return path.read_bytes()


@pytest.mark.parametrize(
    "broken", ["not-a-database", "damaged-database", "foreign-database", "bad-rules", "bad-settings", "missing-file"]
)
def test_a_broken_backup_changes_nothing(api: WebApi, backup: Path, tmp_path: Path, broken: str) -> None:
    with ZipFile(backup) as archive:
        database = archive.read("activity.sqlite3")
    changes: dict[str, bytes | None] = {
        "not-a-database": {"db": b"hello"},
        "damaged-database": {"db": database[:100] + b"\xff" * (len(database) - 100)},
        "foreign-database": {"db": _empty_database(tmp_path)},
        "bad-rules": {"rules": b"{not json"},
        "bad-settings": {"settings": b"[1, 2]"},
        "missing-file": {"settings": None},
    }[broken]
    _record(api, "later.exe")
    rules_before = api.rules_path.read_bytes()
    settings_before = api.settings_store.path.read_bytes()

    result = _restore(api, _tampered(backup, tmp_path / "broken.tmbak", **changes))

    assert "복원하지 못했습니다" in result["message"]
    assert "dailyGoalMinutes" not in result  # UI 가 복원 성공으로 처리하면 안 됨
    assert _apps(api) == [*IN_BACKUP, "later.exe"]
    assert api.rules_path.read_bytes() == rules_before
    assert api.settings_store.path.read_bytes() == settings_before


def test_a_file_that_is_not_a_backup_is_reported(api: WebApi, tmp_path: Path) -> None:
    junk = tmp_path / "junk.tmbak"
    junk.write_bytes(b"junk")

    assert "복원하지 못했습니다" in _restore(api, junk)["message"]
