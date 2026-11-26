"""Windows 로그인 시 자동 실행 등록·해제 (레지스트리 HKCU Run 키)."""
from __future__ import annotations

import sys

from time_manager.paths import APP_NAME

_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


# 자동 실행은 창을 열지 않고 트레이에서 시작
TRAY_ARGUMENT = "--tray"


def _launch_command() -> str:
    return f"{_program_command()} {TRAY_ARGUMENT}"


def _program_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    python = pythonw if pythonw.exists() else Path(sys.executable)
    return f'"{python}" "{root / "main.py"}"'


def is_enabled() -> bool:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except Exception:
        return False


def upgrade_command() -> None:
    """이전 버전이 이 프로그램으로 등록한 자동 실행에만 트레이 인자를 붙임. 설치본에서만."""
    if not getattr(sys, "frozen", False):
        return
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH) as key:
            registered, _ = winreg.QueryValueEx(key, APP_NAME)
        if str(registered).lower() == _program_command().lower():
            enable()
    except Exception:  # 등록하지 않았거나 레지스트리를 쓸 수 없음
        return


def enable() -> None:
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _launch_command())


def disable() -> None:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
    except Exception:
        pass
