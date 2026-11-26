"""자리 비움·영상 재생 판단, 날짜가 바뀔 때의 작업, 트레이, 다시 실행."""

import sys
import threading
import uuid
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from time_manager import single_instance, startup
from time_manager.models import ActiveTarget, Category
from time_manager.notifications import NullNotifier, RecordingNotifier
from time_manager.rules import RuleClassifier
from time_manager.settings import SettingsStore
from time_manager.storage import ActivityStore
from time_manager.tracker import ActivityTracker
from time_manager.tray import TrayController
from time_manager.webapi import WebApi


class Monitor:
    last_status = ""

    def __init__(self):
        self.idle = 0
        self.playing = False
        self.target = ActiveTarget("chrome.exe", "lecture", "https://example.com")
        self.media_checks = 0

    def get_active_target(self):
        return self.target

    def idle_seconds(self):
        return self.idle

    def media_playing(self, app_name):
        self.media_checks += 1
        return self.playing and app_name == self.target.app_name


@pytest.fixture
def parts(tmp_path):
    store = ActivityStore(tmp_path / "activity.sqlite3")
    monitor = Monitor()
    tracker = ActivityTracker(
        store=store, classifier=RuleClassifier.from_dict({}), monitor=monitor,
        notifier=RecordingNotifier(NullNotifier()),
    )
    yield store, monitor, tracker
    store.close()


def _recorded(store):
    return sum(row.seconds for row in store.summary_for_day(date.today()))


def _away(tracker, monitor, seconds, start=0):
    """입력 없이 ``seconds`` 초가 지남."""
    for passed in range(start + tracker.poll_seconds, start + seconds + 1, tracker.poll_seconds):
        monitor.idle = passed
        tracker._tick()


