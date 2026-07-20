import logging
from pathlib import Path
from unittest.mock import patch

import pytest

import main


def test_main_logs_unhandled_exception(caplog) -> None:
    failure = RuntimeError("startup failed")

    with patch("main.run_webview", side_effect=failure), patch("main.handle_crash") as mock_handle_crash, caplog.at_level(
        logging.ERROR
    ):
        with pytest.raises(SystemExit) as exc_info:
            main.main()

    assert exc_info.value.code == 1
    assert "Unhandled Time Manager error" in caplog.text
    assert "startup failed" in caplog.text
    mock_handle_crash.assert_called_once()
    assert mock_handle_crash.call_args.args[0] is failure


def test_main_uses_project_root() -> None:
    with patch("main.run_webview") as run_webview:
        main.main()

    run_webview.assert_called_once_with(Path(main.__file__).resolve().parent)
