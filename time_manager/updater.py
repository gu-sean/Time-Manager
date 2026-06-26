from __future__ import annotations

import json
import urllib.request
from typing import Any

from time_manager import __version__

_RELEASES_URL = "https://api.github.com/repos/gu-sean/Time-Manager/releases/latest"


def _parse_version(tag: str) -> tuple[int, ...]:
    clean = tag.lstrip("v").strip()
    try:
        return tuple(int(x) for x in clean.split(".") if x.isdigit())
    except ValueError:
        return (0,)


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
            "error": "",
        }
    except Exception as exc:
        return {
            "hasUpdate": False,
            "latest": "",
            "current": __version__,
            "url": "",
            "error": f"버전 확인 실패: {exc}",
        }
