import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from time_manager import crash_report


def _make_exc() -> Exception:
    try:
        raise ValueError("boom")
    except ValueError as exc:
        return exc


class BuildCrashReportTests(unittest.TestCase):
    def test_report_includes_exception_and_environment(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            report = crash_report.build_crash_report(_make_exc(), data_dir)

        self.assertIn("ValueError", report)
        self.assertIn("boom", report)
        self.assertIn(str(data_dir), report)

    def test_report_includes_recent_log_lines(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            (data_dir / "time-manager.log").write_text("line1\nline2\nline3\n", encoding="utf-8")
            report = crash_report.build_crash_report(_make_exc(), data_dir)

        self.assertIn("line3", report)

    def test_report_handles_missing_log_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            report = crash_report.build_crash_report(_make_exc(), data_dir)

        self.assertIn("로그 파일을 읽을 수 없습니다", report)


class HandleCrashTests(unittest.TestCase):
    def test_writes_report_file_copies_clipboard_and_opens_form(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "nested"
            with patch("time_manager.crash_report.subprocess.run") as mock_run, patch(
                "time_manager.crash_report.webbrowser.open"
            ) as mock_open, patch("time_manager.crash_report.ctypes.windll.user32.MessageBoxW") as mock_box:
                crash_report.handle_crash(_make_exc(), data_dir)

            crash_file = data_dir / "last-crash.txt"
            self.assertTrue(crash_file.exists())
            self.assertIn("ValueError", crash_file.read_text(encoding="utf-8"))
            mock_run.assert_called_once()
            mock_open.assert_called_once_with(crash_report.REPORT_FORM_URL)
            mock_box.assert_called_once()

    def test_never_raises_even_if_everything_fails(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            with patch("time_manager.crash_report.subprocess.run", side_effect=OSError("no clip")), patch(
                "time_manager.crash_report.webbrowser.open", side_effect=OSError("no browser")
            ), patch("time_manager.crash_report.ctypes.windll.user32.MessageBoxW", side_effect=OSError("no gui")):
                crash_report.handle_crash(_make_exc(), data_dir)  # must not raise


if __name__ == "__main__":
    unittest.main()
