import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class AppSettings:
    daily_goal_minutes: int = 180
    weekly_goal_minutes: int = 900
    exclude_self_app: bool = True
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


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return AppSettings()
        return AppSettings(
            daily_goal_minutes=int(data.get("daily_goal_minutes", 180)),
            weekly_goal_minutes=int(data.get("weekly_goal_minutes", 900)),
            exclude_self_app=bool(data.get("exclude_self_app", True)),
            unproductive_limit_minutes=int(data.get("unproductive_limit_minutes", 120)),
            work_start_hour=int(data.get("work_start_hour", 9)),
            work_end_hour=int(data.get("work_end_hour", 18)),
            onboarding_profile=str(data.get("onboarding_profile", "")),
            store_domain_only=bool(data.get("store_domain_only", False)),
            store_window_titles=bool(data.get("store_window_titles", True)),
            retention_days=max(0, int(data.get("retention_days", 0))),
            notifications_enabled=bool(data.get("notifications_enabled", True)),
            auto_backup_enabled=bool(data.get("auto_backup_enabled", True)),
            last_auto_backup=str(data.get("last_auto_backup", "")),
            last_weekly_summary_notified=str(data.get("last_weekly_summary_notified", "")),
            theme=_coerce_theme(data.get("theme", "light")),
        )

    def load_or_create(self) -> AppSettings:
        settings = self.load()
        if not self.path.exists():
            self.save(settings)
        return settings

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(settings), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _coerce_theme(value: object) -> str:
    theme = str(value).strip().lower()
    return theme if theme in {"light", "dark"} else "light"
