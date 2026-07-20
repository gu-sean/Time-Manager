"""Best-effort crash reporting: on an unhandled top-level exception, capture a
diagnostic snapshot, copy it to the clipboard, and open the bug-report form so
the user can paste it in — instead of the app just silently dying or showing
PyInstaller's raw traceback dialog.
"""
from __future__ import annotations

import ctypes
import logging
import platform
import subprocess
import traceback
import webbrowser
from pathlib import Path

from time_manager import __version__

_log = logging.getLogger(__name__)

REPORT_FORM_URL = (
    "https://docs.google.com/forms/d/e/1FAIpQLSc3P-8LfIng9NUMfu3rNOsP4t22LYyjAURxBZjGadKLY1QMgQ/viewform?usp=publish-editor"
)
_LOG_TAIL_LINES = 60


def _log_tail(log_path: Path, lines: int = _LOG_TAIL_LINES) -> str:
    try:
        content = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(content[-lines:])
    except OSError:
        return "(로그 파일을 읽을 수 없습니다)"


def build_crash_report(exc: BaseException, data_dir: Path) -> str:
    log_path = data_dir / "time-manager.log"
    return "\n".join(
        (
            f"Time Manager v{__version__} 크래시 리포트",
            f"환경: {platform.system()} {platform.release()} ({platform.machine()})",
            f"데이터 폴더: {data_dir}",
            "",
            "== 예외 ==",
            "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            "== 최근 로그 ==",
            _log_tail(log_path),
        )
    )


def _copy_to_clipboard(text: str) -> bool:
    try:
        subprocess.run(["clip"], input=text.encode("utf-16-le"), check=True)
        return True
    except Exception as exc:
        _log.warning("Failed to copy crash report to clipboard: %s", exc)
        return False


def _notify_user(copied: bool) -> None:
    message = (
        "예기치 못한 오류로 앱이 종료됩니다.\n\n"
        + ("진단 정보를 클립보드에 복사했습니다. " if copied else "")
        + "잠시 후 열리는 문제 신고 페이지에 붙여넣어 알려주시면 큰 도움이 됩니다."
    )
    try:
        ctypes.windll.user32.MessageBoxW(None, message, "Time Manager 오류", 0x30)
    except Exception as exc:
        _log.warning("Failed to show crash message box: %s", exc)


def handle_crash(exc: BaseException, data_dir: Path) -> None:
    """Never let this raise — it runs after the app has already failed."""
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        report = build_crash_report(exc, data_dir)
        try:
            (data_dir / "last-crash.txt").write_text(report, encoding="utf-8")
        except OSError:
            pass
        copied = _copy_to_clipboard(report)
        _notify_user(copied)
        webbrowser.open(REPORT_FORM_URL)
    except Exception as exc2:
        _log.error("Crash handler itself failed: %s", exc2)
