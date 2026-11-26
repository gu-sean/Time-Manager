from __future__ import annotations

from typing import Any

from time_manager.formatting import _display_label, _format_seconds, _friendly_time, _truncate
from time_manager.models import ActiveTarget, Category
from datetime import datetime, time, timedelta

from time_manager.rules import (
    RuleClassifier,
    RuleConflictError,
    _domain_from_url,
    activity_rule_target,
    add_rule_value,
    load_rules,
    rule_from_candidate,
    rule_would_apply,
)

from ._shared import WebApiBase, _CATEGORY_LABELS, _parse_category, _parse_day

_SEARCH_LIMIT = 500
_MANUAL_LABEL_LIMIT = 80
_MANUAL_MINUTES_LIMIT = 12 * 60


def _describe_activity(title: str, url: str | None, app_name: str) -> dict[str, str]:
    """첫 줄은 한 일(제목 우선), 둘째 줄은 장소."""
    address = _display_label(url) if url else ""
    label = title or address or app_name
    where = address or app_name
    return {"label": _truncate(label, 80), "detail": "" if where == label else _truncate(where, 80)}


class InboxMixin(WebApiBase):
    def _add_rule_value(self, key: str, value: str) -> RuleClassifier | None:
        try:
            return add_rule_value(self.rules_path, key, value)
        except RuleConflictError:
            return None

    def get_inbox(self, query: str = "", category: str | None = None, date_iso: str | None = None) -> dict[str, Any]:
        query = str(query or "")
        wanted = _parse_category(category)
        category = wanted.value if wanted else None
        searching = bool(query.strip()) or bool(category)
        truncated = False
        if searching:
            rows = self.store.search_events(query=query, category=wanted, days=30, limit=_SEARCH_LIMIT + 1)
            truncated = len(rows) > _SEARCH_LIMIT
            rows = rows[:_SEARCH_LIMIT]
        else:
            selected_day = _parse_day(date_iso)
            rows = self.store.recent_for_day(selected_day, limit=None)  # 화면에서 쪽으로 나눔
        rules = load_rules(self.rules_path)
        classifier = RuleClassifier.from_dict(rules)
        records = [
            {
                "id": row.id,
                "time": _friendly_time(row.started_at),
                "category": row.category.value,
                "categoryLabel": _CATEGORY_LABELS[row.category],
                "duration": _format_seconds(row.seconds),
                **_describe_activity(row.title, row.url, row.app_name),
                "ruleTarget": self._offered_rule_target(rules, classifier, row),
            }
            for row in rows
        ]
        return {
            "records": records,
            "searchActive": searching,
            # 그대로 돌려줌: 기록 변경 후 UI 가 같은 화면을 다시 불러오게 함
            "query": query,
            "category": category,
            "resultCount": len(records) if searching else None,
            "truncated": truncated,
        }

    def reclassify_event(self, event_id: int, category: str) -> dict[str, Any]:
        wanted = _parse_category(category)
        if wanted:
            self.store.reclassify_event(event_id, wanted)
        return self.get_inbox()

    @staticmethod
    def _offered_rule_target(rules: dict[str, list[str]], classifier: RuleClassifier, row: Any) -> str:
        """앞으로의 분류 결과가 실제로 달라질 때만 제안."""
        if row.category == Category.NEUTRAL:
            return ""
        activity = ActiveTarget(row.app_name, row.title, row.url)
        target = activity_rule_target(row.app_name, row.url)
        if not target or classifier.classify(activity).category == row.category:
            return ""
        return target if rule_would_apply(rules, target, row.category, activity) else ""

    def add_rule_for_event(self, event_id: int) -> dict[str, str]:
        """기록 하나의 분류를 그 사이트·앱에 앞으로도 적용."""
        event = self.store.get_event(int(event_id))
        if event is None:
            return {"message": "", "error": "기록을 찾을 수 없어요."}
        target = activity_rule_target(event.app_name, event.url)
        if event.category == Category.NEUTRAL or not target:
            return {"message": "", "error": "이 기록으로는 규칙을 만들 수 없어요."}
        activity = ActiveTarget(event.app_name, event.title, event.url)
        refused = {
            "message": "",
            "error": f"'{target}' 규칙은 추가하지 않았어요. 기존 규칙과 겹쳐 결과가 달라지지 않아요. 규칙 탭에서 확인하세요.",
        }
        if not rule_would_apply(load_rules(self.rules_path), target, event.category, activity):
            return refused
        key, value = rule_from_candidate(target, event.category)
        classifier = self._add_rule_value(key, value)
        if classifier is None:
            return refused
        self.tracker.classifier = classifier
        return {"message": f"앞으로 {value}은(는) {_CATEGORY_LABELS[event.category]}으로 분류해요.", "error": ""}

    def delete_event(self, event_id: int) -> dict[str, Any]:
        self.store.soft_delete_event(event_id)
        self.store.purge_deleted()
        return self.get_inbox()

    @staticmethod
    def _target_of(app_name: str, url: str | None) -> tuple[str, str, str]:
        """(종류, 값, 화면 이름): 주소가 있으면 사이트, 없으면 앱."""
        domain = _domain_from_url(url)
        return ("domain", domain, "사이트") if domain else ("app", app_name, "앱")

    def preview_delete_target(self, event_id: int) -> dict[str, Any]:
        """이 기록의 사이트·앱 기록 전체를 지우면 몇 건인지. 아무것도 바꾸지 않음."""
        event = self.store.get_event(int(event_id))
        if event is None:
            return {"error": "기록을 찾을 수 없어요."}
        kind, value, kind_label = self._target_of(event.app_name, event.url)
        count, seconds = self.store.count_target(kind, value)
        return {"error": "", "target": value, "kindLabel": kind_label, "count": count, "timeLabel": _format_seconds(seconds)}

    def delete_target_records(self, event_id: int) -> dict[str, str]:
        """이 기록의 사이트·앱 기록 전체를 완전히 지움."""
        event = self.store.get_event(int(event_id))
        if event is None:
            return {"message": "", "error": "기록을 찾을 수 없어요."}
        kind, value, kind_label = self._target_of(event.app_name, event.url)
        removed = self.store.delete_target(kind, value)
        return {"message": f"{value} {kind_label}의 기록 {removed}건을 완전히 지웠어요.", "error": ""}

    def add_manual_entry(
        self, date_iso: str, start_hhmm: str, minutes: Any, label: str, category: str
    ) -> dict[str, str]:
        """PC 밖에서 한 일을 직접 추가. 오류 문구가 있으면 추가하지 않음."""
        day = _parse_day(date_iso)
        try:
            hour, minute = (int(part) for part in str(start_hhmm).split(":"))
            started = datetime(day.year, day.month, day.day, hour, minute).astimezone()
            seconds = int(minutes) * 60
        except (TypeError, ValueError):
            return {"message": "", "error": "시작 시각과 시간을 확인해주세요."}
        text = " ".join(str(label or "").split())
        wanted = _parse_category(category)
        if not text:
            return {"message": "", "error": "무엇을 했는지 입력해주세요."}
        if len(text) > _MANUAL_LABEL_LIMIT:
            return {"message": "", "error": f"내용은 {_MANUAL_LABEL_LIMIT}자까지 입력할 수 있어요."}
        if wanted is None:
            return {"message": "", "error": "분류를 선택해주세요."}
        if not 1 <= seconds // 60 <= _MANUAL_MINUTES_LIMIT:
            return {"message": "", "error": f"시간은 1~{_MANUAL_MINUTES_LIMIT}분으로 입력해주세요."}
        ended = started + timedelta(seconds=seconds)
        if ended > datetime.now().astimezone():
            return {"message": "", "error": "아직 지나지 않은 시간은 추가할 수 없어요."}
        if ended.date() != started.date() and ended.time() != time.min:
            return {"message": "", "error": "자정을 넘기지 않도록 나눠서 추가해주세요."}
        clash = self.store.overlapping(started, seconds)
        if clash:
            first = datetime.fromisoformat(clash[0].started_at)
            return {"message": "", "error": f"{first:%H:%M}부터의 기록과 시간이 겹쳐요. 겹치지 않게 조정해주세요."}
        self.store.add_manual_entry(started, seconds, text, wanted)
        return {"message": f"{started:%H:%M}부터 {_format_seconds(seconds)}을 추가했어요.", "error": ""}

    def restore_deleted_event(self) -> dict[str, Any]:
        self.store.restore_last_deleted()
        return self.get_inbox()
