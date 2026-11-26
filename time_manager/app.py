import logging
import logging.handlers
import threading
from pathlib import Path

from time_manager import single_instance, startup
from time_manager.paths import ensure_writable_rules, is_frozen, user_data_dir
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
    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
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
        store_domain_only=settings.store_domain_only,
        store_window_titles=settings.store_window_titles,
        unproductive_alert_seconds=settings.unproductive_limit_minutes * 60,
        work_end_hour=settings.work_end_hour,
        daily_goal_seconds=settings.daily_goal_minutes * 60,
        idle_threshold_seconds=settings.idle_minutes * 60,
        record_media=settings.record_media,
        trim_idle_time=settings.trim_idle_time,
    )
    if hasattr(tracker.notifier, "set_enabled"):
        tracker.notifier.set_enabled(settings.notifications_enabled)
    return rules_path, settings_store, settings, store, tracker


def run_webview(project_root: Path, *, start_hidden: bool = False) -> None:
    data_dir = user_data_dir(project_root)
    _configure_logging(data_dir)  # 가장 먼저: 복호화의 성공·실패도 로그에 남김

    instance = single_instance.acquire(data_dir)
    if instance is None:
        logging.getLogger(__name__).info("Time Manager is already running")
        # 자동 실행이 두 번 일어난 경우에는 창을 열지 않음
        if not start_hidden and not single_instance.request_show(data_dir):
            single_instance.show_running_window(single_instance.WINDOW_TITLE)
        return
    if is_frozen():  # 설치본만: 소스로 실행 중이라는 이유로 설치를 막지 않음
        single_instance.announce_to_installer()
    try:
        _run(project_root, data_dir, instance, start_hidden)
    finally:
        instance.release()


def _run(project_root: Path, data_dir: Path, instance: single_instance.Instance, start_hidden: bool) -> None:
    from time_manager.webapp import run_webview as _run_webview
    from time_manager.db_crypto import decrypt_if_needed, encrypt_and_replace

    db_path = data_dir / "activity.sqlite3"
    decrypt_if_needed(db_path)

    rules_path, settings_store, _settings, store, tracker = _bootstrap(project_root)
    securing = threading.Lock()

    def secure_data() -> None:
        """기록을 멈추고 DB 를 암호화. 여러 번 불러도 됨.

        - 앱이 끝날 때, 그리고 Windows 종료처럼 끝까지 실행되지 못할 수 있는 때에 호출
        """
        with securing:
            tracker.stop()
            store.shutdown()
            encrypt_and_replace(db_path)

    startup.upgrade_command()
    tracker.start()
    try:
        _run_webview(
            project_root, store=store, tracker=tracker, settings_store=settings_store, rules_path=rules_path,
            secure_data=secure_data, instance=instance, start_hidden=start_hidden,
        )
    finally:
        secure_data()
