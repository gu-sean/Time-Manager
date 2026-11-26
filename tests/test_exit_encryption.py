"""종료할 때 활동 DB 가 빠짐없이 암호화되고 평문이 남지 않아야 함.

화면 요청은 여러 스레드에서 처리되고, 스레드마다 DB 연결이 따로 생김.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import date
from pathlib import Path

import pytest

from time_manager import db_crypto
from time_manager.diagnostics import run_diagnostics
from time_manager.models import ActiveTarget, Category, ClassifiedActivity
from time_manager.storage import ActivityStore

fernet = pytest.importorskip("cryptography.fernet")


@pytest.fixture(autouse=True)
def fixed_key(monkeypatch: pytest.MonkeyPatch) -> bytes:
    """실제 자격 증명 저장소를 건드리지 않음."""
    key = fernet.Fernet.generate_key()
    monkeypatch.setattr(db_crypto, "_get_or_create_key", lambda: key)
    return key


def record(store: ActivityStore, count: int) -> None:
    for index in range(count):
        store.record(ClassifiedActivity(ActiveTarget(f"app{index}.exe", "t"), Category.PRODUCTIVE, "r"), 5)


def rows_in_encrypted_copy(db: Path, key: bytes) -> int:
    copy = db.with_name("copy.sqlite3")
    copy.write_bytes(fernet.Fernet(key).decrypt(Path(f"{db}.enc").read_bytes()))
    connection = sqlite3.connect(copy)
    try:
        return connection.execute("SELECT COUNT(*) FROM activity_events").fetchone()[0]
    finally:
        connection.close()


def leftovers(db: Path) -> list[str]:
    return sorted(p.name for p in db.parent.glob(f"{db.name}*") if p.suffix != ".enc")


class LivingThread:
    """DB 를 한 번 쓴 뒤 계속 살아 있는 스레드."""

    def __init__(self, work) -> None:
        self.release, done = threading.Event(), threading.Event()

        def run() -> None:
            work()
            done.set()
            self.release.wait(30)

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        assert done.wait(10)

    def stop(self) -> None:
        self.release.set()
        self.thread.join(10)


def test_connections_of_other_threads_do_not_keep_the_plain_database(tmp_path: Path, fixed_key: bytes) -> None:
    db = tmp_path / "activity.sqlite3"
    store = ActivityStore(db)
    other = LivingThread(lambda: store.summaries_between(date.today(), date.today()))
    try:
        record(store, 50)
        store.close()
        assert db_crypto.encrypt_and_replace(db)
        assert leftovers(db) == []
        assert rows_in_encrypted_copy(db, fixed_key) == 50
    finally:
        other.stop()


def test_records_written_by_finished_threads_are_encrypted(tmp_path: Path, fixed_key: bytes) -> None:
    db = tmp_path / "activity.sqlite3"
    store = ActivityStore(db)
    worker = threading.Thread(target=record, args=(store, 20))
    worker.start()
    worker.join()
    store.close()

    assert db_crypto.encrypt_and_replace(db)
    assert leftovers(db) == []
    assert rows_in_encrypted_copy(db, fixed_key) == 20


def test_connections_of_finished_threads_are_released(tmp_path: Path) -> None:
    """화면 요청마다 새 스레드가 생기므로 연결이 쌓이면 안 됨."""
    store = ActivityStore(tmp_path / "activity.sqlite3")
    for _ in range(30):
        worker = threading.Thread(target=store.summaries_between, args=(date.today(), date.today()))
        worker.start()
        worker.join()
    try:
        assert len(store._connections) <= 2  # 만든 스레드 + 마지막 작업 스레드
    finally:
        store.close()


def test_after_shutdown_the_database_is_not_reopened(tmp_path: Path) -> None:
    store = ActivityStore(tmp_path / "activity.sqlite3")
    store.shutdown()

    with pytest.raises(sqlite3.ProgrammingError):
        record(store, 1)
    store.shutdown()  # 두 번 호출해도 괜찮음


def test_a_closed_store_can_be_used_again_from_every_thread(tmp_path: Path) -> None:
    store = ActivityStore(tmp_path / "activity.sqlite3")
    again, finished, errors = threading.Event(), threading.Event(), []

    def use_twice() -> None:
        record(store, 1)
        finished.set()
        again.wait(10)
        try:
            record(store, 1)
        except sqlite3.Error as exc:
            errors.append(exc)

    worker = threading.Thread(target=use_twice)
    worker.start()
    assert finished.wait(10)
    store.close()
    again.set()
    worker.join(10)
    record(store, 1)
    store.close()

    assert errors == []


def test_diagnostics_leave_no_connection_open(tmp_path: Path, fixed_key: bytes) -> None:
    db = tmp_path / "activity.sqlite3"
    store = ActivityStore(db)
    record(store, 3)
    kept = []  # 결과를 붙잡고 있어도 연결은 닫혀 있어야 함
    kept.append(run_diagnostics(
        data_dir=tmp_path, db_path=db, rules_path=tmp_path / "r.json",
        settings_path=tmp_path / "s.json", log_path=tmp_path / "t.log",
    ))
    store.shutdown()

    assert db_crypto.encrypt_and_replace(db)
    assert leftovers(db) == []
    assert rows_in_encrypted_copy(db, fixed_key) == 3


def test_data_still_in_the_wal_is_encrypted_even_if_another_program_has_the_file_open(
    tmp_path: Path, fixed_key: bytes
) -> None:
    db = tmp_path / "activity.sqlite3"
    store = ActivityStore(db)
    outside = sqlite3.connect(db)  # 앱이 닫을 수 없는 연결 (다른 프로그램)
    outside.execute("SELECT COUNT(*) FROM activity_events").fetchone()
    try:
        record(store, 50)
        store.close()
        db_crypto.encrypt_and_replace(db)

        assert rows_in_encrypted_copy(db, fixed_key) == 50
        # 평문을 못 지웠다면, 남은 평문도 완전해야 다음 실행에서 기록이 유지됨
        if db.exists():
            assert outside.execute("SELECT COUNT(*) FROM activity_events").fetchone()[0] == 50
    finally:
        outside.close()


def test_an_incomplete_copy_never_replaces_the_previous_encrypted_file(tmp_path: Path) -> None:
    db = tmp_path / "activity.sqlite3"
    enc = Path(f"{db}.enc")
    enc.write_bytes(b"previous encrypted history")
    store = ActivityStore(db)
    reader = sqlite3.connect(db, isolation_level=None)
    try:
        reader.execute("BEGIN")
        reader.execute("SELECT COUNT(*) FROM activity_events").fetchone()  # 읽는 중: WAL 을 본 파일로 못 옮김
        record(store, 10)
        store.close()

        assert db_crypto.encrypt_and_replace(db) is False
        assert enc.read_bytes() == b"previous encrypted history"
        assert db.exists() and Path(f"{db}-wal").exists()
    finally:
        reader.execute("ROLLBACK")
        reader.close()
