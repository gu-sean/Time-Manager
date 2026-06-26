from __future__ import annotations

from datetime import date

from time_manager.formatting import _format_seconds
from time_manager.models import Category
from time_manager.storage import ActivityStore

_CATEGORY_LABELS = {
    Category.PRODUCTIVE: "생산적",
    Category.UNPRODUCTIVE: "비생산적",
    Category.NEUTRAL: "중립",
}

_STAT_BADGES = {
    "total": {"bg": "#EAF1EC", "fg": "#6F9A7C", "glyph": "⏱"},
    Category.PRODUCTIVE: {"bg": "#EAF1EC", "fg": "#6F9A7C", "glyph": "▲"},
    Category.UNPRODUCTIVE: {"bg": "#F8EDE3", "fg": "#CB8056", "glyph": "▽"},
    Category.NEUTRAL: {"bg": "#EBF0F4", "fg": "#7E97AC", "glyph": "●"},
    "score": {"bg": "#F6EFDD", "fg": "#C19A45", "glyph": "★"},
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
