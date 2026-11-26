"""파일 저장: 강제 종료·디스크 부족에도 반쯤 쓰인 파일이 남지 않게 함."""

from __future__ import annotations

import os
import time
from pathlib import Path

_REPLACE_ATTEMPTS = 5
_RETRY_SECONDS = 0.05


def atomic_write_text(path: Path, text: str) -> None:
    _replace_with(path, lambda temporary: temporary.write_text(text, encoding="utf-8"))


def atomic_write_bytes(path: Path, data: bytes) -> None:
    _replace_with(path, lambda temporary: temporary.write_bytes(data))


def _replace_with(path: Path, write) -> None:
    """옆에 먼저 쓴 뒤 교체: 읽는 쪽은 이전 파일 또는 새 파일만 보게 됨."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        write(temporary)
        for attempt in range(_REPLACE_ATTEMPTS):
            try:
                os.replace(temporary, path)
                return
            except PermissionError:  # 백신·인덱서가 잠깐 점유한 경우
                if attempt == _REPLACE_ATTEMPTS - 1:
                    raise
                time.sleep(_RETRY_SECONDS)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
