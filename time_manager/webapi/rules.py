from __future__ import annotations

import logging
import sqlite3
from datetime import date, timedelta
from typing import Any

from time_manager.formatting import _format_seconds, _truncate
from time_manager.models import Category
from time_manager.rules import (
    BROWSER_APPS,
    RuleClassifier,
    RuleConflictError,
    _domain_from_url,
    load_rules,
    remove_rule_value,
    rule_from_candidate,
    rule_key_for_selection,
    update_rule_value,
)
from time_manager.storage import BreakdownRow, Reclassification

from ._shared import WebApiBase, _CATEGORY_LABELS

_MIN_SUGGESTION_SECONDS = 60
_PREVIEW_ROWS = 10
_log = logging.getLogger(__name__)


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
        ("기록 제외", "도메인", "excluded_domains"),
    )
    _EXCLUDE_BY_TITLE = "기록 제외는 앱 이름이나 도메인으로만 등록할 수 있어요."

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
        if category == "기록 제외" and rule_type == "창 제목 키워드":
            return {**self.get_rules(), "error": self._EXCLUDE_BY_TITLE}
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
        if category == "기록 제외" and rule_type == "창 제목 키워드":
            return {**self.get_rules(), "error": self._EXCLUDE_BY_TITLE}
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

    def preview_rule_reapply(self) -> dict[str, Any]:
        """지난 기록에 지금 규칙을 적용하면 바뀌는 내용. 아무것도 바꾸지 않음."""
        changes = self._rule_changes()
        grouped: dict[tuple[str, Category, Category], list[int]] = {}
        for item in changes:
            name = _domain_from_url(item.url) or item.app_name
            totals = grouped.setdefault((name, item.old, item.new), [0, 0])
            totals[0] += 1
            totals[1] += item.seconds
        ranked = sorted(grouped.items(), key=lambda entry: entry[1][1], reverse=True)
        return {
            "count": len(changes),
            "timeLabel": _format_seconds(sum(item.seconds for item in changes)),
            "items": [
                {
                    "target": _truncate(name, 60),
                    "from": _CATEGORY_LABELS[old],
                    "to": _CATEGORY_LABELS[new],
                    "count": count,
                    "timeLabel": _format_seconds(seconds),
                }
                for (name, old, new), (count, seconds) in ranked[:_PREVIEW_ROWS]
            ],
            "more": max(0, len(ranked) - _PREVIEW_ROWS),
        }

    def reapply_rules(self) -> dict[str, Any]:
        """지난 기록에 지금 규칙을 적용. 되돌릴 수 있도록 먼저 백업."""
        changes = self._rule_changes()
        if not changes:
            return {"message": "바뀌는 기록이 없어요.", "error": ""}
        try:
            safety = self._backup_manager().safety_backup("reapply")
        except (OSError, sqlite3.Error) as exc:
            _log.warning("backup before reapply failed: %s", type(exc).__name__)
            return {"message": "", "error": "먼저 백업하지 못해 기록을 바꾸지 않았어요. 디스크 공간과 데이터 폴더 권한을 확인하세요."}
        count = self.store.apply_reclassification(changes)
        return {"message": f"지난 기록 {count}건의 분류를 바꿨어요. 이전 상태 백업: {safety.name}", "error": ""}

    def _rule_changes(self) -> list[Reclassification]:
        return self.store.reclassification_changes(RuleClassifier.from_file(self.rules_path).classify)

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
