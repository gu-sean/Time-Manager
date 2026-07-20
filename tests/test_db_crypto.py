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
        # Regression test: an interrupted secure-delete during encrypt_and_replace can
        # leave a zeroed, invalid activity.sqlite3 next to a valid .enc backup. On the
        # next launch decrypt_if_needed must ignore the corrupt plain file and restore
        # from the backup instead of letting the app try to open a non-database file.
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "activity.sqlite3"
            enc_path = Path(str(db_path) + ".enc")
            real_content = b"SQLite format 3\x00" + b"real-data"
            db_path.write_bytes(b"\x00" * len(real_content))  # corrupted leftover
            enc_path.write_bytes(Fernet(_FIXED_KEY).encrypt(real_content))

            self.assertTrue(db_crypto.decrypt_if_needed(db_path))
            self.assertEqual(real_content, db_path.read_bytes())

    def test_encrypt_restores_plaintext_when_unlink_fails(self) -> None:
        # Regression test: if the final unlink of the plaintext file fails (e.g. a
        # transient lock from an AV scanner) after it has already been zeroed, the
        # plaintext must be restored rather than left corrupted.
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
