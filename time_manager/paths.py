import os
import sys
from pathlib import Path


APP_NAME = "TimeManager"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundled_root(project_root: Path) -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return project_root


def user_data_dir(project_root: Path) -> Path:
    if not is_frozen():
        return project_root / "data"

    base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return base / APP_NAME


def writable_rules_path(project_root: Path) -> Path:
    if not is_frozen():
        return project_root / "rules.json"
    return user_data_dir(project_root) / "rules.json"


def ensure_writable_rules(project_root: Path) -> Path:
    rules_path = writable_rules_path(project_root)
    if rules_path.exists():
        return rules_path

    rules_path.parent.mkdir(parents=True, exist_ok=True)
    default_rules = bundled_root(project_root) / "rules.json"
    rules_path.write_text(default_rules.read_text(encoding="utf-8"), encoding="utf-8")
    return rules_path

