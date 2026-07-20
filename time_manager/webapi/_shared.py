from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from time_manager.formatting import _format_seconds
from time_manager.models import Category
from time_manager.storage import ActivityStore

if TYPE_CHECKING:
    from pathlib import Path

    from time_manager.settings import AppSettings, SettingsStore
    from time_manager.tracker import ActivityTracker


class WebApiBase:
    """Mixin base: declares shared instance attributes for type checkers."""

    store: ActivityStore
    tracker: ActivityTracker
    settings: AppSettings
    settings_store: SettingsStore
    rules_path: Path

_CATEGORY_LABELS = {
    Category.PRODUCTIVE: "생산적",
    Category.UNPRODUCTIVE: "비생산적",
    Category.NEUTRAL: "중립",
}

CATEGORY_COLORS = {
    Category.PRODUCTIVE: "#7FA98A",
    Category.UNPRODUCTIVE: "#DB9163",
    Category.NEUTRAL: "#99ABBE",
}


def _day_totals(store: ActivityStore, day: date) -> dict[Category, int]:
    totals = {category: 0 for category in Category}
    for row in store.summary_for_day(day):
        totals[row.category] = row.seconds
    return totals


def _productivity_score(totals: dict[Category, int]) -> int:
    focused = totals[Category.PRODUCTIVE] + totals[Category.UNPRODUCTIVE]
    if focused <= 0:
        return 0
    return round((totals[Category.PRODUCTIVE] / focused) * 100)


def _delta_text(delta: int, *, unit: str = "") -> str:
    arrow = "▲" if delta >= 0 else "▼"
    value = _format_seconds(abs(delta)) if not unit else f"{abs(delta)}{unit}"
    return f"{arrow} {value} (어제 대비)"
