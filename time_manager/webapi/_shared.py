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
    """믹스인 공통 기반: 공유 인스턴스 속성을 타입 검사기에 선언."""

    store: ActivityStore
    tracker: ActivityTracker
    settings: AppSettings
    settings_store: SettingsStore
    rules_path: Path

    def _ai_settings_payload(self) -> dict[str, object]: ...

_CATEGORY_LABELS = {
    Category.PRODUCTIVE: "생산적",
    Category.UNPRODUCTIVE: "비생산적",
    Category.NEUTRAL: "중립",
}

CATEGORY_COLORS = {
    Category.PRODUCTIVE: "#128C6E",
    Category.UNPRODUCTIVE: "#D58528",
    Category.NEUTRAL: "#7A82D6",
}


def _parse_day(value: str | None) -> date:
    """요청한 날짜. 없거나 해석할 수 없으면 오늘."""
    try:
        return date.fromisoformat(value) if value else date.today()
    except (TypeError, ValueError):
        return date.today()


def _parse_category(value: str | None) -> Category | None:
    try:
        return Category(value) if value else None
    except ValueError:
        return None


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
    if delta == 0:
        return "어제와 같음"
    arrow = "▲" if delta > 0 else "▼"
    value = _format_seconds(abs(delta)) if not unit else f"{abs(delta)}{unit}"
    return f"{arrow} {value} (어제 대비)"
