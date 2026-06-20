from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from time_manager.formatting import _format_percent, _format_seconds, _report_period_for_label, _truncate
from time_manager.models import Category
from time_manager.rules import (
    PROFILE_PRESETS,
    RuleClassifier,
    RuleConflictError,
    add_rule_value,
    apply_profile_preset,
    candidate_still_unclassified,
    load_rules,
    remove_rule_value,
    rule_from_candidate,
    rule_key_for_selection,
    update_rule_value,
)
from time_manager.settings import SettingsStore
from time_manager.storage import ActivityStore
from time_manager.tracker import ActivityTracker

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


class WebApi:
    # React에서 window.pywebview.api로 접근하는 Python 브릿지

    def __init__(
        self,
        *,
        store: ActivityStore,
        tracker: ActivityTracker,
        settings_store: SettingsStore,
        rules_path: Path,
    ) -> None:
        self.store = store
        self.tracker = tracker
        self.settings_store = settings_store
        self.settings = settings_store.load()
        self.rules_path = rules_path
        self.selected_day = date.today()
        self._candidate_sort: tuple[str, bool] = ("duration", True)
        self._maybe_auto_backup()

    # -- 날짜 이동 ----------------------------------------------------------
    def change_day(self, delta: int) -> dict[str, Any]:
        today = date.today()
        self.selected_day = min(today, self.selected_day + timedelta(days=delta))
        return self.get_dashboard()

    def return_to_today(self) -> dict[str, Any]:
        self.selected_day = date.today()
        return self.get_dashboard()

    # -- 설정 토글 ---------------------------------------------------------
    def toggle_notifications(self, enabled: bool) -> dict[str, Any]:
        self.settings.notifications_enabled = bool(enabled)
        self.settings_store.save(self.settings)
        if hasattr(self.tracker.notifier, "set_enabled"):
            self.tracker.notifier.set_enabled(self.settings.notifications_enabled)
        if self.settings.notifications_enabled and hasattr(self.tracker.notifier, "send"):
            self.tracker.notifier.send("알림이 켜졌습니다", "목표와 집중 알림을 표시합니다.")
        return self.get_dashboard()

    def send_focus_notification(self, title: str, body: str) -> None:
        # 포커스 타이머 직접 호출용 — 알림 토글 설정과 무관하게 전송
        notifier = getattr(self.tracker, "notifier", None)
        if notifier is None:
            return
        if hasattr(notifier, "alert"):
            notifier.alert(str(title), str(body))
        elif hasattr(notifier, "send"):
            notifier.send(str(title), str(body))

    def toggle_tracking(self) -> dict[str, Any]:
        if self.tracker.is_running:
            self.tracker.toggle_pause()
        else:
            self.tracker.start()
        return self.get_dashboard()

    # -- 대시보드 ----------------------------------------------------------
    def get_dashboard(self) -> dict[str, Any]:
        today = date.today()
        viewing_today = self.selected_day == today
        totals = _day_totals(self.store, self.selected_day)
        yesterday_totals = _day_totals(self.store, self.selected_day - timedelta(days=1))
        total_seconds = sum(totals.values())
        yesterday_total = sum(yesterday_totals.values())
        score = _productivity_score(totals)
        yesterday_score = _productivity_score(yesterday_totals)

        stats = [
            {
                "key": "total",
                "label": "총 사용 시간",
                "value": _format_seconds(total_seconds),
                "delta": _delta_text(total_seconds - yesterday_total),
                "badge": _STAT_BADGES["total"],
            }
        ]
        for category in (Category.PRODUCTIVE, Category.UNPRODUCTIVE, Category.NEUTRAL):
            stats.append(
                {
                    "key": category.value,
                    "label": f"{_CATEGORY_LABELS[category]} 시간",
                    "value": _format_seconds(totals[category]),
                    "delta": _delta_text(totals[category] - yesterday_totals[category]),
                    "badge": _STAT_BADGES[category],
                }
            )
        stats.append(
            {
                "key": "score",
                "label": "생산성 점수",
                "value": f"{score}%",
                "delta": _delta_text(score - yesterday_score, unit="점"),
                "badge": _STAT_BADGES["score"],
            }
        )

        donut_segments = []
        if total_seconds > 0:
            colors = {
                Category.PRODUCTIVE: "#7FA98A",
                Category.UNPRODUCTIVE: "#DB9163",
                Category.NEUTRAL: "#99ABBE",
            }
            for category in (Category.PRODUCTIVE, Category.UNPRODUCTIVE, Category.NEUTRAL):
                seconds = totals[category]
                donut_segments.append(
                    {
                        "category": category.value,
                        "label": _CATEGORY_LABELS[category],
                        "color": colors[category],
                        "pct": round((seconds / total_seconds) * 100),
                        "time": _format_seconds(seconds),
                        "ratio": seconds / total_seconds,
                    }
                )

        hourly_rows = self.store.hourly_summaries_between(self.selected_day, self.selected_day)
        hourly = [
            {
                "hour": row.hour,
                "productive": row.productive_seconds,
                "unproductive": row.unproductive_seconds,
                "neutral": row.neutral_seconds,
            }
            for row in hourly_rows
        ]

        top_targets = self.store.top_targets_for_day(self.selected_day, limit=5)
        peak = max((row.seconds for row in top_targets), default=0) or 1
        top_apps = [
            {
                "rank": index + 1,
                "label": row.label,
                "time": _format_seconds(row.seconds),
                "category": row.category.value,
                "ratio": row.seconds / peak,
            }
            for index, row in enumerate(top_targets)
        ]

        current_activity = self._current_activity_payload()

        category, streak_seconds = self.tracker.current_streak()
        threshold = self.tracker.unproductive_alert_seconds
        on_streak = category == Category.UNPRODUCTIVE and streak_seconds > 0
        focus_mode = {
            "enabled": self.settings.notifications_enabled,
            "streakLabel": _format_seconds(streak_seconds if on_streak else 0),
            "ratio": min(1.0, streak_seconds / threshold) if on_streak else 0.0,
            "thresholdMinutes": threshold // 60,
        }

        return {
            "dateLabel": "오늘" if viewing_today else self.selected_day.strftime("%Y년 %m월 %d일"),
            "viewingToday": viewing_today,
            "tracking": self.tracker.is_running and not self.tracker.is_paused,
            "stats": stats,
            "donut": {"total": _format_seconds(total_seconds), "segments": donut_segments},
            "hourly": hourly,
            "topApps": top_apps,
            "focusMode": focus_mode,
            "currentActivity": current_activity,
        }

    _CATEGORY_COLORS = {
        Category.PRODUCTIVE: "#7FA98A",
        Category.UNPRODUCTIVE: "#DB9163",
        Category.NEUTRAL: "#99ABBE",
    }

    def get_current_activity(self) -> dict[str, Any] | None:
        return self._current_activity_payload()

    def _current_activity_payload(self) -> dict[str, Any] | None:
        activity = self.tracker.current_activity()
        if activity is None:
            return None
        target = activity.target
        label = _truncate(target.url or target.window_title or target.app_name, 80)
        if not label:
            return None
        return {
            "label": label,
            "category": activity.category.value,
            "categoryLabel": _CATEGORY_LABELS[activity.category],
            "color": self._CATEGORY_COLORS[activity.category],
        }

    # -- 활동 인박스 --------------------------------------------------------
    def _add_rule_value(self, key: str, value: str) -> RuleClassifier | None:
        try:
            return add_rule_value(self.rules_path, key, value)
        except RuleConflictError:
            return None

    def get_inbox(self, query: str = "", category: str | None = None) -> dict[str, Any]:
        searching = bool(query.strip()) or bool(category)
        if searching:
            cat = Category(category) if category else None
            rows = self.store.search_events(query=query, category=cat, days=30, limit=200)
        else:
            rows = self.store.recent_for_day(self.selected_day, limit=30)
        records = [
            {
                "id": row.id,
                "time": row.started_at.replace("T", " "),
                "category": row.category.value,
                "categoryLabel": _CATEGORY_LABELS[row.category],
                "duration": _format_seconds(row.seconds),
                "label": _truncate(row.url or row.title or row.app_name, 68),
            }
            for row in rows
        ]
        return {
            "records": records,
            "searchActive": searching,
            "resultCount": len(records) if searching else None,
            "candidates": self._candidate_payload(),
        }

    def _candidate_payload(self) -> list[dict[str, Any]]:
        ignored = {label.lower() for label in self.settings.ignored_suggestions}
        candidates = self.store.classification_suggestions(7, min_occurrences=2, min_total_seconds=300, limit=50)
        rows = [
            row
            for row in candidates
            if row.label.lower() not in ignored and candidate_still_unclassified(row.label, self.tracker.classifier)
        ]
        sort_key, reverse = self._candidate_sort
        key_fn = (lambda r: r.occurrences) if sort_key == "occurrences" else (lambda r: r.seconds)
        rows.sort(key=key_fn, reverse=reverse)
        return [
            {"label": row.label, "duration": _format_seconds(row.seconds), "occurrences": row.occurrences}
            for row in rows
        ]

    def sort_candidates(self, column: str) -> list[dict[str, Any]]:
        current_col, reverse = self._candidate_sort
        reverse = not reverse if current_col == column else True
        self._candidate_sort = (column, reverse)
        return self._candidate_payload()

    def reclassify_event(self, event_id: int, category: str) -> dict[str, Any]:
        self.store.reclassify_event(event_id, Category(category))
        return self.get_inbox()

    def save_event_as_rule(self, event_id: int, label: str, category: str) -> dict[str, Any]:
        cat = Category(category)
        if cat == Category.NEUTRAL:
            return self.get_inbox()
        key, value = rule_from_candidate(label, cat)
        classifier = self._add_rule_value(key, value)
        if classifier is not None:
            self.tracker.classifier = classifier
            self.store.reclassify_event(event_id, cat)
        return self.get_inbox()

    def delete_event(self, event_id: int) -> dict[str, Any]:
        self.store.soft_delete_event(event_id)
        return self.get_inbox()

    def restore_deleted_event(self) -> dict[str, Any]:
        self.store.restore_last_deleted()
        return self.get_inbox()

    def classify_candidates(self, labels: list[str], category: str) -> dict[str, Any]:
        cat = Category(category)
        for label in labels:
            key, value = rule_from_candidate(label, cat)
            classifier = self._add_rule_value(key, value)
            if classifier is not None:
                self.tracker.classifier = classifier
        return self.get_inbox()

    def exclude_candidates(self, labels: list[str]) -> dict[str, Any]:
        for label in labels:
            if not label.lower().endswith(".exe"):
                continue
            classifier = self._add_rule_value("excluded_apps", label)
            if classifier is not None:
                self.tracker.classifier = classifier
        return self.get_inbox()

    def ignore_candidates(self, labels: list[str]) -> dict[str, Any]:
        ignored = {item.lower() for item in self.settings.ignored_suggestions}
        new_labels = tuple(label for label in labels if label.lower() not in ignored)
        if new_labels:
            self.settings.ignored_suggestions = self.settings.ignored_suggestions + new_labels
            self.settings_store.save(self.settings)
        return self.get_inbox()

    # -- 데일리 리뷰 --------------------------------------------------------
    def get_review(self) -> dict[str, Any]:
        totals = _day_totals(self.store, self.selected_day)
        total_seconds = sum(totals.values())
        colors = {Category.PRODUCTIVE: "#7FA98A", Category.UNPRODUCTIVE: "#DB9163", Category.NEUTRAL: "#99ABBE"}
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
                        "color": colors[category],
                        "pct": round((seconds / total_seconds) * 100),
                        "time": _format_seconds(seconds),
                    }
                )

        review = self.store.daily_review(self.selected_day)
        flow = self.store.day_flow(self.selected_day)

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

    # -- 분류 규칙 ---------------------------------------------------------
    _RULE_GROUPS = (
        ("생산적", "도메인", "productive_domains"),
        ("생산적", "창 제목 키워드", "productive_title_keywords"),
        ("생산적", "앱 이름", "productive_apps"),
        ("비생산적", "도메인", "unproductive_domains"),
        ("비생산적", "창 제목 키워드", "unproductive_title_keywords"),
        ("비생산적", "앱 이름", "unproductive_apps"),
        ("중립", "창 제목 키워드", "neutral_title_keywords"),
        ("기록 제외", "앱 이름", "excluded_apps"),
    )

    def get_rules(self) -> dict[str, Any]:
        rules = load_rules(self.rules_path)
        items = []
        for category, rule_type, key in self._RULE_GROUPS:
            for index, value in enumerate(rules.get(key, [])):
                items.append(
                    {
                        "priority": len(items) + 1,
                        "category": category,
                        "ruleType": rule_type,
                        "key": key,
                        "value": value,
                    }
                )
        return {"items": items, "total": len(items)}

    def add_rule(self, rule_type: str, category: str, value: str) -> dict[str, Any]:
        value = value.strip()
        if not value:
            return {**self.get_rules(), "error": "값을 입력하세요."}
        key = rule_key_for_selection(rule_type, category)
        classifier = self._add_rule_value(key, value)
        if classifier is None:
            return {**self.get_rules(), "error": f"'{value}' 항목은 이미 다른 분류 규칙에 있습니다."}
        self.tracker.classifier = classifier
        return self.get_rules()

    def update_rule(
        self, old_key: str, old_value: str, rule_type: str, category: str, value: str
    ) -> dict[str, Any]:
        value = value.strip()
        if not value:
            return {**self.get_rules(), "error": "값을 입력하세요."}
        new_key = rule_key_for_selection(rule_type, category)
        if new_key == old_key and value == old_value:
            return self.get_rules()
        try:
            classifier = update_rule_value(self.rules_path, old_key, old_value, new_key, value)
        except RuleConflictError:
            return {**self.get_rules(), "error": f"'{value}' 항목은 이미 다른 분류 규칙에 있습니다."}
        self.tracker.classifier = classifier
        return self.get_rules()

    def delete_rule(self, key: str, value: str) -> dict[str, Any]:
        self.tracker.classifier = remove_rule_value(self.rules_path, key, value)
        return self.get_rules()

    # -- 리포트 ------------------------------------------------------------
    REPORT_RANGE_LABELS = ("최근 7일", "최근 30일", "이번 달")
    _WEEKDAY_LABELS = ("월", "화", "수", "목", "금", "토", "일")

    def get_report(self, period: str = "최근 7일") -> dict[str, Any]:
        today = date.today()
        start_day, end_day = _report_period_for_label(period, today)
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

    # -- 개인화 및 설정 ----------------------------------------------------
    PROFILE_LABELS = {
        "": "선택 안 함",
        "developer": "개발자",
        "student": "학생",
        "office": "사무직",
        "creator": "크리에이터",
        "researcher": "연구자",
        "designer": "디자이너",
        "marketer": "마케터",
        "finance": "재무/투자",
        "manager": "매니저",
    }

    def _backup_manager(self):
        from time_manager.backup import BackupManager

        return BackupManager(
            activity_path=self.store.db_path,
            rules_path=self.rules_path,
            settings_path=self.settings_store.path,
            backup_dir=self.store.db_path.parent / "backups",
        )

    def get_settings(self) -> dict[str, Any]:
        profile = self.settings.onboarding_profile
        preset_items = [
            {"key": key, "value": value}
            for key, values in PROFILE_PRESETS.get(profile, {}).items()
            for value in values
        ]
        return {
            "dailyGoalMinutes": self.settings.daily_goal_minutes,
            "weeklyGoalMinutes": self.settings.weekly_goal_minutes,
            "unproductiveLimitMinutes": self.settings.unproductive_limit_minutes,
            "workStartHour": self.settings.work_start_hour,
            "workEndHour": self.settings.work_end_hour,
            "profile": profile,
            "profileOptions": [{"value": k, "label": v} for k, v in self.PROFILE_LABELS.items()],
            "presetItems": preset_items,
            "excludeSelf": self.settings.exclude_self_app,
            "notificationsEnabled": self.settings.notifications_enabled,
            "autoBackupEnabled": self.settings.auto_backup_enabled,
            "storeDomainOnly": self.settings.store_domain_only,
            "storeWindowTitles": self.settings.store_window_titles,
            "retentionDays": self.settings.retention_days,
            "theme": self.settings.theme,
            "notificationStatus": self._notification_status_text(),
            "diagnosticInfo": self._diagnostic_info_text(),
            "diagnosticResults": "",
        }

    def _notification_status_text(self) -> str:
        if not self.settings.notifications_enabled:
            return "앱 알림이 꺼져 있습니다."
        notifier = getattr(self.tracker, "notifier", None)
        if notifier and hasattr(notifier, "status"):
            status = notifier.status()
            message = status.get("message") if isinstance(status, dict) else None
            if message:
                return str(message)
        return "앱 알림이 켜져 있습니다. 표시되지 않으면 Windows 알림 설정을 확인하세요."

    def _diagnostic_info_text(self) -> str:
        import platform

        from time_manager import __version__

        settings_path = self.settings_store.path if self.settings_store else "없음"
        environment = f"v{__version__} · {platform.system()} {platform.release()}"
        log_path = self.store.db_path.parent / "time-manager.log"
        return "\n".join(
            (
                f"환경: {environment}",
                f"데이터: {self.store.db_path}",
                f"규칙: {self.rules_path}",
                f"설정: {settings_path}",
                f"로그: {log_path}",
            )
        )

    def save_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            daily_goal = int(payload["dailyGoalMinutes"])
            weekly_goal = int(payload["weeklyGoalMinutes"])
            unproductive_limit = int(payload["unproductiveLimitMinutes"])
            start_hour = int(payload["workStartHour"])
            end_hour = int(payload["workEndHour"])
            retention_days = int(payload["retentionDays"])
        except (ValueError, TypeError, KeyError):
            return {**self.get_settings(), "error": "값을 숫자로 입력해주세요."}
        if min(daily_goal, weekly_goal, unproductive_limit) < 1:
            return {**self.get_settings(), "error": "목표와 상한은 1분 이상이어야 합니다."}
        if weekly_goal < daily_goal:
            return {**self.get_settings(), "error": "주간 생산 목표는 일간 목표 이상으로 설정해주세요."}
        if not 0 <= start_hour <= 23 or not 1 <= end_hour <= 24 or start_hour >= end_hour:
            return {**self.get_settings(), "error": "근무 시간을 0~24 사이로, 종료가 시작보다 늦게 입력해주세요."}
        if retention_days < 0:
            return {**self.get_settings(), "error": "데이터 보존 기간은 0 이상이어야 합니다."}

        self.settings.daily_goal_minutes = daily_goal
        self.settings.weekly_goal_minutes = weekly_goal
        self.settings.unproductive_limit_minutes = unproductive_limit
        self.settings.work_start_hour = start_hour
        self.settings.work_end_hour = end_hour
        self.settings.retention_days = retention_days
        self.settings.store_domain_only = bool(payload.get("storeDomainOnly", self.settings.store_domain_only))
        self.settings.store_window_titles = bool(payload.get("storeWindowTitles", self.settings.store_window_titles))
        theme = str(payload.get("theme", self.settings.theme))
        self.settings.theme = theme if theme in {"light", "dark"} else self.settings.theme
        self.settings_store.save(self.settings)
        self.tracker.set_privacy_options(self.settings.store_domain_only, self.settings.store_window_titles)
        return self.get_settings()

    def set_theme(self, theme: str) -> dict[str, Any]:
        self.settings.theme = theme if theme in {"light", "dark"} else "light"
        self.settings_store.save(self.settings)
        return self.get_settings()

    def toggle_exclude_self(self, enabled: bool) -> dict[str, Any]:
        self.settings.exclude_self_app = bool(enabled)
        self.tracker.set_exclude_self_app(self.settings.exclude_self_app)
        self.settings_store.save(self.settings)
        return self.get_settings()

    def toggle_auto_backup(self, enabled: bool) -> dict[str, Any]:
        self.settings.auto_backup_enabled = bool(enabled)
        self.settings_store.save(self.settings)
        if self.settings.auto_backup_enabled:
            self._maybe_auto_backup()
        return self.get_settings()

    def _maybe_auto_backup(self) -> None:
        # 백업 실패 시 예외를 UI로 전파하지 않음 — 앱 기동·토글을 막지 않기 위해
        from time_manager.backup import should_auto_backup

        if not should_auto_backup(
            self.settings.auto_backup_enabled, self.settings.last_auto_backup, date.today()
        ):
            return
        try:
            self._backup_manager().auto_backup(date.today())
        except OSError:
            return
        self.settings.last_auto_backup = date.today().isoformat()
        self.settings_store.save(self.settings)

    def set_profile(self, profile: str) -> dict[str, Any]:
        self.settings.onboarding_profile = profile
        self.settings_store.save(self.settings)
        return self.get_settings()

    def apply_preset(self) -> dict[str, Any]:
        if self.settings.onboarding_profile:
            self.tracker.classifier = apply_profile_preset(self.rules_path, self.settings.onboarding_profile)
        return self.get_settings()

    def run_diagnostics(self) -> dict[str, Any]:
        from time_manager.diagnostics import run_diagnostics as _run_diagnostics

        settings_path = self.settings_store.path if self.settings_store else self.store.db_path.parent / "settings.json"
        results = _run_diagnostics(
            data_dir=self.store.db_path.parent,
            db_path=self.store.db_path,
            rules_path=self.rules_path,
            settings_path=settings_path,
            log_path=self.store.db_path.parent / "time-manager.log",
        )
        lines = []
        for result in results:
            lines.append(f"[{result.status.value.upper()}] {result.name}: {result.message}")
            lines.append(f"    {result.path}")
        return {**self.get_settings(), "diagnosticResults": "\n".join(lines) if lines else "문제가 없습니다."}

    def export_csv(self, day_iso: str | None = None) -> dict[str, Any]:
        target_day = date.fromisoformat(day_iso) if day_iso else self.selected_day
        import webview

        output = webview.windows[0].create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=f"activity-{target_day.isoformat()}.csv",
            file_types=("CSV 파일 (*.csv)",),
        )
        if not output:
            return {"message": ""}
        path = Path(output if isinstance(output, str) else output[0])
        rows = self.store.export_csv_for_day(target_day, path)
        return {"message": f"{rows}건의 기록을 CSV로 내보냈습니다." if rows else "해당 날짜에 내보낼 기록이 없습니다."}

    def export_backup(self) -> dict[str, Any]:
        import webview

        manager = self._backup_manager()
        output = webview.windows[0].create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=f"time-manager-{date.today().isoformat()}.tmbak",
            file_types=("Time Manager 백업 (*.tmbak)",),
        )
        if not output:
            return {"message": ""}
        path = Path(output if isinstance(output, str) else output[0])
        manager.export(path)
        return {"message": f"백업을 저장했습니다: {path}"}

    def restore_backup(self) -> dict[str, Any]:
        import webview

        manager = self._backup_manager()
        source = webview.windows[0].create_file_dialog(webview.OPEN_DIALOG, file_types=("Time Manager 백업 (*.tmbak)",))
        if not source:
            return {"message": ""}
        path = Path(source[0] if isinstance(source, (list, tuple)) else source)
        manager.restore(path)
        self.settings = self.settings_store.load()
        self.tracker.classifier = RuleClassifier.from_file(self.rules_path)
        self.tracker.set_exclude_self_app(self.settings.exclude_self_app)
        self.tracker.set_privacy_options(self.settings.store_domain_only, self.settings.store_window_titles)
        return {"message": "백업을 복원했습니다.", **self.get_settings()}
