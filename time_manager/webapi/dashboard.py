from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from time_manager.formatting import _display_label, _format_seconds, _truncate
from time_manager import notices
from time_manager.models import Category

from ._shared import CATEGORY_COLORS, WebApiBase, _CATEGORY_LABELS, _day_totals, _delta_text, _delta_tone, _parse_day, _productivity_score


class DashboardMixin(WebApiBase):
    def toggle_notifications(self, enabled: bool) -> dict[str, Any]:
        self.settings.notifications_enabled = bool(enabled)
        self.settings_store.save(self.settings)
        if hasattr(self.tracker.notifier, "set_enabled"):
            self.tracker.notifier.set_enabled(self.settings.notifications_enabled)
        if self.settings.notifications_enabled and hasattr(self.tracker.notifier, "send"):
            self.tracker.notifier.send("알림이 켜졌습니다", "목표와 집중 알림을 표시합니다.")
        return self.get_dashboard()

    def send_focus_notification(self, title: str, body: str) -> None:
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

    def get_dashboard(self, date_iso: str | None = None) -> dict[str, Any]:
        today = date.today()
        selected_day = _parse_day(date_iso)
        viewing_today = selected_day == today
        totals = _day_totals(self.store, selected_day)
        previous_day = selected_day - timedelta(days=1)
        if viewing_today:
            # 끝나지 않은 오늘은 어제의 같은 시각까지와 비교
            basis = "어제 같은 시각"
            yesterday_totals = self.store.category_totals_before(datetime.combine(previous_day, datetime.now().time()))
        else:
            basis = "전날"
            yesterday_totals = _day_totals(self.store, previous_day)
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
                "tone": _delta_tone("total", total_seconds - yesterday_total),
            }
        ]
        for category in (Category.PRODUCTIVE, Category.UNPRODUCTIVE, Category.NEUTRAL):
            stats.append(
                {
                    "key": category.value,
                    "label": f"{_CATEGORY_LABELS[category]} 시간",
                    "value": _format_seconds(totals[category]),
                    "delta": _delta_text(totals[category] - yesterday_totals[category]),
                    "tone": _delta_tone(category.value, totals[category] - yesterday_totals[category]),
                }
            )
        stats.append(
            {
                "key": "score",
                "label": "생산성 점수",
                "value": f"{score}점",  # 리포트·회고와 같은 단위
                "delta": _delta_text(score - yesterday_score, unit="점"),
                "tone": _delta_tone("score", score - yesterday_score),
            }
        )

        donut_segments = []
        if total_seconds > 0:
            for category in (Category.PRODUCTIVE, Category.UNPRODUCTIVE, Category.NEUTRAL):
                seconds = totals[category]
                donut_segments.append(
                    {
                        "category": category.value,
                        "label": _CATEGORY_LABELS[category],
                        "color": CATEGORY_COLORS[category],
                        "pct": round((seconds / total_seconds) * 100),
                        "time": _format_seconds(seconds),
                        "ratio": seconds / total_seconds,
                    }
                )

        hourly_rows = self.store.hourly_summaries_between(selected_day, selected_day)
        hourly = [
            {
                "hour": row.hour,
                "productive": row.productive_seconds,
                "unproductive": row.unproductive_seconds,
                "neutral": row.neutral_seconds,
            }
            for row in hourly_rows
        ]

        top_targets = self.store.top_targets_for_day(selected_day, limit=10)
        peak = max((row.seconds for row in top_targets), default=0) or 1
        top_apps = [
            {
                "rank": index + 1,
                "label": _display_label(row.label),
                "time": _format_seconds(row.seconds),
                "category": row.category.value,
                "ratio": row.seconds / peak,
            }
            for index, row in enumerate(top_targets)
        ]

        current_activity = self._current_activity_payload()
        goal_seconds = max(60, self.settings.daily_goal_minutes * 60)
        productive = totals[Category.PRODUCTIVE]
        off_day = selected_day.weekday() not in self.settings.goal_weekdays
        goal = {
            "offDay": off_day,
            "value": f"{_format_seconds(productive) if productive else '0분'} / {_format_seconds(goal_seconds)}",
            "pct": productive * 100 // goal_seconds,  # 다 채우기 전에 100% 로 보이지 않게 내림
            "ratio": min(1.0, productive / goal_seconds),
            "achieved": productive >= goal_seconds,
            "remaining": "" if productive >= goal_seconds else _format_seconds(goal_seconds - productive),
        }

        flow = self.store.day_flow(selected_day)
        focus_sessions = flow.focus_sessions(min_seconds=25 * 60)
        total_focus = sum(s.seconds for s in focus_sessions)
        focus_summary = {
            "count": len(focus_sessions),
            "totalTime": _format_seconds(total_focus) if total_focus > 0 else None,
        }

        return {
            "dateLabel": "오늘" if viewing_today else selected_day.strftime("%Y년 %m월 %d일"),
            "viewingToday": viewing_today,
            "tracking": self.tracker.is_running and not self.tracker.is_paused,
            "pausedUntil": self._paused_until_label(),
            "problem": self.tracker.problem,
            "notices": notices.current(),
            "stats": stats,
            "donut": {"total": _format_seconds(total_seconds), "segments": donut_segments},
            "hourly": hourly,
            "topApps": top_apps,
            "goal": goal,
            "comparedWith": basis,
            "focusSummary": focus_summary,
            "currentActivity": current_activity,
        }

    def pause_tracking(self, minutes: int | None = None) -> dict[str, Any]:
        """``minutes`` 동안 일시정지 (없으면 직접 다시 켤 때까지)."""
        try:
            minutes = int(minutes) if minutes is not None else None
        except (TypeError, ValueError):
            minutes = None
        if minutes is not None and not 1 <= minutes <= 24 * 60:
            minutes = None
        if not self.tracker.is_running:
            self.tracker.start()
        self.tracker.pause(minutes)
        return self.get_dashboard()

    def set_focus_session(self, ends_at_ms: float | None = None) -> None:
        """화면의 집중 타이머: 집중 단계가 끝나는 때(epoch ms). 멈추거나 쉬면 None."""
        try:
            ends_at = float(ends_at_ms) / 1000 if ends_at_ms else None
        except (TypeError, ValueError):
            ends_at = None
        self.tracker.set_focus_session(ends_at)

    def _paused_until_label(self) -> str:
        until = self.tracker.paused_until
        if until is None:
            return ""
        moment = datetime.fromtimestamp(until)
        prefix = "" if moment.date() == date.today() else "내일 "
        return f"{prefix}{moment:%H:%M}"

    def get_current_activity(self) -> dict[str, Any] | None:
        return self._current_activity_payload()

    def _current_activity_payload(self) -> dict[str, Any] | None:
        activity = self.tracker.current_activity()
        if activity is None:
            return None
        target = activity.target
        label = _truncate(_display_label(target.url or target.window_title or target.app_name), 80)
        if not label:
            return None
        return {
            "label": label,
            "category": activity.category.value,
            "categoryLabel": _CATEGORY_LABELS[activity.category],
            "color": CATEGORY_COLORS[activity.category],
        }
