from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest
from test_ai import FakeKeys

from time_manager import ai
from time_manager.ask import QuerySpec, QuestionError, parse_local, parse_model_spec
from time_manager.models import Category
from time_manager.webapi import WebApi

TODAY = date(2026, 11, 26)  # 목요일
NAMES = ["Code.exe", "youtube.com", "stackoverflow.com", "KakaoTalk.exe"]


def _parse(question: str) -> QuerySpec:
    return parse_local(question, NAMES, TODAY)


class TestBuiltinParser:
    @pytest.mark.parametrize(
        "question",
        [
            "오늘 얼마나 썼어?", "어제 몇 시간 했지", "지난주에 총 얼마나 사용했어요", "오늘 활동 시간 알려주세요",
            "이번 주에는 얼마나 썼나요", "오늘 내가 몇 시간 썼는지 알려줘", "어제 컴퓨터",
        ][:6],
    )
    def test_everyday_phrasings_are_understood(self, question: str) -> None:
        assert _parse(question).targets is None

    @pytest.mark.parametrize(
        "question,start,end",
        [
            ("오늘 얼마나 썼어?", TODAY, TODAY),
            ("어제 총 사용 시간 알려줘", date(2026, 11, 25), date(2026, 11, 25)),
            ("지난주에 몇 시간 했어", date(2026, 11, 16), date(2026, 11, 22)),
            ("이번 주 활동 시간", date(2026, 11, 23), TODAY),
            ("최근 3일 동안 몇 시간", date(2026, 11, 24), TODAY),
            ("지난달 사용 시간", date(2026, 10, 1), date(2026, 10, 31)),
            ("이번 달 얼마나 썼어", date(2026, 11, 1), TODAY),
            ("얼마나 썼어", date(2026, 11, 20), TODAY),  # 기간 없음: 최근 7일
        ],
    )
    def test_periods(self, question: str, start: date, end: date) -> None:
        spec = _parse(question)

        assert (spec.start, spec.end) == (start, end)

    @pytest.mark.parametrize(
        "question,category",
        [("오늘 생산적인 시간은?", Category.PRODUCTIVE), ("오늘 비생산 시간 얼마야", Category.UNPRODUCTIVE),
         ("어제 딴짓 얼마나 했어", Category.UNPRODUCTIVE), ("오늘 중립 시간", Category.NEUTRAL)],
    )
    def test_categories(self, question: str, category: Category) -> None:
        assert _parse(question).category == category

    @pytest.mark.parametrize(
        "question,target",
        [("지난주 유튜브 얼마나 봤어?", "youtube.com"), ("지난주 youtube 시간", "youtube.com"),
         ("어제 code 몇 시간 썼어", "Code.exe"), ("오늘 카톡 얼마나 했어", "KakaoTalk.exe"),
         ("youtube.com 사용 시간", "youtube.com")],
    )
    def test_targets(self, question: str, target: str) -> None:
        assert _parse(question).targets == (target,)

    def test_grouping(self) -> None:
        assert _parse("이번 주 요일별 생산 시간").group_by == "day"
        assert _parse("지난주에 가장 많이 쓴 앱 뭐야?").group_by == "target"
        assert _parse("오늘 뭐 했어").group_by == "target"

    @pytest.mark.parametrize(
        "question",
        [
            "지난주 코딩 몇 시간 했어?",  # 모르는 개념은 무시하면 안 됨
            "지난주 틱톡 얼마나 봤어",  # 기록에 없음
            "3월에 얼마나 썼어",
            # 비교는 서로 다른 두 기간이 필요하고 합계만 가능
            "지난주 비교해줘",
            "지난주 이번 주 얼마나 썼어",
            "오늘이랑 이번 주 비교해줘",
            "지난주랑 이번 주 요일별 비교해줘",
            "어제랑 오늘이랑 지난주 비교해줘",
            "지난주랑 이번 주 코딩 비교해줘",
            "언제 요일별로 썼어",
            "오늘 생산 시간과 비생산 시간",
            "decode 사용 시간",  # "code" 와 일치하면 안 됨
            "오늘 날씨 어때",
            # 조사·어미를 이어 붙인 것처럼 보이는 실제 단어
            "지난주 일 몇 시간 했어",
            "오늘 요가 얼마나 했어",
            "지난주 지도 얼마나 봤어",
            "어제 아이 시간 알려줘",
            "어제 게이 시간",
            "지난주 분야 시간",
            "이번 주 나이 시간",
            "오늘 시간표 알려줘",
            "오늘 사용자 시간",
            "",
        ],
    )
    def test_refuses_instead_of_guessing(self, question: str) -> None:
        with pytest.raises(QuestionError):
            _parse(question)


def _spec(**changes: object) -> dict:
    data = {"answerable": True, "start": "2026-11-16", "end": "2026-11-22", "category": None,
            "targets": None, "groupBy": "none"}
    return {**data, **changes}


