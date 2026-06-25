from datetime import date, timedelta


def _format_seconds(seconds: int) -> str:
    minutes, remainder = divmod(max(0, seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}시간 {minutes}분"
    if minutes:
        return f"{minutes}분"
    return f"{remainder}초"


def _dashboard_date_label(day: date, today: date) -> str:
    if day == today:
        return "오늘"
    weekdays = ("월", "화", "수", "목", "금", "토", "일")
    return f"{day.month}월 {day.day}일({weekdays[day.weekday()]})"


def _hero_date_label(day: date, today: date) -> str:
    prefix = "오늘" if day == today else "기록"
    return f"{prefix} · {day.month}월 {day.day}일"


def _shift_selected_day(day: date, delta: int, today: date) -> date:
    return min(today, day + timedelta(days=delta))


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "..."


def _format_percent(value: float) -> str:
    return f"{round(value * 100):d}%"


def _heat_color(intensity: float) -> str:
    # intensity(0~1)로 배경색 → 테라코타 포인트 색 선형 보간
    intensity = max(0.0, min(1.0, intensity))
    base = (0xF3, 0xF1, 0xEB)  # 배경색
    peak = (0xBA, 0x6A, 0x49)  # 포인트 색(테라코타)
    blended = tuple(round(b + (p - b) * intensity) for b, p in zip(base, peak))
    return f"#{blended[0]:02X}{blended[1]:02X}{blended[2]:02X}"


def _signed_minutes(seconds: int) -> str:
    sign = "+" if seconds >= 0 else "-"
    return f"{sign}{abs(seconds) // 60}분"


def _report_period_for_label(label: str, today: date) -> tuple[date, date]:
    if label == "이번 달":
        return date(today.year, today.month, 1), today
    if label == "최근 30일":
        return today - timedelta(days=29), today
    return today - timedelta(days=6), today
