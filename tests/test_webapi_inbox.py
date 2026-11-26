from time_manager.local_model import MANUAL_REASON
from time_manager.models import ActiveTarget, Category, ClassifiedActivity
from time_manager.webapi import WebApi


def _record(api: WebApi, app: str) -> int:
    api.store.record(
        ClassifiedActivity(ActiveTarget(app_name=app, window_title="Editor"), Category.NEUTRAL, "no matching rule"),
        600,
    )
    return api.get_inbox()["records"][0]["id"]


def test_reclassify_updates_record_and_marks_it_manual(api: WebApi) -> None:
    event_id = _record(api, "editor.exe")

    result = api.reclassify_event(event_id, "productive")

    assert result["records"][0]["category"] == "productive"
    [signature] = api.store.activity_signatures()
    assert (signature.category, signature.reason) == (Category.PRODUCTIVE, MANUAL_REASON)


def test_inbox_echoes_the_current_view(api: WebApi) -> None:
    assert (api.get_inbox()["query"], api.get_inbox()["category"]) == ("", None)

    result = api.get_inbox("edit", "neutral")

    assert (result["query"], result["category"], result["searchActive"]) == ("edit", "neutral", True)
