from time_manager.local_coaching import build_local_coaching
from time_manager.local_model import LocalClassifier, Signature, evaluate
from time_manager.models import Category

P, U, N = Category.PRODUCTIVE, Category.UNPRODUCTIVE, Category.NEUTRAL


def _sig(target: str, title: str, category: Category, reason: str = "rule", seconds: int = 600) -> Signature:
    app, url = (target, "") if target.endswith(".exe") else ("chrome.exe", f"https://{target}/page")
    return Signature(app, url, title, category, reason, seconds)


def _history() -> list[Signature]:
    work = [("a.com", "python tutorial"), ("b.com", "python reference"), ("c.exe", "python project"),
            ("d.com", "algorithm lecture python")]
    play = [("e.com", "funny highlights video"), ("f.com", "game highlights"), ("g.exe", "game lobby"),
            ("h.com", "funny game clips")]
    return [_sig(t, title, P) for t, title in work] + [_sig(t, title, U) for t, title in play]


class TestLocalClassifier:
    def test_learns_from_title_words_for_unseen_targets(self) -> None:
        model = LocalClassifier.train(_history())

        work = model.predict("new-site.com", {"advanced python tutorial": 300})
        play = model.predict("other.exe", {"funny game highlights": 300})

        assert work is not None and work.category == P
        assert play is not None and play.category == U

    def test_abstains_without_evidence(self) -> None:
        model = LocalClassifier.train(_history())

        assert model.predict("unknown.exe", {"qwerty zxcv": 100}) is None

    def test_abstains_without_enough_training_data(self) -> None:
        model = LocalClassifier.train(_history()[:2])

        assert model.predict("new.com", {"python tutorial": 100}) is None

    def test_ignores_unlabeled_history(self) -> None:
        history = [_sig(f"x{i}.com", "python", N, "no matching rule") for i in range(10)]

        assert LocalClassifier.train(history).history_examples == 0

    def test_browser_name_is_not_evidence(self) -> None:
        model = LocalClassifier.train(_history())

        assert model.predict("unknown.exe", {"Google Chrome": 100}) is None

    def test_user_rules_override_preset(self) -> None:
        model = LocalClassifier.train(
            [], rules={"productive_domains": ["youtube.com"]}, preset={"unproductive_domains": ["youtube.com"]}
        )

        result = model.predict("youtube.com")

        assert result is not None and result.category == P

    def test_evaluate_holds_out_whole_targets(self) -> None:
        result = evaluate(_history())

        assert result.targets == 8
        assert 0 < result.predicted <= 8
        assert result.correct <= result.predicted


def _payload(**overrides: object) -> dict:
    payload = {
        "scope": "day",
        "daily": [{"date": "2026-01-05", "weekday": "월", "productiveMin": 60, "unproductiveMin": 150, "neutralMin": 10}],
        "goals": {"dailyProductiveMin": 120, "weeklyProductiveMin": 600, "unproductiveLimitMin": 90},
        "includesToday": False,
        "comparison": {"comparedDays": 1, "currentProductiveMin": 60, "previousProductiveMin": 100},
        "bestProductiveHours": [10],
        "topTargets": {"productive": [], "unproductive": [{"name": "youtube.com", "minutes": 150}], "neutral": []},
        "flow": {"focusBlocks25minPlus": 0},
    }
    payload.update(overrides)
    return payload


class TestLocalCoaching:
    def test_uses_the_numbers(self) -> None:
        result = build_local_coaching(_payload())

        assert "50%" in result["headline"]
        assert "전날보다 생산 시간이 40분 줄었어요." in result["insights"]
        assert any("1시간" in line and "youtube.com" in line for line in result["actions"])
        assert len(result["insights"]) <= 3 and len(result["actions"]) <= 3

    def test_no_comparison_without_previous_data(self) -> None:
        result = build_local_coaching(_payload(comparison=None))

        assert not any("전날" in line for line in result["insights"])

    def test_marks_today_as_unfinished(self) -> None:
        result = build_local_coaching(_payload(includesToday=True, comparison=None))

        assert result["headline"].startswith("오늘 지금까지")
