import json
import unittest
from unittest.mock import MagicMock, patch

from time_manager import updater


def _fake_response(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode("utf-8")
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


class CheckForUpdateTests(unittest.TestCase):
    def test_finds_installer_asset_when_update_available(self) -> None:
        payload = {
            "tag_name": "v99.0.0",
            "html_url": "https://example.com/releases/v99.0.0",
            "assets": [
                {"name": "TimeManager.exe", "browser_download_url": "https://example.com/TimeManager.exe"},
                {"name": "TimeManager-Setup-99.0.0.exe", "browser_download_url": "https://example.com/Setup.exe"},
            ],
        }
        with patch("time_manager.updater.urllib.request.urlopen", return_value=_fake_response(payload)):
            result = updater.check_for_update()

        self.assertTrue(result["hasUpdate"])
        self.assertEqual("https://example.com/Setup.exe", result["assetUrl"])

    def test_no_asset_url_when_no_update(self) -> None:
        payload = {
            "tag_name": f"v{updater.__version__}",
            "html_url": "https://example.com",
            "assets": [{"name": "TimeManager-Setup-0.0.1.exe", "browser_download_url": "https://example.com/Setup.exe"}],
        }
        with patch("time_manager.updater.urllib.request.urlopen", return_value=_fake_response(payload)):
            result = updater.check_for_update()

        self.assertFalse(result["hasUpdate"])
        self.assertEqual("", result["assetUrl"])

    def test_network_failure_returns_error_without_asset_url(self) -> None:
        with patch("time_manager.updater.urllib.request.urlopen", side_effect=OSError("boom")):
            result = updater.check_for_update()

        self.assertFalse(result["hasUpdate"])
        self.assertEqual("", result["assetUrl"])
        self.assertIn("실패", result["error"])


class DownloadAndLaunchInstallerTests(unittest.TestCase):
    def test_missing_url_returns_error_without_network_call(self) -> None:
        with patch("time_manager.updater.urllib.request.urlopen") as mock_urlopen:
            result = updater.download_and_launch_installer("")

        self.assertFalse(result["started"])
        self.assertTrue(result["error"])
        mock_urlopen.assert_not_called()

    def test_success_downloads_and_launches_installer(self) -> None:
        resp = MagicMock()
        resp.read.return_value = b"fake-installer-bytes"
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = False

        with patch("time_manager.updater.urllib.request.urlopen", return_value=resp), patch(
            "time_manager.updater.subprocess.Popen"
        ) as mock_popen, patch("time_manager.updater.Path.write_bytes") as mock_write:
            result = updater.download_and_launch_installer("https://example.com/Setup.exe")

        self.assertTrue(result["started"])
        self.assertEqual("", result["error"])
        mock_write.assert_called_once_with(b"fake-installer-bytes")
        mock_popen.assert_called_once()

    def test_download_failure_returns_error(self) -> None:
        with patch("time_manager.updater.urllib.request.urlopen", side_effect=OSError("network down")):
            result = updater.download_and_launch_installer("https://example.com/Setup.exe")

        self.assertFalse(result["started"])
        self.assertIn("실패", result["error"])


if __name__ == "__main__":
    unittest.main()
