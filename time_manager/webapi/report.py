from __future__ import annotations

from datetime import date
from typing import Any

from time_manager.formatting import _format_seconds, _report_period_for_label, _truncate
from time_manager.models import Category


class ReportMixin:
    REPORT_RANGE_LABELS = ("최근 7일", "최근 30일", "이번 달")
    _WEEKDAY_LABELS = ("월", "화", "수", "목", "금", "토", "일")

    def _build_report(self, start_day: date, end_day: date, period: str) -> dict[str, Any]:
        rows = self.store.summaries_between(start_day, end_day)
        hourly_rows = self.store.hourly_summaries_between(start_day, end_day)
        weekdays = self.store.weekday_summaries_between(start_day, end_day)
        top_targets = self.store.top_targets_for_period(start_day, end_day, limit=5)
        progress = self.store.weekly_progress(self.settings.weekly_goal_minutes, self.settings.daily_goal_minutes)
        change = progress.productive_seconds - progress.previous_productive_seconds

        active_days = [row for row in rows if row.total_seconds > 0]
        if active_days:
            average_score = round(sum(row.productivity_score for row in active_days) / len(active_days))
            weakest_day = min(active_days, key=lambda row: row.productivity_score)
            worst_hour = max(hourly_rows, key=lambda row: row.unproductive_seconds) if hourly_rows else None
            if worst_hour and worst_hour.unproductive_seconds > 0:
                insight_main = (
                    f"평균 생산 점수는 {average_score}%입니다. 가장 약한 날이 {weakest_day.day}"
                    f"({weakest_day.productivity_score}%)이고, 비생산 피크는 {worst_hour.hour:02d}시입니다."
                )
            else:
                insight_main = f"평균 생산 점수는 {average_score}%입니다. 현재 비생산 피크 시간이 없습니다."
        else:
            insight_main = "기록된 데이터가 없습니다."

        if len(rows) >= 2:
            today_row, prev_row = rows[-1], rows[-2]
            p_delta = today_row.productive_seconds - prev_row.productive_seconds
            u_delta = today_row.unproductive_seconds - prev_row.unproductive_seconds

            def _signed(seconds: int) -> str:
                sign = "+" if seconds >= 0 else "-"
                return f"{sign}{abs(seconds) // 60}분"

            insight_sub = f"어제보다 생산 시간 {_signed(p_delta)}, 비생산 시간 {_signed(u_delta)}입니다. "
        else:
            insight_sub = ""
        if hourly_rows:
            worst_hour2 = max(hourly_rows, key=lambda row: row.unproductive_seconds)
            insight_sub += (
                f"{worst_hour2.hour:02d}시 전후에 비생산 시간이 가장 많았습니다. 이 시간대의 상위 활동을 먼저 점검해보세요."
                if worst_hour2.unproductive_seconds > 0
                else "뚜렷한 비생산 피크 시간은 아직 없습니다."
            )
        else:
            insight_sub += "기록된 데이터가 없습니다."

        weekly_distractions = [row for row in top_targets if row.category == Category.UNPRODUCTIVE][:3]
        if weekly_distractions:
            coaching = f"반복 비생산 활동은 {_truncate(weekly_distractions[0].label, 30)}입니다."
        else:
            coaching = "뚜렷한 반복 비생산 활동은 아직 없습니다."
        if hourly_rows:
            worst_hour3 = max(hourly_rows, key=lambda row: row.unproductive_seconds)
            if worst_hour3.unproductive_seconds > 0:
                coaching += f" {worst_hour3.hour:02d}시 전후의 사용 패턴을 먼저 점검해보세요."

        active_weekdays = [row for row in weekdays if row.productive_seconds + row.unproductive_seconds + row.neutral_seconds > 0]
        if active_weekdays:
            weakest_weekday = max(active_weekdays, key=lambda row: row.unproductive_seconds)
            if weakest_weekday.unproductive_seconds > 0:
                weekday_text = (
                    f"{self._WEEKDAY_LABELS[weakest_weekday.weekday]}요일에 비생산 시간이 가장 많았습니다. "
                    f"{_format_seconds(weakest_weekday.unproductive_seconds)}부터 줄여보세요."
                )
            else:
                strongest_weekday = max(active_weekdays, key=lambda row: row.productive_seconds)
                weekday_text = f"{self._WEEKDAY_LABELS[strongest_weekday.weekday]}요일의 생산 흐름이 가장 안정적입니다."
        else:
            weekday_text = "기록된 데이터가 없습니다."

        weekday_peak = max((row.productive_seconds for row in weekdays), default=0) or 1
        weekday_bars = [
            {
                "day": self._WEEKDAY_LABELS[row.weekday],
                "seconds": row.productive_seconds,
                "pct": round((row.productive_seconds / weekday_peak) * 100),
                "isWeekend": row.weekday >= 5,
            }
            for row in weekdays
        ]

        hourly = [
            {"hour": row.hour, "productive": row.productive_seconds, "unproductive": row.unproductive_seconds, "neutral": row.neutral_seconds}
            for row in hourly_rows
        ]

        trend = [{"day": row.day[5:], "score": row.productivity_score} for row in rows if row.total_seconds > 0]

        heat_grid = self.store.weekday_hour_totals_between(start_day, end_day)
        peak_cell = max((value for row in heat_grid for value in row), default=0) or 1
        heatmap = [
            {
                "day": self._WEEKDAY_LABELS[weekday],
                "cells": [round(seconds / peak_cell, 3) for seconds in heat_grid[weekday]],
            }
            for weekday in range(7)
        ]

        daily = [
            {
                "day": row.day,
                "total": _format_seconds(row.total_seconds),
                "prod": _format_seconds(row.productive_seconds),
                "score": row.productivity_score,
            }
            for row in reversed(rows)
        ]

        peak_top = max((row.seconds for row in top_targets), default=0) or 1
        top_activities = [
            {
                "name": row.label,
                "time": _format_seconds(row.seconds),
                "ratio": row.seconds / peak_top,
                "color": {"productive": "#7FA98A", "unproductive": "#DB9163", "neutral": "#99ABBE"}[row.category.value],
            }
            for row in top_targets
        ]

        return {
            "period": period,
            "periodOptions": list(self.REPORT_RANGE_LABELS),
            "startIso": start_day.isoformat(),
            "endIso": end_day.isoformat(),
            "weeklyScorePct": round(progress.progress_ratio * 100),
            "weeklyProgressText": (
                f"{_format_seconds(progress.productive_seconds)} / {_format_seconds(progress.weekly_goal_minutes * 60)} "
                f"({round(progress.progress_ratio * 100)}%) · 일간 목표 달성 {progress.achieved_days}일 · "
                f"지난주 대비 {'+' if change >= 0 else '-'}{abs(change) // 60}분"
            ),
            "coachingText": coaching,
            "weekdayText": weekday_text,
            "weekdayBars": weekday_bars,
            "insightMain": insight_main,
            "insightSub": insight_sub,
            "hourly": hourly,
            "trend": trend,
            "heatmap": heatmap,
            "daily": daily,
            "topActivities": top_activities,
        }

    def get_report(self, period: str = "최근 7일") -> dict[str, Any]:
        today = date.today()
        start_day, end_day = _report_period_for_label(period, today)
        return self._build_report(start_day, end_day, period)

    def get_report_range(self, start_iso: str, end_iso: str) -> dict[str, Any]:
        try:
            start_day = date.fromisoformat(start_iso)
            end_day = date.fromisoformat(end_iso)
        except ValueError:
            return {**self.get_report(), "error": "날짜 형식이 올바르지 않습니다."}
        today = date.today()
        end_day = min(end_day, today)
        if start_day > end_day:
            return {**self.get_report(), "error": "시작일이 종료일보다 늦을 수 없습니다."}
        label = f"{start_day.strftime('%m/%d')}–{end_day.strftime('%m/%d')}"
        return self._build_report(start_day, end_day, label)
