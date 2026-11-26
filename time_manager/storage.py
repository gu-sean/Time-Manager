import csv
import json
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Iterator

from time_manager.local_model import Signature
from time_manager.models import (
    MANUAL_APP,
    MANUAL_ENTRY_REASON,
    NO_RULE_REASON,
    PRIVATE_REASON,
    ActiveTarget,
    Category,
    ClassifiedActivity,
)


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


# 이보다 긴 공백이 있으면 분류가 같아도 다른 구간 (자리 비움 기준과 같은 5분)
SESSION_BREAK_SECONDS = 5 * 60


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
class EventTarget:
    """기록 하나의 대상과 현재 분류."""

    app_name: str
    title: str
    url: str | None
    category: Category


# 사용자가 직접 바꾼 분류
_MANUAL_REASON = "manual correction"
# 삭제한 기록을 되돌릴 수 있는 시간. 지나면 파일에서도 지움
RESTORE_HOURS = 24


@dataclass(frozen=True)
class Reclassification:
    id: int
    app_name: str
    url: str | None
    seconds: int
    old: Category
    new: Category
    reason: str


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
        # 모든 스레드의 연결: 하나라도 열려 있으면 종료할 때 평문 DB 를 지울 수 없음
        self._connections: list[tuple[threading.Thread, sqlite3.Connection]] = []
        self._connections_lock = threading.Lock()
        self._closed = False
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
            ORDER BY started_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
        if not row:
            return False

        event_id, started_at, existing_seconds, category, app_name, title, url, reason = row
        # 날짜가 바뀌면 새 행: 일별 집계는 시작 날짜 기준
        if str(started_at)[:10] != now[:10]:
            return False
        target = activity.target
        if (
            category != activity.category.value
            or app_name != target.app_name
            or reason != activity.reason
        ):
            return False
        # 같은 URL 이면 창 제목이 바뀌어도 병합 (같은 사이트 안의 페이지 이동 등)
        # URL 이 없으면 창 제목이 완전히 같아야 병합
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

    def remove_recent_seconds(self, seconds: int) -> None:
        """가장 최근 기록부터 ``seconds`` 만큼 뺌 (자리를 비운 것으로 확인된 시간)."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT id, seconds FROM activity_events WHERE deleted_at IS NULL"
                " ORDER BY started_at DESC, id DESC LIMIT ?",
                (max(1, seconds),),  # 행마다 1초 이상
            ).fetchall()
            for event_id, recorded in rows:
                if seconds <= 0:
                    break
                if recorded <= seconds:
                    # 삭제 목록에 넣지 않음: 사용자가 지운 기록의 "복원" 대상이 아님
                    conn.execute("DELETE FROM activity_events WHERE id = ?", (event_id,))
                else:
                    conn.execute("UPDATE activity_events SET seconds = seconds - ? WHERE id = ?", (seconds, event_id))
                seconds -= recorded

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
                ORDER BY started_at DESC, id DESC
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

    def recent_for_day(self, day: date, limit: int | None = 30) -> list[RecentRow]:
        """그날의 기록, 최신순. ``limit`` 이 None 이면 전부."""
        start, end = self._day_bounds(day)
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT id, started_at, seconds, category, app_name, window_title, url, reason
                FROM activity_events
                WHERE started_at >= ? AND started_at < ?
                    AND deleted_at IS NULL
                ORDER BY started_at DESC, id DESC
                LIMIT ?
                """,
                (start, end, -1 if limit is None else limit),  # SQLite: 음수는 제한 없음
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
            escaped = query.strip().lower().replace("!", "!!").replace("%", "!%").replace("_", "!_")
            like = f"%{escaped}%"
            sql_parts.append(
                "    AND (LOWER(app_name) LIKE ? ESCAPE '!' OR LOWER(window_title) LIKE ? ESCAPE '!' OR LOWER(COALESCE(url, '')) LIKE ? ESCAPE '!')"
            )
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
        return self.top_targets_for_period(day, day, limit)

    def neutral_candidates_for_day(self, day: date, limit: int = 10) -> list[BreakdownRow]:
        return self._neutral_candidates_between(day, day, limit)

    def neutral_candidates_for_range(self, days: int, limit: int = 30) -> list[BreakdownRow]:
        end_day = date.today()
        start_day = end_day - timedelta(days=days - 1)
        return self._neutral_candidates_between(start_day, end_day, limit)

    def _neutral_candidates_between(self, start_day: date, end_day: date, limit: int) -> list[BreakdownRow]:
        return self.app_domain_totals(start_day, end_day, unmatched_only=True)[:limit]

    def app_domain_totals(
        self, start_day: date, end_day: date, *, unmatched_only: bool = False
    ) -> list[BreakdownRow]:
        """도메인(URL 이 있을 때) 또는 앱 이름별 합계. 창 제목으로는 묶지 않음.

        - AI 기능에서 사용: 창 제목·URL 경로가 PC 밖으로 나가지 않게 함
        """
        from time_manager.rules import _domain_from_url

        start, end = self._period_bounds(start_day, end_day)
        sql = """
            SELECT app_name, COALESCE(url, ''), category, COALESCE(SUM(seconds), 0)
            FROM activity_events
            WHERE started_at >= ? AND started_at < ?
                AND deleted_at IS NULL
        """
        params: list[object] = [start, end]
        if unmatched_only:
            sql += " AND category = ? AND reason = 'no matching rule'"
            params.append(Category.NEUTRAL.value)
        sql += " GROUP BY app_name, url, category"
        with self._connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        totals: dict[tuple[str, Category], int] = {}
        for app_name, url, category, seconds in rows:
            target = _domain_from_url(url) or (app_name or "").strip()
            if not target:
                continue
            key = (target, Category(category))
            totals[key] = totals.get(key, 0) + int(seconds)
        ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)
        return [BreakdownRow(target, category, seconds) for (target, category), seconds in ranked]

    def ensure_schema(self) -> None:
        """없는 테이블 추가 (예: 구버전 백업으로 DB 파일이 교체된 경우)."""
        self._init_db()

    # -- 코칭 기록: 기간·분석 방식별 최신 결과 -------------------------------------

    def save_coaching(
        self, *, scope: str, start_day: str, end_day: str, source: str, generated: bool,
        headline: str, insights: list[str], actions: list[str], fingerprint: str,
    ) -> str:
        created_at = datetime.now().astimezone().isoformat(timespec="seconds")
        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO coaching_history
                    (created_at, scope, start_day, end_day, source, generated, headline, insights, actions, fingerprint)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at, scope, start_day, end_day, source, int(generated), headline,
                    json.dumps(insights, ensure_ascii=False), json.dumps(actions, ensure_ascii=False), fingerprint,
                ),
            )
        return created_at

    def find_coaching(self, fingerprint: str) -> dict[str, object] | None:
        """완전히 같은 요청으로 저장된 결과 (있으면)."""
        rows = self._coaching_rows("WHERE fingerprint = ?", (fingerprint,), 1)
        return rows[0] if rows else None

    def list_coaching(self, limit: int = 50) -> list[dict[str, object]]:
        return self._coaching_rows("", (), limit)

    def _coaching_rows(self, where: str, params: tuple[object, ...], limit: int) -> list[dict[str, object]]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT id, created_at, scope, start_day, end_day, source, generated, headline, insights, actions"
                f" FROM coaching_history {where} ORDER BY created_at DESC, id DESC LIMIT ?",
                (*params, limit),
            ).fetchall()
        keys = ("id", "createdAt", "scope", "startDay", "endDay", "source", "generated", "headline")
        return [
            {**dict(zip(keys, row)), "generated": bool(row[6]),
             "insights": json.loads(row[8]), "actions": json.loads(row[9])}
            for row in rows
        ]

    def delete_coaching(self, entry_id: int) -> None:
        with self._connection() as conn:
            conn.execute("DELETE FROM coaching_history WHERE id = ?", (entry_id,))

    def clear_coaching(self) -> None:
        with self._connection() as conn:
            conn.execute("DELETE FROM coaching_history")

    def first_activity_day(self) -> date | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT MIN(started_at) FROM activity_events WHERE deleted_at IS NULL"
            ).fetchone()
        return date.fromisoformat(row[0][:10]) if row and row[0] else None

    def activity_signatures(
        self, start_day: date | None = None, end_day: date | None = None
    ) -> list[Signature]:
        """내장 분류기에 쓰는 서로 다른 활동 조합.

        - 창 제목이 포함되므로 결과를 PC 밖으로 보내면 안 됨
        """
        sql = """
            SELECT app_name, COALESCE(url, ''), window_title, category, reason, COALESCE(SUM(seconds), 0)
            FROM activity_events
            WHERE deleted_at IS NULL
        """
        params: list[object] = []
        if start_day is not None and end_day is not None:
            start, end = self._period_bounds(start_day, end_day)
            sql += " AND started_at >= ? AND started_at < ?"
            params = [start, end]
        sql += " GROUP BY app_name, url, window_title, category, reason"
        with self._connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            Signature(row[0], row[1], row[2], Category(row[3]), row[4], int(row[5]))
            for row in rows
        ]

    def top_targets_for_range(self, days: int, limit: int = 10) -> list[BreakdownRow]:
        end_day = date.today()
        start_day = end_day - timedelta(days=days - 1)
        return self.top_targets_for_period(start_day, end_day, limit)

    def top_targets_for_period(self, start_day: date, end_day: date, limit: int = 10) -> list[BreakdownRow]:
        """많이 쓴 대상: 같은 사이트의 페이지, 같은 앱의 창은 하나로 묶음."""
        return self.app_domain_totals(start_day, end_day)[:limit]

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

            new_session = (
                current_end is None
                or category != current_category
                or (started - current_end).total_seconds() > SESSION_BREAK_SECONDS
            )
            if new_session:
                close_session()  # 첫 행이면 닫을 구간이 없음
                current_start = started
                current_end = ended
                current_seconds = 0
                current_targets = {}

            current_category = category
            current_end = max(current_end, ended)  # 겹치는 행이 끝 시각을 당기지 않게 함
            current_seconds += seconds
            current_targets[target] = current_targets.get(target, 0) + seconds
            previous_target = target
            previous_category = category

        close_session()
        return ActivityFlow(tuple(sessions), target_switches, category_switches)

    def weekly_progress(
        self,
        weekly_goal_minutes: int,
        daily_goal_minutes: int,
        reference_day: date | None = None,
        now: datetime | None = None,
        goal_weekdays: frozenset[int] | set[int] | None = None,
    ) -> WeeklyProgress:
        """이번 주 월요일 ~ 기준일의 생산 시간과, 지난주의 같은 구간.

        - 기준일이 오늘이면 지난주 같은 요일은 지금 시각까지만 계산 (끝나지 않은 오늘과 맞춤)
        - 기준일이 지난 날이면 하루 전체를 비교 (일요일 기준 = 두 주 전체)
        """
        now = now or datetime.now()
        current_day = reference_day or now.date()
        week_start = current_day - timedelta(days=current_day.weekday())
        days = current_day.weekday() + 1
        current_rows = self._daily_summaries_between(week_start, days)

        unfinished = current_day == now.date()
        full_days = days - 1 if unfinished else days
        previous_start = week_start - timedelta(days=7)
        previous = 0
        if full_days:
            previous = sum(
                row.productive_seconds for row in self._daily_summaries_between(previous_start, full_days)
            )
        if unfinished:
            same_day = current_day - timedelta(days=7)
            previous += self.category_totals_before(datetime.combine(same_day, now.time()))[Category.PRODUCTIVE]

        threshold = daily_goal_minutes * 60
        return WeeklyProgress(
            productive_seconds=sum(row.productive_seconds for row in current_rows),
            previous_productive_seconds=previous,
            # 목표를 쉬는 요일은 세지 않음
            achieved_days=sum(
                1
                for row in current_rows
                if row.productive_seconds >= threshold
                and (goal_weekdays is None or date.fromisoformat(row.day).weekday() in goal_weekdays)
            ),
            weekly_goal_minutes=weekly_goal_minutes,
        )

    def category_totals_before(self, cutoff: datetime) -> dict[Category, int]:
        """``cutoff`` 날짜의 기록 중 ``cutoff`` 시각 전까지의 분류별 합."""
        start, end = self._day_bounds(cutoff.date())
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT started_at, seconds, category
                FROM activity_events
                WHERE started_at >= ? AND started_at < ?
                    AND deleted_at IS NULL
                """,
                (start, end),
            ).fetchall()
        totals = {category: 0 for category in Category}
        for started_at, seconds, category in rows:
            started = datetime.fromisoformat(started_at).replace(tzinfo=None)  # 기록된 벽시계 시각
            totals[Category(category)] += min(int(seconds), max(0, int((cutoff - started).total_seconds())))
        return totals

    def get_event(self, event_id: int) -> EventTarget | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT app_name, window_title, url, category FROM activity_events WHERE id = ? AND deleted_at IS NULL",
                (event_id,),
            ).fetchone()
        if row is None:
            return None
        return EventTarget(str(row[0] or ""), str(row[1] or ""), row[2], Category(row[3]))

    def reclassification_changes(
        self, classify: Callable[[ActiveTarget], ClassifiedActivity]
    ) -> list[Reclassification]:
        """지금 규칙을 지난 기록에 적용하면 분류가 달라지는 기록.

        - 직접 바꾼 분류, 직접 입력한 기록, 비공개 창, 삭제한 기록은 제외
        - 맞는 규칙이 없으면 그대로 둠: 창 제목을 저장하지 않은 기록은 제목 규칙으로 다시 판단할 수 없음
        """
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT id, app_name, window_title, url, category, seconds
                FROM activity_events
                WHERE deleted_at IS NULL AND reason NOT IN (?, ?, ?)
                """,
                (_MANUAL_REASON, MANUAL_ENTRY_REASON, PRIVATE_REASON),
            ).fetchall()
        results: dict[tuple[str, str, str | None], ClassifiedActivity] = {}
        changes = []
        for event_id, app_name, title, url, category, seconds in rows:
            key = (app_name or "", title or "", url)
            if key not in results:
                results[key] = classify(ActiveTarget(*key))
            result = results[key]
            if result.reason == NO_RULE_REASON or result.category.value == category:
                continue
            changes.append(
                Reclassification(int(event_id), key[0], url, int(seconds), Category(category), result.category, result.reason)
            )
        return changes

    def apply_reclassification(self, changes: list[Reclassification]) -> int:
        with self._connection() as conn:
            cursor = conn.executemany(
                "UPDATE activity_events SET category = ?, reason = ?"
                " WHERE id = ? AND deleted_at IS NULL AND reason != ?",
                [(item.new.value, item.reason, item.id, _MANUAL_REASON) for item in changes],
            )
        return max(0, cursor.rowcount)

    def reclassify_event(self, event_id: int, category: Category) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE activity_events
                SET category = ?, reason = ?
                WHERE id = ? AND deleted_at IS NULL
                """,
                (category.value, _MANUAL_REASON, event_id),
            )

    def purge_deleted(self, hours: int = RESTORE_HOURS, now: datetime | None = None) -> int:
        """되돌릴 수 있는 시간이 지난 삭제 기록을 파일에서 지움."""
        cutoff = ((now or datetime.now().astimezone()) - timedelta(hours=hours)).isoformat(timespec="seconds")
        with self._connection() as conn:
            cursor = conn.execute(
                "DELETE FROM activity_events WHERE deleted_at IS NOT NULL AND deleted_at <= ?", (cutoff,)
            )
        return max(0, cursor.rowcount)

    def _target_ids(self, conn: sqlite3.Connection, kind: str, value: str) -> list[tuple[int, int]]:
        """(id, 초): ``kind`` 가 "domain" 이면 그 사이트(하위 도메인 포함), "app" 이면 주소가 없는 그 앱의 기록."""
        from time_manager.rules import _domain_from_url, _matches_domain

        wanted = value.strip().lower()
        found = []
        for event_id, seconds, app_name, url in conn.execute(
            "SELECT id, seconds, app_name, COALESCE(url, '') FROM activity_events"
        ):
            domain = _domain_from_url(url)
            if kind == "domain" and domain and _matches_domain(domain, (wanted,)):
                found.append((int(event_id), int(seconds)))
            elif kind == "app" and not domain and str(app_name).lower() == wanted:
                found.append((int(event_id), int(seconds)))
        return found

    def count_target(self, kind: str, value: str) -> tuple[int, int]:
        """(건수, 초). 삭제한 기록은 세지 않음."""
        with self._connection() as conn:
            ids = self._target_ids(conn, kind, value)
            if not ids:
                return 0, 0
            live = {
                int(row[0])
                for row in conn.execute("SELECT id FROM activity_events WHERE deleted_at IS NULL")
            }
        kept = [seconds for event_id, seconds in ids if event_id in live]
        return len(kept), sum(kept)

    def delete_target(self, kind: str, value: str) -> int:
        """그 사이트·앱의 모든 기록을 완전히 지움 (되돌릴 수 없음)."""
        with self._connection() as conn:
            ids = [event_id for event_id, _ in self._target_ids(conn, kind, value)]
            conn.executemany("DELETE FROM activity_events WHERE id = ?", [(event_id,) for event_id in ids])
        return len(ids)

    def count_period(self, start_day: date, end_day: date) -> tuple[int, int]:
        start, end = self._period_bounds(start_day, end_day)
        with self._connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(seconds), 0) FROM activity_events"
                " WHERE started_at >= ? AND started_at < ? AND deleted_at IS NULL",
                (start, end),
            ).fetchone()
        return int(row[0]), int(row[1])

    def delete_period(self, start_day: date, end_day: date) -> int:
        """기간의 모든 기록을 완전히 지움 (삭제 대기 중인 것 포함, 되돌릴 수 없음)."""
        start, end = self._period_bounds(start_day, end_day)
        with self._connection() as conn:
            cursor = conn.execute(
                "DELETE FROM activity_events WHERE started_at >= ? AND started_at < ?", (start, end)
            )
        return max(0, cursor.rowcount)

    def overlapping(self, started: datetime, seconds: int) -> list[RecentRow]:
        """``started`` 부터 ``seconds`` 동안과 겹치는 기록."""
        ended = started + timedelta(seconds=seconds)
        rows = self.recent_for_day(started.date(), limit=None) + self.recent_for_day(
            started.date() - timedelta(days=1), limit=None
        )
        found = []
        for row in rows:
            begin = datetime.fromisoformat(row.started_at)
            if begin < ended and begin + timedelta(seconds=row.seconds) > started:
                found.append(row)
        return found

    def add_manual_entry(self, started: datetime, seconds: int, label: str, category: Category) -> int:
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO activity_events (started_at, seconds, category, app_name, window_title, url, reason)
                VALUES (?, ?, ?, ?, ?, NULL, ?)
                """,
                (started.isoformat(timespec="seconds"), seconds, category.value, MANUAL_APP, label,
                 MANUAL_ENTRY_REASON),
            )
        return int(cursor.lastrowid)

    def soft_delete_event(self, event_id: int) -> None:
        deleted_at = datetime.now().astimezone().isoformat(timespec="seconds")
        with self._connection() as conn:
            conn.execute(
                "UPDATE activity_events SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
                (deleted_at, event_id),
            )

    def purge_older_than(self, retention_days: int, reference_day: date | None = None) -> int:
        # retention_days <= 0 이면 삭제 안 함. 기준일 당일을 포함한 이후 데이터는 유지
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
            # 코칭 결과도 같은 활동을 인용하므로 같은 보존 기간 적용
            conn.execute("DELETE FROM coaching_history WHERE end_day < ?", (cutoff_day.isoformat(),))
        if removed > 0:
            self._vacuum()
        return removed if removed and removed > 0 else 0

    def _vacuum(self) -> None:
        # VACUUM 은 배타적 접근이 필요 → 스레드 로컬 연결을 먼저 해제
        self._release_own_connection()
        conn = sqlite3.connect(self.db_path, timeout=self.connection_timeout_seconds)
        try:
            conn.execute("PRAGMA secure_delete = ON")
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

        with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(_CSV_HEADERS)
            writer.writerows(_format_csv_row(row) for row in rows)
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
        rows = [(hour, category, seconds) for _, hour, category, seconds, _, _ in self._clock_hour_slices(start_day, end_day)]
        by_hour = {hour: {category: 0 for category in Category} for hour in range(24)}
        for hour, category, seconds in rows:
            by_hour[int(hour)][Category(category)] += int(seconds)  # 같은 시각의 기록이 여러 개
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
        # 요일(월=0 ~ 일=6) × 시간(0~23) 2차원 배열: 총 추적 초
        grid = [[0 for _ in range(24)] for _ in range(7)]
        for day, hour, _, seconds, _, _ in self._clock_hour_slices(start_day, end_day):
            grid[day.weekday()][hour] += seconds
        return grid

    def target_hour_totals(self, start_day: date, end_day: date) -> list[tuple[int, BreakdownRow]]:
        """``app_domain_totals`` 와 같되 하루의 시각(0~23시)별로 나눔."""
        from time_manager.rules import _domain_from_url

        totals: dict[tuple[int, str, str], int] = {}
        for _, hour, category, seconds, app_name, url in self._clock_hour_slices(start_day, end_day):
            target = _domain_from_url(url) or app_name.strip()
            if target:
                key = (hour, target, category)
                totals[key] = totals.get(key, 0) + seconds
        return [
            (hour, BreakdownRow(target, Category(category), seconds))
            for (hour, target, category), seconds in totals.items()
        ]

    def _clock_hour_slices(
        self, start_day: date, end_day: date
    ) -> Iterator[tuple[date, int, str, int, str, str]]:
        """실제 사용한 시각별 조각: (날짜, 시, 분류, 초, 앱, url).

        - 이어진 사용은 첫 시점에서 시작하는 한 행으로 저장 → 지나간 정시마다 잘라야 함
        - 기간 전날도 읽음: 전날 마지막 행이 자정을 넘길 수 있음
        """
        start, end = self._period_bounds(start_day - timedelta(days=1), end_day)
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT started_at, seconds, category, COALESCE(app_name, ''), COALESCE(url, '')
                FROM activity_events
                WHERE started_at >= ? AND started_at < ?
                    AND deleted_at IS NULL
                """,
                (start, end),
            ).fetchall()
        for started_at, seconds, category, app_name, url in rows:
            for day, hour, part in _split_by_hour(str(started_at), int(seconds)):
                if start_day <= day <= end_day:
                    yield day, hour, category, part, str(app_name), str(url)

    def close(self) -> None:
        """모든 스레드의 SQLite 연결 닫기. 이후 사용하면 새로 엶."""
        with self._connections_lock:
            for _, conn in self._connections:
                conn.close()
            self._connections.clear()
            self._local = threading.local()  # 다른 스레드에 남은 닫힌 연결도 버림

    def shutdown(self) -> None:
        """앱 종료용: 모두 닫고 다시 열지 않음 (DB 파일 암호화 전에 호출).

        - 늦게 도착한 화면 요청이 DB 를 다시 여는 것 방지
        """
        with self._connections_lock:
            self._closed = True
        self.close()

    def _open_connection(self) -> sqlite3.Connection:
        with self._connections_lock:
            if self._closed:
                raise sqlite3.ProgrammingError("ActivityStore is closed")
            # 화면 요청마다 스레드가 새로 생김 → 끝난 스레드의 연결은 바로 정리
            alive = []
            for owner, conn in self._connections:
                if owner.is_alive():
                    alive.append((owner, conn))
                else:
                    conn.close()
            # 각 연결은 만든 스레드만 사용. 검사를 끄는 것은 다른 스레드에서 닫기 위함
            conn = sqlite3.connect(self.db_path, timeout=self.connection_timeout_seconds, check_same_thread=False)
            # 지운 기록의 내용이 파일의 빈 공간에 남지 않게 덮어씀
            conn.execute("PRAGMA secure_delete = ON")
            self._connections = [*alive, (threading.current_thread(), conn)]
        return conn

    def _release_own_connection(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            return
        with self._connections_lock:
            self._connections = [item for item in self._connections if item[1] is not conn]
        conn.close()
        del self._local.conn

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        if not hasattr(self._local, 'conn'):
            self._local.conn = self._open_connection()
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
            _split_rows_at_midnight(conn)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS coaching_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    start_day TEXT NOT NULL,
                    end_day TEXT NOT NULL,
                    source TEXT NOT NULL,
                    generated INTEGER NOT NULL,
                    headline TEXT NOT NULL,
                    insights TEXT NOT NULL,
                    actions TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    UNIQUE (scope, start_day, end_day, source)
                )
                """
            )

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


