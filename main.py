import logging
from pathlib import Path

from time_manager.app import run_webview


def main() -> None:
    try:
        run_webview(Path(__file__).resolve().parent)
    except Exception:
        logging.getLogger(__name__).exception("Unhandled Time Manager error")
        raise


if __name__ == "__main__":
    main()
