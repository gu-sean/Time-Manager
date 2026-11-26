from datetime import date

import pytest

from time_manager.formatting import _display_label, _friendly_time
from time_manager.models import ActiveTarget, Category, ClassifiedActivity
from time_manager.webapi import WebApi


@pytest.mark.parametrize(
    "raw,shown",
    [
        ("https://www.youtube.com/watch?v=abc#t=1", "youtube.com/watch"),
        ("http://example.com/", "example.com"),
        ("https://docs.python.org/3/library/", "docs.python.org/3/library"),
        ("main.py - project", "main.py - project"),
        ("Code.exe", "Code.exe"),
        ("https://", "https://"),
        ("http://[bad", "http://[bad"),
    ],
)
def test_display_label(raw: str, shown: str) -> None:
    assert _display_label(raw) == shown


@pytest.mark.parametrize(
    "iso,shown",
    [
        ("2026-11-26T15:00:00+09:00", "오늘 15:00"),
        ("2026-11-25T09:05:59+09:00", "어제 09:05"),
        ("2026-11-03T00:00:00+09:00", "11월 3일 00:00"),
        ("2025-12-31T23:59:00+09:00", "2025년 12월 31일 23:59"),
        ("not a time", "not a time"),
    ],
)
def test_friendly_time(iso: str, shown: str) -> None:
    assert _friendly_time(iso, date(2026, 11, 26)) == shown


def _record(api: WebApi, app: str, title: str, url: str | None = None) -> None:
    api.store.record(ClassifiedActivity(ActiveTarget(app, title, url), Category.UNPRODUCTIVE, "rule"), 600)


@pytest.mark.parametrize(
    "app,title,url,label,detail",
    [
        ("chrome.exe", "Funny video", "https://www.youtube.com/watch?v=1", "Funny video", "youtube.com/watch"),
        ("chrome.exe", "", "https://www.youtube.com/watch?v=1", "youtube.com/watch", ""),
        ("Code.exe", "main.py", None, "main.py", "Code.exe"),
        ("Code.exe", "", None, "Code.exe", ""),
    ],
)
def test_inbox_shows_what_then_where(
    api: WebApi, app: str, title: str, url: str | None, label: str, detail: str
) -> None:
    _record(api, app, title, url)

    [record] = api.get_inbox()["records"]

    assert (record["label"], record["detail"]) == (label, detail)
    assert record["time"].startswith("오늘 ")


def test_no_screen_shows_a_raw_address(api: WebApi) -> None:
    _record(api, "chrome.exe", "", "https://www.youtube.com/watch?v=secret")

    dashboard, review, report = api.get_dashboard(), api.get_review(), api.get_report()

    for payload in (dashboard["topApps"], review["highlights"], review["suggestion"], report):
        assert "https://" not in str(payload) and "v=secret" not in str(payload)
    assert dashboard["topApps"][0]["label"] == "youtube.com"  # 같은 사이트의 페이지는 하나로 묶음


def test_no_change_is_not_shown_as_an_increase(api: WebApi) -> None:
    assert {stat["delta"] for stat in api.get_dashboard()["stats"]} == {"어제 같은 시각과 같음"}

    _record(api, "game.exe", "t")

    deltas = {stat["key"]: stat["delta"] for stat in api.get_dashboard()["stats"]}
    assert deltas["unproductive"].startswith("▲") and deltas["productive"] == "어제 같은 시각과 같음"
