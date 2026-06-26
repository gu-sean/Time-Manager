from __future__ import annotations

from datetime import date
from typing import Any

from time_manager.formatting import _format_seconds, _truncate
from time_manager.models import Category

from ._shared import CATEGORY_COLORS, WebApiBase, _CATEGORY_LABELS, _day_totals


class ReviewMixin(WebApiBase):
    def get_review(self, date_iso: str | None = None) -> dict[str, Any]:
        selected_day = date.fromisoformat(date_iso) if date_iso else date.today()
        totals = _day_totals(self.store, selected_day)
        total_seconds = sum(totals.values())
        segments = []
        if total_seconds > 0:
            for category in (Category.PRODUCTIVE, Category.UNPRODUCTIVE, Category.NEUTRAL):
                seconds = totals[category]
                if seconds <= 0:
                    continue
                segments.append(
                    {
                        "category": category.value,
                        "label": _CATEGORY_LABELS[category],
                        "color": CATEGORY_COLORS[category],
                        "pct": round((seconds / total_seconds) * 100),
                        "time": _format_seconds(seconds),
                    }
                )

        review = self.store.daily_review(selected_day)
        flow = self.store.day_flow(selected_day)

        highlights = [
            self._review_highlight("생산", "#EAF1EC", "#6F9A7C", "가장 많이 쓴 생산 활동", review.strongest_productive, "#7FA98A"),
            self._review_highlight("주의", "#F8EDE3", "#CB8056", "가장 큰 방해 요소", review.largest_distraction, "#DB9163"),
            self._review_highlight("정리", "#EBF0F4", "#7E97AC", "정리가 필요한 중립 활동", review.unresolved_candidate, "#99ABBE"),
        ]

        if review.largest_distraction:
            suggestion = f"'{_truncate(review.largest_distraction.label, 34)}' 사용 시간을 줄일 규칙이나 업무 시간 패턴을 먼저 점검하세요."
        elif review.unresolved_candidate:
            suggestion = "중립 활동을 분류하면 다음 회고가 더 또렷해집니다."
        elif review.strongest_productive:
            suggestion = "생산적인 흐름이 안정적입니다. 같은 시간대의 활동 패턴을 유지해보세요."
        else:
            suggestion = "기록된 데이터가 없습니다."

        if flow.sessions:
            flow_stats = [
                {"label": "활동 흐름", "value": str(len(flow.sessions)), "unit": "개"},
                {"label": "대상 전환", "value": str(flow.target_switches), "unit": "회"},
                {"label": "분류 전환", "value": str(flow.category_switches), "unit": "회"},
            ]
            if flow.longest_productive:
                flow_stats.append({"label": "최장 생산 구간", "value": _format_seconds(flow.longest_productive.seconds), "unit": ""})
            if flow.longest_unproductive:
                flow_stats.append({"label": "최장 비생산 구간", "value": _format_seconds(flow.longest_unproductive.seconds), "unit": ""})
            flow_payload = {"empty": False, "note": "", "stats": flow_stats}
        else:
            flow_payload = {"empty": True, "note": "기록된 데이터가 없습니다.", "stats": []}

        focus_sessions = flow.focus_sessions(min_seconds=25 * 60)
        if focus_sessions:
            total_focus = sum(session.seconds for session in focus_sessions)
            deepest = max(focus_sessions, key=lambda session: session.seconds)
            label = _truncate(deepest.primary_label, 24) if deepest.primary_label else "생산 활동"
            focus_payload = {
                "empty": False,
                "note": f"가장 깊은 몰입 · {label}",
                "stats": [
                    {"label": "집중 구간", "value": str(len(focus_sessions)), "unit": "개"},
                    {"label": "누적 시간", "value": _format_seconds(total_focus), "unit": ""},
                    {"label": "최장 몰입", "value": _format_seconds(deepest.seconds), "unit": ""},
                ],
            }
        elif flow.deepest_focus:
            focus_payload = {
                "empty": False,
                "note": "25분 이상 이어진 집중 구간은 아직 없어요.",
                "stats": [{"label": "가장 긴 생산 구간", "value": _format_seconds(flow.deepest_focus.seconds), "unit": ""}],
            }
        else:
            focus_payload = {"empty": True, "note": "기록된 데이터가 없습니다.", "stats": []}

        return {
            "composition": {"total": _format_seconds(total_seconds), "segments": segments},
            "highlights": highlights,
            "suggestion": suggestion,
            "flow": flow_payload,
            "focus": focus_payload,
        }

    @staticmethod
    def _review_highlight(tag: str, t_bg: str, t_fg: str, title: str, row, accent: str) -> dict[str, Any]:
        if row is None:
            return {"tag": tag, "tBg": t_bg, "tFg": t_fg, "title": title, "value": "기록 없음", "time": "", "color": accent, "empty": True}
        return {"tag": tag, "tBg": t_bg, "tFg": t_fg, "title": title, "value": _truncate(row.label, 30), "time": _format_seconds(row.seconds), "color": accent, "empty": False}
