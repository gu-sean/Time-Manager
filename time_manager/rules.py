import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from time_manager import notices
from time_manager.fileio import atomic_write_text
from time_manager.models import NO_RULE_REASON, ActiveTarget, Category, ClassifiedActivity


class RuleConflictError(ValueError):
    def __init__(self, rule_key: str, existing_key: str, value: str) -> None:
        self.rule_key = rule_key
        self.existing_key = existing_key
        self.value = value
        super().__init__(f"Rule value {value!r} already exists in {existing_key}.")


PROFILE_PRESETS: dict[str, dict[str, tuple[str, ...]]] = {
    "developer": {
        "productive_domains": ("github.com", "stackoverflow.com", "docs.python.org", "openai.com"),
        "productive_apps": ("Code.exe", "Cursor.exe", "WindowsTerminal.exe", "powershell.exe"),
        "unproductive_domains": ("youtube.com", "instagram.com", "tiktok.com", "netflix.com"),
    },
    "student": {
        "productive_domains": ("wikipedia.org", "khanacademy.org", "coursera.org", "edx.org"),
        "productive_title_keywords": ("강의", "수업", "과제"),
        "unproductive_domains": ("instagram.com", "tiktok.com", "netflix.com"),
    },
    "office": {
        "productive_domains": ("docs.google.com", "office.com", "notion.so", "slack.com"),
        "productive_apps": ("Teams.exe", "OUTLOOK.EXE", "EXCEL.EXE", "WINWORD.EXE"),
        "unproductive_domains": ("youtube.com", "facebook.com", "x.com"),
    },
    "creator": {
        "productive_domains": ("canva.com", "figma.com", "behance.net", "youtube.com"),
        "productive_apps": ("Photoshop.exe", "Illustrator.exe", "Premiere Pro.exe", "Figma.exe"),
        "unproductive_domains": ("instagram.com", "tiktok.com", "netflix.com"),
    },
    "researcher": {
        "productive_domains": ("scholar.google.com", "arxiv.org", "pubmed.ncbi.nlm.nih.gov", "semanticscholar.org"),
        "productive_title_keywords": ("논문", "리서치", "research", "paper"),
        "unproductive_domains": ("instagram.com", "tiktok.com", "netflix.com"),
    },
    "designer": {
        "productive_domains": ("figma.com", "dribbble.com", "behance.net", "material.io"),
        "productive_apps": ("Figma.exe", "Photoshop.exe", "Illustrator.exe"),
        "unproductive_domains": ("netflix.com", "tiktok.com", "facebook.com"),
    },
    "marketer": {
        "productive_domains": ("analytics.google.com", "ads.google.com", "mailchimp.com", "hubspot.com"),
        "productive_title_keywords": ("캠페인", "광고", "analytics", "campaign"),
        "unproductive_domains": ("netflix.com", "tiktok.com", "instagram.com"),
    },
    "finance": {
        "productive_domains": ("finance.yahoo.com", "tradingview.com", "investing.com", "sec.gov"),
        "productive_apps": ("EXCEL.EXE", "POWERPNT.EXE"),
        "unproductive_domains": ("youtube.com", "instagram.com", "tiktok.com"),
    },
    "manager": {
        "productive_domains": ("slack.com", "notion.so", "asana.com", "linear.app", "calendar.google.com"),
        "productive_apps": ("Teams.exe", "Slack.exe", "OUTLOOK.EXE"),
        "unproductive_domains": ("youtube.com", "facebook.com", "x.com"),
    },
}


