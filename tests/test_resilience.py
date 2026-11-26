"""문제가 생겼을 때의 동작: 잠기거나 못 읽는 데이터, 디스크 부족, 손상된 파일."""
import json
import os
import sqlite3
import time
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from time_manager import db_crypto, notices
from time_manager.fileio import atomic_write_text
from time_manager.models import ActiveTarget, Category, ClassifiedActivity
from time_manager.rules import load_rules
from time_manager.settings import AppSettings, SettingsStore
from time_manager.webapi import WebApi


@pytest.fixture(autouse=True)
def _clean_notices() -> Iterator[None]:
    notices.clear()
    yield
    notices.clear()


# -- 복호화할 수 없는 데이터 -----------------------------------------------------

class TestUnreadableDatabase:
    def test_the_old_history_survives_a_run_with_the_wrong_key(self, tmp_path: Path) -> None:
        from cryptography.fernet import Fernet

        database = tmp_path / "activity.sqlite3"
        database.write_bytes(b"SQLite format 3\x00 months of history")
        keys = [Fernet.generate_key(), Fernet.generate_key()]
        with patch.object(db_crypto, "_get_or_create_key", return_value=keys[0]):
            db_crypto.encrypt_and_replace(database)
        original = Path(f"{database}.enc").read_bytes()

        with patch.object(db_crypto, "_get_or_create_key", return_value=keys[1]):
            assert db_crypto.decrypt_if_needed(database) is False
            database.write_bytes(b"SQLite format 3\x00 new empty database")
            db_crypto.encrypt_and_replace(database)  # 정상 종료

        [kept] = tmp_path.glob("activity.sqlite3.enc.unreadable-*")
        assert kept.read_bytes() == original
        assert str(kept) in notices.current()[0]

    def test_start_up_stops_rather_than_overwrite_what_cannot_be_moved(self, tmp_path: Path) -> None:
        encrypted = tmp_path / "activity.sqlite3.enc"
        encrypted.write_bytes(b"not decryptable")

        with patch.object(db_crypto, "_get_or_create_key", return_value=b"x" * 44), patch(
            "os.replace", side_effect=PermissionError("locked")
        ), pytest.raises(PermissionError):
            db_crypto.decrypt_if_needed(tmp_path / "activity.sqlite3")

        assert encrypted.read_bytes() == b"not decryptable"

    def test_a_failed_encryption_keeps_the_previous_copy(self, tmp_path: Path) -> None:
        from cryptography.fernet import Fernet

        database = tmp_path / "activity.sqlite3"
        database.write_bytes(b"SQLite format 3\x00 data")
        encrypted = Path(f"{database}.enc")
        encrypted.write_bytes(b"previous good copy")

        with patch.object(db_crypto, "_get_or_create_key", return_value=Fernet.generate_key()), patch(
            "os.replace", side_effect=OSError("disk full")
        ):
            assert db_crypto.encrypt_and_replace(database) is False

        assert encrypted.read_bytes() == b"previous good copy"
        assert database.exists()
        assert not list(tmp_path.glob("*.tmp"))


# -- 추적 스레드 -------------------------------------------------------------------

class _Monitor:
    last_status = ""

    def __init__(self, target: ActiveTarget | None = None) -> None:
        self.target = target or ActiveTarget("editor.exe", "t")

    def idle_seconds(self) -> int:
        return 0

    def get_active_target(self) -> ActiveTarget:
        return self.target


