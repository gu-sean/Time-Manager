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

# 이 앱의 기록이 있을 수 없는 이전 날짜
EARLIEST_DAY = date(2000, 1, 1)

CATEGORY_COLORS = {
    Category.PRODUCTIVE: "#128C6E",
    Category.UNPRODUCTIVE: "#D58528",
    Category.NEUTRAL: "#7A82D6",
}


def _parse_day(value: str | None) -> date:
    """요청한 날짜. 없거나 해석할 수 없거나 범위 밖이면 오늘."""
    try:
        day = date.fromisoformat(value) if value else date.today()
    except (TypeError, ValueError):
        return date.today()
    return day if EARLIEST_DAY <= day <= date.today() else date.today()


def _clamp_day(day: date) -> date:
    """날짜 입력칸에는 0001년 같은 값도 넣을 수 있음 → 계산 가능한 범위로 제한."""
    return min(max(day, EARLIEST_DAY), date.today())


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
    """짧은 변화량 (예: "▲ 34분"). 비교 대상은 화면에 한 번만 표시."""
    if delta == 0:
        return "변화 없음"
    arrow = "▲" if delta > 0 else "▼"
    value = _format_seconds(abs(delta)) if not unit else f"{abs(delta)}{unit}"
    return f"{arrow} {value}"


def _delta_tone(key: str, delta: int) -> str:
    """good·bad: 늘면 좋은 것(생산·점수)과 줄면 좋은 것(비생산). 총·중립 시간은 판단하지 않음."""
    direction = {"productive": 1, "score": 1, "unproductive": -1}.get(key, 0)
    if delta == 0 or direction == 0:
        return "neutral"
    return "good" if delta * direction > 0 else "bad"
