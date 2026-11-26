"""사용자 정의 직업 프리셋: 적용할 수 있는 규칙 후보 묶음.

- 형식: ``{"id", "name", "emoji", "base", "rules"}``
- ``base``: 복제 원본인 기본 프리셋 (없으면 "")
- 모델에 보낼 수 있는 것은 ``base`` 뿐 (이름은 사용자가 직접 쓴 글)
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any
from uuid import uuid4

from time_manager.rules import PROFILE_PRESETS, _domain_from_url

CUSTOM_PREFIX = "custom:"
MAX_PRESETS = 20
MAX_NAME_LENGTH = 30
MAX_EMOJI_LENGTH = 8
MAX_VALUES_PER_LIST = 100
MAX_VALUE_LENGTH = 200
DEFAULT_EMOJI = "🧩"

PRESET_KEYS = (
    "productive_domains",
    "productive_apps",
    "productive_title_keywords",
    "unproductive_domains",
    "unproductive_apps",
    "unproductive_title_keywords",
)


class PresetError(ValueError):
    """메시지는 사용자에게 표시."""


def new_preset_id() -> str:
    return f"{CUSTOM_PREFIX}{uuid4().hex[:12]}"


def clean_name(name: object, taken: Iterable[str]) -> str:
    text = " ".join(str(name or "").split())
    if not text:
        raise PresetError("프리셋 이름을 입력하세요.")
    if len(text) > MAX_NAME_LENGTH:
        raise PresetError(f"프리셋 이름은 {MAX_NAME_LENGTH}자 이내로 입력하세요.")
    if text.casefold() in {other.casefold() for other in taken}:
        raise PresetError(f"'{text}' 이름의 프리셋이 이미 있어요.")
    return text


def clean_emoji(emoji: object) -> str:
    return str(emoji or "").strip()[:MAX_EMOJI_LENGTH] or DEFAULT_EMOJI


def _clean_value(key: str, value: object) -> str:
    text = " ".join(str(value or "").split())
    if not text or len(text) > MAX_VALUE_LENGTH:
        raise PresetError(f"값은 1자에서 {MAX_VALUE_LENGTH}자 사이로 입력하세요.")
    if key.endswith("_domains"):
        domain = _domain_from_url(text) if "." in text else None
        if not domain or "." not in domain or " " in text:
            raise PresetError(f"'{text}'은(는) 도메인 형식이 아니에요. 예: company.com")
        return domain
    return text


def build_rules(items: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    """``[{"key", "value"}, ...]`` 를 검증해 규칙 목록으로 변환."""
    rules: dict[str, list[str]] = {}
    sides: dict[tuple[str, str], str] = {}  # (규칙 유형, 값) -> productive | unproductive
    for item in items:
        if not isinstance(item, Mapping) or item.get("key") not in PRESET_KEYS:
            raise PresetError("지원하지 않는 규칙 유형이에요.")
        key = str(item["key"])
        value = _clean_value(key, item.get("value"))
        side, _, kind = key.partition("_")
        previous = sides.setdefault((kind, value.casefold()), side)
        if previous != side:
            raise PresetError(f"'{value}'이(가) 생산적과 비생산적에 모두 들어 있어요.")
        bucket = rules.setdefault(key, [])
        if value.casefold() not in {existing.casefold() for existing in bucket}:
            bucket.append(value)
        if len(bucket) > MAX_VALUES_PER_LIST:
            raise PresetError(f"규칙은 유형마다 {MAX_VALUES_PER_LIST}개까지 넣을 수 있어요.")
    return rules


def copy_rules(source: Mapping[str, Sequence[str]]) -> dict[str, list[str]]:
    """규칙 묶음(기본 프리셋 또는 내 규칙) 중 프리셋에 담는 부분."""
    copied = {key: [str(value) for value in source.get(key, [])][:MAX_VALUES_PER_LIST] for key in PRESET_KEYS}
    return {key: values for key, values in copied.items() if values}


def coerce_presets(data: object) -> list[dict[str, Any]]:
    """저장된 프리셋 읽기. 형식이 잘못된 것은 실패 대신 제외."""
    if not isinstance(data, list):
        return []
    presets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in data[:MAX_PRESETS]:
        if not isinstance(entry, dict):
            continue
        preset_id = str(entry.get("id", ""))
        name = " ".join(str(entry.get("name", "")).split())[:MAX_NAME_LENGTH]
        rules = entry.get("rules")
        if not preset_id.startswith(CUSTOM_PREFIX) or preset_id in seen or not name or not isinstance(rules, dict):
            continue
        seen.add(preset_id)
        base = str(entry.get("base", ""))
        presets.append(
            {
                "id": preset_id,
                "name": name,
                "emoji": clean_emoji(entry.get("emoji")),
                "base": base if base in PROFILE_PRESETS else "",
                "rules": copy_rules(
                    {k: [v for v in values if isinstance(v, str) and v.strip()]
                     for k, values in rules.items() if isinstance(values, list)}
                ),
            }
        )
    return presets
