from time_manager.models import ActiveTarget, Category, ClassifiedActivity
from time_manager.webapi import WebApi


def _unclassified(app: str, title: str, url: str | None = None) -> ClassifiedActivity:
    return ClassifiedActivity(
        target=ActiveTarget(app_name=app, window_title=title, url=url),
        category=Category.NEUTRAL,
        reason="no matching rule",
    )


class TestGetRuleSuggestions:
    def test_surfaces_top_unclassified_targets_by_time(self, api: WebApi) -> None:
        api.store.record(_unclassified("notion.exe", "Notion", None), 600)
        api.store.record(_unclassified("slack.exe", "Slack", None), 60)

        suggestions = api.get_rule_suggestions()

        targets = [s["target"] for s in suggestions]
        assert targets[0] == "Notion"
        assert "10분" == suggestions[0]["timeLabel"]

    def test_ignores_already_classified_activity(self, api: WebApi) -> None:
        productive = ClassifiedActivity(
            target=ActiveTarget(app_name="vscode.exe", window_title="main.py"),
            category=Category.PRODUCTIVE,
            reason="rule:productive_apps",
        )
        api.store.record(productive, 600)

        suggestions = api.get_rule_suggestions()

        assert suggestions == []

    def test_respects_limit(self, api: WebApi) -> None:
        for i in range(5):
            api.store.record(_unclassified(f"app{i}.exe", f"App {i}"), 60)

        suggestions = api.get_rule_suggestions(limit=2)

        assert len(suggestions) == 2


class TestApplyRuleSuggestion:
    def test_marks_app_as_productive(self, api: WebApi) -> None:
        result = api.apply_rule_suggestion("notion.exe", "productive")

        assert "error" not in result
        keys = {(item["key"], item["value"]) for item in result["items"]}
        assert ("productive_apps", "notion.exe") in keys

    def test_marks_domain_as_unproductive(self, api: WebApi) -> None:
        result = api.apply_rule_suggestion("reddit.com", "unproductive")

        assert "error" not in result
        keys = {(item["key"], item["value"]) for item in result["items"]}
        assert ("unproductive_domains", "reddit.com") in keys

    def test_rejects_neutral_category(self, api: WebApi) -> None:
        result = api.apply_rule_suggestion("notion.exe", "neutral")

        assert result.get("error")

    def test_rejects_invalid_category(self, api: WebApi) -> None:
        result = api.apply_rule_suggestion("notion.exe", "not-a-category")

        assert result.get("error")

    def test_conflicting_rule_returns_error(self, api: WebApi) -> None:
        api.apply_rule_suggestion("notion.exe", "productive")
        result = api.apply_rule_suggestion("notion.exe", "unproductive")

        assert result.get("error")
