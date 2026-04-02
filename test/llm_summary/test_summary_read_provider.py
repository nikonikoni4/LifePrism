import shutil
import importlib
from pathlib import Path
from uuid import uuid4

from lifeprism.llm.providers.summary_read_provider import SummaryReadProvider

summary_read_provider_module = importlib.import_module("lifeprism.llm.providers.summary_read_provider")


def test_get_activity_logs_by_range_delegates_to_llm_provider(monkeypatch):
    provider = SummaryReadProvider()
    calls = {}

    def fake_query(start_time, end_time, limit=None, order_by="start_time ASC", category_id=None, sub_category_id=None):
        calls["args"] = (start_time, end_time, limit, order_by)
        return [{"start_time": start_time, "end_time": end_time, "duration": 600, "category_name": "工作"}]

    monkeypatch.setattr(summary_read_provider_module.llm_lw_data_provider, "query_behavior_logs", fake_query)

    rows = provider.get_activity_logs_by_range("2026-04-02 04:00:00", "2026-04-03 04:00:00")
    assert calls["args"] == ("2026-04-02 04:00:00", "2026-04-03 04:00:00", None, "start_time ASC")
    assert rows[0]["duration"] == 600


def test_get_diaries_by_range_reads_excerpt_from_settings_path(monkeypatch):
    provider = SummaryReadProvider()

    test_root = Path("test/.tmp") / f"summary-read-{uuid4().hex}"
    diary_path = test_root / "diary" / "2026" / "04" / "2026-04-02.md"
    diary_path.parent.mkdir(parents=True, exist_ok=True)
    diary_path.write_text("line1\nline2", encoding="utf-8")

    monkeypatch.setattr(
        summary_read_provider_module.diary_provider,
        "get_diaries_by_date_range",
        lambda start_date, end_date: [{"date": "2026-04-02", "ai_summary": "summary-text"}],
    )
    monkeypatch.setattr(summary_read_provider_module.settings, "_lifeprism_data_path", test_root)

    try:
        rows = provider.get_diaries_by_range("2026-04-02", "2026-04-02")
        assert rows[0]["content_excerpt"] == "line1 line2"
        assert rows[0]["ai_summary"] == "summary-text"
    finally:
        shutil.rmtree(test_root, ignore_errors=True)


def test_get_todos_by_range_collects_all_days(monkeypatch):
    provider = SummaryReadProvider()

    def fake_get_todos(date, include_cross_day=False):
        return [{"id": f"todo-{date}", "date": date, "include_cross_day": include_cross_day}]

    monkeypatch.setattr(summary_read_provider_module.todo_provider, "get_todos_by_date", fake_get_todos)

    rows = provider.get_todos_by_range("2026-04-02", "2026-04-03")
    assert len(rows) == 2
    assert rows[0]["id"] == "todo-2026-04-02"
    assert rows[1]["id"] == "todo-2026-04-03"
    assert rows[0]["include_cross_day"] is False
    assert rows[1]["include_cross_day"] is False
