import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from time_manager import notices
from time_manager.fileio import atomic_write_text
from time_manager.ai import DEFAULT_SERVICE, PROVIDER_IDS, PROVIDER_LOCAL, SERVICES
from time_manager.presets import coerce_presets


@dataclass
class AppSettings:
    daily_goal_minutes: int = 180
    weekly_goal_minutes: int = 900
    unproductive_limit_minutes: int = 120
    work_start_hour: int = 9
    work_end_hour: int = 18
    onboarding_profile: str = ""
    store_domain_only: bool = False
    store_window_titles: bool = True
    retention_days: int = 0
    notifications_enabled: bool = True
    auto_backup_enabled: bool = True
    last_auto_backup: str = ""
    last_weekly_summary_notified: str = ""
    theme: str = "light"
    ai_provider: str = PROVIDER_LOCAL
    ai_service: str = DEFAULT_SERVICE
    # 서비스별 {"model": ..., "base_url": ...}: 서비스를 바꿔도 각 설정 유지
    ai_service_configs: dict[str, dict[str, str]] = field(default_factory=dict)
    # 모델에 이름을 보내지 않는 앱·도메인
    ai_excluded_targets: list[str] = field(default_factory=list)
    # 다시 보지 않기로 한 분류 추천 (소문자)
    dismissed_suggestions: list[str] = field(default_factory=list)
    # 사용자 직업 프리셋 (``time_manager.presets`` 참고)
    custom_presets: list[dict[str, Any]] = field(default_factory=list)


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> AppSettings:
        """읽을 수 있는 값은 유지. 파일이 손상돼도 앱 시작을 막지 않음."""
        if not self.path.exists():
            return AppSettings()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except ValueError:  # 잘못된 JSON 또는 UTF-8 아님
            data = None
        if not isinstance(data, dict):
            self._keep_damaged_copy()
            return AppSettings()

        damaged: list[str] = []

        def number(key: str, default: int) -> int:
            try:
                return int(data.get(key, default))
            except (TypeError, ValueError, OverflowError):
                damaged.append(key)
                return default

        settings = AppSettings(
            daily_goal_minutes=number("daily_goal_minutes", 180),
            weekly_goal_minutes=number("weekly_goal_minutes", 900),
            unproductive_limit_minutes=number("unproductive_limit_minutes", 120),
            work_start_hour=number("work_start_hour", 9),
            work_end_hour=number("work_end_hour", 18),
            onboarding_profile=str(data.get("onboarding_profile", "")),
            store_domain_only=bool(data.get("store_domain_only", False)),
            store_window_titles=bool(data.get("store_window_titles", True)),
            retention_days=max(0, number("retention_days", 0)),
            notifications_enabled=bool(data.get("notifications_enabled", True)),
            auto_backup_enabled=bool(data.get("auto_backup_enabled", True)),
            last_auto_backup=str(data.get("last_auto_backup", "")),
            last_weekly_summary_notified=str(data.get("last_weekly_summary_notified", "")),
            theme=_coerce_theme(data.get("theme", "light")),
            ai_provider=_coerce_ai_provider(data.get("ai_provider", PROVIDER_LOCAL)),
            ai_service=_coerce_ai_service(data.get("ai_service", DEFAULT_SERVICE)),
            ai_service_configs=_coerce_ai_service_configs(data.get("ai_service_configs")),
            ai_excluded_targets=_coerce_names(data.get("ai_excluded_targets")),
            dismissed_suggestions=_coerce_names(data.get("dismissed_suggestions")),
            custom_presets=coerce_presets(data.get("custom_presets")),
        )
        if damaged:
            self._keep_damaged_copy()
        return settings

    def load_or_create(self) -> AppSettings:
        settings = self.load()
        if not self.path.exists():
            self.save(settings)
        return settings

    def save(self, settings: AppSettings) -> None:
        """저장 실패 시 ``settings`` 를 디스크 상태로 되돌린 뒤 예외 발생."""
        try:
            atomic_write_text(self.path, json.dumps(asdict(settings), indent=2, ensure_ascii=False) + "\n")
        except OSError:
            # 되돌리지 않으면 저장된 것처럼 동작함
            saved = self.load()
            for item in fields(AppSettings):
                setattr(settings, item.name, getattr(saved, item.name))
            raise

    def _keep_damaged_copy(self) -> None:
        kept = self.path.with_name(f"{self.path.name}.corrupt")
        try:
            kept.write_bytes(self.path.read_bytes())
        except OSError:
            return
        notices.add(f"설정 파일이 손상되어 읽지 못한 항목은 기본값을 사용해요. 원본은 '{kept}' 파일로 보관했습니다.")


def _coerce_theme(value: object) -> str:
    theme = str(value).strip().lower()
    return theme if theme in {"light", "dark"} else "light"


def _coerce_ai_provider(value: object) -> str:
    provider = str(value).strip()
    return provider if provider in PROVIDER_IDS else PROVIDER_LOCAL


def _coerce_names(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(name.strip().lower() for name in value if isinstance(name, str) and name.strip()))


def _coerce_ai_service(value: object) -> str:
    service = str(value).strip()
    return service if service in SERVICES else DEFAULT_SERVICE


def _coerce_ai_service_configs(value: object) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict):
        return {}
    return {
        service: {"model": str(config.get("model", "")), "base_url": str(config.get("base_url", ""))}
        for service, config in value.items()
        if service in SERVICES and isinstance(config, dict)
    }
