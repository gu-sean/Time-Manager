"""업데이트 직후 새 버전이 실행돼야 함.

파일 하나로 묶은 exe 는 자기 임시 폴더 위치를 환경 변수로 남김. 설치 프로그램을 거쳐
새 exe 까지 전달되면, 이미 지워진 이전 폴더를 찾다가 "Failed to load Python DLL" 로 실패함.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pytest

from time_manager import __version__, updater

ROOT = Path(__file__).resolve().parents[1]
PYINSTALLER_VARIABLES = {
    "_PYI_APPLICATION_HOME_DIR": r"C:\Temp\_MEI123",
    "_PYI_ARCHIVE_FILE": r"C:\Program Files\TimeManager\TimeManager.exe",
    "_PYI_PARENT_PROCESS_LEVEL": "1",
    "_MEIPASS2": r"C:\Temp\_MEI123",  # PyInstaller 5 이하의 이름
}


@pytest.fixture()
def launched(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict:
    for name, value in PYINSTALLER_VARIABLES.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("KEEP_ME", "yes")
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"installer"))
    seen: dict = {}
    monkeypatch.setattr(updater.subprocess, "Popen", lambda command, **kwargs: seen.update(command=command, **kwargs))
    assert updater.download_and_launch_installer("https://example.invalid/setup.exe")["started"]
    return seen


def test_the_installer_does_not_inherit_this_exe_s_unpack_folder(launched: dict) -> None:
    env = launched["env"]

    assert not set(PYINSTALLER_VARIABLES) & set(env)
    # 새 exe 의 부트로더가 남은 상태를 버리고 새로 시작하도록 요청
    assert env["PYINSTALLER_RESET_ENVIRONMENT"] == "1"


def test_everything_else_is_passed_on(launched: dict) -> None:
    assert launched["env"]["KEEP_ME"] == "yes"
    assert "PATH" in launched["env"] or "Path" in launched["env"]


def test_this_process_keeps_its_own_environment(launched: dict) -> None:
    import os

    assert os.environ["_PYI_APPLICATION_HOME_DIR"] == PYINSTALLER_VARIABLES["_PYI_APPLICATION_HOME_DIR"]
    assert "PYINSTALLER_RESET_ENVIRONMENT" not in os.environ


# -- 설치 프로그램 -------------------------------------------------------------------

def run_section() -> list[str]:
    text = (ROOT / "installer" / "TimeManager.iss").read_text(encoding="utf-8-sig")
    section = text.split("[Run]", 1)[1].split("\n[", 1)[0]
    return [line for line in section.splitlines() if line.strip() and not line.startswith(";")]


def test_the_app_is_started_by_explorer_not_by_the_installer() -> None:
    """v1.1.0 의 업데이트 코드는 고칠 수 없음 → 설치 프로그램이 환경을 넘기지 않아야 함.

    탐색기를 통해 실행하면 새 앱은 바탕 화면의 환경을 받음.
    """
    [line] = run_section()

    assert line.startswith('Filename: "{win}\\explorer.exe"; Parameters: """{app}\\{#AppExe}"""')
    assert "postinstall" in line and "nowait" in line and "skipifsilent" in line
    assert "unchecked" not in line  # "Time Manager 실행" 은 기본 체크 유지


def test_the_version_is_the_same_everywhere() -> None:
    installer = (ROOT / "installer" / "TimeManager.iss").read_text(encoding="utf-8-sig")
    info = (ROOT / "version_info.txt").read_text(encoding="utf-8-sig")
    numbers = ", ".join(__version__.split(".")) + ", 0"

    assert re.search(r'#define AppVersion "(.+)"', installer)[1] == __version__
    assert info.count(f"({numbers})") == 2  # filevers, prodvers
    assert info.count(f'"{__version__}.0"') == 2  # FileVersion, ProductVersion
    assert f"({__version__})" in info  # 상단 안내 주석
