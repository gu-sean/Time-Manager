import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cryptography.fernet import Fernet

from time_manager import db_crypto

_FIXED_KEY = Fernet.generate_key()


class DbCryptoTests(unittest.TestCase):
    def setUp(self) -> None:
        self._key_patch = patch("time_manager.db_crypto._get_or_create_key", return_value=_FIXED_KEY)
        self._key_patch.start()
        self.addCleanup(self._key_patch.stop)

    def test_encrypt_then_decrypt_roundtrip(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "activity.sqlite3"
            content = b"SQLite format 3\x00" + b"rest-of-db"
            db_path.write_bytes(content)

            self.assertTrue(db_crypto.encrypt_and_replace(db_path))
            self.assertFalse(db_path.exists())
            enc_path = Path(str(db_path) + ".enc")
            self.assertTrue(enc_path.exists())

            self.assertTrue(db_crypto.decrypt_if_needed(db_path))
            self.assertEqual(content, db_path.read_bytes())

    def test_decrypt_skips_when_valid_plain_file_present(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "activity.sqlite3"
            enc_path = Path(str(db_path) + ".enc")
            plain_content = b"SQLite format 3\x00" + b"current-data"
            db_path.write_bytes(plain_content)
            enc_path.write_bytes(Fernet(_FIXED_KEY).encrypt(b"SQLite format 3\x00stale-backup"))

            self.assertFalse(db_crypto.decrypt_if_needed(db_path))
            self.assertEqual(plain_content, db_path.read_bytes())

    def test_decrypt_recovers_from_corrupted_plain_file(self) -> None:
        # 회귀 테스트: encrypt_and_replace 의 안전 삭제가 중단되면
        # 정상 .enc 옆에 0 으로 채워진 activity.sqlite3 가 남을 수 있음
        # → 다음 실행의 decrypt_if_needed 는 손상된 평문을 무시하고 백업에서 복구해야 함
        # (DB 가 아닌 파일을 열려고 하면 안 됨)
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "activity.sqlite3"
            enc_path = Path(str(db_path) + ".enc")
            real_content = b"SQLite format 3\x00" + b"real-data"
            db_path.write_bytes(b"\x00" * len(real_content))  # 손상된 잔여 파일
            enc_path.write_bytes(Fernet(_FIXED_KEY).encrypt(real_content))

            self.assertTrue(db_crypto.decrypt_if_needed(db_path))
            self.assertEqual(real_content, db_path.read_bytes())

    def test_encrypt_restores_plaintext_when_unlink_fails(self) -> None:
        # 회귀 테스트: 평문을 0 으로 채운 뒤 마지막 삭제가 실패하면 (백신의 일시적 잠금 등)
        # 손상된 채 두지 말고 평문을 되돌려야 함
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "activity.sqlite3"
            content = b"SQLite format 3\x00" + b"rest-of-db"
            db_path.write_bytes(content)

            with patch.object(Path, "unlink", side_effect=OSError("file in use")):
                self.assertTrue(db_crypto.encrypt_and_replace(db_path))

            self.assertTrue(db_path.exists())
            self.assertEqual(content, db_path.read_bytes())
            enc_path = Path(str(db_path) + ".enc")
            self.assertTrue(enc_path.exists())


if __name__ == "__main__":
    unittest.main()
