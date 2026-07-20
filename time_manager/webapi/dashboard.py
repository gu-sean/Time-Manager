from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from time_manager.formatting import _format_seconds, _truncate
from time_manager.models import Category

from ._shared import CATEGORY_COLORS, WebApiBase, _CATEGORY_LABELS, _day_totals, _delta_text, _productivity_score


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
        selected_day = date.fromisoformat(date_iso) if date_iso else today
        viewing_today = selected_day == today
        totals = _day_totals(self.store, selected_day)
        yesterday_totals = _day_totals(self.store, selected_day - timedelta(days=1))
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
            }
        ]
        for category in (Category.PRODUCTIVE, Category.UNPRODUCTIVE, Category.NEUTRAL):
            stats.append(
                {
                    "key": category.value,
                    "label": f"{_CATEGORY_LABELS[category]} 시간",
                    "value": _format_seconds(totals[category]),
                    "delta": _delta_text(totals[category] - yesterday_totals[category]),
                }
            )
        stats.append(
            {
                "key": "score",
                "label": "생산성 점수",
                "value": f"{score}%",
                "delta": _delta_text(score - yesterday_score, unit="점"),
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
                "label": row.label,
                "time": _format_seconds(row.seconds),
                "category": row.category.value,
                "ratio": row.seconds / peak,
            }
            for index, row in enumerate(top_targets)
        ]

        current_activity = self._current_activity_payload()

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
            "stats": stats,
            "donut": {"total": _format_seconds(total_seconds), "segments": donut_segments},
            "hourly": hourly,
            "topApps": top_apps,
            "focusSummary": focus_summary,
            "currentActivity": current_activity,
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
            "color": CATEGORY_COLORS[activity.category],
        }
