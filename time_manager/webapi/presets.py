from __future__ import annotations

from typing import Any

from time_manager import presets as _presets
from time_manager.rules import PROFILE_PRESETS, apply_preset_rules, load_rules

from ._shared import WebApiBase

_BUILTIN_PRESETS: tuple[tuple[str, str, str], ...] = (
    ("developer", "개발자", "💻"),
    ("student", "학생", "📚"),
    ("office", "사무직", "💼"),
    ("creator", "크리에이터", "🎨"),
    ("researcher", "연구자", "🔬"),
    ("designer", "디자이너", "🎨"),
    ("marketer", "마케터", "📣"),
    ("finance", "재무/투자", "💰"),
    ("manager", "매니저", "📊"),
)
_CURRENT_RULES = "current_rules"


class PresetMixin(WebApiBase):
    """기본 직업 프리셋(읽기 전용)과 사용자 프리셋."""

    # -- 조회 -------------------------------------------------------------------

    def _custom_preset(self, preset_id: str) -> dict[str, Any] | None:
        return next((p for p in self.settings.custom_presets if p["id"] == preset_id), None)

    def _preset_rules(self, preset_id: str) -> dict[str, Any]:
        custom = self._custom_preset(preset_id)
        return custom["rules"] if custom else PROFILE_PRESETS.get(preset_id, {})

    def _preset_role(self, preset_id: str) -> str:
        """모델에 알려도 되는 직업명 (사용자가 입력한 이름은 제외)."""
        custom = self._custom_preset(preset_id)
        if custom:
            return custom["base"]
        return preset_id if preset_id in PROFILE_PRESETS else ""

    def _preset_settings_payload(self) -> dict[str, Any]:
        selected = self.settings.onboarding_profile
        options = [{"value": "", "label": "선택 안 함", "emoji": "", "custom": False}]
        options += [{"value": v, "label": label, "emoji": emoji, "custom": False} for v, label, emoji in _BUILTIN_PRESETS]
        options += [
            {"value": p["id"], "label": p["name"], "emoji": p["emoji"], "custom": True}
            for p in self.settings.custom_presets
        ]
        return {
            "profile": selected,
            "profileOptions": options,
            "presetItems": [
                {"key": key, "value": value} for key, values in self._preset_rules(selected).items() for value in values
            ],
        }

    # -- 선택·적용 --------------------------------------------------------------

    def set_profile(self, profile: str) -> dict[str, Any]:
        if profile and profile not in PROFILE_PRESETS and not self._custom_preset(profile):
            return self._preset_error("없는 프리셋이에요.")
        self.settings.onboarding_profile = profile
        self.settings_store.save(self.settings)
        return self.get_settings()

    def apply_preset(self) -> dict[str, Any]:
        preset = self._preset_rules(self.settings.onboarding_profile)
        if not preset:
            return self._preset_error("적용할 규칙이 없어요.")
        classifier, added, kept = apply_preset_rules(self.rules_path, preset)
        self.tracker.classifier = classifier
        notice = f"프리셋 규칙 {added}개를 추가했습니다."
        if kept:
            notice += f" {kept}개는 이미 다른 분류에 있어 기존 규칙을 유지했어요."
        return {**self.get_settings(), "notice": notice}

    # -- 사용자 프리셋 ----------------------------------------------------------

    def create_preset(self, name: str, emoji: str = "", source: str = "") -> dict[str, Any]:
        """``source``: ""(빈 프리셋), "current_rules"(현재 규칙), 또는 복제할 프리셋 id."""
        if len(self.settings.custom_presets) >= _presets.MAX_PRESETS:
            return self._preset_error(f"내 프리셋은 {_presets.MAX_PRESETS}개까지 만들 수 있어요.")
        if source == _CURRENT_RULES:
            rules, base = _presets.copy_rules(load_rules(self.rules_path)), ""
        elif not source:
            rules, base = {}, ""
        elif source in PROFILE_PRESETS or self._custom_preset(source):
            rules, base = _presets.copy_rules(self._preset_rules(source)), self._preset_role(source)
        else:
            return self._preset_error("복제할 프리셋을 찾을 수 없어요.")
        try:
            preset = {
                "id": _presets.new_preset_id(),
                "name": _presets.clean_name(name, self._taken_preset_names()),
                "emoji": _presets.clean_emoji(emoji),
                "base": base,
                "rules": rules,
            }
        except _presets.PresetError as exc:
            return self._preset_error(str(exc))
        self.settings.custom_presets.append(preset)
        self.settings.onboarding_profile = preset["id"]
        self.settings_store.save(self.settings)
        return self.get_settings()

    def update_preset(self, preset_id: str, name: str, emoji: str, items: list[dict[str, str]]) -> dict[str, Any]:
        preset = self._custom_preset(preset_id)
        if preset is None:
            return self._preset_error("직접 만든 프리셋만 수정할 수 있어요.")
        try:
            changes = {
                "name": _presets.clean_name(name, self._taken_preset_names(except_id=preset_id)),
                "emoji": _presets.clean_emoji(emoji),
                "rules": _presets.build_rules(items),
            }
        except _presets.PresetError as exc:
            return self._preset_error(str(exc))
        preset.update(changes)
        self.settings_store.save(self.settings)
        return self.get_settings()

    def delete_preset(self, preset_id: str) -> dict[str, Any]:
        """프리셋에서 이미 적용한 규칙은 그대로 유지."""
        preset = self._custom_preset(preset_id)
        if preset is None:
            return self._preset_error("직접 만든 프리셋만 삭제할 수 있어요.")
        self.settings.custom_presets.remove(preset)
        if self.settings.onboarding_profile == preset_id:
            self.settings.onboarding_profile = ""
        self.settings_store.save(self.settings)
        return self.get_settings()

    def _taken_preset_names(self, except_id: str = "") -> list[str]:
        builtin = [label for _value, label, _emoji in _BUILTIN_PRESETS]
        return builtin + [p["name"] for p in self.settings.custom_presets if p["id"] != except_id]

    def _preset_error(self, message: str) -> dict[str, Any]:
        return {**self.get_settings(), "error": message}
