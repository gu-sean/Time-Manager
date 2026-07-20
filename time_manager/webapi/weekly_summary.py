from __future__ import annotations

from datetime import date, timedelta

from ._shared import WebApiBase


class WeeklySummaryMixin(WebApiBase):
    def _maybe_weekly_summary_notify(self) -> None:
        today = date.today()
        if today.weekday() != 0:  # only check on Monday, once per week
            return
        last_sunday = today - timedelta(days=1)
        last_monday = last_sunday - timedelta(days=6)
        iso_year, iso_week, _ = last_monday.isocalendar()
        week_key = f"{iso_year}-W{iso_week:02d}"
        if self.settings.last_weekly_summary_notified == week_key:
            return
        try:
            progress = self.store.weekly_progress(
                self.settings.weekly_goal_minutes,
                self.settings.daily_goal_minutes,
                reference_day=last_sunday,
            )
            self._send_weekly_summary_notification(progress)
        except Exception:
            return
        self.settings.last_weekly_summary_notified = week_key
        self.settings_store.save(self.settings)

    def _send_weekly_summary_notification(self, progress) -> None:
        notifier = getattr(self.tracker, "notifier", None)
        if notifier is None or not hasattr(notifier, "send"):
            return
        current_min = progress.productive_seconds // 60
        previous_min = progress.previous_productive_seconds // 60
        delta = current_min - previous_min
        trend = f"▲ {delta}분" if delta >= 0 else f"▼ {abs(delta)}분"
        hours, mins = divmod(current_min, 60)
        label = f"{hours}시간 {mins}분" if hours else f"{mins}분"
        notifier.send("지난주 생산성 요약", f"지난주 생산 시간 {label} · 2주 전 대비 {trend}")
