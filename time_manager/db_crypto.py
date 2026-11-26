"""SQLite DB 저장 암호화: Fernet (AES-128-CBC + HMAC-SHA256).

키 관리:

- 최초 실행: Fernet.generate_key() 로 무작위 32바이트 키 생성
- `keyring` 라이브러리로 Windows 자격 증명 관리자에 저장
- keyring 실패 시: PC 이름·사용자 이름에서 PBKDF2 로 고정 키 유도

한계:

- 앱 실행 중에는 DB 파일이 복호화된 상태로 디스크에 있음
- 보호 범위는 저장 상태의 데이터 (기기 도난, 오프라인 파일 접근)
- 진짜 페이지 단위 암호화는 SQLCipher (https://www.zetetic.net/sqlcipher/) 필요: 네이티브 빌드 과정이 필요함
"""
from __future__ import annotations

import base64
import getpass
import hashlib
import logging
import os
import platform
import sqlite3
from datetime import datetime
from pathlib import Path

from time_manager import notices
from time_manager.fileio import atomic_write_bytes

_log = logging.getLogger(__name__)

_KEYRING_SERVICE = "TimeManager"
_KEYRING_USER = "db-encryption-key"
_ENC_SUFFIX = ".enc"
_SQLITE_HEADER = b"SQLite format 3\x00"


def _looks_like_sqlite(path: Path) -> bool:
    """DB 를 열지 않고 SQLite 파일 헤더(매직 바이트) 확인."""
    try:
        with path.open("rb") as fh:
            return fh.read(len(_SQLITE_HEADER)) == _SQLITE_HEADER
    except OSError:
        return False


def _get_or_create_key() -> bytes:
    """Fernet 키(URL-safe base64 44바이트) 반환. keyring 에 없으면 저장."""
    try:
        import keyring  # type: ignore[import-untyped]
        stored = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USER)
        if stored:
            return stored.encode()
        from cryptography.fernet import Fernet
        key = Fernet.generate_key()
        keyring.set_password(_KEYRING_SERVICE, _KEYRING_USER, key.decode())
        _log.info("Generated new DB encryption key and stored in Credential Manager")
        return key
    except Exception as exc:
        _log.warning("keyring unavailable — using machine-derived key fallback: %s", exc)
        return _machine_derived_key()


def _machine_derived_key() -> bytes:
    seed = f"{platform.node()}\x00{getpass.getuser()}\x00TimeManager-v1"
    raw = hashlib.pbkdf2_hmac("sha256", seed.encode(), b"TM-db-salt-v1", 200_000, dklen=32)
    return base64.urlsafe_b64encode(raw)


def decrypt_if_needed(db_path: Path) -> bool:
    """평문 파일이 없고 암호화 파일만 있으면 ``db_path.enc`` → ``db_path`` 복호화.

    - 복호화했으면 True
    """
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        _log.debug("cryptography not installed — skipping DB decryption")
        return False

    enc_path = Path(str(db_path) + _ENC_SUFFIX)
    if not enc_path.exists():
        return False
    if db_path.exists():
        if _looks_like_sqlite(db_path):
            # 평문 파일이 있으면 그것을 사용 (직전 암호화 전에 비정상 종료한 경우)
            _log.info("Plain DB exists alongside %s — skipping decrypt", enc_path.name)
            return False
        _log.warning(
            "%s exists but is not a valid SQLite file (leftover from an interrupted "
            "encrypt) — ignoring it and decrypting from %s instead", db_path.name, enc_path.name
        )
    ciphertext = enc_path.read_bytes()  # 읽기 실패는 암호 문제가 아님 → 시작 중단
    try:
        plaintext = _decrypt_with_any_key(ciphertext)
    except Exception as exc:
        _log.error("DB decryption failed (%s) — app will open without prior data", type(exc).__name__)
        _set_aside_unreadable(enc_path)
        return False
    _set_aside_stale_sidecars(db_path)
    # 쓰기 실패(디스크 부족 등)는 시작 중단: .enc 는 그대로, 반쯤 쓰인 평문도 남지 않음
    atomic_write_bytes(db_path, plaintext)
    _log.info("DB decrypted: %s → %s", enc_path.name, db_path.name)
    return True


def _decrypt_with_any_key(ciphertext: bytes) -> bytes:
    """자격 증명의 키, 다음으로 대체 키.

    - 암호화할 때 자격 증명 저장소가 잠깐 실패하면 대체 키가 쓰임 → 둘 다 시도해야 열림
    """
    from cryptography.fernet import Fernet, InvalidToken

    for key_of in (_get_or_create_key, _machine_derived_key):
        try:
            return Fernet(key_of()).decrypt(ciphertext)
        except (InvalidToken, ValueError):  # ValueError: 저장된 키의 형식이 잘못됨
            continue
    raise InvalidToken


