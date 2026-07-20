from __future__ import annotations

import logging
from pathlib import Path

import webview

from time_manager.paths import bundled_root
from time_manager.settings import SettingsStore
from time_manager.storage import ActivityStore
from time_manager.tracker import ActivityTracker
from time_manager.webapi import WebApi

logger = logging.getLogger(__name__)


def run_webview(
    project_root: Path,
    *,
    store: ActivityStore,
    tracker: ActivityTracker,
    settings_store: SettingsStore,
    rules_path: Path,
) -> None:
    index_path = bundled_root(project_root) / "webui" / "dist" / "index.html"
    if not index_path.exists():
        raise FileNotFoundError(
            f"React build not found at {index_path}. Run `npm run build` in webui/ first."
        )

    api = WebApi(store=store, tracker=tracker, settings_store=settings_store, rules_path=rules_path)
    storage_path = settings_store.path.parent / "webview-profile"
    storage_path.mkdir(parents=True, exist_ok=True)
    webview.create_window(
        "시간 관리 매니저",
        url=index_path.as_uri(),
        js_api=api,
        width=1040,
        height=700,
        resizable=True,
        background_color="#F6F5F0",
    )
    try:
        webview.start(debug=False, private_mode=False, storage_path=str(storage_path))
    finally:
        tracker.stop()
