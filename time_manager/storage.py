import csv
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterator

from time_manager.models import Category, ClassifiedActivity


@dataclass(frozen=True)
class SummaryRow:
    category: Category
    seconds: int


@dataclass(frozen=True)
class RecentRow:
    id: int
    started_at: str
    seconds: int
    category: Category
    app_name: str
    title: str
    url: str | None
    reason: str


@dataclass(frozen=True)
class BreakdownRow:
    label: str
    category: Category
    seconds: int


@dataclass(frozen=True)
class DaySummary:
    day: str
    productive_seconds: int
    unproductive_seconds: int
    neutral_seconds: int

    @property
    def total_seconds(self) -> int:
        return self.productive_seconds + self.unproductive_seconds + self.neutral_seconds

    @property
    def productivity_score(self) -> int:
        focused = self.productive_seconds + self.unproductive_seconds
        if focused <= 0:
            return 0
        return round((self.productive_seconds / focused) * 100)


@dataclass(frozen=True)
class HourSummary:
    hour: int
    productive_seconds: int
    unproductive_seconds: int
    neutral_seconds: int


@dataclass(frozen=True)
class WeekdaySummary:
    weekday: int
    productive_seconds: int
    unproductive_seconds: int
    neutral_seconds: int


@dataclass(frozen=True)
class DayComparison:
    current: DaySummary
    previous: DaySummary

    @property
    def productive_delta_seconds(self) -> int:
        return self.current.productive_seconds - self.previous.productive_seconds

    @property
    def unproductive_delta_seconds(self) -> int:
        return self.current.unproductive_seconds - self.previous.unproductive_seconds

    @property
    def neutral_delta_seconds(self) -> int:
        return self.current.neutral_seconds - self.previous.neutral_seconds


@dataclass(frozen=True)
class DailyReview:
    strongest_productive: BreakdownRow | None
    largest_distraction: BreakdownRow | None
    unresolved_candidate: BreakdownRow | None


@dataclass(frozen=True)
class ActivitySession:
    started_at: str
    ended_at: str
    category: Category
    seconds: int
    primary_label: str


@dataclass(frozen=True)
class ActivityFlow:
    sessions: tuple[ActivitySession, ...]
    target_switches: int
    category_switches: int

    @property
    def longest_productive(self) -> ActivitySession | None:
        return _longest_session(self.sessions, Category.PRODUCTIVE)

    @property
    def longest_unproductive(self) -> ActivitySession | None:
        return _longest_session(self.sessions, Category.UNPRODUCTIVE)

    def focus_sessions(self, min_seconds: int = 25 * 60) -> tuple[ActivitySession, ...]:
        return tuple(
            session
            for session in self.sessions
            if session.category == Category.PRODUCTIVE and session.seconds >= min_seconds
        )

    @property
    def deepest_focus(self) -> ActivitySession | None:
        return self.longest_productive


@dataclass(frozen=True)
class WeeklyProgress:
    productive_seconds: int
    previous_productive_seconds: int
    achieved_days: int
    weekly_goal_minutes: int

    @property
    def progress_ratio(self) -> float:
        return min(1.0, self.productive_seconds / max(60, self.weekly_goal_minutes * 60))


@dataclass(frozen=True)
class ActivityEvent:
    id: int
    started_at: str
    seconds: int
    category: Category
    app_name: str
    title: str
    url: str | None
    reason: str


