from __future__ import annotations

from typing import Any

from time_manager.formatting import _display_label, _format_seconds, _friendly_time, _truncate
from time_manager.models import ActiveTarget, Category
from time_manager.rules import (
    RuleClassifier,
    RuleConflictError,
    activity_rule_target,
    add_rule_value,
    load_rules,
    rule_from_candidate,
    rule_would_apply,
)

from ._shared import WebApiBase, _CATEGORY_LABELS, _parse_category, _parse_day


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
        if searching:
            rows = self.store.search_events(query=query, category=wanted, days=30, limit=200)
        else:
            selected_day = _parse_day(date_iso)
            rows = self.store.recent_for_day(selected_day, limit=30)
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
        return self.get_inbox()

    def restore_deleted_event(self) -> dict[str, Any]:
        self.store.restore_last_deleted()
        return self.get_inbox()
