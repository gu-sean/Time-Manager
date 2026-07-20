from __future__ import annotations

import json
import logging
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


def _find_installer_asset_url(assets: list[dict[str, Any]]) -> str:
    for asset in assets:
        name = str(asset.get("name", ""))
        if name.lower().endswith(".exe") and "setup" in name.lower():
            return str(asset.get("browser_download_url", ""))
    return ""


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
        return {
            "hasUpdate": has_update,
            "latest": latest,
            "current": __version__,
            "url": url,
            "assetUrl": _find_installer_asset_url(data.get("assets", [])) if has_update else "",
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


def download_and_launch_installer(asset_url: str, timeout: float = 60.0) -> dict[str, Any]:
    """Download the installer asset and launch it, ready for the caller to quit the app."""
    if not asset_url:
        return {"started": False, "error": "다운로드 주소가 없습니다."}
    try:
        req = urllib.request.Request(
            asset_url,
            headers={"User-Agent": f"TimeManager/{__version__}"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read()
        installer_path = Path(tempfile.gettempdir()) / "TimeManager-Update-Setup.exe"
        installer_path.write_bytes(payload)
        subprocess.Popen([str(installer_path)], close_fds=True)
        return {"started": True, "error": ""}
    except Exception as exc:
        _log.error("Update installer download/launch failed: %s", exc)
        return {"started": False, "error": f"업데이트 설치 실패: {exc}"}