class TestModelSpec:
    def test_valid(self) -> None:
        spec = parse_model_spec(_spec(category="productive", targets=["CODE.EXE"], groupBy="day"), NAMES, TODAY)

        assert spec == QuerySpec(date(2026, 11, 16), date(2026, 11, 22), Category.PRODUCTIVE, ("Code.exe",), "day")

    @pytest.mark.parametrize(
        "changes",
        [{"answerable": False}, {"start": "soon"}, {"start": "2026-11-23"}, {"start": "2024-01-01"},
         {"category": "fun"}, {"targets": ["made-up.exe"]}, {"targets": ["Code.exe", "made-up.exe"]},
         {"targets": "Code.exe"}, {"groupBy": "month"}],
    )
    def test_anything_invalid_is_refused_not_widened(self, changes: dict) -> None:
        with pytest.raises(QuestionError):
            parse_model_spec(_spec(**changes), NAMES, TODAY)

    def test_not_an_object(self) -> None:
        with pytest.raises(QuestionError):
            parse_model_spec(None, NAMES, TODAY)


def _add(api: WebApi, days_ago: int, app: str, category: str, minutes: int, url: str | None = None) -> None:
    day = date.today() - timedelta(days=days_ago)
    started = datetime(day.year, day.month, day.day, 9).astimezone()
    with api.store._connection() as conn:
        conn.execute(
            "INSERT INTO activity_events (started_at, seconds, category, app_name, window_title, url, reason)"
            " VALUES (?, ?, ?, ?, 'private title', ?, 'rule')",
            (started.isoformat(timespec="seconds"), minutes * 60, category, app, url),
        )


@pytest.fixture
def logged(api: WebApi) -> WebApi:
    api._ai_keys = FakeKeys()
    _add(api, 0, "Code.exe", "productive", 90)
    _add(api, 1, "Code.exe", "productive", 30)
    _add(api, 1, "chrome.exe", "unproductive", 45, "https://youtube.com/watch?v=secret")
    _add(api, 40, "Code.exe", "productive", 600)
    return api


class TestAsk:
    def test_builtin_computes_from_the_log_without_any_request(self, logged: WebApi) -> None:
        with patch("time_manager.ai.complete") as llm:
            result = logged.ask_activity("최근 2일 code 얼마나 썼어?")

        llm.assert_not_called()
        assert result["error"] == ""
        assert "2시간" in result["answer"]
        assert "Code.exe" in result["interpretation"]

    def test_ranking_and_daily_rows(self, logged: WebApi) -> None:
        ranking = logged.ask_activity("최근 2일 가장 많이 쓴 앱")
        daily = logged.ask_activity("최근 2일 일별 생산 시간")

        assert [r["label"] for r in ranking["rows"]] == ["Code.exe", "youtube.com"]
        assert [r["time"] for r in daily["rows"]] == ["30분", "1시간 30분"]
        assert daily["answer"].startswith("생산적 활동 시간은")
        assert ranking["answer"].startswith("사용 시간은")

    def test_no_records(self, logged: WebApi) -> None:
        assert "없어요" in logged.ask_activity("최근 2일 중립 시간")["answer"]

    def test_model_gets_names_but_no_times_and_the_pc_does_the_math(self, logged: WebApi) -> None:
        logged.save_ai_settings("model", "ollama", "m")
        today = date.today()
        reply = (
            f'{{"answerable": true, "start": "{today - timedelta(days=1)}", "end": "{today}",'
            ' "category": null, "targets": ["Code.exe"], "groupBy": "none", "answer": "999 hours"}'
        )

        with patch("time_manager.ai.complete", return_value=reply) as llm:
            result = logged.ask_activity("지난 이틀 코딩 얼마나 했어?")

        sent = llm.call_args.kwargs["user"]
        assert "private title" not in sent and "watch?v" not in sent
        assert "5400" not in sent and "seconds" not in sent and "minutes" not in sent
        assert "2시간" in result["answer"] and "999" not in result["answer"]
        assert result["source"] == "Ollama · m"

    def test_failure_offers_the_builtin_parser(self, logged: WebApi) -> None:
        logged.save_ai_settings("model", "ollama", "m")
        with patch("time_manager.ai.complete", side_effect=ai.AIError("down")):
            failed = logged.ask_activity("오늘 code 시간")
        with patch("time_manager.ai.complete") as llm:
            fallback = logged.ask_activity("오늘 code 시간", "", True)

        assert (failed["error"], failed["canFallback"]) == ("down", True)
        llm.assert_not_called()
        assert "1시간 30분" in fallback["answer"]

    def test_unreadable_reply_gives_no_answer(self, logged: WebApi) -> None:
        logged.save_ai_settings("model", "ollama", "m")
        with patch("time_manager.ai.complete", return_value="You used it a lot"):
            result = logged.ask_activity("오늘 code 시간")

        assert result["answer"] == "" and result["error"]

    @pytest.mark.parametrize("question", ["", "   ", "가" * 301])
    def test_rejects_empty_or_huge_questions_without_sending(self, logged: WebApi, question: str) -> None:
        logged.save_ai_settings("model", "ollama", "m")
        with patch("time_manager.ai.complete") as llm:
            assert logged.ask_activity(question)["error"]

        llm.assert_not_called()