@dataclass(frozen=True)
class RuleClassifier:
    productive_domains: tuple[str, ...]
    unproductive_domains: tuple[str, ...]
    productive_title_keywords: tuple[str, ...]
    unproductive_title_keywords: tuple[str, ...]
    neutral_title_keywords: tuple[str, ...]
    excluded_apps: tuple[str, ...]
    productive_apps: tuple[str, ...]
    unproductive_apps: tuple[str, ...]
    # 기록하지 않는 사이트 (하위 도메인 포함)
    excluded_domains: tuple[str, ...] = ()

    @classmethod
    def from_file(cls, path: Path) -> "RuleClassifier":
        return cls.from_dict(load_rules(path))

    @classmethod
    def from_dict(cls, rules: dict[str, list[str]]) -> "RuleClassifier":
        return cls(
            productive_domains=tuple(rules.get("productive_domains", [])),
            unproductive_domains=tuple(rules.get("unproductive_domains", [])),
            productive_title_keywords=tuple(rules.get("productive_title_keywords", [])),
            unproductive_title_keywords=tuple(rules.get("unproductive_title_keywords", [])),
            neutral_title_keywords=tuple(rules.get("neutral_title_keywords", [])),
            excluded_apps=tuple(rules.get("excluded_apps", [])),
            productive_apps=tuple(rules.get("productive_apps", [])),
            unproductive_apps=tuple(rules.get("unproductive_apps", [])),
            excluded_domains=tuple(_domain_from_url(item) or item.lower() for item in rules.get("excluded_domains", [])),
        )

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "productive_domains": list(self.productive_domains),
            "unproductive_domains": list(self.unproductive_domains),
            "productive_title_keywords": list(self.productive_title_keywords),
            "unproductive_title_keywords": list(self.unproductive_title_keywords),
            "neutral_title_keywords": list(self.neutral_title_keywords),
            "excluded_apps": list(self.excluded_apps),
            "productive_apps": list(self.productive_apps),
            "unproductive_apps": list(self.unproductive_apps),
            "excluded_domains": list(self.excluded_domains),
        }

    def classify(self, target: ActiveTarget) -> ClassifiedActivity:
        domain = _domain_from_url(target.url)
        if domain:
            if _matches_domain(domain, self.productive_domains):
                return ClassifiedActivity(target, Category.PRODUCTIVE, f"productive site: {domain}")
            if _matches_domain(domain, self.unproductive_domains):
                return ClassifiedActivity(target, Category.UNPRODUCTIVE, f"unproductive site: {domain}")

        app_name = target.app_name.lower()
        if app_name in {item.lower() for item in self.productive_apps}:
            return ClassifiedActivity(target, Category.PRODUCTIVE, f"productive app: {target.app_name}")
        if app_name in {item.lower() for item in self.unproductive_apps}:
            return ClassifiedActivity(target, Category.UNPRODUCTIVE, f"unproductive app: {target.app_name}")

        title = target.window_title.lower()
        neutral_keyword = _matching_keyword(title, self.neutral_title_keywords)
        if neutral_keyword:
            return ClassifiedActivity(target, Category.NEUTRAL, f"neutral title keyword: {neutral_keyword}")
        productive_keyword = _matching_keyword(title, self.productive_title_keywords)
        if productive_keyword:
            return ClassifiedActivity(target, Category.PRODUCTIVE, f"productive title keyword: {productive_keyword}")
        unproductive_keyword = _matching_keyword(title, self.unproductive_title_keywords)
        if unproductive_keyword:
            return ClassifiedActivity(target, Category.UNPRODUCTIVE, f"unproductive title keyword: {unproductive_keyword}")

        return ClassifiedActivity(target, Category.NEUTRAL, NO_RULE_REASON)


def _domain_from_url(url: str | None) -> str | None:
    if not url:
        return None

    normalized = url if "://" in url else f"https://{url}"
    try:
        parsed = urlparse(normalized)
    except ValueError:
        return None
    if not parsed.hostname:
        return None
    return parsed.hostname.lower().removeprefix("www.")


def _matches_domain(domain: str, patterns: tuple[str, ...]) -> bool:
    return any(domain == pattern or domain.endswith(f".{pattern}") for pattern in patterns)


def _matching_keyword(text: str, keywords: tuple[str, ...]) -> str | None:
    for keyword in keywords:
        if keyword.lower() in text:
            return keyword
    return None


