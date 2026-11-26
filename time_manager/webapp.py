from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

import webview

from time_manager.paths import bundled_root
from time_manager.settings import SettingsStore
from time_manager.single_instance import WINDOW_TITLE, Instance
from time_manager.storage import ActivityStore
from time_manager.tracker import ActivityTracker
from time_manager.tray import TrayController
from time_manager.webapi import WebApi

logger = logging.getLogger(__name__)


def run_webview(
    project_root: Path,
    *,
    store: ActivityStore,
    tracker: ActivityTracker,
    settings_store: SettingsStore,
    rules_path: Path,
    secure_data: Callable[[], None],
    instance: Instance | None = None,
    start_hidden: bool = False,
) -> None:
    index_path = bundled_root(project_root) / "webui" / "dist" / "index.html"
    if not index_path.exists():
        raise FileNotFoundError(
            f"React build not found at {index_path}. Run `npm run build` in webui/ first."
        )

    api = WebApi(store=store, tracker=tracker, settings_store=settings_store, rules_path=rules_path)
    storage_path = settings_store.path.parent / "webview-profile"
    storage_path.mkdir(parents=True, exist_ok=True)
    window = webview.create_window(
        WINDOW_TITLE,
        url=index_path.as_uri(),
        js_api=api,
        width=1040,
        height=700,
        resizable=True,
        min_size=(760, 560),  # 이보다 작으면 화면 배치가 내용을 담지 못함
        background_color="#F6F5F0",
        hidden=start_hidden,
    )

    def take_first_hint() -> bool:
        if api.settings.tray_hint_shown:
            return False
        api.settings.tray_hint_shown = True
        settings_store.save(api.settings)
        return True

    tray = TrayController(
        window,
        tracker,
        bundled_root(project_root) / "assets" / "icon.ico",
        close_to_tray=lambda: api.settings.close_to_tray,
        take_first_hint=take_first_hint,
        on_session_end=secure_data,
        start_hidden=start_hidden,
    )
    api._quit_handler = tray.quit
    window.events.before_show += tray.attach

    def on_started() -> None:
        tray.start()
        if instance is not None:
            instance.on_show_requested(tray.show_window)

    try:
        webview.start(on_started, debug=False, private_mode=False, storage_path=str(storage_path))
    finally:
        # 트레이 창은 마지막에 없앰: Windows 종료 때 이 창은 암호화가 끝난 뒤에 응답함
        try:
            secure_data()
        finally:
            tray.stop()
