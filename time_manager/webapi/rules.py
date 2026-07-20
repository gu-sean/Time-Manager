from __future__ import annotations

from typing import Any

from time_manager.formatting import _format_seconds, _truncate
from time_manager.models import Category
from time_manager.rules import (
    RuleConflictError,
    load_rules,
    remove_rule_value,
    rule_from_candidate,
    rule_key_for_selection,
    update_rule_value,
)

from ._shared import WebApiBase


class RulesMixin(WebApiBase):
    _RULE_GROUPS = (
        ("생산적", "도메인", "productive_domains"),
        ("생산적", "창 제목 키워드", "productive_title_keywords"),
        ("생산적", "앱 이름", "productive_apps"),
        ("비생산적", "도메인", "unproductive_domains"),
        ("비생산적", "창 제목 키워드", "unproductive_title_keywords"),
        ("비생산적", "앱 이름", "unproductive_apps"),
        ("중립", "창 제목 키워드", "neutral_title_keywords"),
        ("기록 제외", "앱 이름", "excluded_apps"),
    )

    def get_rules(self) -> dict[str, Any]:
        rules = load_rules(self.rules_path)
        items = []
        for category, rule_type, key in self._RULE_GROUPS:
            for index, value in enumerate(rules.get(key, [])):
                items.append(
                    {
                        "priority": len(items) + 1,
                        "category": category,
                        "ruleType": rule_type,
                        "key": key,
                        "value": value,
                    }
                )
        return {"items": items, "total": len(items)}

    def add_rule(self, rule_type: str, category: str, value: str) -> dict[str, Any]:
        value = value.strip()
        if not value:
            return {**self.get_rules(), "error": "값을 입력하세요."}
        key = rule_key_for_selection(rule_type, category)
        classifier = self._add_rule_value(key, value)
        if classifier is None:
            return {**self.get_rules(), "error": f"'{value}' 항목은 이미 다른 분류 규칙에 있습니다."}
        self.tracker.classifier = classifier
        return self.get_rules()

    def update_rule(
        self, old_key: str, old_value: str, rule_type: str, category: str, value: str
    ) -> dict[str, Any]:
        value = value.strip()
        if not value:
            return {**self.get_rules(), "error": "값을 입력하세요."}
        new_key = rule_key_for_selection(rule_type, category)
        if new_key == old_key and value == old_value:
            return self.get_rules()
        try:
            classifier = update_rule_value(self.rules_path, old_key, old_value, new_key, value)
        except RuleConflictError:
            return {**self.get_rules(), "error": f"'{value}' 항목은 이미 다른 분류 규칙에 있습니다."}
        self.tracker.classifier = classifier
        return self.get_rules()

    def delete_rule(self, key: str, value: str) -> dict[str, Any]:
        self.tracker.classifier = remove_rule_value(self.rules_path, key, value)
        return self.get_rules()

    def get_rule_suggestions(self, days: int = 14, limit: int = 5) -> list[dict[str, Any]]:
        candidates = self.store.neutral_candidates_for_range(days, limit=limit)
        return [
            {
                "target": row.label,
                "timeLabel": _format_seconds(row.seconds),
                "displayTarget": _truncate(row.label, 60),
            }
            for row in candidates
            if row.seconds > 0
        ]

    def apply_rule_suggestion(self, target: str, category: str) -> dict[str, Any]:
        try:
            cat = Category(category)
        except ValueError:
            return {**self.get_rules(), "error": "분류를 선택하세요."}
        if cat == Category.NEUTRAL:
            return {**self.get_rules(), "error": "생산적 또는 비생산적만 선택할 수 있습니다."}
        key, value = rule_from_candidate(target, cat)
        classifier = self._add_rule_value(key, value)
        if classifier is None:
            return {**self.get_rules(), "error": f"'{value}' 항목은 이미 다른 분류 규칙에 있습니다."}
        self.tracker.classifier = classifier
        return self.get_rules()