def _split_rows_at_midnight(conn: sqlite3.Connection) -> None:
    """자정을 넘긴 행을 날짜별 행으로 나눔 (합계는 그대로).

    - 이전 버전이 저장한 기록과 복원한 백업용. 여러 번 실행해도 결과가 같음
    """
    rows = conn.execute(
        """
        SELECT id, started_at, seconds, category, app_name, window_title, url, reason, deleted_at
        FROM activity_events
        WHERE CAST(SUBSTR(started_at, 12, 2) AS INTEGER) * 3600
            + CAST(SUBSTR(started_at, 15, 2) AS INTEGER) * 60
            + CAST(SUBSTR(started_at, 18, 2) AS INTEGER)
            + seconds > 86400
        """
    ).fetchall()
    for event_id, started_at, seconds, *copied, deleted_at in rows:
        try:
            moment = datetime.fromisoformat(started_at)
        except ValueError:
            continue
        parts: list[tuple[datetime, int]] = []
        remaining = int(seconds)
        while remaining > 0:
            midnight = moment.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            part = min(remaining, int((midnight - moment).total_seconds()))
            parts.append((moment, part))
            remaining -= part
            moment = midnight
        conn.execute("UPDATE activity_events SET seconds = ? WHERE id = ?", (parts[0][1], event_id))
        conn.executemany(
            """
            INSERT INTO activity_events
                (started_at, seconds, category, app_name, window_title, url, reason, deleted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [(at.isoformat(timespec="seconds"), part, *copied, deleted_at) for at, part in parts[1:]],
        )


def _split_by_hour(started_at: str, seconds: int) -> Iterator[tuple[date, int, int]]:
    try:
        moment = datetime.fromisoformat(started_at)
    except ValueError:
        return
    while seconds > 0:
        next_hour = moment.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        part = min(seconds, max(1, int((next_hour - moment).total_seconds())))
        yield moment.date(), moment.hour, part
        seconds -= part
        moment = next_hour


# 스프레드시트가 수식 시작으로 인식하는 문자
# 창 제목·URL 은 외부 입력: =cmd|'/c calc'!A1 같은 수식 인젝션(CWE-1236) 위험
_CSV_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")

_CATEGORY_KO: dict[str, str] = {
    "productive": "생산적",
    "unproductive": "비생산적",
    "neutral": "중립",
}

_CSV_HEADERS = ["날짜", "시작 시간", "종료 시간", "소요 시간", "분류", "앱", "창 제목", "URL", "분류 근거"]


def _sanitize_csv_cell(cell: object) -> object:
    # 수식 시작 문자 앞에 어포스트로피를 붙여 문자열로 강제 (숫자 셀은 그대로)
    if isinstance(cell, str) and cell.startswith(_CSV_FORMULA_TRIGGERS):
        return "'" + cell
    return cell


def _fmt_duration(seconds: int) -> str:
    h, rem = divmod(max(0, seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"


def _format_csv_row(raw: tuple) -> tuple:
    started_at_raw, seconds, category, app_name, window_title, url, reason = raw
    secs = int(seconds) if seconds else 0
    try:
        dt_start = datetime.fromisoformat(str(started_at_raw))
        dt_end = dt_start + timedelta(seconds=secs)
        date_str = dt_start.strftime("%Y-%m-%d")
        start_str = dt_start.strftime("%H:%M:%S")
        end_str = dt_end.strftime("%H:%M:%S")
    except (ValueError, TypeError):
        date_str = str(started_at_raw)
        start_str = ""
        end_str = ""
    return (
        date_str,
        start_str,
        end_str,
        _fmt_duration(secs),
        _CATEGORY_KO.get(str(category), str(category)),
        _sanitize_csv_cell(app_name),
        _sanitize_csv_cell(window_title),
        _sanitize_csv_cell(url) if url else "",
        _sanitize_csv_cell(reason) if reason else "",
    )


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