def _set_aside_stale_sidecars(db_path: Path) -> None:
    """복호화한 DB 옆에 다른 DB 의 WAL 이 남아 있으면 섞여 손상될 수 있음 → 삭제 대신 옮김."""
    stamp = f"{datetime.now():%Y%m%d-%H%M%S-%f}"
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{db_path}{suffix}")
        if sidecar.exists():
            os.replace(sidecar, sidecar.with_name(f"{sidecar.name}.stale-{stamp}"))


def _set_aside_unreadable(enc_path: Path) -> None:
    """빈 상태로 시작하기 전에 암호화된 기록을 다른 이름으로 옮김.

    - 종료 시 (빈) DB 가 ``enc_path`` 에 암호화되므로, 그대로 두면 기존 기록이 파괴됨
    - 키를 일시적으로 못 읽은 것일 수 있어 파일은 보관
    - 옮기지 못하면 예외 발생 → 앱 시작 중단
    """
    kept = enc_path.with_name(f"{enc_path.name}.unreadable-{datetime.now():%Y%m%d-%H%M%S-%f}")
    os.replace(enc_path, kept)
    notices.add(
        "이전 활동 기록의 암호를 풀지 못해 새 기록으로 시작했어요. 기존 기록은 삭제하지 않고 "
        f"'{kept}' 파일로 보관했습니다."
    )


def _merge_wal(db_path: Path) -> None:
    """WAL 에만 있는 기록을 본 DB 파일로 합침. 합치지 못하면 예외.

    - 암호화는 본 파일만 읽음 → 합치지 않으면 최근 기록(처음이면 테이블까지)이 빠짐
    """
    wal = Path(f"{db_path}-wal")
    if not wal.exists() or wal.stat().st_size == 0:
        return
    connection = sqlite3.connect(db_path, timeout=5)
    try:
        busy = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0]
    finally:
        connection.close()
    if busy:
        raise RuntimeError("the database is still in use, so its recent records cannot be merged")


def encrypt_and_replace(db_path: Path) -> bool:
    """``db_path`` → ``db_path.enc`` 암호화 후 평문 파일을 안전 삭제.

    - SQLite WAL/SHM 보조 파일도 제거
    - 성공하면 True
    """
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        _log.debug("cryptography not installed — skipping DB encryption")
        return False

    if not db_path.exists():
        return False
    enc_path = Path(str(db_path) + _ENC_SUFFIX)
    try:
        key = _get_or_create_key()
        _merge_wal(db_path)  # 실패하면 이전 .enc 와 평문을 그대로 둠
        original = db_path.read_bytes()
        ciphertext = Fernet(key).encrypt(original)
        atomic_write_bytes(enc_path, ciphertext)  # 쓰기에 실패해도 이전 사본은 유지
        # WAL/SHM 을 먼저 제거 (본 파일을 참조함)
        for sidecar_suffix in ("-wal", "-shm"):
            sidecar = Path(str(db_path) + sidecar_suffix)
            try:
                sidecar.unlink(missing_ok=True)
            except OSError:
                pass
        _zero_and_delete(db_path, original)
        _log.info("DB encrypted → %s", enc_path.name)
        return True
    except Exception as exc:
        _log.error("DB encryption failed: %s", exc)
        return False


def _zero_and_delete(path: Path, original: bytes) -> None:
    """0 으로 덮어쓴 뒤 삭제 (단순한 파일 복구 시도를 막는 수준).

    - 실행 시점에 ``enc_path`` 에는 ``original`` 의 암호화 사본이 이미 있음
    - 백신·인덱서가 잠가 삭제에 실패하면 ``original`` 을 되돌림
    - 0 으로 채워진 못 읽는 파일을 남기는 것보다 이번 한 번 평문으로 두는 편이 안전
    """
    try:
        size = path.stat().st_size
        with path.open("r+b") as fh:
            fh.write(b"\x00" * size)
            fh.flush()
            os.fsync(fh.fileno())
        path.unlink()
    except OSError as exc:
        _log.warning(
            "Could not securely delete plaintext DB (%s) — restoring it so it stays "
            "a valid SQLite file until the next successful close", exc
        )
        try:
            path.write_bytes(original)
        except OSError:
            pass