def _use(tracker, monitor, seconds):
    monitor.idle = 0
    for _ in range(seconds // tracker.poll_seconds):
        tracker._tick()


def test_playing_media_is_recorded_without_input(parts):
    store, monitor, tracker = parts
    monitor.playing = True
    _away(tracker, monitor, 40 * 60)
    assert _recorded(store) == 40 * 60


def test_quiet_moments_do_not_end_playback_but_a_stop_does(parts):
    store, monitor, tracker = parts
    monitor.playing = True
    _away(tracker, monitor, 600)
    monitor.playing = False
    _away(tracker, monitor, 120, start=600)  # 조용한 장면
    assert _recorded(store) == 720
    _away(tracker, monitor, 600, start=720)
    assert _recorded(store) == 720


def test_playback_stops_counting_after_three_hours_without_input(parts):
    store, monitor, tracker = parts
    monitor.playing = True
    _away(tracker, monitor, 4 * 3600)
    assert _recorded(store) == 3 * 3600 - tracker.poll_seconds


def test_turning_media_off_uses_only_the_idle_time(parts):
    store, monitor, tracker = parts
    tracker.record_media = False
    monitor.playing = True
    _away(tracker, monitor, 40 * 60)
    assert _recorded(store) == 5 * 60 - tracker.poll_seconds
    assert monitor.media_checks == 0


def test_media_in_another_app_does_not_carry_over(parts):
    store, monitor, tracker = parts
    monitor.playing = True
    _away(tracker, monitor, 600)
    monitor.playing = False
    monitor.target = ActiveTarget("notepad.exe", "memo", None)
    _away(tracker, monitor, 600, start=600)
    assert _recorded(store) == 600


def test_a_failing_media_check_counts_as_not_playing(parts):
    store, monitor, tracker = parts

    def broken(app_name):
        raise OSError("no audio service")

    monitor.media_playing = broken
    _away(tracker, monitor, 40 * 60)
    assert _recorded(store) == 5 * 60 - tracker.poll_seconds
    assert tracker.problem == ""


@pytest.mark.parametrize("minutes", [1, 10])
def test_the_idle_time_setting_is_used(parts, minutes):
    store, monitor, tracker = parts
    tracker.idle_threshold_seconds = minutes * 60
    _away(tracker, monitor, 40 * 60)
    assert _recorded(store) == minutes * 60 - tracker.poll_seconds


def test_idle_time_stays_by_default(parts):
    store, monitor, tracker = parts
    _use(tracker, monitor, 60)
    _away(tracker, monitor, 20 * 60)
    assert _recorded(store) == 60 + 5 * 60 - tracker.poll_seconds


def test_idle_time_can_be_removed_leaving_the_real_use(parts):
    store, monitor, tracker = parts
    tracker.trim_idle_time = True
    _use(tracker, monitor, 60)
    _away(tracker, monitor, 20 * 60)
    assert _recorded(store) == 60
    _away(tracker, monitor, 600, start=20 * 60)  # 한 번만 뺌
    assert _recorded(store) == 60
    assert store.restore_last_deleted() is None


def test_watched_time_is_not_removed(parts):
    store, monitor, tracker = parts
    tracker.trim_idle_time = True
    monitor.playing = True
    _away(tracker, monitor, 1200)
    monitor.playing = False
    _away(tracker, monitor, 600, start=1200)
    assert _recorded(store) == 1200 + 120


def test_trimming_spans_several_rows(parts):
    store, monitor, tracker = parts
    tracker.trim_idle_time = True
    _use(tracker, monitor, 60)
    monitor.target = ActiveTarget("notepad.exe", "first", None)
    _away(tracker, monitor, 120)
    monitor.target = ActiveTarget("notepad.exe", "second", None)  # 창이 스스로 바뀜
    _away(tracker, monitor, 600, start=120)
    assert _recorded(store) == 60
    assert [row.app_name for row in store.recent()] == ["chrome.exe"]


@pytest.mark.parametrize(
    "target",
    [ActiveTarget("LockApp.exe", "Windows 기본 잠금 화면", None), ActiveTarget("LogonUI.exe", "", None),
     ActiveTarget("Unknown", "", None)],
)
def test_the_lock_screen_is_not_recorded(parts, target):
    store, monitor, tracker = parts
    monitor.target = target
    _use(tracker, monitor, 60)
    assert _recorded(store) == 0


def test_a_new_day_runs_the_daily_tasks_once_and_rearms_the_evening_notice(parts, monkeypatch):
    _, monitor, tracker = parts
    runs = []
    tracker.on_new_day = lambda: runs.append(True)
    tracker.work_end_hour = 24  # 지금은 항상 퇴근 전
    tracker._current_day = date.today() - timedelta(days=1)
    tracker._work_end_armed = False

    _use(tracker, monitor, 30)

    assert runs == [True]
    assert tracker._work_end_armed


def test_a_failing_daily_task_does_not_stop_recording(parts):
    store, monitor, tracker = parts

    def broken():
        raise OSError("disk full")

    tracker.on_new_day = broken
    tracker._current_day = date.today() - timedelta(days=1)
    _use(tracker, monitor, 30)
    assert _recorded(store) == 30
    assert tracker.problem == ""


def _api(tmp_path, store, tracker, **changes):
    rules = tmp_path / "rules.json"
    rules.write_text("{}", encoding="utf-8")
    settings = SettingsStore(tmp_path / "settings.json")
    saved = settings.load_or_create()
    saved.auto_backup_enabled = False
    for key, value in changes.items():
        setattr(saved, key, value)
    settings.save(saved)
    return WebApi(store=store, tracker=tracker, settings_store=settings, rules_path=rules)


def test_daily_tasks_delete_old_records_and_back_up(tmp_path, parts):
    store, _, tracker = parts
    api = _api(tmp_path, store, tracker)
    with store._connection() as conn:
        conn.execute(
            "INSERT INTO activity_events (started_at, seconds, category, app_name, window_title, url, reason)"
            " VALUES ('2020-01-01T09:00:00+09:00', 60, 'neutral', 'a', 'a', NULL, 'r')"
        )
    api.settings.retention_days = 30
    api.settings.auto_backup_enabled = True

    assert tracker.on_new_day == api.run_daily_tasks
    api.run_daily_tasks()

    assert store.first_activity_day() is None
    assert list((tmp_path / "backups").glob("*"))


def test_tracking_options_are_saved_and_applied_at_once(tmp_path, parts):
    store, _, tracker = parts
    api = _api(tmp_path, store, tracker)

    result = api.save_tracking_options({"idleMinutes": 12, "recordMedia": False, "trimIdleTime": True})

    assert (result["idleMinutes"], result["recordMedia"], result["trimIdleTime"], result["closeToTray"]) == (
        12, False, True, True)
    assert (tracker.idle_threshold_seconds, tracker.record_media, tracker.trim_idle_time) == (720, False, True)
    assert api.settings_store.load().idle_minutes == 12


@pytest.mark.parametrize("minutes", [0, 61, "", "abc", None])
def test_a_wrong_idle_time_changes_nothing(tmp_path, parts, minutes):
    store, _, tracker = parts
    api = _api(tmp_path, store, tracker)

    result = api.save_tracking_options({"idleMinutes": minutes, "recordMedia": False})

    assert result["error"]
    assert (result["idleMinutes"], result["recordMedia"]) == (5, True)


class Window:
    def __init__(self):
        self.calls = []

    def destroy(self):
        self.calls.append("destroy")

    def show(self):
        self.calls.append("show")


def _tray(tmp_path, tracker=None, *, enabled=True, start_hidden=False):
    return TrayController(
        Window(), tracker, tmp_path / "icon.ico", close_to_tray=lambda: enabled,
        take_first_hint=lambda: False, on_session_end=lambda: None, start_hidden=start_hidden,
    )


def test_only_a_close_by_the_user_hides_the_window(tmp_path):
    tray = _tray(tmp_path)
    tray._ready.set()
    assert tray.should_hide(True)
    assert not tray.should_hide(False)  # Windows 종료, 작업 관리자


def test_the_window_is_not_hidden_without_an_icon_or_when_turned_off(tmp_path):
    assert not _tray(tmp_path).should_hide(True)
    off = _tray(tmp_path, enabled=False)
    off._ready.set()
    assert not off.should_hide(True)


def test_quitting_really_closes_the_window(tmp_path):
    tray = _tray(tmp_path)
    tray._ready.set()
    tray.quit()
    assert tray.window.calls == ["destroy"]
    assert not tray.should_hide(True)


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows only")
def test_no_tray_window_refuses_to_end_the_session(tmp_path):
    """실제 아이콘 창에 메시지를 보냄: pystray 의 기본 동작은 0(거부)."""
    import ctypes
    from ctypes import wintypes
    from pathlib import Path

    tray = _tray(tmp_path, tracker=SimpleNamespace(is_running=True, is_paused=False))  # 메뉴를 만들 때 읽음
    tray.icon_path = Path(__file__).resolve().parents[1] / "assets" / "tray.png"
    ended = []
    tray._on_session_end = lambda: ended.append(True)
    tray.start()
    try:
        assert tray._ready.is_set()
        send = ctypes.WinDLL("user32").SendMessageTimeoutW
        send.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM, wintypes.UINT,
                         wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]

        def ask(message, wparam):
            answer = ctypes.c_size_t(99)
            assert send(tray._icon._hwnd, message, wparam, 0, 0x0002, 5000, ctypes.byref(answer))
            return answer.value

        assert ask(0x0011, 0) == 1  # WM_QUERYENDSESSION: 동의
        ask(0x0016, 0)  # 취소됨
        assert ended == []
        ask(0x0016, 1)  # 실제 종료: 반환하기 전에 정리가 끝남
        assert ended == [True]
        assert tray.window.calls == []  # 창은 Windows 의 메시지로 닫힘
    finally:
        tray.stop()


