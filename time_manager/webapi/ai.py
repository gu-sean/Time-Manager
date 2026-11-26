from __future__ import annotations

import json
import threading
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any

from time_manager import ai as _ai
from time_manager.formatting import _format_seconds
from time_manager.local_coaching import build_local_coaching
from time_manager.local_model import LocalClassifier
from time_manager.models import Category
from time_manager.rules import PROFILE_PRESETS, load_rules

from ._shared import WebApiBase, _CATEGORY_LABELS

_WEEKDAYS = ("월", "화", "수", "목", "금", "토", "일")
_MIN_ACTIVITY_SECONDS = 10 * 60
_MAX_PENDING_TOKENS = 50
_token_lock = threading.Lock()
_BUILTIN_LABEL = "내장 분석"
_NOT_ENOUGH_ACTIVITY = "분석할 활동 기록이 아직 부족합니다."


class AIMixin(WebApiBase):
    """Classification suggestions and coaching.

    The default provider runs entirely on this PC. External providers are opt-in
    and receive only app names, domains and aggregated numbers — never window
    titles or full URLs. A failing provider never silently falls back to another.
    """

    _ai_keys = _ai.AIKeyStore()

    # -- settings ---------------------------------------------------------------

    def _ai_settings_payload(self) -> dict[str, Any]:
        return {
            "aiProvider": self.settings.ai_provider,
            "aiProviderOptions": [{"value": v, "label": label} for v, label in _ai.PROVIDER_OPTIONS],
            "aiService": self.settings.ai_service,
            "aiServices": [self._ai_service_payload(service) for service in _ai.SERVICES.values()],
        }

    def _ai_service_payload(self, service: _ai.Service) -> dict[str, Any]:
        model, base_url = self._ai_service_config(service.id)
        return {
            "value": service.id,
            "label": service.label,
            "help": service.help,
            "editableUrl": service.editable_url,
            "keyRequired": service.key_required,
            "keyPlaceholder": service.key_placeholder,
            "suggestedModels": [{"value": v, "label": label} for v, label in service.suggested_models],
            "model": model,
            "baseUrl": base_url,
            "hasKey": bool(base_url and self._ai_keys.get(_ai.key_account(service.id, base_url))),
        }

    def _ai_service_config(self, service_id: str) -> tuple[str, str]:
        """Saved (model, base URL) of a service, falling back to its defaults."""
        service = _ai.SERVICES[service_id]
        config = self.settings.ai_service_configs.get(service_id, {})
        base_url = config.get("base_url", "") if service.editable_url else ""
        return config.get("model") or service.default_model, base_url or service.base_url

    def _ai_uses_model(self, service_id: str) -> bool:
        return self.settings.ai_provider == _ai.PROVIDER_MODEL and self.settings.ai_service == service_id

    def save_ai_settings(
        self, provider: str, service_id: str = "", model: str = "", base_url: str = ""
    ) -> dict[str, Any]:
        if provider not in _ai.PROVIDER_IDS:
            return self._ai_settings_error("지원하지 않는 분석 방식입니다.")
        if provider == _ai.PROVIDER_LOCAL:
            self.settings.ai_provider = provider
            self.settings_store.save(self.settings)
            return self.get_settings()

        service = _ai.SERVICES.get(service_id)
        if service is None:
            return self._ai_settings_error("지원하지 않는 서비스입니다.")
        try:
            url = _ai.resolve_base_url(service_id, base_url)
        except _ai.AIError as exc:
            return self._ai_settings_error(str(exc))
        model = (model or "").strip()
        if not model:
            return self._ai_settings_error("사용할 모델을 입력하거나 목록에서 선택하세요.")
        if service.key_required and not self._ai_keys.get(_ai.key_account(service_id, url)):
            return self._ai_settings_error(f"{service.label}의 API 키를 먼저 저장하세요.")
        self.settings.ai_provider = provider
        self.settings.ai_service = service_id
        self.settings.ai_service_configs[service_id] = {"model": model, "base_url": url}
        self.settings_store.save(self.settings)
        return self.get_settings()

    def set_ai_api_key(self, service_id: str, api_key: str, base_url: str = "") -> dict[str, Any]:
        service = _ai.SERVICES.get(service_id)
        if service is None:
            return self._ai_settings_error("지원하지 않는 서비스입니다.")
        key = (api_key or "").strip()
        if len(key) < service.min_key_length or any(ch.isspace() for ch in key):
            return self._ai_settings_error("API 키 형식이 올바르지 않습니다.")
        try:
            url = _ai.resolve_base_url(service_id, base_url)
            model, saved_url = self._ai_service_config(service_id)
            # Saving a key must not silently redirect the model that is in use.
            if url != saved_url and self._ai_uses_model(service_id):
                return self._ai_settings_error("서버 주소를 바꿨다면 먼저 '저장하고 사용'을 눌러주세요.")
            self._ai_keys.set(_ai.key_account(service_id, url), key)
        except _ai.AIError as exc:
            return self._ai_settings_error(str(exc))
        if service.editable_url and url != saved_url:
            self.settings.ai_service_configs[service_id] = {"model": model, "base_url": url}
            self.settings_store.save(self.settings)
        self._ai_coaching_cache().clear()
        return self.get_settings()

    def clear_ai_api_key(self, service_id: str, base_url: str = "") -> dict[str, Any]:
        service = _ai.SERVICES.get(service_id)
        if service is None:
            return self._ai_settings_error("지원하지 않는 서비스입니다.")
        try:
            url = _ai.resolve_base_url(service_id, base_url)
        except _ai.AIError as exc:
            return self._ai_settings_error(str(exc))
        self._ai_keys.delete(_ai.key_account(service_id, url))
        if service.key_required and self._ai_uses_model(service_id):
            self.settings.ai_provider = _ai.PROVIDER_LOCAL
            self.settings_store.save(self.settings)
        self._ai_coaching_cache().clear()
        return self.get_settings()

    def list_ai_models(self, service_id: str, base_url: str = "") -> dict[str, Any]:
        service = _ai.SERVICES.get(service_id)
        if service is None:
            return {"models": [], "error": "지원하지 않는 서비스입니다."}
        try:
            url = _ai.resolve_base_url(service_id, base_url)
            api_key = self._ai_keys.get(_ai.key_account(service_id, url))
            if service.key_required and not api_key:
                raise _ai.AIError("API 키를 먼저 저장하세요.")
            models = _ai.list_models(service_id=service_id, base_url=url, api_key=api_key)
        except _ai.AIError as exc:
            return {"models": [], "error": str(exc)}
        return {"models": models, "error": ""}

    def test_ai_connection(self) -> dict[str, Any]:
        if self.settings.ai_provider == _ai.PROVIDER_LOCAL:
            return {"ok": True, "message": "내장 분석은 연결이 필요 없습니다."}
        try:
            self._ai_complete("Reply with the single word: OK", "ping", max_tokens=1024)
        except _ai.AIError as exc:
            return {"ok": False, "message": str(exc)}
        return {"ok": True, "message": "연결에 성공했습니다."}

    # -- rule suggestions ---------------------------------------------------------

    def get_ai_rule_suggestions(
        self, request_id: str = "", builtin: bool = False, days: int = 14, limit: int = 12
    ) -> dict[str, Any]:
        """``builtin`` analyses on this PC for this one call, without changing settings."""
        local = builtin or self.settings.ai_provider == _ai.PROVIDER_LOCAL
        source = _BUILTIN_LABEL if local else self._ai_source_label()
        end_day = date.today()
        start_day = end_day - timedelta(days=max(1, int(days)) - 1)
        candidates = self._unclassified_targets(days, limit)
        if not candidates:
            return self._suggestion_result(source=source)

        targets = [row.label for row in candidates]
        seconds_by_target = {row.label: row.seconds for row in candidates}
        if local:
            results = self._local_classifications(targets, load_rules(self.rules_path), start_day, end_day)
        else:
            try:
                text = self._ai_complete(
                    _ai.CLASSIFY_SYSTEM, self._classification_message(targets), max_tokens=8000,
                    request_id=request_id,
                )
                results = _ai.parse_classifications(text, targets)
            except _ai.AIError as exc:
                return self._suggestion_result(source=source, **self._failure(exc))

        items = [
            {
                "target": result["target"],
                "displayTarget": result["target"],
                "timeLabel": _format_seconds(seconds_by_target[result["target"]]),
                "category": result["category"],
                "categoryLabel": _CATEGORY_LABELS[Category(result["category"])],
                "reason": result["reason"],
            }
            for result in results
        ]
        return self._suggestion_result(source=source, items=items, skipped=len(targets) - len(items))

    @staticmethod
    def _suggestion_result(
        *, source: str, items: list | None = None, skipped: int = 0, error: str = "", canFallback: bool = False
    ) -> dict[str, Any]:
        return {
            "items": items or [], "skipped": skipped, "source": source,
            "error": error, "canFallback": canFallback,
        }

    def _classification_message(self, targets: list[str]) -> str:
        return _ai.build_classify_request(self.settings.onboarding_profile, targets)

    def _local_classifications(
        self, targets: list[str], rules: dict[str, list[str]], start_day: date, end_day: date
    ) -> list[dict[str, str]]:
        model = LocalClassifier.train(
            self.store.activity_signatures(),
            rules=rules,
            preset=PROFILE_PRESETS.get(self.settings.onboarding_profile, {}),
        )
        titles: dict[str, Counter[str]] = defaultdict(Counter)
        for signature in self.store.activity_signatures(start_day, end_day):
            titles[signature.target][signature.title] += signature.seconds
        results = []
        for target in targets:
            prediction = model.predict(target, titles.get(target))
            if prediction is not None:
                results.append(
                    {"target": target, "category": prediction.category.value, "reason": prediction.reason}
                )
        return results

    # -- coaching -------------------------------------------------------------------

    def get_ai_coaching(
        self,
        scope: str = "week",
        date_iso: str | None = None,
        refresh: bool = False,
        request_id: str = "",
        builtin: bool = False,
    ) -> dict[str, Any]:
        try:
            start_day, anchor = self._coaching_period(scope, date_iso)
        except ValueError as exc:
            return self._coaching_error(str(exc))

        local = builtin or self.settings.ai_provider == _ai.PROVIDER_LOCAL
        cache = self._ai_coaching_cache()
        cache_key = (
            scope,
            start_day.isoformat(),
            anchor.isoformat(),
            self.settings.ai_provider,
            self.settings.ai_service,
            *self._ai_service_config(self.settings.ai_service),
        )
        # The built-in analysis is free and instant, so it is never cached.
        if not local and not refresh and cache_key in cache:
            return cache[cache_key]

        payload = self._coaching_payload(scope, start_day, anchor)
        if payload["totalMinutes"] * 60 < _MIN_ACTIVITY_SECONDS:
            return self._coaching_error(_NOT_ENOUGH_ACTIVITY)

        if local:
            coaching = build_local_coaching(payload)
        else:
            try:
                text = self._ai_complete(
                    _ai.COACHING_SYSTEM, self._coaching_message(payload), max_tokens=8000,
                    request_id=request_id,
                )
                coaching = _ai.parse_coaching(text)
            except _ai.AIError as exc:
                return self._coaching_error(**self._failure(exc))

        result = {
            **coaching,
            "scopeLabel": "최근 7일" if scope == "week" else anchor.isoformat(),
            "source": _BUILTIN_LABEL if local else self._ai_source_label(),
            "generated": not local,
            "error": "",
            "canFallback": False,
        }
        if not local:
            cache[cache_key] = result
        return result

    @staticmethod
    def _coaching_period(scope: str, date_iso: str | None) -> tuple[date, date]:
        if scope not in {"day", "week"}:
            raise ValueError("분석 범위가 올바르지 않습니다.")
        try:
            anchor = date.fromisoformat(date_iso) if date_iso else date.today()
        except ValueError as exc:
            raise ValueError("날짜 형식이 올바르지 않습니다.") from exc
        return anchor - timedelta(days=6 if scope == "week" else 0), anchor

    @staticmethod
    def _coaching_message(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False)

    # -- preview and cancel ---------------------------------------------------------

    def preview_ai_request(self, kind: str, scope: str = "day", date_iso: str | None = None) -> dict[str, Any]:
        """What the next analysis would send, built by the same code that sends it.

        Nothing is sent by this call.
        """
        preview = {"serviceLabel": "", "url": "", "model": "", "instructions": "", "data": "", "error": ""}
        if self.settings.ai_provider != _ai.PROVIDER_MODEL:
            return {**preview, "error": "내장 분석은 아무것도 전송하지 않습니다."}
        if kind == "suggestions":
            targets = [row.label for row in self._unclassified_targets(14, 12)]
            if not targets:
                return {**preview, "error": "분류할 항목이 없어 아무것도 보내지 않습니다."}
            system, message = _ai.CLASSIFY_SYSTEM, self._classification_message(targets)
        elif kind == "coaching":
            try:
                start_day, anchor = self._coaching_period(scope, date_iso)
            except ValueError as exc:
                return {**preview, "error": str(exc)}
            payload = self._coaching_payload(scope, start_day, anchor)
            if payload["totalMinutes"] * 60 < _MIN_ACTIVITY_SECONDS:
                return {**preview, "error": f"{_NOT_ENOUGH_ACTIVITY} 아무것도 보내지 않습니다."}
            system, message = _ai.COACHING_SYSTEM, self._coaching_message(payload)
        else:
            return {**preview, "error": "알 수 없는 요청입니다."}

        service = _ai.SERVICES[self.settings.ai_service]
        model, base_url = self._ai_service_config(service.id)
        return {
            **preview,
            "serviceLabel": service.label,
            "url": _ai.request_url(service.id, base_url),
            "model": model,
            "instructions": system,
            "data": json.dumps(json.loads(message), ensure_ascii=False, indent=2),
        }

    def cancel_ai_request(self, request_id: str) -> None:
        if request_id:
            self._ai_token(request_id).cancel()

    def _ai_token(self, request_id: str) -> _ai.CancelToken:
        """Get or create, so a cancel that arrives before the request still counts."""
        if not request_id:
            return _ai.CancelToken()
        with _token_lock:
            tokens = self.__dict__.setdefault("_ai_tokens", {})
            if len(tokens) >= _MAX_PENDING_TOKENS:  # leftovers of cancels that arrived too late
                for stale in [key for key, token in tokens.items() if token.cancelled]:
                    del tokens[stale]
            return tokens.setdefault(request_id, _ai.CancelToken())

    def _release_ai_token(self, request_id: str) -> None:
        with _token_lock:
            self.__dict__.get("_ai_tokens", {}).pop(request_id, None)

    @staticmethod
    def _failure(exc: _ai.AIError) -> dict[str, Any]:
        """Error fields; the UI offers the built-in analysis, it is never used silently."""
        return {"error": str(exc), "canFallback": True}

    def _coaching_payload(self, scope: str, start_day: date, end_day: date) -> dict[str, Any]:
        summaries = self.store.summaries_between(start_day, end_day)
        daily = []
        for row in summaries:
            day = date.fromisoformat(row.day)
            daily.append(
                {
                    "date": row.day,
                    "weekday": _WEEKDAYS[day.weekday()],
                    "productiveMin": row.productive_seconds // 60,
                    "unproductiveMin": row.unproductive_seconds // 60,
                    "neutralMin": row.neutral_seconds // 60,
                    "score": row.productivity_score,
                }
            )

        hours = self.store.hourly_summaries_between(start_day, end_day)
        best_hours = [h.hour for h in sorted(hours, key=lambda h: h.productive_seconds, reverse=True)[:3] if h.productive_seconds > 0]
        worst_hours = [h.hour for h in sorted(hours, key=lambda h: h.unproductive_seconds, reverse=True)[:3] if h.unproductive_seconds > 0]

        focus_blocks = target_switches = category_switches = 0
        current = start_day
        while current <= end_day:
            flow = self.store.day_flow(current)
            focus_blocks += len(flow.focus_sessions(min_seconds=25 * 60))
            target_switches += flow.target_switches
            category_switches += flow.category_switches
            current += timedelta(days=1)

        totals = self.store.app_domain_totals(start_day, end_day)
        top: dict[str, list[dict[str, Any]]] = {"productive": [], "unproductive": [], "neutral": []}
        for row in totals:
            bucket = top[row.category.value]
            if len(bucket) < 5 and row.seconds >= 60:
                bucket.append({"name": row.label, "minutes": row.seconds // 60})

        return {
            "includesToday": end_day >= date.today(),
            "comparison": self._comparison(summaries, start_day, end_day),
            "scope": scope,
            "period": f"{start_day.isoformat()}~{end_day.isoformat()}",
            "userProfile": self.settings.onboarding_profile or "unspecified",
            "goals": {
                "dailyProductiveMin": self.settings.daily_goal_minutes,
                "weeklyProductiveMin": self.settings.weekly_goal_minutes,
                "unproductiveLimitMin": self.settings.unproductive_limit_minutes,
                "workHours": f"{self.settings.work_start_hour}-{self.settings.work_end_hour}",
            },
            "daily": daily,
            "bestProductiveHours": best_hours,
            "mostUnproductiveHours": worst_hours,
            "topTargets": top,
            "flow": {
                "focusBlocks25minPlus": focus_blocks,
                "targetSwitches": target_switches,
                "categorySwitches": category_switches,
            },
            "totalMinutes": sum(row.total_seconds for row in summaries) // 60,
        }

    def _comparison(self, summaries: list, start_day: date, end_day: date) -> dict[str, int] | None:
        """Productive time versus the same days one period earlier, only when that is fair.

        Today is left out because it is not over yet. The app must have been in use
        before the earlier period began, and both sides need about as many recorded days.
        """
        length = end_day - start_day + timedelta(days=1)
        last_full_day = min(end_day, date.today() - timedelta(days=1))
        if last_full_day < start_day:
            return None
        previous_start = start_day - length
        first_day = self.store.first_activity_day()
        if first_day is None or first_day >= previous_start:
            return None
        current = [row for row in summaries if row.day <= last_full_day.isoformat()]
        previous = self.store.summaries_between(previous_start, last_full_day - length)
        current_days = sum(1 for row in current if row.total_seconds)
        previous_days = sum(1 for row in previous if row.total_seconds)
        if not current_days or not previous_days or abs(current_days - previous_days) > 1:
            return None
        return {
            "comparedDays": len(current),
            "currentProductiveMin": sum(row.productive_seconds for row in current) // 60,
            "previousProductiveMin": sum(row.productive_seconds for row in previous) // 60,
        }

    # -- helpers --------------------------------------------------------------------

    def _ai_complete(self, system: str, user: str, *, max_tokens: int, request_id: str = "") -> str:
        """Call the user's selected model."""
        if self.settings.ai_provider != _ai.PROVIDER_MODEL:
            raise _ai.AIError("개인 모델이 선택되어 있지 않습니다.")
        service = _ai.SERVICES[self.settings.ai_service]
        model, saved_url = self._ai_service_config(service.id)
        url = _ai.resolve_base_url(service.id, saved_url)
        api_key = self._ai_keys.get(_ai.key_account(service.id, url))
        if service.key_required and not api_key:
            raise _ai.AIError(f"설정에서 {service.label}의 API 키를 저장하세요.")
        token = self._ai_token(request_id)
        try:
            return _ai.complete(
                service_id=service.id,
                base_url=url,
                model=model,
                api_key=api_key,
                system=system,
                user=user,
                max_tokens=max_tokens,
                cancel=token,
            )
        finally:
            self._release_ai_token(request_id)

    def _ai_source_label(self) -> str:
        if self.settings.ai_provider != _ai.PROVIDER_MODEL:
            return _BUILTIN_LABEL
        service = _ai.SERVICES[self.settings.ai_service]
        model, _ = self._ai_service_config(service.id)
        return f"{service.label} · {model}"

    def _ai_settings_error(self, message: str) -> dict[str, Any]:
        return {**self.get_settings(), "error": message}

    def _ai_coaching_cache(self) -> dict[tuple[str, ...], dict[str, Any]]:
        cache = getattr(self, "_ai_coaching_cache_store", None)
        if cache is None:
            cache = {}
            self._ai_coaching_cache_store = cache
        return cache

    @staticmethod
    def _coaching_error(error: str, canFallback: bool = False) -> dict[str, Any]:
        return {
            "headline": "", "insights": [], "actions": [],
            "scopeLabel": "", "source": "", "generated": False, "error": error, "canFallback": canFallback,
        }
