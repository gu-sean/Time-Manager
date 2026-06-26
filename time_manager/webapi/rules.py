from __future__ import annotations

from typing import Any

from time_manager.rules import (
    RuleConflictError,
    load_rules,
    remove_rule_value,
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
