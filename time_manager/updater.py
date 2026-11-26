from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

from time_manager import __version__

_log = logging.getLogger(__name__)

_RELEASES_URL = "https://api.github.com/repos/gu-sean/Time-Manager/releases/latest"


def _parse_version(tag: str) -> tuple[int, ...]:
    clean = tag.lstrip("v").strip()
    try:
        return tuple(int(x) for x in clean.split(".") if x.isdigit())
    except ValueError:
        return (0,)


# 확인한 릴리스의 설치 파일 주소 → GitHub 가 알려 준 SHA-256
# - 화면이 넘겨준 주소만으로는 파일을 믿을 수 없음: 확인한 값과 같은 파일만 실행
_expected_sha256: dict[str, str] = {}


def _find_installer_asset(assets: list[dict[str, Any]]) -> dict[str, Any]:
    for asset in assets:
        name = str(asset.get("name", ""))
        if name.lower().endswith(".exe") and "setup" in name.lower():
            return asset
    return {}


def _find_installer_asset_url(assets: list[dict[str, Any]]) -> str:
    return str(_find_installer_asset(assets).get("browser_download_url", ""))


def check_for_update(timeout: float = 6.0) -> dict[str, Any]:
    try:
        req = urllib.request.Request(
            _RELEASES_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"TimeManager/{__version__}",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        tag = data.get("tag_name", "")
        url = data.get("html_url", "")
        latest = tag.lstrip("v").strip()
        has_update = bool(latest) and _parse_version(latest) > _parse_version(__version__)
        asset = _find_installer_asset(data.get("assets", [])) if has_update else {}
        asset_url = str(asset.get("browser_download_url", ""))
        digest = str(asset.get("digest") or "")
        if asset_url and digest.lower().startswith("sha256:"):
            _expected_sha256[asset_url] = digest.split(":", 1)[1].strip().lower()
        return {
            "hasUpdate": has_update,
            "latest": latest,
            "current": __version__,
            "url": url,
            "assetUrl": asset_url,
            "error": "",
        }
    except Exception as exc:
        return {
            "hasUpdate": False,
            "latest": "",
            "current": __version__,
            "url": "",
            "assetUrl": "",
            "error": f"버전 확인 실패: {exc}",
        }


# 파일 하나로 묶은 exe 가 자기 임시 폴더를 알리는 환경 변수
_PACKAGER_VARIABLES = ("_PYI_", "_MEIPASS")


def _installer_environment() -> dict[str, str]:
    """설치 프로그램에 줄 환경: 이 exe 의 임시 폴더 정보를 빼고 전달.

    - 넘기면 설치 뒤 실행되는 새 exe 가 이미 지워진 폴더를 찾다 "Failed to load Python DLL" 로 실패
    """
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith(_PACKAGER_VARIABLES)}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def download_and_launch_installer(asset_url: str, timeout: float = 60.0) -> dict[str, Any]:
    """설치 파일을 내려받아 실행. 호출한 쪽이 앱을 종료하면 됨."""
    if not asset_url:
        return {"started": False, "error": "다운로드 주소가 없습니다."}
    expected = _expected_sha256.get(asset_url)
    if not expected:
        return {
            "started": False,
            "error": "설치 파일을 확인할 정보가 없어 설치하지 않았어요. 업데이트를 다시 확인하거나 릴리스 페이지에서 직접 받으세요.",
        }
    try:
        req = urllib.request.Request(
            asset_url,
            headers={"User-Agent": f"TimeManager/{__version__}"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read()
        if hashlib.sha256(payload).hexdigest() != expected:
            _log.error("Update installer did not match the published SHA-256; not started")
            return {
                "started": False,
                "error": "내려받은 설치 파일이 릴리스에 올린 파일과 달라 실행하지 않았어요. 잠시 후 다시 시도하세요.",
            }
        installer_path = Path(tempfile.gettempdir()) / "TimeManager-Update-Setup.exe"
        installer_path.write_bytes(payload)
        subprocess.Popen([str(installer_path)], close_fds=True, env=_installer_environment())
        return {"started": True, "error": ""}
    except Exception as exc:
        _log.error("Update installer download/launch failed: %s", exc)
        return {"started": False, "error": f"업데이트 설치 실패: {exc}"}
