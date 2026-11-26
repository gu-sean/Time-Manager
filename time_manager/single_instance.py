"""데이터 폴더 하나당 앱을 하나만 실행.

- 두 개가 같은 DB 를 쓰면, 한쪽이 종료하며 사용 중인 DB 를 암호화·삭제하려 함
- 설치 파일의 자동 실행과 앱의 자동 실행을 함께 켜면 실제로 두 번 실행됨
"""
from __future__ import annotations

import ctypes
import hashlib
import logging
import sys
import threading
from pathlib import Path
from typing import Callable

WINDOW_TITLE = "시간 관리 매니저"
# installer/TimeManager.iss 의 AppMutex 와 같아야 함: 실행 중이면 설치·제거 전에 종료를 안내
INSTALLER_MUTEX = "TimeManagerAppRunning"
_ERROR_ACCESS_DENIED = 5
_ERROR_ALREADY_EXISTS = 183
_SW_RESTORE = 9
_EVENT_MODIFY_STATE = 0x0002
_WAIT_OBJECT_0 = 0
_ASFW_ANY = -1
_log = logging.getLogger(__name__)


class Instance:
    def __init__(self, handle: int | None, show_event: int | None = None) -> None:
        self._handle = handle
        self._show_event = show_event
        self._released = threading.Event()
        self._listener: threading.Thread | None = None

    def on_show_requested(self, callback: Callable[[], None]) -> None:
        """다시 실행하면 ``callback`` 호출. 트레이에 숨긴 창은 밖에서 열 수 없어 앱이 직접 엶."""
        if not self._show_event or self._listener:
            return

        def wait() -> None:
            library = _kernel32()
            while not self._released.is_set():
                if library.WaitForSingleObject(self._show_event, 300) == _WAIT_OBJECT_0:
                    try:
                        callback()
                    except Exception:
                        _log.exception("could not show the window")

        self._listener = threading.Thread(target=wait, name="show-requests", daemon=True)
        self._listener.start()

    def release(self) -> None:
        self._released.set()
        if self._listener:
            self._listener.join(timeout=2)
            self._listener = None
        if self._show_event:
            _kernel32().CloseHandle(self._show_event)
            self._show_event = None
        if self._handle:
            _kernel32().CloseHandle(self._handle)
            self._handle = None


def _kernel32():
    from ctypes import wintypes

    library = ctypes.WinDLL("kernel32", use_last_error=True)
    library.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    library.CreateMutexW.restype = wintypes.HANDLE
    library.CloseHandle.argtypes = [wintypes.HANDLE]
    library.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    library.CreateEventW.restype = wintypes.HANDLE
    library.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    library.OpenEventW.restype = wintypes.HANDLE
    library.SetEvent.argtypes = [wintypes.HANDLE]
    library.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    library.WaitForSingleObject.restype = wintypes.DWORD
    return library


def _object_name(data_dir: Path) -> str:
    folder = str(Path(data_dir).resolve()).lower()
    return f"Local\\TimeManager-{hashlib.sha256(folder.encode('utf-8')).hexdigest()[:24]}"


def acquire(data_dir: Path) -> Instance | None:
    """이 데이터 폴더를 차지함. 이미 실행 중이면 None.

    - 이름에 폴더를 넣음: 설치본과 소스 실행은 데이터가 달라 함께 실행 가능
    - 프로세스가 끝나면 Windows 가 자동으로 해제 → 비정상 종료 후에도 다시 실행 가능
    """
    if not sys.platform.startswith("win"):
        return Instance(None)
    name = _object_name(data_dir)
    library = _kernel32()
    handle = library.CreateMutexW(None, False, name)
    error = ctypes.get_last_error()
    if not handle:
        if error == _ERROR_ACCESS_DENIED:  # 권한이 다른 실행이 이미 차지함
            return None
        _log.warning("could not check for a running instance (error %d)", error)
        return Instance(None)  # 확인 실패로 실행까지 막지는 않음
    if error == _ERROR_ALREADY_EXISTS:
        library.CloseHandle(handle)
        return None
    return Instance(handle, library.CreateEventW(None, False, False, f"{name}-show") or None)


def announce_to_installer() -> int | None:
    """설치 프로그램이 확인하는 표시를 만듦. 프로세스가 끝날 때까지 유지.

    - 설치 프로그램은 트레이에 숨은 앱을 스스로 닫지 못함
    """
    if not sys.platform.startswith("win"):
        return None
    return _kernel32().CreateMutexW(None, False, INSTALLER_MUTEX) or None


def request_show(data_dir: Path) -> bool:
    """실행 중인 앱에 창을 열어 달라고 요청. 요청을 받을 앱이 없으면 False (이전 버전 등)."""
    if not sys.platform.startswith("win"):
        return False
    library = _kernel32()
    event = library.OpenEventW(_EVENT_MODIFY_STATE, False, f"{_object_name(data_dir)}-show")
    if not event:
        return False
    # 방금 실행한 이 프로세스의 "앞으로 나오기" 권한을 실행 중인 앱에 넘김
    ctypes.WinDLL("user32").AllowSetForegroundWindow(_ASFW_ANY)
    sent = bool(library.SetEvent(event))
    library.CloseHandle(event)
    return sent


def show_running_window(title: str) -> None:
    """이미 실행 중인 창을 앞으로 가져옴 (가능한 경우)."""
    if not sys.platform.startswith("win"):
        return
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32")
    user32.FindWindowW.restype = wintypes.HWND
    hwnd = user32.FindWindowW(None, title)
    if hwnd:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, _SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
