import re
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit


# 스킴 없는 주소: 점으로 나뉜 이름(또는 IPv4), 포트, 그 뒤에 경로·쿼리·프래그먼트
_BARE_ADDRESS = re.compile(r"^(?:(?:[\w-]+\.)+[^\W\d_]{2,}|(?:\d{1,3}\.){3}\d{1,3})(?::\d+)?[/?#]\S*$")


def _format_seconds(seconds: int) -> str:
    minutes, remainder = divmod(max(0, seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}시간 {minutes}분"
    if minutes:
        return f"{minutes}분"
    return f"{remainder}초"


def _display_label(label: str) -> str:
    """사람이 읽는 형태의 웹 주소: 스킴, "www.", 쿼리, 프래그먼트 제거.

    - 그 외(창 제목, 앱 이름)는 그대로 반환
    """
    if label.lower().startswith(("http://", "https://")):
        address = label
    elif _BARE_ADDRESS.match(label):  # 브라우저 주소창은 "https://" 를 숨김
        address = f"https://{label}"
    else:
        return label
    try:
        parts = urlsplit(address)
        host = (parts.hostname or "").removeprefix("www.")
        port = f":{parts.port}" if parts.port else ""
    except ValueError:
        return label
    return f"{host}{port}{parts.path.rstrip('/')}" if host else label


def _friendly_time(iso: str, today: date | None = None) -> str:
    """표시 형식: 오늘 15:00 / 어제 09:30 / 11월 3일 09:30 (해가 다르면 연도 포함)."""
    try:
        moment = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    today = today or date.today()
    day = moment.date()
    if day == today:
        name = "오늘"
    elif day == today - timedelta(days=1):
        name = "어제"
    else:
        name = f"{day.month}월 {day.day}일"
        if day.year != today.year:
            name = f"{day.year}년 {name}"
    return f"{name} {moment:%H:%M}"


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