class ActivityStore:
    def __init__(self, db_path: Path, merge_gap_seconds: int = 60, connection_timeout_seconds: float = 5.0) -> None:
        self.db_path = db_path
        self.merge_gap_seconds = merge_gap_seconds
        self.connection_timeout_seconds = connection_timeout_seconds
        self._local = threading.local()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def record(self, activity: ClassifiedActivity, seconds: int) -> None:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        with self._connection() as conn:
            if self._merge_with_latest(conn, activity, seconds, now):
                return
            conn.execute(
                """
                INSERT INTO activity_events
                    (started_at, seconds, category, app_name, window_title, url, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    seconds,
                    activity.category.value,
                    activity.target.app_name,
                    activity.target.window_title,
                    activity.target.url,
                    activity.reason,
                ),
            )

    def _merge_with_latest(self, conn: sqlite3.Connection, activity: ClassifiedActivity, seconds: int, now: str) -> bool:
        row = conn.execute(
            """
            SELECT id, started_at, seconds, category, app_name, window_title, url, reason
            FROM activity_events
            WHERE deleted_at IS NULL
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        if not row:
            return False

        event_id, started_at, existing_seconds, category, app_name, title, url, reason = row
        target = activity.target
        if (
            category != activity.category.value
            or app_name != target.app_name
            or reason != activity.reason
        ):
            return False
        # 같은 URL이면 창 제목이 바뀌어도 동일 활동으로 병합(예: 같은 사이트 내 페이지 이동).
        # URL이 없으면 창 제목이 완전히 일치해야 병합.
        if target.url:
            if url != target.url:
                return False
        elif url is not None or title != target.window_title:
            return False
        if not self._is_contiguous(started_at, int(existing_seconds), now):
            return False

        conn.execute(
            """
            UPDATE activity_events
            SET seconds = seconds + ?,
                event_count = event_count + 1,
                window_title = ?
            WHERE id = ?
            """,
            (seconds, target.window_title, int(event_id)),
        )
        return True

    def _is_contiguous(self, started_at: str, seconds: int, now: str) -> bool:
        try:
            started = datetime.fromisoformat(started_at)
            current = datetime.fromisoformat(now)
        except ValueError:
            return False
        expected_end = started + timedelta(seconds=seconds)
        gap_seconds = abs((current - expected_end).total_seconds())
        return gap_seconds <= self.merge_gap_seconds

    def total_productive_seconds(self) -> int:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(seconds), 0) FROM activity_events WHERE category = ? AND deleted_at IS NULL",
                (Category.PRODUCTIVE.value,),
            ).fetchone()
        return int(row[0]) if row else 0

    def summary_for_day(self, day: date) -> list[SummaryRow]:
        start, end = self._day_bounds(day)

        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT category, COALESCE(SUM(seconds), 0)
                FROM activity_events
                WHERE started_at >= ? AND started_at < ?
                    AND deleted_at IS NULL
                GROUP BY category
                """,
                (start, end),
            ).fetchall()
        return [SummaryRow(Category(category), int(seconds)) for category, seconds in rows]

    def recent(self, limit: int = 30) -> list[RecentRow]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT id, started_at, seconds, category, app_name, window_title, url, reason
                FROM activity_events
                WHERE deleted_at IS NULL
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            RecentRow(
                id=int(row[0]),
                started_at=row[1],
                seconds=int(row[2]),
                category=Category(row[3]),
                app_name=row[4],
                title=row[5],
                url=row[6],
                reason=row[7],
            )
            for row in rows
        ]

    def recent_for_day(self, day: date, limit: int = 30) -> list[RecentRow]:
        start, end = self._day_bounds(day)
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT id, started_at, seconds, category, app_name, window_title, url, reason
                FROM activity_events
                WHERE started_at >= ? AND started_at < ?
                    AND deleted_at IS NULL
                ORDER BY id DESC
                LIMIT ?
                """,
                (start, end, limit),
            ).fetchall()
        return [
            RecentRow(
                id=int(row[0]),
                started_at=row[1],
                seconds=int(row[2]),
                category=Category(row[3]),
                app_name=row[4],
                title=row[5],
                url=row[6],
                reason=row[7],
            )
            for row in rows
        ]

    def search_events(
        self,
        query: str = "",
        category: Category | None = None,
        days: int = 7,
        limit: int = 200,
    ) -> list[RecentRow]:
        end_day = date.today()
        start_day = end_day - timedelta(days=max(0, days - 1))
        start, end = self._period_bounds(start_day, end_day)
        params: list[object] = [start, end]
        sql_parts = [
            """
            SELECT id, started_at, seconds, category, app_name, window_title, url, reason
            FROM activity_events
            WHERE started_at >= ? AND started_at < ?
                AND deleted_at IS NULL
            """
        ]
        if query.strip():
            like = f"%{query.strip().lower()}%"
            sql_parts.append("    AND (LOWER(app_name) LIKE ? OR LOWER(window_title) LIKE ? OR LOWER(COALESCE(url, '')) LIKE ?)")
            params += [like, like, like]
        if category:
            sql_parts.append("    AND category = ?")
            params.append(category.value)
        sql_parts.append("ORDER BY started_at DESC\nLIMIT ?")
        params.append(limit)
        with self._connection() as conn:
            rows = conn.execute("\n".join(sql_parts), params).fetchall()
        return [
            RecentRow(
                id=int(row[0]),
                started_at=row[1],
                seconds=int(row[2]),
                category=Category(row[3]),
                app_name=row[4],
                title=row[5],
                url=row[6],
                reason=row[7],
            )
            for row in rows
        ]

    def events_after(self, last_id: int, limit: int = 500) -> list[ActivityEvent]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT id, started_at, seconds, category, app_name, window_title, url, reason
                FROM activity_events
                WHERE id > ?
                    AND deleted_at IS NULL
                ORDER BY id ASC
                LIMIT ?
                """,
                (last_id, limit),
            ).fetchall()
        return [
            ActivityEvent(
                id=int(row[0]),
                started_at=row[1],
                seconds=int(row[2]),
                category=Category(row[3]),
                app_name=row[4],
                title=row[5],
                url=row[6],
                reason=row[7],
            )
            for row in rows
        ]

    def top_targets_for_day(self, day: date, limit: int = 10) -> list[BreakdownRow]:
        start, end = self._day_bounds(day)
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    COALESCE(NULLIF(url, ''), NULLIF(window_title, ''), app_name) AS target,
                    category,
                    COALESCE(SUM(seconds), 0) AS total_seconds
                FROM activity_events
                WHERE started_at >= ? AND started_at < ?
                    AND deleted_at IS NULL
                GROUP BY target, category
                ORDER BY total_seconds DESC
                LIMIT ?
                """,
                (start, end, limit),
            ).fetchall()
        return [BreakdownRow(row[0], Category(row[1]), int(row[2])) for row in rows]

    def neutral_candidates_for_day(self, day: date, limit: int = 10) -> list[BreakdownRow]:
        start, end = self._day_bounds(day)
        return self._neutral_candidates_between(start, end, limit)

    def neutral_candidates_for_range(self, days: int, limit: int = 30) -> list[BreakdownRow]:
        end_day = date.today()
        start_day = end_day - timedelta(days=days - 1)
        start, _ = self._day_bounds(start_day)
        _, end = self._day_bounds(end_day)
        return self._neutral_candidates_between(start, end, limit)

    def _neutral_candidates_between(self, start: str, end: str, limit: int) -> list[BreakdownRow]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    COALESCE(NULLIF(url, ''), NULLIF(window_title, ''), app_name) AS target,
                    COALESCE(SUM(seconds), 0) AS total_seconds
                FROM activity_events
                WHERE started_at >= ?
                    AND started_at < ?
                    AND deleted_at IS NULL
                    AND category = ?
                    AND reason = 'no matching rule'
                GROUP BY target
                ORDER BY total_seconds DESC
                LIMIT ?
                """,
                (start, end, Category.NEUTRAL.value, limit),
            ).fetchall()
        return [BreakdownRow(row[0], Category.NEUTRAL, int(row[1])) for row in rows]

    def top_targets_for_range(self, days: int, limit: int = 10) -> list[BreakdownRow]:
        end_day = date.today()
        start_day = end_day - timedelta(days=days - 1)
        return self.top_targets_for_period(start_day, end_day, limit)

    def top_targets_for_period(self, start_day: date, end_day: date, limit: int = 10) -> list[BreakdownRow]:
        start, end = self._period_bounds(start_day, end_day)
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    COALESCE(NULLIF(url, ''), NULLIF(window_title, ''), app_name) AS target,
                    category,
                    COALESCE(SUM(seconds), 0) AS total_seconds
                FROM activity_events
                WHERE started_at >= ? AND started_at < ?
                    AND deleted_at IS NULL
                GROUP BY target, category
                ORDER BY total_seconds DESC
                LIMIT ?
                """,
                (start, end, limit),
            ).fetchall()
        return [BreakdownRow(row[0], Category(row[1]), int(row[2])) for row in rows]

    def top_targets_between(
        self,
        started_at: datetime,
        ended_at: datetime,
        category: Category | None = None,
        limit: int = 10,
    ) -> list[BreakdownRow]:
        params: list[object] = [
            started_at.isoformat(timespec="seconds"),
            ended_at.isoformat(timespec="seconds"),
        ]
        sql_parts = [
            """
            SELECT
                COALESCE(NULLIF(url, ''), NULLIF(window_title, ''), app_name) AS target,
                category,
                COALESCE(SUM(seconds), 0) AS total_seconds
            FROM activity_events
            WHERE started_at >= ? AND started_at < ?
                AND deleted_at IS NULL
            """
        ]
        if category:
            sql_parts.append("    AND category = ?")
            params.append(category.value)
        sql_parts.append("GROUP BY target, category\nORDER BY total_seconds DESC\nLIMIT ?")
        params.append(limit)
        with self._connection() as conn:
            rows = conn.execute("\n".join(sql_parts), params).fetchall()
        return [BreakdownRow(row[0], Category(row[1]), int(row[2])) for row in rows]

    def compare_days(self, current_day: date, previous_day: date) -> DayComparison:
        return DayComparison(
            current=_single_day_summary(current_day, self.summary_for_day(current_day)),
            previous=_single_day_summary(previous_day, self.summary_for_day(previous_day)),
        )

    def daily_review(self, day: date) -> DailyReview:
        targets = self.top_targets_for_day(day, limit=50)
        productive = next((row for row in targets if row.category == Category.PRODUCTIVE), None)
        distraction = next((row for row in targets if row.category == Category.UNPRODUCTIVE), None)
        candidates = self.neutral_candidates_for_day(day, limit=1)
        return DailyReview(
            strongest_productive=productive,
            largest_distraction=distraction,
            unresolved_candidate=candidates[0] if candidates else None,
        )

    def day_flow(self, day: date) -> ActivityFlow:
        start, end = self._day_bounds(day)
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    started_at,
                    seconds,
                    category,
                    COALESCE(NULLIF(url, ''), NULLIF(window_title, ''), app_name) AS target
                FROM activity_events
                WHERE started_at >= ? AND started_at < ?
                    AND deleted_at IS NULL
                ORDER BY started_at ASC, id ASC
                """,
                (start, end),
            ).fetchall()
        if not rows:
            return ActivityFlow((), 0, 0)

        target_switches = 0
        category_switches = 0
        sessions: list[ActivitySession] = []
        current_category: Category | None = None
        current_start: datetime | None = None
        current_end: datetime | None = None
        current_seconds = 0
        current_targets: dict[str, int] = {}
        previous_target: str | None = None
        previous_category: Category | None = None

        def close_session() -> None:
            if current_category is None or current_start is None or current_end is None:
                return
            primary_label = max(current_targets.items(), key=lambda item: item[1])[0] if current_targets else ""
            sessions.append(
                ActivitySession(
                    started_at=current_start.strftime("%H:%M"),
                    ended_at=current_end.strftime("%H:%M"),
                    category=current_category,
                    seconds=current_seconds,
                    primary_label=primary_label,
                )
            )

        for started_at, seconds, category_value, target in rows:
            category = Category(category_value)
            seconds = int(seconds)
            target = str(target)
            started = datetime.fromisoformat(started_at)
            ended = started + timedelta(seconds=seconds)

            if previous_target is not None and target != previous_target:
                target_switches += 1
            if previous_category is not None and category != previous_category:
                category_switches += 1

            if current_category is not None and category != current_category:
                close_session()
                current_start = started
                current_seconds = 0
                current_targets = {}
            elif current_category is None:
                current_start = started

            current_category = category
            current_end = ended
            current_seconds += seconds
            current_targets[target] = current_targets.get(target, 0) + seconds
            previous_target = target
            previous_category = category

        close_session()
        return ActivityFlow(tuple(sessions), target_switches, category_switches)

    def weekly_progress(self, weekly_goal_minutes: int, daily_goal_minutes: int, reference_day: date | None = None) -> WeeklyProgress:
        current_day = reference_day or date.today()
        week_start = current_day - timedelta(days=current_day.weekday())
        current_rows = self._daily_summaries_between(week_start, (current_day - week_start).days + 1)
        previous_rows = self._daily_summaries_between(week_start - timedelta(days=7), 7)
        threshold = daily_goal_minutes * 60
        return WeeklyProgress(
            productive_seconds=sum(row.productive_seconds for row in current_rows),
            previous_productive_seconds=sum(row.productive_seconds for row in previous_rows),
            achieved_days=sum(1 for row in current_rows if row.productive_seconds >= threshold),
            weekly_goal_minutes=weekly_goal_minutes,
        )

    def reclassify_event(self, event_id: int, category: Category) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE activity_events
                SET category = ?, reason = ?
                WHERE id = ? AND deleted_at IS NULL
                """,
                (category.value, "manual correction", event_id),
            )

    def soft_delete_event(self, event_id: int) -> None:
        deleted_at = datetime.now().astimezone().isoformat(timespec="seconds")
        with self._connection() as conn:
            conn.execute(
                "UPDATE activity_events SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
                (deleted_at, event_id),
            )

    def purge_older_than(self, retention_days: int, reference_day: date | None = None) -> int:
        # retention_days <= 0이면 삭제 안 함. 기준일 당일 포함 이후 데이터는 유지.
        if retention_days <= 0:
            return 0
        today = reference_day or date.today()
        cutoff_day = today - timedelta(days=retention_days - 1)
        cutoff, _ = self._day_bounds(cutoff_day)
        with self._connection() as conn:
            cursor = conn.execute(
                "DELETE FROM activity_events WHERE started_at < ?",
                (cutoff,),
            )
            removed = cursor.rowcount
        if removed > 0:
            self._vacuum()
        return removed if removed and removed > 0 else 0

    def _vacuum(self) -> None:
        # VACUUM은 exclusive 접근이 필요하므로 스레드 로컬 연결을 먼저 해제
        if hasattr(self._local, 'conn'):
            self._local.conn.close()
            del self._local.conn
        conn = sqlite3.connect(self.db_path, timeout=self.connection_timeout_seconds)
        try:
            conn.execute("VACUUM")
        finally:
            conn.close()

    def restore_last_deleted(self) -> int | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT id
                FROM activity_events
                WHERE deleted_at IS NOT NULL
                ORDER BY deleted_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
            if not row:
                return None
            event_id = int(row[0])
            conn.execute("UPDATE activity_events SET deleted_at = NULL WHERE id = ?", (event_id,))
        return event_id

    def export_csv_for_day(self, day: date, output_path: Path) -> int:
        return self.export_csv_for_period(day, day, output_path)

    def export_csv_for_period(self, start_day: date, end_day: date, output_path: Path) -> int:
        start, end = self._period_bounds(start_day, end_day)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT started_at, seconds, category, app_name, window_title, url, reason
                FROM activity_events
                WHERE started_at >= ? AND started_at < ?
                    AND deleted_at IS NULL
                ORDER BY started_at ASC
                """,
                (start, end),
            ).fetchall()

        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["started_at", "seconds", "category", "app_name", "window_title", "url", "reason"])
            writer.writerows(tuple(_sanitize_csv_cell(cell) for cell in row) for row in rows)
        return len(rows)

    def daily_summaries(self, days: int) -> list[DaySummary]:
        end_day = date.today()
        start_day = end_day - timedelta(days=days - 1)
        return self._daily_summaries_between(start_day, days)

    def summaries_between(self, start_day: date, end_day: date) -> list[DaySummary]:
        if end_day < start_day:
            raise ValueError("end_day must be on or after start_day")
        return self._daily_summaries_between(start_day, (end_day - start_day).days + 1)

    def _daily_summaries_between(self, start_day: date, days: int) -> list[DaySummary]:
        start, _ = self._day_bounds(start_day)
        _, end = self._day_bounds(start_day + timedelta(days=days - 1))
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT SUBSTR(started_at, 1, 10) AS day, category, COALESCE(SUM(seconds), 0)
                FROM activity_events
                WHERE started_at >= ? AND started_at < ?
                    AND deleted_at IS NULL
                GROUP BY day, category
                ORDER BY day ASC
                """,
                (start, end),
            ).fetchall()
        return _daily_rows(start_day, days, rows)

    def month_summaries(self, day: date | None = None) -> list[DaySummary]:
        current = day or date.today()
        start_day = date(current.year, current.month, 1)
        if current.month == 12:
            next_month = date(current.year + 1, 1, 1)
        else:
            next_month = date(current.year, current.month + 1, 1)
        start, _ = self._day_bounds(start_day)
        end, _ = self._day_bounds(next_month)
        days = (next_month - start_day).days
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT SUBSTR(started_at, 1, 10) AS day, category, COALESCE(SUM(seconds), 0)
                FROM activity_events
                WHERE started_at >= ? AND started_at < ?
                    AND deleted_at IS NULL
                GROUP BY day, category
                ORDER BY day ASC
                """,
                (start, end),
            ).fetchall()
        return _daily_rows(start_day, days, rows)

    def hourly_summaries(self, days: int = 7) -> list[HourSummary]:
        end_day = date.today()
        start_day = end_day - timedelta(days=days - 1)
        return self.hourly_summaries_between(start_day, end_day)

    def hourly_summaries_between(self, start_day: date, end_day: date) -> list[HourSummary]:
        start, end = self._period_bounds(start_day, end_day)
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT CAST(SUBSTR(started_at, 12, 2) AS INTEGER) AS hour, category, COALESCE(SUM(seconds), 0)
                FROM activity_events
                WHERE started_at >= ? AND started_at < ?
                    AND deleted_at IS NULL
                GROUP BY hour, category
                ORDER BY hour ASC
                """,
                (start, end),
            ).fetchall()
        by_hour = {hour: {category: 0 for category in Category} for hour in range(24)}
        for hour, category, seconds in rows:
            by_hour[int(hour)][Category(category)] = int(seconds)
        return [
            HourSummary(
                hour=hour,
                productive_seconds=values[Category.PRODUCTIVE],
                unproductive_seconds=values[Category.UNPRODUCTIVE],
                neutral_seconds=values[Category.NEUTRAL],
            )
            for hour, values in by_hour.items()
        ]

    def weekday_summaries_between(self, start_day: date, end_day: date) -> list[WeekdaySummary]:
        start, end = self._period_bounds(start_day, end_day)
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT CAST(strftime('%w', started_at) AS INTEGER) AS weekday, category, COALESCE(SUM(seconds), 0)
                FROM activity_events
                WHERE started_at >= ? AND started_at < ?
                    AND deleted_at IS NULL
                GROUP BY weekday, category
                ORDER BY weekday ASC
                """,
                (start, end),
            ).fetchall()
        by_weekday = {weekday: {category: 0 for category in Category} for weekday in range(7)}
        for sqlite_weekday, category, seconds in rows:
            weekday = (int(sqlite_weekday) + 6) % 7
            by_weekday[weekday][Category(category)] = int(seconds)
        return [
            WeekdaySummary(
                weekday=weekday,
                productive_seconds=values[Category.PRODUCTIVE],
                unproductive_seconds=values[Category.UNPRODUCTIVE],
                neutral_seconds=values[Category.NEUTRAL],
            )
            for weekday, values in by_weekday.items()
        ]

    def weekday_hour_totals_between(self, start_day: date, end_day: date) -> list[list[int]]:
        # 요일(월=0 ~ 일=6) × 시간(0~23) 2차원 배열로 총 추적 초 반환
        start, end = self._period_bounds(start_day, end_day)
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    CAST(strftime('%w', started_at) AS INTEGER) AS weekday,
                    CAST(SUBSTR(started_at, 12, 2) AS INTEGER) AS hour,
                    COALESCE(SUM(seconds), 0) AS total
                FROM activity_events
                WHERE started_at >= ? AND started_at < ?
                    AND deleted_at IS NULL
                GROUP BY weekday, hour
                """,
                (start, end),
            ).fetchall()
        grid = [[0 for _ in range(24)] for _ in range(7)]
        for sqlite_weekday, hour, total in rows:
            weekday = (int(sqlite_weekday) + 6) % 7
            grid[weekday][int(hour)] = int(total)
        return grid

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(self.db_path, timeout=self.connection_timeout_seconds)
        conn = self._local.conn
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _init_db(self) -> None:
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS activity_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    seconds INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    app_name TEXT NOT NULL,
                    window_title TEXT NOT NULL,
                    url TEXT,
                    reason TEXT NOT NULL,
                    event_count INTEGER NOT NULL DEFAULT 1,
                    deleted_at TEXT
                )
                """
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(activity_events)").fetchall()}
            if "event_count" not in columns:
                conn.execute("ALTER TABLE activity_events ADD COLUMN event_count INTEGER NOT NULL DEFAULT 1")
            if "deleted_at" not in columns:
                conn.execute("ALTER TABLE activity_events ADD COLUMN deleted_at TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_started_at ON activity_events(started_at)")

    def _day_bounds(self, day: date) -> tuple[str, str]:
        local_timezone = datetime.now().astimezone().tzinfo
        start = datetime(day.year, day.month, day.day, tzinfo=local_timezone)
        end = start + timedelta(days=1)
        return start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")

    def _period_bounds(self, start_day: date, end_day: date) -> tuple[str, str]:
        if end_day < start_day:
            raise ValueError("end_day must be on or after start_day")
        start, _ = self._day_bounds(start_day)
        _, end = self._day_bounds(end_day)
        return start, end


# 스프레드시트가 수식 시작으로 인식하는 문자 목록.
# 창 제목·URL은 외부 입력이므로 =cmd|'/c calc'!A1 같은 수식 인젝션(CWE-1236) 위험이 있음.
_CSV_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def _sanitize_csv_cell(cell: object) -> object:
    # 수식 시작 문자 앞에 어포스트로피를 붙여 리터럴 텍스트로 강제. 숫자 셀은 그대로 반환.
    if isinstance(cell, str) and cell.startswith(_CSV_FORMULA_TRIGGERS):
        return "'" + cell
    return cell


def _daily_rows(start_day: date, days: int, rows: list[tuple[str, str, int]]) -> list[DaySummary]:
    by_day = {
        (start_day + timedelta(days=offset)).isoformat(): {category: 0 for category in Category}
        for offset in range(days)
    }
    for day, category, seconds in rows:
        if day in by_day:
            by_day[day][Category(category)] = int(seconds)
    return [
        DaySummary(
            day=day,
            productive_seconds=values[Category.PRODUCTIVE],
            unproductive_seconds=values[Category.UNPRODUCTIVE],
            neutral_seconds=values[Category.NEUTRAL],
        )
        for day, values in by_day.items()
    ]


def _single_day_summary(day: date, rows: list[SummaryRow]) -> DaySummary:
    values = {category: 0 for category in Category}
    for row in rows:
        values[row.category] = row.seconds
    return DaySummary(
        day=day.isoformat(),
        productive_seconds=values[Category.PRODUCTIVE],
        unproductive_seconds=values[Category.UNPRODUCTIVE],
        neutral_seconds=values[Category.NEUTRAL],
    )


def _longest_session(sessions: tuple[ActivitySession, ...], category: Category) -> ActivitySession | None:
    matching = [session for session in sessions if session.category == category]
    if not matching:
        return None
    return max(matching, key=lambda session: session.seconds)
