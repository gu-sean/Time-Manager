from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from time_manager.formatting import _format_seconds, _truncate
from time_manager.models import Category
from time_manager.rules import (
    BROWSER_APPS,
    RuleConflictError,
    load_rules,
    remove_rule_value,
    rule_from_candidate,
    rule_key_for_selection,
    update_rule_value,
)
from time_manager.storage import BreakdownRow

from ._shared import WebApiBase

_MIN_SUGGESTION_SECONDS = 60


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

    def get_rule_suggestions(self, days: int = 14, limit: int = 12) -> list[dict[str, Any]]:
        return [
            {
                "target": row.label,
                "timeLabel": _format_seconds(row.seconds),
                "displayTarget": _truncate(row.label, 60),
            }
            for row in self._unclassified_targets(days, limit)
        ]

    def _unclassified_targets(self, days: int, limit: int) -> list[BreakdownRow]:
        """아직 규칙이 없는 앱·도메인. 목록과 맞춤 추천이 함께 사용."""
        end_day = date.today()
        start_day = end_day - timedelta(days=max(1, int(days)) - 1)
        known = {value.lower() for values in load_rules(self.rules_path).values() for value in values}
        return [
            row
            for row in self.store.app_domain_totals(start_day, end_day, unmatched_only=True)
            if row.seconds >= _MIN_SUGGESTION_SECONDS
            and row.label.lower() not in known
            and row.label.lower() not in BROWSER_APPS
            and row.label.lower() not in self.settings.dismissed_suggestions
        ][: max(1, int(limit))]

    def get_dismissed_suggestions(self) -> list[str]:
        return list(self.settings.dismissed_suggestions)

    def dismiss_rule_suggestion(self, target: str) -> list[str]:
        """추천을 계속 숨김 (예: 중립으로 두고 싶은 항목)."""
        name = str(target or "").strip().lower()
        if name and name not in self.settings.dismissed_suggestions:
            self.settings.dismissed_suggestions.append(name)
            self.settings_store.save(self.settings)
        return self.get_dismissed_suggestions()

    def restore_rule_suggestion(self, target: str) -> list[str]:
        name = str(target or "").strip().lower()
        if name in self.settings.dismissed_suggestions:
            self.settings.dismissed_suggestions.remove(name)
            self.settings_store.save(self.settings)
        return self.get_dismissed_suggestions()

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
