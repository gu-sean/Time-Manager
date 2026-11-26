import shutil
from pathlib import Path

import pytest

from time_manager.rules import RuleClassifier
from time_manager.settings import SettingsStore
from time_manager.storage import ActivityStore
from time_manager.tracker import ActivityTracker
from time_manager.webapi import WebApi

_REPO_RULES = Path(__file__).resolve().parent.parent / "rules.json"


@pytest.fixture
def api(tmp_path: Path) -> WebApi:
    rules_path = tmp_path / "rules.json"
    shutil.copy(_REPO_RULES, rules_path)
    store = ActivityStore(tmp_path / "activity.sqlite3")
    tracker = ActivityTracker(store=store, classifier=RuleClassifier.from_file(rules_path))
    return WebApi(
        store=store,
        tracker=tracker,
        settings_store=SettingsStore(tmp_path / "settings.json"),
        rules_path=rules_path,
    )
