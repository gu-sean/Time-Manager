"""활동 기록에 대한 질문 처리 ("지난주 유튜브 얼마나 봤어?").

- 질문을 ``QuerySpec`` 으로 변환 (내장 규칙 또는 사용자 모델)
- 숫자는 항상 이 PC에서 계산 → 모델은 사용 시간을 볼 수 없고 지어낼 수도 없음
- 두 파서 모두 추측 대신 거절: 질문 일부를 무시하면 다른 질문에 자신 있게 답하게 됨
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from time_manager.formatting import _format_seconds
from time_manager.models import Category
from time_manager.storage import ActivityStore, BreakdownRow

MAX_QUESTION_LENGTH = 300
MAX_RANGE_DAYS = 366
_MAX_TARGET_ROWS = 10
_MAX_DAY_ROWS = 62
_CATEGORY_NAMES = {Category.PRODUCTIVE: "생산적", Category.UNPRODUCTIVE: "비생산적", Category.NEUTRAL: "중립"}


class QuestionError(Exception):
    """답할 수 없는 질문. 메시지는 사용자에게 그대로 표시."""


@dataclass(frozen=True)
class QuerySpec:
    start: date
    end: date
    category: Category | None = None
    targets: tuple[str, ...] | None = None  # None 이면 모든 앱·사이트
    group_by: str = "none"  # none | day | hour | target
    # ``start``..``end`` 와 비교할 두 번째(더 이전) 기간
    compare: tuple[date, date] | None = None


# -- 내장 파서 -------------------------------------------------------------------

_KOREAN_ALIASES = {
    "youtube": ("유튜브",), "netflix": ("넷플릭스",), "github": ("깃허브", "깃헙"),
    "instagram": ("인스타그램", "인스타"), "notion": ("노션",), "slack": ("슬랙",),
    "naver": ("네이버",), "google": ("구글",), "discord": ("디스코드",), "kakaotalk": ("카카오톡", "카톡"),
}
# 남은 단어를 무시해도 되는 경우
# - ``_WHOLE_WORDS`` 에 통째로 있는 단어
# - 의미 없는 어간 + 어미
# 임의 조각의 결합은 금지: 요가·지도 같은 실제 단어까지 삼켜 전체 합계를 답하게 됨
_WHOLE_WORDS = frozenset(
    "은 는 이 가 을 를 에 의 로 도 만 랑 과 와 에서 에는 에도 으로 이랑 중 중에 때 건 거 것 적 적인 인 분 "
    "나 좀 줘 일간 동안에 그리고 야 요 지 죠 였어 이야 인지".split()
)
_STEMS = (
    "얼마나|얼마|몇|시간|총|합계|전체|사용|활동|기록|앱|사이트|프로그램|정도|동안|내가|나는|"
    "알려|보여|썼|써|쓴|했|해|한|보냈|보낸|봤|본|됐|돼|있었|있"
)
_SUFFIXES = (
    "주세요|거야|이야|이었|였|었|았|했|썼|써|해|한|줘|나요|니|까|지|요|어|아|야|죠|냐|나|"
    "에서|으로|이랑|은|는|이|가|을|를|에|의|로|도|만|랑|과|와|거|것|건|게|인|적인|적"
)
_HARMLESS = re.compile(f"(?:{_STEMS})(?:{_STEMS}|{_SUFFIXES})*")


def _is_harmless(word: str) -> bool:
    return word in _WHOLE_WORDS or bool(_HARMLESS.fullmatch(word))


def parse_local(question: str, target_names: Sequence[str], today: date) -> QuerySpec:
    text = " ".join(question.lower().split())
    if not text:
        raise QuestionError("질문을 입력하세요.")

    def take(pattern: str) -> re.Match[str] | None:
        """표현을 찾아 지움 → 설명되지 않은 단어만 남음."""
        nonlocal text
        match = re.search(pattern, text)
        if match:
            text = f"{text[: match.start()]} {text[match.end() :]}"
        return match

    monday = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    periods: list[tuple[date, date]] = []
    if match := take(r"(?:최근|지난)\s*(\d{1,3})\s*일(?:간)?"):
        days = int(match.group(1))
        if not 1 <= days <= MAX_RANGE_DAYS:
            raise QuestionError(f"기간은 1일에서 {MAX_RANGE_DAYS}일 사이로 물어보세요.")
        periods.append((today - timedelta(days=days - 1), today))
    for pattern, period in (
        (r"지난\s*주|저번\s*주", (monday - timedelta(days=7), monday - timedelta(days=1))),
        (r"이번\s*주", (monday, today)),
        (r"지난\s*달|저번\s*달", ((month_start - timedelta(days=1)).replace(day=1), month_start - timedelta(days=1))),
        (r"이번\s*달", (month_start, today)),
        (r"일주일|한\s*주", (today - timedelta(days=6), today)),
        (r"그저께|그제", (today - timedelta(days=2),) * 2),
        (r"어제", (today - timedelta(days=1),) * 2),
        (r"오늘", (today, today)),
    ):
        if take(pattern):
            periods.append(period)
    # 표현은 하나씩 나열: 아무 어미나 삼키는 패턴은 실제 단어를 가림
    comparing = False
    while take(r"비교(?:해\s*줘|해\s*주세요|해\s*봐|해서|하면|해)?|대비(?:해서)?|보다|차이(?:가|는)?"):
        comparing = True
    compare = None
    if comparing:
        if len(periods) != 2:
            raise QuestionError("비교는 두 기간을 함께 말해주세요. 예: 지난주랑 이번 주 비교해줘")
        earlier, later = sorted(periods)
        if earlier[1] >= later[0]:
            raise QuestionError("서로 겹치지 않는 두 기간을 비교할 수 있어요.")
        compare, periods = earlier, [later]
        # "얼마나 더 많이 썼어", "늘었어?" 는 두 값을 비교한다는 말의 반복일 뿐
        while take(r"(?<![가-힣])(?:더|덜)(?:\s*(?:많이|적게))?(?![가-힣])|(?:늘었|줄었)(?:어요|어|나요|니|지)?|늘어났(?:어|어요)?|줄어들었(?:어|어요)?"):
            pass
    elif len(periods) > 1:
        raise QuestionError("기간 두 개를 비교하려면 '비교해줘'를 붙여주세요.")
    start, end = periods[0] if periods else (today - timedelta(days=6), today)

    categories: list[Category] = []
    for pattern, category in (
        (r"비\s*생산(?:적인|적)?|딴\s*짓|방해", Category.UNPRODUCTIVE),
        (r"생산(?:적인|적)?", Category.PRODUCTIVE),
        (r"중립", Category.NEUTRAL),
    ):
        if take(pattern):
            categories.append(category)
    if len(categories) > 1:
        raise QuestionError("한 번에 한 분류만 물어볼 수 있어요.")

    group_by = "none"
    if take(r"(?:무슨|어느)\s*(?:요일|날)(?:에)?"):
        group_by = "day"
        take(r"(?:가장|제일)\s*많이|많이")  # 여기서는 가장 많이 쓴 "날"을 묻는 말
    if take(r"요일별|날짜별|일별|하루별|날마다|매일"):
        group_by = "day"
    if take(r"(?:어느|무슨)\s*시간대(?:에)?|시간대별|시간대(?:에)?|몇\s*시(?!간)(?:에|쯤)?|언제"):
        if group_by == "day":
            raise QuestionError("날짜별과 시간대별은 한 번에 하나만 물어보세요.")
        group_by = "hour"
        # "언제 가장 많이 봤어" → 앱 순위가 아니라 가장 많이 쓴 시간대
        take(r"(?:가장|제일)\s*많이|많이")
    # 순위 표현은 모두 선택 사항, 발견한 것은 각각 제거
    for pattern in (r"가장\s*많이|제일\s*많이|많이\s*(?:쓴|썼|본|봤)", r"무엇|무슨|어떤|뭐|뭘|어디", r"순위|앱별|사이트별|top"):
        if take(pattern):
            if group_by == "day":
                raise QuestionError("날짜별과 순위를 함께 물어볼 수는 없어요.")
            if group_by == "hour":
                raise QuestionError("시간대와 앱 순위는 한 번에 하나만 물어보세요.")
            group_by = "target"
    if compare and group_by != "none":
        raise QuestionError("비교는 합계만 할 수 있어요. 시간대·날짜·순위는 기간 하나로 물어보세요.")

    aliases: dict[str, set[str]] = {}
    for name in target_names:
        lowered = name.lower()
        stem = lowered.removesuffix(".exe")
        labels = {lowered, stem}
        if not lowered.endswith(".exe") and "." in lowered:
            labels.add(lowered.rsplit(".", 2)[-2])  # youtube.com -> youtube
        for label in list(labels):
            labels.update(_KOREAN_ALIASES.get(label, ()))
        for label in labels:
            if len(label) >= (3 if label.isascii() else 2):
                aliases.setdefault(label, set()).add(name)
    selected: list[str] = []
    for label in sorted(aliases, key=len, reverse=True):
        # 영문 이름은 단독으로만 일치: "decode" 안의 "code" 제외
        pattern = rf"(?<![a-z0-9]){re.escape(label)}(?![a-z0-9])" if label.isascii() else re.escape(label)
        if take(pattern):
            selected.extend(name for name in sorted(aliases[label]) if name not in selected)

    unknown = [word for word in re.findall(r"[a-z0-9가-힣]+", text) if not _is_harmless(word)]
    if unknown:
        raise QuestionError(
            f"'{', '.join(unknown[:3])}'을(를) 이해하지 못했어요. 기간(오늘, 지난주, 최근 N일), "
            "분류(생산적·비생산적), 기록에 있는 앱·사이트 이름으로 물어보세요."
        )
    return QuerySpec(
        start=start,
        end=end,
        category=categories[0] if categories else None,
        targets=tuple(selected) or None,
        group_by=group_by,
        compare=compare,
    )


# -- 모델의 응답 -----------------------------------------------------------------

def parse_model_spec(data: object, target_names: Sequence[str], today: date) -> QuerySpec:
    """모델이 만든 조회 조건 검증. 잘못된 값은 거절하며 범위를 넓히지 않음."""
    if not isinstance(data, dict):
        raise QuestionError("AI가 질문을 해석하지 못했어요. 다시 시도하세요.")
    if data.get("answerable") is not True:
        raise QuestionError("이 질문은 활동 시간 기록만으로는 답할 수 없어요.")
    start, end = _model_period(data.get("start"), data.get("end"), today)
    compare = None
    raw_compare = (data.get("compareStart"), data.get("compareEnd"))
    if any(value not in (None, "", "null") for value in raw_compare):
        compare = _model_period(*raw_compare, today)
        compare, (start, end) = sorted([compare, (start, end)])
        if compare[1] >= start:
            raise QuestionError("서로 겹치지 않는 두 기간을 비교할 수 있어요.")

    raw_category = data.get("category")
    category = None
    if raw_category not in (None, "", "null"):
        try:
            category = Category(str(raw_category).lower())
        except ValueError as exc:
            raise QuestionError("AI가 질문의 분류를 해석하지 못했어요.") from exc

    raw_targets = data.get("targets")
    targets = None
    if raw_targets not in (None, []):
        if not isinstance(raw_targets, list):
            raise QuestionError("AI가 질문의 대상을 해석하지 못했어요.")
        allowed = {name.lower(): name for name in target_names}
        matched = [allowed.get(str(item).strip().lower()) for item in raw_targets]
        if any(name is None for name in matched):
            raise QuestionError("AI가 기록에 없는 앱·사이트를 골랐어요. 이름을 넣어 다시 물어보세요.")
        targets = tuple(dict.fromkeys(name for name in matched if name))

    group_by = str(data.get("groupBy") or "none")
    if group_by not in {"none", "day", "hour", "target"} or (compare and group_by != "none"):
        raise QuestionError("AI가 질문을 해석하지 못했어요. 다시 시도하세요.")
    return QuerySpec(start=start, end=end, category=category, targets=targets, group_by=group_by, compare=compare)


def _model_period(raw_start: object, raw_end: object, today: date) -> tuple[date, date]:
    try:
        start = date.fromisoformat(str(raw_start))
        end = min(date.fromisoformat(str(raw_end)), today)
    except ValueError as exc:
        raise QuestionError("AI가 질문의 기간을 해석하지 못했어요.") from exc
    if start > end or (end - start).days >= MAX_RANGE_DAYS:
        raise QuestionError(f"기간은 오늘까지, 최대 {MAX_RANGE_DAYS}일로 물어보세요.")
    return start, end


# -- 답 계산 ---------------------------------------------------------------------

def run_query(store: ActivityStore, spec: QuerySpec, today: date | None = None) -> dict[str, Any]:
    wanted = None if spec.targets is None else {name.lower() for name in spec.targets}

    def selected(row: BreakdownRow) -> bool:
        return (spec.category is None or row.category == spec.category) and (
            wanted is None or row.label.lower() in wanted
        )

    def total_of(start: date, end: date) -> int:
        return sum(row.seconds for row in store.app_domain_totals(start, end) if selected(row))

    category = _CATEGORY_NAMES[spec.category] if spec.category else "전체"
    if spec.targets is None:
        targets = "전체"
    else:
        targets = ", ".join(spec.targets[:3]) + (f" 외 {len(spec.targets) - 3}개" if len(spec.targets) > 3 else "")
    kind = f"{category} 활동" if spec.category else "사용"
    period = _period_text(spec.start, spec.end)
    # 항상 표시: 질문이 어떻게 해석됐는지 사용자가 확인
    interpretation = f"기간 {period} · 분류 {category} · 대상 {targets}"
    if spec.compare:
        answer, rows = _compare(total_of, spec, kind, today or date.today())
        interpretation = f"비교 {_period_text(*spec.compare)} → {period} · 분류 {category} · 대상 {targets}"
        return {"answer": answer, "interpretation": interpretation, "rows": rows}

    rows: list[tuple[str, int]] = []
    top = ""
    if spec.group_by == "hour":
        by_hour: dict[int, int] = {}
        for hour, row in store.target_hour_totals(spec.start, spec.end):
            if selected(row):
                by_hour[hour] = by_hour.get(hour, 0) + row.seconds
        total = sum(by_hour.values())
        rows = [(f"{hour}시–{hour + 1}시", by_hour[hour]) for hour in sorted(by_hour)]
        if rows:
            label, seconds = max(rows, key=lambda item: item[1])
            top = f" 가장 많이 쓴 시간대는 {label} ({_format_seconds(seconds)})예요."
        interpretation += " · 시간대별"
    else:
        found = [row for row in store.app_domain_totals(spec.start, spec.end) if selected(row)]
        total = sum(row.seconds for row in found)
        if spec.group_by == "target":
            by_target: dict[str, int] = {}
            for row in found:
                by_target[row.label] = by_target.get(row.label, 0) + row.seconds
            rows = sorted(by_target.items(), key=lambda item: item[1], reverse=True)[:_MAX_TARGET_ROWS]
            if rows:
                top = f" 가장 많이 쓴 건 {rows[0][0]} ({_format_seconds(rows[0][1])})예요."
        elif spec.group_by == "day" and total:
            day = max(spec.start, spec.end - timedelta(days=_MAX_DAY_ROWS - 1))
            while day <= spec.end:
                seconds = total_of(day, day)
                if seconds:
                    rows.append((day.isoformat(), seconds))
                day += timedelta(days=1)
            if len(rows) > 1:
                label, seconds = max(rows, key=lambda item: item[1])
                top = f" 가장 많이 쓴 날은 {label} ({_format_seconds(seconds)})이에요."

    answer = f"{kind} 시간은 모두 {_format_seconds(total)}이에요.{top}" if total else "이 조건에 해당하는 활동 기록이 없어요."
    return {"answer": answer, "interpretation": interpretation, "rows": _rows(rows)}


def _period_text(start: date, end: date) -> str:
    return start.isoformat() if start == end else f"{start.isoformat()}~{end.isoformat()}"


def _rows(items: list[tuple[str, int]]) -> list[dict[str, Any]]:
    """``ratio``: 가장 긴 행 대비 막대 길이."""
    peak = max((seconds for _, seconds in items), default=0) or 1
    return [
        {"label": label, "time": _format_seconds(seconds), "ratio": round(seconds / peak, 3)}
        for label, seconds in items
    ]


def _compare(total_of, spec: QuerySpec, kind: str, today: date) -> tuple[str, list[dict[str, Any]]]:
    assert spec.compare is not None
    periods = [spec.compare, (spec.start, spec.end)]
    totals = [total_of(*period) for period in periods]
    lengths = [(end - start).days + 1 for start, end in periods]
    if not any(totals):
        return "두 기간 모두 이 조건에 해당하는 활동 기록이 없어요.", []

    # 길이가 다른 기간은 하루 평균으로 비교
    # (갓 시작한 주가 항상 감소로 보이는 것 방지)
    uneven = lengths[0] != lengths[1]
    values = [total // length for total, length in zip(totals, lengths)] if uneven else totals
    # 분 단위로 절삭: 화면의 두 숫자와 차이값이 일치하도록
    values = [value - value % 60 for value in values]
    # 막대도 문장과 같은 숫자를 표시
    names = [_period_text(*period) for period in periods]
    if uneven:
        names = [f"{name} 하루 평균 (합계 {_format_seconds(total)})" for name, total in zip(names, totals)]
    rows = _rows(list(zip(names, values)))
    what = f"{kind} 시간의 하루 평균" if uneven else f"{kind} 시간"
    change = values[1] - values[0]
    if abs(change) < 60:
        verdict = "거의 같아요."
    else:
        verdict = f"{_format_seconds(abs(change))} {'늘었어요' if change > 0 else '줄었어요'}."
    answer = f"{what}: {_format_seconds(values[0])} → {_format_seconds(values[1])}, {verdict}"
    if uneven:
        answer += f" (기간이 {lengths[0]}일과 {lengths[1]}일로 달라 하루 평균으로 비교했어요.)"
    if spec.end >= today:
        answer += " 오늘은 아직 끝나지 않았어요."
    return answer, rows
