"""Built-in activity classifier: a small multinomial Naive Bayes, pure Python.

It is trained on demand from data that is already on this PC (classified activity,
the user's rules and the selected profile preset). Nothing is saved or sent, so it
may safely learn from window titles.

To check how well it works on real data:
    python -m time_manager.local_model path/to/activity.sqlite3
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from time_manager.models import Category
from time_manager.rules import _domain_from_url

# Reasons stored by the tracker/UI that carry no usable label.
_UNLABELED_REASON = "no matching rule"
_NEUTRAL_REASON_PREFIX = "neutral title keyword"
MANUAL_REASON = "manual correction"

MIN_CONFIDENCE = 0.8
MIN_EXAMPLES_PER_CLASS = 3
_MANUAL_WEIGHT = 3.0
_RULE_WEIGHT = 3.0
_PRESET_WEIGHT = 1.0

_WORD = re.compile(r"[a-z0-9]+|[가-힣]+")
# Words that show up in titles regardless of what the user is doing.
_STOPWORDS = frozenset(
    "google chrome microsoft edge mozilla firefox whale brave opera the and for with from "
    "www com net org new tab exe 새 탭".split()
)
_DOMAIN_SUFFIXES = frozenset("www com net org io co kr jp dev app ai so tv me".split())


@dataclass(frozen=True)
class Signature:
    """Time spent on one distinct (app, url, title, category, reason) combination."""

    app_name: str
    url: str
    title: str
    category: Category
    reason: str
    seconds: int

    @property
    def target(self) -> str:
        """Same grouping as ``ActivityStore.app_domain_totals``: domain, else app name."""
        return _domain_from_url(self.url) or self.app_name.strip()


@dataclass(frozen=True)
class Prediction:
    category: Category
    confidence: float
    reason: str


def identity_tokens(target: str) -> list[str]:
    """Tokens describing an app executable or a domain."""
    name = target.strip().lower()
    if not name:
        return []
    if name.endswith(".exe") or "." not in name:
        return [f"app:{name.removesuffix('.exe')}"]
    parts = [part for part in name.split(".") if part not in _DOMAIN_SUFFIXES and len(part) > 1]
    return [f"dom:{name}", *(f"part:{part}" for part in parts)]


def title_tokens(title: str) -> set[str]:
    return {
        f"word:{word}"
        for word in _WORD.findall(title.lower())
        if len(word) > 1 and not word.isdigit() and word not in _STOPWORDS
    }


class LocalClassifier:
    def __init__(self) -> None:
        self._class_weight: Counter[Category] = Counter()
        self._class_examples: Counter[Category] = Counter()
        self._token_weight: dict[Category, Counter[str]] = defaultdict(Counter)
        self._vocabulary: set[str] = set()
        self._known_targets: dict[str, Category] = {}
        self.history_examples = 0

    # -- training ----------------------------------------------------------------

    def add(self, tokens: Iterable[str], category: Category, weight: float) -> None:
        unique = set(tokens)
        if not unique:
            return
        self._class_weight[category] += weight
        self._class_examples[category] += 1
        for token in unique:
            self._token_weight[category][token] += weight
        self._vocabulary.update(unique)

    @classmethod
    def train(
        cls,
        history: Iterable[Signature],
        rules: Mapping[str, Sequence[str]] | None = None,
        preset: Mapping[str, Sequence[str]] | None = None,
    ) -> "LocalClassifier":
        model = cls()
        for sig in history:
            if not _is_labeled(sig):
                continue
            weight = 1.0 + math.log1p(sig.seconds / 60)
            if sig.reason == MANUAL_REASON:
                weight *= _MANUAL_WEIGHT
            model.add(_signature_tokens(sig), sig.category, weight)
            model.history_examples += 1
        # Presets first so that the user's own rules override them.
        model._add_rules(preset or {}, _PRESET_WEIGHT)
        model._add_rules(rules or {}, _RULE_WEIGHT)
        return model

    def _add_rules(self, rules: Mapping[str, Sequence[str]], weight: float) -> None:
        for key, values in rules.items():
            prefix, _, kind = key.partition("_")
            if prefix not in (Category.PRODUCTIVE.value, Category.UNPRODUCTIVE.value):
                continue
            category = Category(prefix)
            for value in values:
                if kind == "title_keywords":
                    self.add(title_tokens(value), category, weight)
                else:
                    self.add(identity_tokens(value), category, weight)
                    self._known_targets[value.strip().lower()] = category

    # -- prediction ----------------------------------------------------------------

    def predict(self, target: str, titles: Mapping[str, int] | None = None) -> Prediction | None:
        """Classify an app/domain. Returns ``None`` when there is not enough evidence.

        ``titles`` maps window titles seen for this target to seconds spent.
        """
        known = self._known_targets.get(target.strip().lower())
        if known is not None:
            return Prediction(known, 1.0, "직업 프리셋·내 규칙에 있는 항목이에요")

        classes = [c for c in Category if self._class_examples[c] >= MIN_EXAMPLES_PER_CLASS]
        if len(classes) < 2:
            return None

        # Each token counts at most once; title words by the share of time they appear in.
        features: dict[str, float] = {token: 1.0 for token in identity_tokens(target)}
        total_seconds = sum((titles or {}).values())
        if total_seconds > 0:
            for title, seconds in (titles or {}).items():
                for token in title_tokens(title):
                    features[token] = features.get(token, 0.0) + seconds / total_seconds
        features = {t: min(v, 1.0) for t, v in features.items() if t in self._vocabulary}
        if not features:
            return None

        vocabulary_size = len(self._vocabulary)
        likelihood: dict[Category, dict[str, float]] = {}
        for category in classes:
            denominator = sum(self._token_weight[category].values()) + vocabulary_size
            likelihood[category] = {
                token: math.log((self._token_weight[category][token] + 1) / denominator)
                for token in features
            }
        total_weight = sum(self._class_weight[c] for c in classes)
        scores = {
            c: math.log(self._class_weight[c] / total_weight)
            + sum(features[t] * likelihood[c][t] for t in features)
            for c in classes
        }
        best = max(scores, key=scores.__getitem__)
        confidence = 1.0 / sum(math.exp(min(700.0, score - scores[best])) for score in scores.values())
        if confidence < MIN_CONFIDENCE:
            return None

        def support(token: str) -> float:
            return features[token] * (
                likelihood[best][token] - max(likelihood[c][token] for c in classes if c != best)
            )

        # Require real evidence for the winner, not just a lopsided class prior.
        evidence = sorted(
            (t for t in features if self._token_weight[best][t] > 0 and support(t) > 0),
            key=support,
            reverse=True,
        )
        if not evidence:
            return None
        words = ", ".join(f"'{token.split(':', 1)[1]}'" for token in evidence[:2])
        return Prediction(best, confidence, f"{words} 단서가 이전 분류 기록과 비슷해요")


def _is_labeled(sig: Signature) -> bool:
    if sig.reason == MANUAL_REASON:
        return True
    return (
        sig.category != Category.NEUTRAL
        and sig.reason != _UNLABELED_REASON
        and not sig.reason.startswith(_NEUTRAL_REASON_PREFIX)
    )


def _signature_tokens(sig: Signature) -> set[str]:
    # For websites the browser executable says nothing, so only the domain is used.
    return {*identity_tokens(sig.target), *title_tokens(sig.title)}


# -- evaluation --------------------------------------------------------------------

@dataclass(frozen=True)
class Evaluation:
    targets: int
    predicted: int
    correct: int


def evaluate(history: Sequence[Signature]) -> Evaluation:
    """Leave-one-target-out: can the model classify an app/site it has never seen?

    Rules and presets are left out because they would leak the answer. Labels that
    came from rules still reflect those rules, so read the result as an estimate.
    """
    groups: dict[str, list[Signature]] = defaultdict(list)
    for sig in history:
        if _is_labeled(sig) and sig.target:
            groups[sig.target.lower()].append(sig)

    predicted = correct = 0
    for name, held_out in groups.items():
        model = LocalClassifier.train(
            sig for other, sigs in groups.items() if other != name for sig in sigs
        )
        titles: Counter[str] = Counter()
        seconds_by_category: Counter[Category] = Counter()
        for sig in held_out:
            titles[sig.title] += sig.seconds
            seconds_by_category[sig.category] += sig.seconds
        result = model.predict(held_out[0].target, titles)
        if result is not None:
            predicted += 1
            correct += result.category == seconds_by_category.most_common(1)[0][0]
    return Evaluation(targets=len(groups), predicted=predicted, correct=correct)


def _main(argv: list[str]) -> int:
    from pathlib import Path

    from time_manager.storage import ActivityStore

    if len(argv) != 1 or not Path(argv[0]).is_file():
        print("usage: python -m time_manager.local_model path/to/activity.sqlite3")
        return 2
    store = ActivityStore(Path(argv[0]))
    result = evaluate(store.activity_signatures())
    store.close()
    print(f"labeled apps/domains: {result.targets}")
    if not result.targets:
        print("not enough labeled data to evaluate")
        return 0
    print(f"coverage: {result.predicted}/{result.targets} ({result.predicted / result.targets:.0%})")
    if result.predicted:
        print(f"accuracy when it answers: {result.correct}/{result.predicted} ({result.correct / result.predicted:.0%})")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_main(sys.argv[1:]))
