from __future__ import annotations

from datetime import date
from typing import Any

from time_manager.formatting import _format_seconds, _truncate
from time_manager.models import Category
from time_manager.rules import RuleClassifier, RuleConflictError, add_rule_value, rule_from_candidate

from ._shared import _CATEGORY_LABELS


class InboxMixin:
    def _add_rule_value(self, key: str, value: str) -> RuleClassifier | None:
        try:
            return add_rule_value(self.rules_path, key, value)
        except RuleConflictError:
            return None

    def get_inbox(self, query: str = "", category: str | None = None, date_iso: str | None = None) -> dict[str, Any]:
        searching = bool(query.strip()) or bool(category)
        if searching:
            cat = Category(category) if category else None
            rows = self.store.search_events(query=query, category=cat, days=30, limit=200)
        else:
            selected_day = date.fromisoformat(date_iso) if date_iso else date.today()
            rows = self.store.recent_for_day(selected_day, limit=30)
        records = [
            {
                "id": row.id,
                "time": row.started_at.replace("T", " "),
                "category": row.category.value,
                "categoryLabel": _CATEGORY_LABELS[row.category],
                "duration": _format_seconds(row.seconds),
                "label": _truncate(row.url or row.title or row.app_name, 68),
            }
            for row in rows
        ]
        return {
            "records": records,
            "searchActive": searching,
            "resultCount": len(records) if searching else None,
        }

    def reclassify_event(self, event_id: int, category: str) -> dict[str, Any]:
        self.store.reclassify_event(event_id, Category(category))
        return self.get_inbox()

    def save_event_as_rule(self, event_id: int, label: str, category: str) -> dict[str, Any]:
        cat = Category(category)
        if cat == Category.NEUTRAL:
            return self.get_inbox()
        key, value = rule_from_candidate(label, cat)
        classifier = self._add_rule_value(key, value)
        if classifier is not None:
            self.tracker.classifier = classifier
            self.store.reclassify_event(event_id, cat)
        return self.get_inbox()

    def delete_event(self, event_id: int) -> dict[str, Any]:
        self.store.soft_delete_event(event_id)
        return self.get_inbox()

    def restore_deleted_event(self) -> dict[str, Any]:
        self.store.restore_last_deleted()
        return self.get_inbox()
