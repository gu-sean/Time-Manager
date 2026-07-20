import logging
import sys
from pathlib import Path

from time_manager.app import run_webview
from time_manager.crash_report import handle_crash
from time_manager.paths import user_data_dir


def main() -> None:
    project_root = Path(__file__).resolve().parent
    try:
        run_webview(project_root)
    except Exception as exc:
        logging.getLogger(__name__).exception("Unhandled Time Manager error")
        handle_crash(exc, user_data_dir(project_root))
        sys.exit(1)


if __name__ == "__main__":
    main()
