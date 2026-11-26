from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from time_manager import ai as _ai
from time_manager import ask as _ask

from ._shared import WebApiBase

_NAME_HISTORY_DAYS = 90
_MAX_NAMES = 100
_WEEKDAYS = ("월", "화", "수", "목", "금", "토", "일")
_BUILTIN_LABEL = "내장 분석"


class AskMixin(WebApiBase):
    """활동 기록 질문 API (``time_manager.ask`` 참고)."""

    def ask_activity(self, question: str, request_id: str = "", builtin: bool = False) -> dict[str, Any]:
        local = builtin or self.settings.ai_provider == _ai.PROVIDER_LOCAL
        source = _BUILTIN_LABEL if local else self._ai_source_label()
        question = " ".join(str(question or "").split())
        problem = self._question_problem(question)
        if problem:
            return self._ask_result(source=source, error=problem)

        today = date.today()
        try:
            if local:
                spec = _ask.parse_local(question, self._ask_target_names(external=False), today)
            else:
                names = self._ask_target_names(external=True)
                text = self._ai_complete(
                    _ai.ASK_SYSTEM, self._ask_message(question, names), max_tokens=4000, request_id=request_id
                )
                spec = _ask.parse_model_spec(_ai.extract_object(text), names, today)
        except _ai.AIError as exc:
            return self._ask_result(source=source, error=str(exc), canFallback=True)
        except _ask.QuestionError as exc:
            return self._ask_result(source=source, error=str(exc), canFallback=not local)

        note = ""
        if not local and self.settings.ai_excluded_targets:
            note = "전송 제외 항목의 이름은 AI에게 알리지 않아요. 분류·전체 합계에는 그 시간도 포함돼요."
        return self._ask_result(source=source, note=note, **_ask.run_query(self.store, spec, today))

    @staticmethod
    def _question_problem(question: str) -> str:
        if not question:
            return "질문을 입력하세요."
        if len(question) > _ask.MAX_QUESTION_LENGTH:
            return f"질문은 {_ask.MAX_QUESTION_LENGTH}자 이내로 입력하세요."
        return ""

    def _ask_target_names(self, *, external: bool) -> list[str]:
        """질문에서 가리킬 수 있는 앱·사이트 (많이 쓴 순)."""
        today = date.today()
        totals: dict[str, int] = {}
        for row in self.store.app_domain_totals(today - timedelta(days=_NAME_HISTORY_DAYS - 1), today):
            totals[row.label] = totals.get(row.label, 0) + row.seconds
        names = sorted(totals, key=totals.__getitem__, reverse=True)
        if external:
            names = [n for n in names if not _ai.is_excluded(n, self.settings.ai_excluded_targets)]
        return names[:_MAX_NAMES]

    @staticmethod
    def _ask_message(question: str, names: list[str]) -> str:
        today = date.today()
        return json.dumps(
            {"question": question, "today": today.isoformat(), "weekday": _WEEKDAYS[today.weekday()], "targets": names},
            ensure_ascii=False,
        )

    @staticmethod
    def _ask_result(
        *,
        source: str,
        answer: str = "",
        interpretation: str = "",
        rows: list | None = None,
        note: str = "",
        error: str = "",
        canFallback: bool = False,
    ) -> dict[str, Any]:
        return {
            "answer": answer, "interpretation": interpretation, "rows": rows or [], "note": note,
            "source": source, "error": error, "canFallback": canFallback,
        }
