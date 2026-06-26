from datetime import date, timedelta


def _format_seconds(seconds: int) -> str:
    minutes, remainder = divmod(max(0, seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}시간 {minutes}분"
    if minutes:
        return f"{minutes}분"
    return f"{remainder}초"


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "..."


def _report_period_for_label(label: str, today: date) -> tuple[date, date]:
    if label == "이번 달":
        return date(today.year, today.month, 1), today
    if label == "최근 30일":
        return today - timedelta(days=29), today
    return today - timedelta(days=6), today
