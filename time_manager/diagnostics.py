import json
import sqlite3
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from time_manager.rules import load_rules


class DiagnosticStatus(str, Enum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class DiagnosticResult:
    name: str
    status: DiagnosticStatus
    message: str
    path: Path


def run_diagnostics(
    *,
    data_dir: Path,
    db_path: Path,
    rules_path: Path,
    settings_path: Path,
    log_path: Path,
) -> tuple[DiagnosticResult, ...]:
    return (
        _check_data_dir(data_dir),
        _check_database(db_path),
        _check_rules(rules_path),
        _check_settings(settings_path),
        _check_log(log_path),
    )


def _check_data_dir(path: Path) -> DiagnosticResult:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        return DiagnosticResult("data_dir", DiagnosticStatus.ERROR, f"Data directory is not writable: {exc}", path)
    return DiagnosticResult("data_dir", DiagnosticStatus.OK, "Data directory is writable.", path)


def _check_database(path: Path) -> DiagnosticResult:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as conn:
            conn.execute("PRAGMA user_version")
    except sqlite3.Error as exc:
        return DiagnosticResult("database", DiagnosticStatus.ERROR, f"Database cannot be opened: {exc}", path)
    except OSError as exc:
        return DiagnosticResult("database", DiagnosticStatus.ERROR, f"Database path is not writable: {exc}", path)
    return DiagnosticResult("database", DiagnosticStatus.OK, "Database can be opened.", path)


def _check_rules(path: Path) -> DiagnosticResult:
    if not path.exists():
        return DiagnosticResult("rules", DiagnosticStatus.WARNING, "Rules file was not found.", path)
    rules = load_rules(path)
    if not rules:
        return DiagnosticResult("rules", DiagnosticStatus.WARNING, "Rules file is empty or has no usable rules.", path)
    return DiagnosticResult("rules", DiagnosticStatus.OK, f"Loaded {sum(len(values) for values in rules.values())} rules.", path)


def _check_settings(path: Path) -> DiagnosticResult:
    if not path.exists():
        return DiagnosticResult("settings", DiagnosticStatus.WARNING, "Settings file was not found; defaults will be used.", path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return DiagnosticResult("settings", DiagnosticStatus.WARNING, f"Settings file could not be read: {exc}", path)
    if not isinstance(data, dict):
        return DiagnosticResult("settings", DiagnosticStatus.WARNING, "Settings file is not a JSON object.", path)
    return DiagnosticResult("settings", DiagnosticStatus.OK, "Settings file can be read.", path)


def _check_log(path: Path) -> DiagnosticResult:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8"):
            pass
    except OSError as exc:
        return DiagnosticResult("log", DiagnosticStatus.ERROR, f"Log file cannot be written: {exc}", path)
    return DiagnosticResult("log", DiagnosticStatus.OK, "Log file can be written.", path)
