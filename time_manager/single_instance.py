"""데이터 폴더 하나당 앱을 하나만 실행.

- 두 개가 같은 DB 를 쓰면, 한쪽이 종료하며 사용 중인 DB 를 암호화·삭제하려 함
- 설치 파일의 자동 실행과 앱의 자동 실행을 함께 켜면 실제로 두 번 실행됨
"""
from __future__ import annotations

import ctypes
import hashlib
import logging
import sys
from pathlib import Path

WINDOW_TITLE = "시간 관리 매니저"
_ERROR_ACCESS_DENIED = 5
_ERROR_ALREADY_EXISTS = 183
_SW_RESTORE = 9
_log = logging.getLogger(__name__)


class Instance:
    def __init__(self, handle: int | None) -> None:
        self._handle = handle

    def release(self) -> None:
        if self._handle:
            _kernel32().CloseHandle(self._handle)
            self._handle = None


def _kernel32():
    from ctypes import wintypes

    library = ctypes.WinDLL("kernel32", use_last_error=True)
    library.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    library.CreateMutexW.restype = wintypes.HANDLE
    library.CloseHandle.argtypes = [wintypes.HANDLE]
    return library


def acquire(data_dir: Path) -> Instance | None:
    """이 데이터 폴더를 차지함. 이미 실행 중이면 None.

    - 이름에 폴더를 넣음: 설치본과 소스 실행은 데이터가 달라 함께 실행 가능
    - 프로세스가 끝나면 Windows 가 자동으로 해제 → 비정상 종료 후에도 다시 실행 가능
    """
    if not sys.platform.startswith("win"):
        return Instance(None)
    folder = str(Path(data_dir).resolve()).lower()
    name = f"Local\\TimeManager-{hashlib.sha256(folder.encode('utf-8')).hexdigest()[:24]}"
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
    return Instance(handle)


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
