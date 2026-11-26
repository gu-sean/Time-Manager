"""점검에서 찾은 문제: 복호화, 암호화 키, 중복 실행, 잘못된 입력."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

from time_manager import db_crypto, notices
from time_manager.formatting import _display_label
from time_manager.rules import RuleClassifier
from time_manager.settings import SettingsStore
from time_manager.storage import ActivityStore
from time_manager.tracker import ActivityTracker
from time_manager.webapi import WebApi

fernet = pytest.importorskip("cryptography.fernet")
PLAIN = b"SQLite format 3\x00" + b"history" * 100


@pytest.fixture()
def keys(monkeypatch: pytest.MonkeyPatch) -> tuple[bytes, bytes]:
    """(자격 증명의 키, 대체 키). 실제 자격 증명 저장소는 건드리지 않음."""
    stored, fallback = fernet.Fernet.generate_key(), fernet.Fernet.generate_key()
    monkeypatch.setattr(db_crypto, "_get_or_create_key", lambda: stored)
    monkeypatch.setattr(db_crypto, "_machine_derived_key", lambda: fallback)
    notices.clear()
    return stored, fallback


def encrypted(folder: Path, key: bytes) -> tuple[Path, Path]:
    db = folder / "activity.sqlite3"
    enc = Path(f"{db}.enc")
    enc.write_bytes(fernet.Fernet(key).encrypt(PLAIN))
    return db, enc


def test_history_encrypted_with_the_fallback_key_still_opens(tmp_path: Path, keys: tuple[bytes, bytes]) -> None:
    """종료할 때 자격 증명 저장소가 잠깐 실패하면 대체 키로 암호화됨."""
    db, enc = encrypted(tmp_path, keys[1])

    assert db_crypto.decrypt_if_needed(db)
    assert db.read_bytes() == PLAIN and enc.exists()
    assert not list(tmp_path.glob("*.unreadable-*"))


def test_history_no_key_can_open_is_kept_aside(tmp_path: Path, keys: tuple[bytes, bytes]) -> None:
    db, enc = encrypted(tmp_path, fernet.Fernet.generate_key())

    assert db_crypto.decrypt_if_needed(db) is False
    assert not enc.exists() and len(list(tmp_path.glob("*.unreadable-*"))) == 1


def test_a_failed_write_stops_start_up_and_leaves_the_history_in_place(
    tmp_path: Path, keys: tuple[bytes, bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    """디스크 부족 등은 암호 문제가 아님: 기록을 옮기고 빈 상태로 시작하면 안 됨."""
    db, enc = encrypted(tmp_path, keys[0])
    before = enc.read_bytes()

    def full_disk(path: Path, data: bytes) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(db_crypto, "atomic_write_bytes", full_disk)

    with pytest.raises(OSError):
        db_crypto.decrypt_if_needed(db)
    assert enc.read_bytes() == before
    assert not db.exists() and not list(tmp_path.glob("*.unreadable-*"))


def test_an_interrupted_decryption_leaves_no_half_written_database(
    tmp_path: Path, keys: tuple[bytes, bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    """반쯤 쓰인 평문이 남으면 다음 실행이 그것을 쓰고 정상 .enc 를 덮어씀."""
    import time_manager.fileio as fileio

    db, _ = encrypted(tmp_path, keys[0])

    def interrupted(source: str, target: object) -> None:
        raise KeyboardInterrupt  # 교체 직전에 종료됨

    monkeypatch.setattr(fileio.os, "replace", interrupted)

    with pytest.raises(KeyboardInterrupt):
        db_crypto.decrypt_if_needed(db)
    assert not db.exists()


def test_decryption_is_written_to_the_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """로그를 먼저 설정해야 복호화의 성공·실패가 남음."""
    from time_manager import app

    order: list[str] = []
    monkeypatch.setattr(app, "user_data_dir", lambda root: tmp_path)
    monkeypatch.setattr(app, "_configure_logging", lambda folder: order.append("logging") or folder / "x.log")

    def decrypt(path: Path) -> bool:
        order.append("decrypt")
        raise SystemExit  # 이후 단계는 필요 없음

    monkeypatch.setattr(db_crypto, "decrypt_if_needed", decrypt)
    with pytest.raises(SystemExit):
        app.run_webview(tmp_path)

    assert order == ["logging", "decrypt"]


# -- 중복 실행 ----------------------------------------------------------------------

@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows only")
def test_only_one_instance_per_data_folder(tmp_path: Path) -> None:
    from time_manager.single_instance import acquire

    first = acquire(tmp_path)
    try:
        assert first is not None
        assert acquire(tmp_path) is None
        other = acquire(tmp_path / "another-folder")  # 소스 실행과 설치본은 함께 실행 가능
        assert other is not None
        other.release()
    finally:
        first.release()
    again = acquire(tmp_path)
    assert again is not None
    again.release()


def test_a_second_instance_never_touches_the_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from time_manager import app, single_instance

    shown: list[str] = []
    monkeypatch.setattr(app, "user_data_dir", lambda root: tmp_path)
    monkeypatch.setattr(app, "_configure_logging", lambda folder: folder / "x.log")
    monkeypatch.setattr(single_instance, "acquire", lambda folder: None)
    monkeypatch.setattr(single_instance, "show_running_window", lambda title: shown.append(title))
    monkeypatch.setattr(db_crypto, "decrypt_if_needed", lambda path: pytest.fail("must not decrypt"))
    monkeypatch.setattr(db_crypto, "encrypt_and_replace", lambda path: pytest.fail("must not encrypt"))

    app.run_webview(tmp_path)

    assert shown == ["시간 관리 매니저"]


# -- 잘못된 입력 ----------------------------------------------------------------------

@pytest.fixture()
def api(tmp_path: Path):
    rules = tmp_path / "rules.json"
    rules.write_text("{}", encoding="utf-8")
    store = ActivityStore(tmp_path / "activity.sqlite3")
    tracker = ActivityTracker(store=store, classifier=RuleClassifier.from_file(rules))
    value = WebApi(
        store=store, tracker=tracker, settings_store=SettingsStore(tmp_path / "settings.json"), rules_path=rules
    )
    yield value
    store.close()


@pytest.mark.parametrize("value", [None, {}, {"a": 1}, ["x"], 5])
def test_a_wrong_profile_value_does_not_break_the_settings_screen(api: WebApi, value: object) -> None:
    before = api.settings.onboarding_profile

    api.set_profile(value)

    assert api.settings.onboarding_profile == before
    assert api.get_settings()["theme"] in {"light", "dark"}


def test_a_wrong_theme_value_is_ignored(api: WebApi) -> None:
    api.set_theme(["x"])

    assert api.get_settings()["theme"] == "light"


@pytest.mark.parametrize("day", ["0001-01-01", "9999-12-31", "", "not-a-date", None])
def test_extreme_dates_show_a_page_instead_of_failing(api: WebApi, day: object) -> None:
    for method in (api.get_dashboard, api.get_review):
        assert method(day)


@pytest.mark.parametrize(
    "start,end", [("0001-01-01", "0001-01-01"), ("0001-01-01", "9999-12-31"), (None, None), ("x", "y")]
)
def test_extreme_report_ranges_answer(api: WebApi, start: object, end: object) -> None:
    result = api.get_report_range(start, end)

    assert result["startIso"] >= "2000-01-01" and result["endIso"] <= date.today().isoformat()


# -- 주소 표시 -------------------------------------------------------------------------

@pytest.mark.parametrize(
    "stored,shown",
    [
        # 브라우저 주소창은 "https://" 를 숨김 → 저장된 값에도 없음
        ("youtube.com/watch?v=abc123", "youtube.com/watch"),
        ("www.google.com/search?q=private+words", "google.com/search"),
        ("127.0.0.1:8000/page?token=secret#top", "127.0.0.1:8000/page"),
        ("github.com/", "github.com"),
        # 주소가 아닌 것은 그대로
        ("main.py", "main.py"),
        ("What is a/b testing? - Notes", "What is a/b testing? - Notes"),
        ("보고서/최종?", "보고서/최종?"),
        ("Code.exe", "Code.exe"),
    ],
)
def test_addresses_without_a_scheme_hide_the_query(stored: str, shown: str) -> None:
    assert _display_label(stored) == shown


def test_a_large_backup_of_a_long_used_app_can_be_restored() -> None:
    from time_manager.backup import BackupManager

    assert BackupManager._MAX_RESTORE_BYTES >= 1024 * 1024 * 1024


def test_a_wal_left_by_another_database_is_moved_aside_not_applied(tmp_path: Path, keys: tuple[bytes, bytes]) -> None:
    db, _ = encrypted(tmp_path, keys[0])
    Path(f"{db}-wal").write_bytes(b"left over from another database")

    assert db_crypto.decrypt_if_needed(db)
    assert db.read_bytes() == PLAIN and not Path(f"{db}-wal").exists()
    [kept] = tmp_path.glob("activity.sqlite3-wal.stale-*")
    assert kept.read_bytes() == b"left over from another database"  # 삭제하지 않음