def test_a_failing_cleanup_does_not_block_the_shutdown(tmp_path):
    tray = _tray(tmp_path)

    def broken():
        raise OSError("disk full")

    tray._on_session_end = broken
    assert tray._end_session(1, 0) == 0


def test_an_unknown_tray_library_gets_no_icon_rather_than_one_that_blocks_shutdown(tmp_path):
    tray = _tray(tmp_path)
    with pytest.raises(AttributeError):
        tray._watch_session_end(object())


def test_a_hidden_start_shows_the_window_when_the_icon_fails(tmp_path, monkeypatch):
    tray = _tray(tmp_path, start_hidden=True)
    shown = []
    monkeypatch.setattr(tray, "_create_icon", lambda: (_ for _ in ()).throw(OSError("no tray")))
    monkeypatch.setattr(tray, "show_window", lambda: shown.append(True))
    tray.start()
    assert shown == [True]


def test_installing_an_update_quits_through_the_tray(tmp_path, parts, monkeypatch):
    store, _, tracker = parts
    api = _api(tmp_path, store, tracker)
    quits = []
    api._quit_handler = lambda: quits.append(True)
    monkeypatch.setattr(
        "time_manager.updater.download_and_launch_installer", lambda url: {"started": True, "error": ""}
    )
    api.install_update("https://example.invalid/setup.exe")
    assert quits == [True]


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows only")
def test_running_again_asks_the_first_instance_to_show_itself(tmp_path):
    folder = tmp_path / uuid.uuid4().hex
    folder.mkdir()
    assert not single_instance.request_show(folder)  # 실행 중인 앱 없음
    first = single_instance.acquire(folder)
    try:
        assert single_instance.acquire(folder) is None
        assert single_instance.request_show(folder)  # 듣기 시작하기 전의 요청도 전달
        shown = threading.Event()
        first.on_show_requested(shown.set)
        assert shown.wait(3)
        shown.clear()
        assert single_instance.request_show(folder)
        assert shown.wait(3)
    finally:
        first.release()
    assert not single_instance.request_show(folder)


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows only")
def test_the_app_is_told_about_a_shutdown_before_its_launcher():
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32")
    level, flags = wintypes.DWORD(), wintypes.DWORD()
    assert kernel.GetProcessShutdownParameters(ctypes.byref(level), ctypes.byref(flags))
    original = (level.value, flags.value)
    try:
        assert single_instance.end_before_launcher()
        kernel.GetProcessShutdownParameters(ctypes.byref(level), ctypes.byref(flags))
        assert level.value == 0x300 > 0x280  # 0x280: 부모 프로세스가 쓰는 기본값
    finally:
        kernel.SetProcessShutdownParameters(*original)