def _wait_for(condition, seconds: float = 3.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return False


class TestTrackerSurvives:
    @pytest.mark.parametrize("where", ["record", "classify", "notify"])
    def test_keeps_recording_after_an_error(self, api: WebApi, where: str) -> None:
        tracker = api.tracker
        tracker.poll_seconds = 0.01
        tracker.monitor = _Monitor()
        failures = {"left": 5}

        def flaky(original):
            def call(*args, **kwargs):
                if failures["left"]:
                    failures["left"] -= 1
                    raise sqlite3.OperationalError("database is locked")
                return original(*args, **kwargs)

            return call

        if where == "record":
            api.store.record = flaky(api.store.record)
        elif where == "classify":
            object.__setattr__(tracker, "classifier", _Classifier(flaky(tracker.classifier.classify)))
        else:
            tracker._maybe_end_of_day_notify = flaky(lambda: None)

        tracker.start()
        try:
            assert _wait_for(lambda: failures["left"] == 0 and tracker._failures_in_a_row == 0)
            assert tracker.is_running and tracker.problem == ""
        finally:
            tracker.stop()

    def test_reports_a_lasting_problem_and_clears_it(self, api: WebApi) -> None:
        tracker = api.tracker
        tracker.poll_seconds = 0.01
        tracker.monitor = _Monitor()
        original = api.store.record
        api.store.record = lambda *a: (_ for _ in ()).throw(sqlite3.OperationalError("disk I/O error"))

        tracker.start()
        try:
            assert _wait_for(lambda: "OperationalError" in tracker.problem)
            assert api.get_dashboard()["problem"] == tracker.problem
            api.store.record = original
            assert _wait_for(lambda: tracker.problem == "")
        finally:
            tracker.stop()


class _Classifier:
    excluded_apps: tuple[str, ...] = ()

    def __init__(self, classify) -> None:
        self.classify = classify


# -- 이 앱은 기록하지 않음 -----------------------------------------------------------

class TestOwnAppIsNeverRecorded:
    @pytest.mark.parametrize("name", ["TimeManager.exe", "TimeManagerWeb.exe", "python.exe", "아무이름.exe"])
    def test_own_window_whatever_the_executable_is_called(self, api: WebApi, name: str) -> None:
        target = ActiveTarget(name, "시간 관리 매니저", process_id=os.getpid())

        assert api.tracker._should_skip_target(target)

    @pytest.mark.parametrize("name", ["TimeManager.exe", "timemanagerweb.exe"])
    def test_a_second_instance(self, api: WebApi, name: str) -> None:
        assert api.tracker._should_skip_target(ActiveTarget(name, "t", process_id=os.getpid() + 1))

    def test_other_programs_are_recorded_even_with_similar_titles(self, api: WebApi) -> None:
        other = ActiveTarget("python.exe", "time manager 강의 노트", process_id=os.getpid() + 1)

        assert not api.tracker._should_skip_target(other)

    def test_the_switch_is_gone_and_an_old_setting_cannot_turn_it_off(self, api: WebApi) -> None:
        api.settings_store.path.write_text('{"exclude_self_app": false}', encoding="utf-8")
        api.settings = api.settings_store.load()

        assert "excludeSelf" not in api.get_settings()
        assert not hasattr(api, "toggle_exclude_self")
        assert api.tracker._should_skip_target(ActiveTarget("x.exe", "t", process_id=os.getpid()))


# -- 손상·쓰기 불가 파일 ----------------------------------------------------------------

class TestDamagedFiles:
    @pytest.mark.parametrize("content", [b"[1, 2]", b"{oops", b"\xff\xfe\x00bad", b'"text"', b""])
    def test_unreadable_settings_fall_back_to_defaults_and_keep_a_copy(self, tmp_path: Path, content: bytes) -> None:
        path = tmp_path / "settings.json"
        path.write_bytes(content)

        assert SettingsStore(path).load() == AppSettings()
        assert (tmp_path / "settings.json.corrupt").read_bytes() == content
        assert notices.current()

    def test_one_bad_value_does_not_lose_the_others(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        path.write_text(json.dumps({"daily_goal_minutes": "abc", "weekly_goal_minutes": 600, "theme": "dark"}), encoding="utf-8")

        settings = SettingsStore(path).load()

        assert (settings.daily_goal_minutes, settings.weekly_goal_minutes, settings.theme) == (180, 600, "dark")

    def test_a_byte_order_mark_is_not_damage(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        path.write_text('{"theme": "dark"}', encoding="utf-8-sig")

        assert SettingsStore(path).load().theme == "dark" and not notices.current()

    def test_unreadable_rules_are_set_aside_and_reported(self, tmp_path: Path) -> None:
        path = tmp_path / "rules.json"
        path.write_bytes(b"\xff\xfe\x00bad")

        assert load_rules(path) == {}
        assert (tmp_path / "rules.json.corrupt").exists() and notices.current()

    def test_notices_reach_the_dashboard(self, api: WebApi) -> None:
        notices.add("문제가 있었어요")

        assert api.get_dashboard()["notices"] == ["문제가 있었어요"]


def _disk_full(*args: object, **kwargs: object) -> None:
    raise OSError(28, "No space left on device")


class TestFailedWrites:
    def test_a_failed_write_leaves_the_old_file(self, tmp_path: Path) -> None:
        path = tmp_path / "data.json"
        atomic_write_text(path, "old")

        with patch("os.replace", side_effect=OSError("disk full")), pytest.raises(OSError):
            atomic_write_text(path, "new")

        assert path.read_text(encoding="utf-8") == "old"
        assert list(tmp_path.iterdir()) == [path]

    def test_a_briefly_locked_file_is_retried(self, tmp_path: Path) -> None:
        real, calls = os.replace, []

        def locked_twice(source, target):
            calls.append(1)
            if len(calls) < 3:
                raise PermissionError("held by antivirus")
            real(source, target)

        with patch("os.replace", side_effect=locked_twice):
            atomic_write_text(tmp_path / "data.json", "new")

        assert (tmp_path / "data.json").read_text(encoding="utf-8") == "new"

    @pytest.mark.parametrize(
        "change",
        [
            lambda api: api.set_theme("dark"),
            lambda api: api.set_profile("developer"),
            lambda api: api.dismiss_rule_suggestion("x.exe"),
            lambda api: api.add_ai_exclusion("secret.com"),
            lambda api: api.create_preset("mine"),
        ],
    )
    def test_a_setting_that_was_not_saved_is_not_kept_in_memory(self, api: WebApi, change) -> None:
        api.settings_store.save(api.settings)
        before = api.get_settings()

        with patch.object(Path, "write_text", _disk_full), pytest.raises(OSError):
            change(api)

        assert api.get_settings() == before

    def test_a_rule_that_was_not_saved_does_not_classify(self, api: WebApi) -> None:
        with patch.object(Path, "write_text", _disk_full), pytest.raises(OSError):
            api.add_rule("앱 이름", "생산적", "new.exe")

        assert "new.exe" not in api.tracker.classifier.productive_apps
        assert "new.exe" not in str(api.get_rules())

    @pytest.mark.parametrize(
        "export",
        [lambda api: api.export_csv(), lambda api: api.export_csv_period("최근 7일"),
         lambda api: api.export_csv_range("2026-01-01", "2026-01-02"), lambda api: api.export_backup()],
    )
    def test_a_failed_export_explains_instead_of_raising(self, api: WebApi, tmp_path: Path, export) -> None:
        folder = tmp_path / "is-a-folder"
        folder.mkdir()
        with patch.object(WebApi, "_save_dialog", return_value=folder):
            message = export(api)["message"]

        assert "저장하지 못했습니다" in message


# -- UI 에서 온 예상 밖 입력 -----------------------------------------------------------

@pytest.mark.parametrize(
    "call",
    [
        lambda api: api.get_dashboard("junk"),
        lambda api: api.get_review("2026-13-40"),
        lambda api: api.get_inbox("", None, "x"),
        lambda api: api.get_inbox("a", "not-a-category"),
        lambda api: api.reclassify_event(1, "not-a-category"),
    ],
)
def test_bad_input_never_raises(api: WebApi, call) -> None:
    api.store.record(ClassifiedActivity(ActiveTarget("a.exe", "t"), Category.PRODUCTIVE, "r"), 60)

    assert call(api) is not None
    assert api.get_inbox()["records"][0]["category"] == "productive"
