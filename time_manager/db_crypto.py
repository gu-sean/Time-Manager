"""Encrypt-at-rest for the SQLite database using Fernet (AES-128-CBC + HMAC-SHA256).

Key lifecycle:
  - First run: Fernet.generate_key() produces a random 32-byte key.
  - The key is stored in Windows Credential Manager via the `keyring` library.
  - Fallback: derive a stable key from machine+user with PBKDF2 when keyring fails.

Trade-off:
  The database file is decrypted on disk while the app is running. This protects data
  at rest (device theft, offline file access). True page-level encryption requires
  SQLCipher (https://www.zetetic.net/sqlcipher/), which needs a native build pipeline.
"""
from __future__ import annotations

import base64
import getpass
import hashlib
import logging
import os
import platform
from pathlib import Path

_log = logging.getLogger(__name__)

_KEYRING_SERVICE = "TimeManager"
_KEYRING_USER = "db-encryption-key"
_ENC_SUFFIX = ".enc"
_SQLITE_HEADER = b"SQLite format 3\x00"


def _looks_like_sqlite(path: Path) -> bool:
    """Check the SQLite file-header magic bytes without opening a DB connection."""
    try:
        with path.open("rb") as fh:
            return fh.read(len(_SQLITE_HEADER)) == _SQLITE_HEADER
    except OSError:
        return False


def _get_or_create_key() -> bytes:
    """Return a Fernet key (44-byte URL-safe base64), persisting it in keyring if absent."""
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
    """Decrypt ``db_path.enc`` → ``db_path`` if the encrypted file exists but the plain one does not.

    Returns True when decryption was performed.
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
            # Plain file already present (possible crash before last encrypt); prefer it.
            _log.info("Plain DB exists alongside %s — skipping decrypt", enc_path.name)
            return False
        _log.warning(
            "%s exists but is not a valid SQLite file (leftover from an interrupted "
            "encrypt) — ignoring it and decrypting from %s instead", db_path.name, enc_path.name
        )
    try:
        key = _get_or_create_key()
        plaintext = Fernet(key).decrypt(enc_path.read_bytes())
        db_path.write_bytes(plaintext)
        _log.info("DB decrypted: %s → %s", enc_path.name, db_path.name)
        return True
    except Exception as exc:
        _log.error("DB decryption failed (%s) — app will open without prior data", exc)
        return False


def encrypt_and_replace(db_path: Path) -> bool:
    """Encrypt ``db_path`` → ``db_path.enc`` then securely erase the plaintext file.

    Also removes SQLite WAL/SHM sidecars.  Returns True on success.
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
        original = db_path.read_bytes()
        ciphertext = Fernet(key).encrypt(original)
        enc_path.write_bytes(ciphertext)
        # Remove WAL/SHM sidecars first (they reference the main file).
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
    """Overwrite with zeros then delete — basic protection against trivial file recovery.

    ``enc_path`` already holds a valid encrypted copy of ``original`` by the time this
    runs. If a concurrent process (AV scanner, indexer) holds a transient lock on
    ``path`` and the final unlink fails after we've already zeroed it, restore
    ``original`` instead of leaving a zeroed, unreadable file behind — the file is
    still redundant with the .enc backup, so leaving it as plaintext this one time is
    safer than corrupting it.
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
