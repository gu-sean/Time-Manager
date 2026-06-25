import logging
from pathlib import Path

from time_manager.paths import ensure_writable_rules, user_data_dir
from time_manager.rules import RuleClassifier
from time_manager.settings import SettingsStore
from time_manager.storage import ActivityStore
from time_manager.tracker import ActivityTracker


def _configure_logging(data_dir: Path) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / "time-manager.log"
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    for handler in list(logger.handlers):
        if getattr(handler, "_time_manager_file_handler", False):
            logger.removeHandler(handler)
            handler.close()
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler._time_manager_file_handler = True
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    return log_path


def _bootstrap(project_root: Path):
    data_dir = user_data_dir(project_root)
    log_path = _configure_logging(data_dir)
    logging.getLogger(__name__).info("Starting Time Manager with data dir %s and log %s", data_dir, log_path)
    rules_path = ensure_writable_rules(project_root)
    settings_store = SettingsStore(data_dir / "settings.json")
    settings = settings_store.load_or_create()
    store = ActivityStore(data_dir / "activity.sqlite3")
    store.purge_older_than(settings.retention_days)
    classifier = RuleClassifier.from_file(rules_path)
    tracker = ActivityTracker(
        store=store,
        classifier=classifier,
        exclude_self_app=settings.exclude_self_app,
        store_domain_only=settings.store_domain_only,
        store_window_titles=settings.store_window_titles,
        unproductive_alert_seconds=settings.unproductive_limit_minutes * 60,
    )
    if hasattr(tracker.notifier, "set_enabled"):
        tracker.notifier.set_enabled(settings.notifications_enabled)
    return rules_path, settings_store, settings, store, tracker


def run_webview(project_root: Path) -> None:
    from time_manager.webapp import run_webview as _run_webview

    rules_path, settings_store, _settings, store, tracker = _bootstrap(project_root)
    tracker.start()
    _run_webview(project_root, store=store, tracker=tracker, settings_store=settings_store, rules_path=rules_path)