@pytest.mark.parametrize("frozen", [True, False])
def test_only_the_packaged_app_changes_the_shutdown_order(tmp_path, monkeypatch, frozen):
    from time_manager import app

    calls = []
    monkeypatch.setattr(app, "is_frozen", lambda: frozen)
    monkeypatch.setattr(app, "user_data_dir", lambda root: tmp_path)
    monkeypatch.setattr(app, "_configure_logging", lambda folder: None)
    monkeypatch.setattr(app, "_run", lambda *args: calls.append("run"))
    monkeypatch.setattr(single_instance, "announce_to_installer", lambda: None)
    monkeypatch.setattr(single_instance, "end_before_launcher", lambda: calls.append("order"))

    app.run_webview(tmp_path)

    assert calls == (["order", "run"] if frozen else ["run"])


def test_the_installer_looks_for_the_same_mutex_as_the_app():
    from pathlib import Path

    script = (Path(__file__).resolve().parents[1] / "installer" / "TimeManager.iss").read_text(encoding="utf-8-sig")
    assert f"AppMutex={single_instance.INSTALLER_MUTEX}\n" in script
    assert 'Parameters: "--tray"; Tasks: startup' in script


def test_the_icon_files_have_every_size_and_the_tray_image_is_packaged():
    from pathlib import Path

    from PIL import Image

    root = Path(__file__).resolve().parents[1]
    with Image.open(root / "assets" / "icon.ico") as icon:
        # 16~24: 작업 표시줄·트레이 (100~150% 배율), 256: 탐색기의 큰 아이콘
        assert {(size, size) for size in (16, 20, 24, 32, 40, 48, 64, 128, 256)} <= icon.info["sizes"]
    with Image.open(root / "assets" / "tray.png") as tray_image:
        assert tray_image.size == (64, 64) and tray_image.convert("RGBA").getpixel((0, 0))[3] == 0
    spec = (root / "time_manager_webview.spec").read_text(encoding="utf-8")
    assert '("assets/tray.png", "assets")' in spec and 'icon="assets/icon.ico"' in spec
    assert '"assets" / "tray.png"' in (root / "time_manager" / "webapp.py").read_text(encoding="utf-8")


def test_autostart_opens_in_the_tray():
    assert startup._launch_command().endswith(" --tray")