def load_rules(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):  # ValueError: 잘못된 JSON 또는 UTF-8 아님
        _quarantine_corrupt_rules(path)
        return {}
    if not isinstance(data, dict):
        _quarantine_corrupt_rules(path)
        return {}
    return _move_domain_exclusions(_normalize_rules(data))


def _move_domain_exclusions(rules: dict[str, list[str]]) -> dict[str, list[str]]:
    """이전 버전이 "도메인 + 기록 제외"를 앱 이름 목록에 넣은 것을 사이트 목록으로 옮김.

    - 그대로 두면 앱 이름과만 비교돼 그 사이트가 계속 기록됨
    """
    apps = rules.get("excluded_apps", [])
    moved = [item for item in apps if _looks_like_domain(item)]
    if moved:
        rules["excluded_apps"] = [item for item in apps if item not in moved]
        domains = rules.setdefault("excluded_domains", [])
        domains.extend(item for item in moved if item not in domains)
    return rules


def _looks_like_domain(value: str) -> bool:
    lower = value.strip().lower()
    return "." in lower and " " not in lower and not lower.endswith(".exe")


def _normalize_rules(data: dict[str, object]) -> dict[str, list[str]]:
    normalized: dict[str, list[str]] = {}
    for key, value in data.items():
        if isinstance(value, list):
            normalized[str(key)] = [str(item) for item in value if str(item).strip()]
    return normalized


def _quarantine_corrupt_rules(path: Path) -> None:
    # 손상된 rules.json 은 .corrupt 로 이동: 빈 규칙으로 시작하고 원본은 보존
    try:
        backup = path.with_suffix(path.suffix + ".corrupt")
        if path.exists():
            path.replace(backup)
            notices.add(f"분류 규칙 파일이 손상되어 빈 규칙으로 시작했어요. 원본은 '{backup}' 파일로 보관했습니다.")
    except OSError:
        pass


def save_rules(path: Path, rules: dict[str, list[str]]) -> None:
    normalized = {key: sorted(set(values), key=str.lower) for key, values in rules.items()}
    atomic_write_text(path, json.dumps(normalized, indent=2, ensure_ascii=False) + "\n")


def add_rule_value(path: Path, rule_key: str, value: str) -> RuleClassifier:
    rules = load_rules(path)
    cleaned = value.strip()
    _raise_for_rule_conflict(rules, rule_key, cleaned)
    if cleaned and cleaned not in rules.setdefault(rule_key, []):
        rules[rule_key].append(cleaned)
    save_rules(path, rules)
    return RuleClassifier.from_dict(rules)


def _raise_for_rule_conflict(rules: dict[str, list[str]], rule_key: str, value: str) -> None:
    if not value:
        return
    normalized = value.lower()
    for existing_key in _conflicting_rule_keys(rule_key):
        for existing_value in rules.get(existing_key, []):
            if existing_value.lower() == normalized:
                raise RuleConflictError(rule_key, existing_key, existing_value)


def _conflicting_rule_keys(rule_key: str) -> tuple[str, ...]:
    groups = (
        ("productive_domains", "unproductive_domains", "excluded_domains"),
        ("productive_title_keywords", "unproductive_title_keywords", "neutral_title_keywords"),
        ("productive_apps", "unproductive_apps", "excluded_apps"),
    )
    for group in groups:
        if rule_key in group:
            return tuple(key for key in group if key != rule_key)
    return ()


def apply_preset_rules(path: Path, preset: Mapping[str, Sequence[str]]) -> tuple[RuleClassifier, int, int]:
    """프리셋 규칙 추가. (분류기, 추가한 수, 유지한 항목) 반환.

    - 사용자 규칙 우선: 충돌 목록(반대 분류, 제외 앱 등)에 있는 값은 그대로 둠
    """
    rules = load_rules(path)
    added = kept = 0
    for key, values in preset.items():
        for value in values:
            bucket = rules.setdefault(key, [])
            if value.lower() in {item.lower() for item in bucket}:
                continue
            try:
                _raise_for_rule_conflict(rules, key, value)
            except RuleConflictError:
                kept += 1
                continue
            bucket.append(value)
            added += 1
    save_rules(path, rules)
    return RuleClassifier.from_dict(rules), added, kept


