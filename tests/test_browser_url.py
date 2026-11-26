"""브라우저 주소 읽기: 주소창만 읽고, 웹 페이지의 내용이나 입력 중인 글은 저장하지 않음."""

from __future__ import annotations

import sys

import pytest

if not sys.platform.startswith("win"):
    pytest.skip("Windows only", allow_module_level=True)

from time_manager.platforms import windows  # noqa: E402


class Control:
    """UI 자동화 컨트롤 대역."""

    def __init__(self, kind, *children, class_name="", value="", focused=False, automation_id="", name=""):
        self.ControlTypeName = kind
        self.ClassName = class_name
        self.AutomationId = automation_id
        self.Name = name
        self.HasKeyboardFocus = focused
        self._children = list(children)
        self._value = value
        self.visited = False

    def GetChildren(self):
        self.visited = True
        return self._children

    def GetValuePattern(self):
        return type("Pattern", (), {"Value": self._value})()


def pane(*children):
    return Control("PaneControl", *children)


def nested(control, levels):
    for _ in range(levels):
        control = pane(control)
    return control


def omnibox(value, **kwargs):
    return Control("EditControl", class_name="OmniboxViewViews", value=value, **kwargs)


def toolbar(*children):
    return Control("ToolBarControl", Control("GroupControl", *children))


def page(*values):
    return Control("DocumentControl", *[Control("EditControl", value=value) for value in values])


def browser_window(bar, document=None):
    """Edge 158·Chrome 158 의 구조: 주소창은 9단계, 페이지는 Document 안."""
    parts = [nested(toolbar(bar), 4)] if bar is not None else []
    return pane(*parts, nested(document or page("someone@example.com"), 3))


def read(window) -> object:
    return windows._read_address_bar(window)[0]


def test_the_address_bar_is_found_where_current_browsers_put_it() -> None:
    assert read(browser_window(omnibox("youtube.com/watch?v=1"))) == "youtube.com/watch?v=1"


def test_the_inside_of_a_web_page_is_never_searched() -> None:
    document = page("http://typed.in.page.example/secret", "private.note.value")
    window = browser_window(omnibox("파이썬 검색어"), document)

    assert read(window) is None  # 주소창에 주소가 없으면 페이지 입력칸을 대신 읽지 않음
    assert not document.visited


def test_without_an_address_bar_nothing_is_read_from_the_page() -> None:
    assert read(browser_window(None, page("secret.example.com"))) is None


def test_a_page_comes_first_in_the_tree_and_is_still_skipped() -> None:
    window = pane(page("decoy.example.com"), nested(toolbar(omnibox("real.example.com")), 4))

    assert read(window) == "real.example.com"


def test_a_find_box_outside_the_toolbar_is_not_the_address_bar() -> None:
    window = pane(Control("EditControl", class_name="Textfield", value="find.me.example"))

    assert read(window) is None


def test_the_known_class_wins_over_another_toolbar_box() -> None:
    other = Control("EditControl", value="other.example.com")
    window = pane(toolbar(other), nested(toolbar(omnibox("real.example.com")), 4))

    assert read(window) == "real.example.com"


def test_a_toolbar_box_is_used_for_browsers_with_another_class_name() -> None:
    firefox = Control("EditControl", automation_id="urlbar-input", value="https://mozilla.org/ko/")

    assert read(pane(toolbar(firefox))) == "https://mozilla.org/ko/"


def test_what_the_user_is_typing_is_not_read() -> None:
    window = browser_window(omnibox("my.secret.draft", focused=True))

    assert read(window) is windows.TYPING


def test_the_name_of_an_empty_address_bar_is_not_an_address() -> None:
    assert read(browser_window(omnibox("", name="address.bar.example"))) is None


def test_a_huge_tree_does_not_stall_the_tracker() -> None:
    wide = pane(*[pane(pane()) for _ in range(5000)], nested(toolbar(omnibox("late.example.com")), 8))

    assert read(wide) is None  # 정한 개수까지만 살펴봄


@pytest.mark.parametrize(
    "value",
    [
        "youtube.com", "github.com/gu-sean/Time-Manager", "https://docs.python.org/3/", "127.0.0.1:8000/x",
        "sub.domain.co.kr/path?q=a.b", "http://example.com", "한글.한국/길",
    ],
)
def test_addresses(value: str) -> None:
    assert windows._looks_like_url(value)


@pytest.mark.parametrize(
    "value",
    [
        "", "python 3.13", "someone@example.com", "https://user:pw@example.com", "3.13", "end.", ".env",
        "file:///C:/Users/me/secret.txt", "chrome-extension://abc.def/page.html", "edge://settings",
        "mailto:someone@example.com", "http://localhost:3000", "localhost", "search.example", "a..b",
        "http://example.com:notaport", "그냥검색어",
    ],
)
def test_other_text(value: str) -> None:
    assert not windows._looks_like_url(value)


# -- 직전 주소를 이어 쓰는 경우 ---------------------------------------------------------

@pytest.fixture()
def monitor(monkeypatch: pytest.MonkeyPatch):
    answers: list = []
    monkeypatch.setattr(windows, "_active_browser_url", lambda hwnd, app: answers.pop(0))
    value = windows.WindowsMonitor(url_poll_seconds=0)
    value.answers = answers
    return value


def look(monitor, answer, title="Video - YouTube", hwnd=1):
    monitor.answers.append(answer)
    return monitor._browser_url(hwnd, "chrome.exe", title)


def test_typing_or_full_screen_keeps_the_address_of_the_same_page(monitor) -> None:
    assert look(monitor, ("youtube.com/watch?v=1", "")) == "youtube.com/watch?v=1"
    assert look(monitor, (windows.TYPING, "")) == "youtube.com/watch?v=1"
    assert look(monitor, (None, "주소창 없음")) == "youtube.com/watch?v=1"


def test_the_address_is_not_carried_to_another_page_or_window(monitor) -> None:
    look(monitor, ("youtube.com/watch?v=1", ""))

    assert look(monitor, (windows.TYPING, ""), title="새 탭") is None
    assert look(monitor, (None, ""), hwnd=2) is None


def test_an_address_bar_without_an_address_forgets_the_old_one(monitor) -> None:
    look(monitor, ("youtube.com/watch?v=1", ""))
    look(monitor, (None, ""))  # 주소창은 있는데 주소가 아닌 값

    assert look(monitor, (None, "주소창 없음")) is None


def test_leaving_the_browser_forgets_the_address(monitor) -> None:
    look(monitor, ("youtube.com/watch?v=1", ""))
    monitor._browser_url(9, "Code.exe", "main.py")

    assert look(monitor, (None, "주소창 없음")) is None


def test_a_failure_is_logged_once_without_addresses(monitor, caplog: pytest.LogCaptureFixture) -> None:
    for _ in range(3):
        look(monitor, (None, "브라우저 주소창을 찾지 못했어요"))

    assert [r.getMessage() for r in caplog.records] == ["브라우저 주소창을 찾지 못했어요"]
