"""Built-in coaching: statistics turned into sentences. No model, no network."""

from __future__ import annotations

from typing import Any

_NOTABLE_CHANGE_MIN = 10


def build_local_coaching(payload: dict[str, Any]) -> dict[str, Any]:
    """Takes the same summary that external providers receive."""
    week = payload["scope"] == "week"
    daily = payload["daily"]
    goals = payload["goals"]
    productive = sum(day["productiveMin"] for day in daily)
    unproductive = sum(day["unproductiveMin"] for day in daily)
    neutral = sum(day["neutralMin"] for day in daily)
    total = productive + unproductive + neutral
    active_days = [d for d in daily if d["productiveMin"] + d["unproductiveMin"] + d["neutralMin"] > 0]
    goal = goals["weeklyProductiveMin"] if week else goals["dailyProductiveMin"]
    limit = goals["unproductiveLimitMin"] * (max(1, len(active_days)) if week else 1)
    partial_day = not week and payload["includesToday"]
    period = "최근 7일" if week else "오늘 지금까지" if partial_day else "이날"

    if goal > 0 and productive >= goal:
        headline = f"{period} 생산 시간 {_minutes(productive)}, 목표를 달성했어요."
    elif goal > 0:
        headline = f"{period} 생산 시간 {_minutes(productive)}, 목표의 {round(productive / goal * 100)}%예요."
    else:
        headline = f"{period} 생산 시간은 {_minutes(productive)}이에요."

    insights: list[str] = []
    comparison = payload.get("comparison")
    if comparison:
        delta = comparison["currentProductiveMin"] - comparison["previousProductiveMin"]
        if abs(delta) >= _NOTABLE_CHANGE_MIN:
            if not week:
                versus = "전날보다"
            elif payload["includesToday"]:
                versus = f"오늘을 뺀 {comparison['comparedDays']}일 기준으로, 지난주 같은 기간보다"
            else:
                versus = "직전 7일보다"
            insights.append(f"{versus} 생산 시간이 {_minutes(abs(delta))} {'늘었어요' if delta > 0 else '줄었어요'}.")
    distraction = _first(payload["topTargets"]["unproductive"])
    if distraction:
        insights.append(f"가장 큰 방해 요소는 {distraction['name']} ({_minutes(distraction['minutes'])})예요.")
    if payload["bestProductiveHours"]:
        hour = payload["bestProductiveHours"][0]
        insights.append(f"생산 시간이 가장 많았던 시간대는 {hour}시~{hour + 1}시예요.")
    top_work = _first(payload["topTargets"]["productive"])
    if top_work:
        insights.append(f"생산 활동 중에는 {top_work['name']}에 가장 많은 시간({_minutes(top_work['minutes'])})을 썼어요.")
    if week and len(active_days) > 1 and productive > 0:
        best = max(active_days, key=lambda d: d["productiveMin"])
        insights.append(f"{best['weekday']}요일에 생산 시간이 가장 많았어요 ({_minutes(best['productiveMin'])}).")

    actions: list[str] = []
    if total and neutral / total >= 0.4:
        actions.append("중립 시간이 많아요. 규칙 탭에서 분류 추천을 확인하면 분석이 정확해져요.")
    if unproductive > limit:
        target = f"{distraction['name']}부터 " if distraction else ""
        actions.append(f"비생산 시간이 상한을 {_minutes(unproductive - limit)} 넘었어요. {target}사용 시간을 정해보세요.")
    if payload["flow"]["focusBlocks25minPlus"] == 0:
        actions.append("25분 이상 이어진 집중이 없었어요. 집중 타이머로 한 번 시작해보세요.")
    if goal > productive and payload["bestProductiveHours"]:
        hour = payload["bestProductiveHours"][0]
        actions.append(f"흐름이 좋았던 {hour}시 전후에 중요한 일을 먼저 배치해보세요.")
    if not actions:
        actions.append("지금의 흐름이 안정적이에요. 같은 패턴을 유지해보세요.")

    return {"headline": headline, "insights": insights[:3], "actions": actions[:3]}


def _first(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    return items[0] if items else None


def _minutes(value: int) -> str:
    hours, minutes = divmod(int(value), 60)
    if not hours:
        return f"{minutes}분"
    return f"{hours}시간 {minutes}분" if minutes else f"{hours}시간"
