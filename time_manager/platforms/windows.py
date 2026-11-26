import ctypes
import logging
import re
import threading
import time
from collections import deque
from ctypes import wintypes
from pathlib import Path
from urllib.parse import urlsplit

from time_manager.models import ActiveTarget
from time_manager.platforms import PlatformMonitor

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

_log = logging.getLogger(__name__)

# 사용자가 주소창에 입력하는 중: 입력 중인 글은 읽지 않음
TYPING = object()
_NO_ADDRESS_BAR = "브라우저 주소창을 찾지 못했어요"
# 검색 한도. Edge·Chrome 158 의 주소창은 9단계, 페이지를 빼면 전체 컨트롤은 수백 개
_MAX_SEARCH_DEPTH = 20
_MAX_SEARCH_CONTROLS = 1500
# 점으로 나뉜 이름 + 글자로 된 최상위 도메인
_HOST_NAME = re.compile(r"^(?:[\w-]+\.)+(?:[^\W\d_]{2,}|xn--[a-z0-9-]+)$")
_IPV4 = re.compile(r"^(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)$")
_com = threading.local()

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
        "whale.exe",
    }

    def __init__(self, url_poll_seconds: int = 10) -> None:
        self.url_poll_seconds = url_poll_seconds
        self._last_url_lookup_at = 0.0
        self._last_browser_key: tuple[int, str, str] | None = None
        self._last_url: str | None = None
        # 주소를 마지막으로 읽은 (창, 앱, 제목): 같은 화면에서만 그 주소를 이어 씀
        self._url_page: tuple[int, str, str] | None = None
        self.last_status = ""

    def get_active_target(self) -> ActiveTarget:
        hwnd = user32.GetForegroundWindow()
        title = _window_title(hwnd)
        process_path = _process_path(hwnd)
        app_name = Path(process_path).name if process_path else "Unknown"
        url = self._browser_url(hwnd, app_name, title)
        return ActiveTarget(app_name=app_name, window_title=title, url=url, process_id=_process_id(hwnd))

    def idle_seconds(self) -> int:
        last_input = LASTINPUTINFO()
        last_input.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not user32.GetLastInputInfo(ctypes.byref(last_input)):
            return 0
        # 32비트 틱은 49.7일마다 0 으로 돌아감 → 차이도 32비트로 계산
        elapsed_ms = (kernel32.GetTickCount() - last_input.dwTime) & 0xFFFFFFFF
        return max(0, int(elapsed_ms / 1000))

    def _browser_url(self, hwnd: int, app_name: str, title: str) -> str | None:
        if app_name.lower() not in self.browser_processes:
            self._last_browser_key = None
            self._last_url = None
            self._url_page = None
            self.last_status = ""
            return None

        now = time.monotonic()
        key = (int(hwnd), app_name, title)
        if key == self._last_browser_key and now - self._last_url_lookup_at < self.url_poll_seconds:
            return self._last_url

        self._last_browser_key = key
        self._last_url_lookup_at = now
        url, status = _active_browser_url(hwnd, app_name)
        if status and status != self.last_status:
            _log.warning("%s", status)  # 주소·창 제목은 남기지 않음
        self.last_status = status

        if url is TYPING or (url is None and status):
            # 입력 중이거나 주소창이 가려짐(전체 화면 등): 같은 화면이면 직전 주소 유지
            if url is TYPING:
                self._last_url_lookup_at = 0.0  # 입력이 끝나면 바로 다시 읽음
            self._last_url = self._last_url if key == self._url_page else None
            return self._last_url

        self._last_url = url
        self._url_page = key if url else None
        return url


def _window_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _process_id(hwnd: int) -> int | None:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value or None


def _process_path(hwnd: int) -> str:
    pid = _process_id(hwnd)
    if not pid:
        return ""

    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""

    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        ok = kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size))
        return buffer.value if ok else ""
    finally:
        kernel32.CloseHandle(handle)


def _active_browser_url(hwnd: int, app_name: str) -> tuple[object, str]:
    # 반환값: (주소 | None | TYPING, 진단 메시지). 메시지가 빈 문자열이면 정상
    if app_name.lower() not in WindowsMonitor.browser_processes:
        return None, ""

    try:
        import uiautomation as auto
    except ImportError:
        return None, "브라우저 URL 수집 불가: uiautomation 미설치 (pip install uiautomation)"

    try:
        # UI 자동화는 스레드마다 초기화가 필요. 스레드가 사는 동안 유지
        if not hasattr(_com, "initializer"):
            _com.initializer = auto.UIAutomationInitializerInThread()
        return _read_address_bar(auto.ControlFromHandle(hwnd))
    except Exception as exc:
        return None, f"브라우저 URL 추출 실패: {type(exc).__name__}"


def _read_address_bar(window: object) -> tuple[object, str]:
    bar = _find_address_bar(window)
    if bar is None:
        return None, _NO_ADDRESS_BAR
    if bar.HasKeyboardFocus:
        return TYPING, ""
    try:
        value = str(bar.GetValuePattern().Value or "").strip()  # 컨트롤 이름은 주소가 아님
    except Exception:
        return None, "브라우저 주소창의 값을 읽지 못했어요"
    return (value if _looks_like_url(value) else None), ""


def _find_address_bar(window: object) -> object | None:
    """주소창 컨트롤. 웹 페이지(Document) 안은 살펴보지 않음.

    - Chromium 계열은 클래스 이름이 ``OmniboxViewViews``
    - 그 외 브라우저는 도구 모음 안의 첫 입력칸
    - 이메일·메모 같은 페이지의 입력값이 주소로 저장되면 안 됨
    """
    queue = deque([(window, 1, False)])
    in_a_toolbar = None
    seen = 0
    while queue and seen < _MAX_SEARCH_CONTROLS:
        control, depth, below_toolbar = queue.popleft()
        seen += 1
        try:
            kind = control.ControlTypeName
            if kind == "DocumentControl":
                continue
            if kind == "EditControl":
                if str(control.ClassName).endswith("OmniboxViewViews"):
                    return control
                if below_toolbar and in_a_toolbar is None:
                    in_a_toolbar = control
                continue
            if depth < _MAX_SEARCH_DEPTH:
                below = below_toolbar or kind == "ToolBarControl"
                queue.extend((child, depth + 1, below) for child in control.GetChildren())
        except Exception:  # 살펴보는 중에 사라진 컨트롤
            continue
    return in_a_toolbar


def _looks_like_url(value: str) -> bool:
    """웹 주소인지 확인. 검색어, 이메일, 파일 경로, 브라우저 내부 주소는 제외."""
    if not value or any(char.isspace() for char in value):
        return False
    lower = value.lower()
    if lower.startswith(("search", "http://localhost:")):
        return False
    if "://" in lower and not lower.startswith(("http://", "https://")):
        return False
    try:
        parts = urlsplit(value if "://" in value else f"https://{value}")
        parts.port  # 포트 형식이 잘못되면 ValueError 발생
    except ValueError:
        return False
    if "@" in parts.netloc:
        return False
    host = parts.hostname or ""
    return bool(_HOST_NAME.match(host) or _IPV4.match(host))
