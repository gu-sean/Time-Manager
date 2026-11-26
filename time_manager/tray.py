"""트레이 상주: 창을 닫아도 앱과 기록을 유지.

- 창을 숨기는 것은 사용자가 닫은 경우뿐. Windows 종료·로그오프·작업 관리자 종료는 막지 않음
- 트레이 아이콘을 만들지 못하면 숨기지 않음 (다시 열 방법이 없는 앱이 되지 않게 함)
"""
from __future__ import annotations

import ctypes
import logging
import threading
from pathlib import Path
from typing import Any, Callable

_log = logging.getLogger(__name__)
_SW_RESTORE = 9
_WM_QUERYENDSESSION = 0x0011
_WM_ENDSESSION = 0x0016
_READY_TIMEOUT_SECONDS = 5.0
HINT_MESSAGE = "창을 닫아도 계속 기록해요. 끝내려면 트레이 아이콘을 오른쪽 클릭해 '종료'를 누르세요."


class TrayController:
    def __init__(
        self,
        window: Any,
        tracker: Any,
        icon_path: Path,
        *,
        close_to_tray: Callable[[], bool],
        take_first_hint: Callable[[], bool],
        on_session_end: Callable[[], None],
        start_hidden: bool = False,
    ) -> None:
        self.window = window
        self.tracker = tracker
        self.icon_path = icon_path
        self._close_to_tray = close_to_tray
        self._take_first_hint = take_first_hint
        self._on_session_end = on_session_end
        self._start_hidden = start_hidden
        self._icon: Any = None
        self._ready = threading.Event()
        self._quitting = False

    # -- 창 -----------------------------------------------------------------

    def attach(self) -> None:
        """네이티브 창이 만들어진 뒤 호출: 닫기 이유를 알 수 있는 것은 네이티브 이벤트뿐."""
        try:
            self.window.native.FormClosing += self._on_form_closing
        except Exception:
            _log.exception("could not watch the window; closing it will quit the app")

    def _on_form_closing(self, form: Any, args: Any) -> None:
        # UI 스레드에서 실행. 예외가 나가면 안 됨
        try:
            from System.Windows.Forms import CloseReason

            if not self.should_hide(args.CloseReason == CloseReason.UserClosing):
                _log.info("window closing: %s", args.CloseReason)
                return
            args.Cancel = True
            form.Hide()
            threading.Thread(target=self._show_first_hint, daemon=True).start()
        except Exception:
            _log.exception("could not hide the window")

    def should_hide(self, closed_by_user: bool) -> bool:
        return closed_by_user and not self._quitting and self._ready.is_set() and self._close_to_tray()

    def show_window(self) -> None:
        try:
            self.window.show()
            handle = self.window.native.Handle.ToInt64()
            user32 = ctypes.WinDLL("user32")
            if user32.IsIconic(ctypes.c_void_p(handle)):
                user32.ShowWindow(ctypes.c_void_p(handle), _SW_RESTORE)
            user32.SetForegroundWindow(ctypes.c_void_p(handle))
        except Exception:
            _log.exception("could not show the window")

    def quit(self) -> None:
        """앱을 실제로 끝냄 (트레이의 종료, 업데이트 설치)."""
        self._quitting = True
        self.window.destroy()

    # -- 아이콘 ---------------------------------------------------------------

    def start(self) -> None:
        """창이 뜬 뒤 별도 스레드에서 호출."""
        try:
            self._icon = self._create_icon()
            self._icon.run_detached(setup=self._on_icon_ready)
            if not self._ready.wait(_READY_TIMEOUT_SECONDS):
                _log.warning("the tray icon did not appear")
        except Exception:
            _log.exception("could not create the tray icon")
        if self._start_hidden and not self._ready.is_set():
            self.show_window()

    def stop(self) -> None:
        icon, self._icon = self._icon, None
        self._ready.clear()
        if icon is None:
            return
        try:
            icon.stop()
        except Exception:
            _log.exception("could not remove the tray icon")

    def _on_icon_ready(self, icon: Any) -> None:
        icon.visible = True
        self._ready.set()

    def _create_icon(self) -> Any:
        import pystray
        from PIL import Image

        menu = pystray.Menu(
            pystray.MenuItem("Time Manager 열기", lambda: self.show_window(), default=True),
            pystray.MenuItem("기록 일시정지", lambda: self.toggle_pause(), checked=lambda _: self.tracker.is_paused),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("종료", lambda: self.quit()),
        )
        icon = pystray.Icon("TimeManager", Image.open(self.icon_path), "Time Manager", menu)
        self._watch_session_end(icon)
        return icon

    # -- Windows 종료, 로그오프, 설치 프로그램의 앱 닫기 ------------------------------

    def _watch_session_end(self, icon: Any) -> None:
        """pystray 의 창은 모르는 메시지에 0 을 돌려줌 = "종료하지 마라".

        - 반드시 바꿔야 함: 그대로 두면 Windows 종료를 막음
        - pystray 내부 구조가 다르면 여기서 예외 → 아이콘을 만들지 않음
        """
        handlers = icon._message_handlers
        handlers[_WM_QUERYENDSESSION] = lambda wparam, lparam: 1
        handlers[_WM_ENDSESSION] = self._end_session

    def _end_session(self, ending: int, flags: int) -> int:
        if not ending:  # 종료가 취소됨
            return 0
        _log.info("the session is ending")
        # 반환하면 Windows 가 프로세스를 끝낼 수 있음 → 기록 저장·암호화는 여기서 끝냄
        # 창은 닫지 않음: 메인 창이 같은 메시지를 받아 스스로 닫힘 (여기서 닫으면 서로 기다림)
        try:
            self._on_session_end()
        except Exception:
            _log.exception("could not secure the data before the session ended")
        return 0

    def toggle_pause(self) -> None:
        if self.tracker.is_running:
            self.tracker.toggle_pause()
        else:
            self.tracker.start()

    def _show_first_hint(self) -> None:
        try:
            if self._icon is not None and self._take_first_hint():
                self._icon.notify(HINT_MESSAGE, "Time Manager")
        except Exception:
            _log.exception("could not show the tray hint")
