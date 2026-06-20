import ctypes
import time
from ctypes import wintypes
from pathlib import Path

from time_manager.models import ActiveTarget
from time_manager.platforms import PlatformMonitor

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.GetTickCount.restype = wintypes.DWORD


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("dwTime", wintypes.DWORD),
    ]


user32.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
user32.GetLastInputInfo.restype = wintypes.BOOL


class WindowsMonitor(PlatformMonitor):
    browser_processes = {
        "chrome.exe",
        "msedge.exe",
        "brave.exe",
        "vivaldi.exe",
        "opera.exe",
        "firefox.exe",
    }

    def __init__(self, url_poll_seconds: int = 10) -> None:
        self.url_poll_seconds = url_poll_seconds
        self._last_url_lookup_at = 0.0
        self._last_browser_key: tuple[int, str, str] | None = None
        self._last_url: str | None = None
        self.last_status = ""

    def get_active_target(self) -> ActiveTarget:
        hwnd = user32.GetForegroundWindow()
        title = _window_title(hwnd)
        process_path = _process_path(hwnd)
        app_name = Path(process_path).name if process_path else "Unknown"
        url = self._browser_url(hwnd, app_name, title)
        return ActiveTarget(app_name=app_name, window_title=title, url=url)

    def idle_seconds(self) -> int:
        last_input = LASTINPUTINFO()
        last_input.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not user32.GetLastInputInfo(ctypes.byref(last_input)):
            return 0
        elapsed_ms = kernel32.GetTickCount() - last_input.dwTime
        return max(0, int(elapsed_ms / 1000))

    def _browser_url(self, hwnd: int, app_name: str, title: str) -> str | None:
        if app_name.lower() not in self.browser_processes:
            self._last_browser_key = None
            self._last_url = None
            self.last_status = ""
            return None

        now = time.monotonic()
        key = (int(hwnd), app_name, title)
        if key == self._last_browser_key and now - self._last_url_lookup_at < self.url_poll_seconds:
            return self._last_url

        self._last_browser_key = key
        self._last_url_lookup_at = now
        url, status = _active_browser_url(hwnd, app_name)
        self.last_status = status
        self._last_url = url
        return url


def _window_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _process_path(hwnd: int) -> str:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""

    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ""

    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        ok = kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size))
        return buffer.value if ok else ""
    finally:
        kernel32.CloseHandle(handle)


def _active_browser_url(hwnd: int, app_name: str) -> tuple[str | None, str]:
    # 반환값: (url, 진단메시지). 진단메시지가 빈 문자열이면 정상.
    if app_name.lower() not in WindowsMonitor.browser_processes:
        return None, ""

    try:
        import uiautomation as auto
    except ImportError:
        return None, "브라우저 URL 수집 불가: uiautomation 미설치 (pip install uiautomation)"

    try:
        window = auto.ControlFromHandle(hwnd)
        edits = _find_edit_controls(window, max_depth=5)
        for edit in edits:
            value = _control_value(edit)
            if _looks_like_url(value):
                return value, ""
    except Exception as exc:
        return None, f"브라우저 URL 추출 실패: {exc}"
    return None, ""


def _find_edit_controls(control: object, max_depth: int) -> list[object]:
    if max_depth <= 0:
        return []

    found = []
    try:
        if getattr(control, "ControlTypeName", "") == "EditControl":
            found.append(control)
        for child in control.GetChildren():
            found.extend(_find_edit_controls(child, max_depth - 1))
    except Exception:
        return found
    return found


def _control_value(control: object) -> str:
    try:
        pattern = control.GetValuePattern()
        value = pattern.Value
        if value:
            return str(value).strip()
    except Exception:
        pass
    try:
        name = control.Name
        return str(name).strip() if name else ""
    except Exception:
        return ""


def _looks_like_url(value: str) -> bool:
    if not value or " " in value:
        return False
    lower = value.lower()
    return "." in lower and not lower.startswith(("search", "http://localhost:"))