def neutralize_rule_value(path: Path, value: str) -> RuleClassifier:
    rules = load_rules(path)
    cleaned = value.strip()
    for key, values in rules.items():
        rules[key] = [item for item in values if item.lower() != cleaned.lower()]
    save_rules(path, rules)
    return RuleClassifier.from_dict(rules)


def update_rule_value(
    path: Path,
    old_rule_key: str,
    old_value: str,
    new_rule_key: str,
    new_value: str,
) -> RuleClassifier:
    # 기존 값을 지운 뒤 충돌 검사: 분류만 바꿀 때 자기 자신과 충돌하지 않게 함
    rules = load_rules(path)
    cleaned_old = old_value.strip()
    cleaned_new = new_value.strip()
    rules[old_rule_key] = [
        item for item in rules.get(old_rule_key, []) if item.lower() != cleaned_old.lower()
    ]
    _raise_for_rule_conflict(rules, new_rule_key, cleaned_new)
    if cleaned_new and cleaned_new not in rules.setdefault(new_rule_key, []):
        rules[new_rule_key].append(cleaned_new)
    save_rules(path, rules)
    return RuleClassifier.from_dict(rules)


def remove_rule_value(path: Path, rule_key: str, value: str) -> RuleClassifier:
    rules = load_rules(path)
    cleaned = value.strip()
    rules[rule_key] = [item for item in rules.get(rule_key, []) if item.lower() != cleaned.lower()]
    save_rules(path, rules)
    return RuleClassifier.from_dict(rules)


# -- 웹 API 규칙 헬퍼 ----------------------------------------------------------

def rule_key_for_selection(rule_type: str, category: str) -> str:
    if category == "중립":
        return "neutral_title_keywords"
    if category == "기록 제외":
        return "excluded_domains" if rule_type == "도메인" else "excluded_apps"
    prefix = "productive" if category == "생산적" else "unproductive"
    if rule_type == "도메인":
        return f"{prefix}_domains"
    if rule_type == "창 제목 키워드":
        return f"{prefix}_title_keywords"
    return f"{prefix}_apps"


# 브라우저 주소를 읽지 못하면 브라우저 이름만 알 수 있음
# → 그에 대한 규칙은 모든 웹 사용을 한꺼번에 분류하게 됨
BROWSER_APPS = frozenset(
    f"{name}.exe" for name in ("chrome", "msedge", "firefox", "whale", "brave", "opera", "vivaldi", "iexplore")
)


def activity_rule_target(app_name: str, url: str | None) -> str:
    """활동 하나로 규칙을 만들 때 쓸 사이트·앱 이름. 안전한 것이 없으면 ""."""
    domain = _domain_from_url(url)
    if domain:
        return domain
    name = (app_name or "").strip()
    return "" if name.lower() in BROWSER_APPS or not name.lower().endswith(".exe") else name


def rule_would_apply(rules: dict[str, list[str]], target: str, category: Category, activity: ActiveTarget) -> bool:
    """``target`` 규칙을 추가하면 ``activity`` 가 실제로 ``category`` 가 되는지 확인.

    - False: 기존 규칙과 충돌하거나, 먼저 검사되는 규칙이 결과를 정하는 경우
    """
    key, value = rule_from_candidate(target, category)
    try:
        _raise_for_rule_conflict(rules, key, value)
    except RuleConflictError:
        return False
    trial = {**rules, key: [*rules.get(key, []), value]}
    return RuleClassifier.from_dict(trial).classify(activity).category == category


def rule_from_candidate(label: str, category: Category) -> tuple[str, str]:
    prefix = "productive" if category == Category.PRODUCTIVE else "unproductive"
    if label.lower().endswith(".exe"):
        return f"{prefix}_apps", label
    if "." in label and " " not in label:
        domain = _domain_from_url(label) or label
        return f"{prefix}_domains", domain
    return f"{prefix}_title_keywords", label


