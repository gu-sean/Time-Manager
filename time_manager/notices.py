"""시작 중 발견한 문제 중 사용자에게 알려야 하는 것.

- 시작 과정 어디서든 추가
- 웹 UI가 준비되면 표시
"""

from __future__ import annotations

_notices: list[str] = []


def add(message: str) -> None:
    if message not in _notices:
        _notices.append(message)


def current() -> list[str]:
    return list(_notices)


def clear() -> None:
    _notices.clear()
