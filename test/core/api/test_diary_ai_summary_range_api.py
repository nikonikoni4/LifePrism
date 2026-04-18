"""
Test for diary AI summary range API.

Tests three existing-summary modes:
- regenerate_all: Update all dates in range (even if unchanged)
- regenerate_changed: Only update if diary content changed (hash mismatch)
- skip_existing: Only create summaries for dates without existing summaries
"""
import pytest
from fastapi.testclient import TestClient

from lifeprism.server.main import app


@pytest.mark.core
def test_range_summary_mode_regenerate_all_updates_existing_summaries(monkeypatch):
    """regenerate_all should call generate_ai_summary for ALL dates in range"""
    from lifeprism.server.providers.diary_provider import diary_provider

    called_dates = []

    async def fake_generate_ai_summary(date: str):
        called_dates.append(date)
        return {"content": f"summary for {date}"}

    def fake_get_diaries_by_date_range(start_date: str, end_date: str):
        return [
            {
                "date": "2026-04-18",
                "mood": "calm",
                "importance": "normal",
                "custom_tags": "[]",
                "ai_summary": "existing summary",
                "diary_source_hash": "abc123",
                "created_at": "",
                "updated_at": "",
            },
            {
                "date": "2026-04-19",
                "mood": "happy",
                "importance": "important",
                "custom_tags": '["work"]',
                "ai_summary": "existing summary 2",
                "diary_source_hash": "def456",
                "created_at": "",
                "updated_at": "",
            },
        ]

    # Patch using string path like existing tests do
    monkeypatch.setattr("lifeprism.server.services.diary_service.generate_diary_ai_summary", fake_generate_ai_summary)
    monkeypatch.setattr(diary_provider, "get_diaries_by_date_range", fake_get_diaries_by_date_range)
    monkeypatch.setattr("lifeprism.server.services.diary_service._read_diary_content", lambda date: "some content")

    client = TestClient(app)
    response = client.post(
        "/api/v2/diary/ai_summary/range",
        json={
            "start_date": "2026-04-18",
            "end_date": "2026-04-19",
            "existing_summary_mode": "regenerate_all",
        },
    )
    assert response.status_code == 200
    # All dates should be called since regenerate_all updates all
    assert called_dates == ["2026-04-18", "2026-04-19"]


@pytest.mark.core
def test_range_summary_mode_regenerate_changed_only_updates_mismatched_hashes(monkeypatch):
    """regenerate_changed should only update dates where hash doesn't match"""
    from lifeprism.server.providers.diary_provider import diary_provider
    import hashlib

    called_dates = []

    async def fake_generate_ai_summary(date: str):
        called_dates.append(date)
        return {"content": f"summary for {date}"}

    # Compute actual hashes for the test content
    content_18 = "some content for 04-18"
    hash_18 = hashlib.md5(content_18.strip().replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")).hexdigest()

    def fake_get_diaries_by_date_range(start_date: str, end_date: str):
        return [
            {
                "date": "2026-04-18",
                "mood": "calm",
                "importance": "normal",
                "custom_tags": "[]",
                "ai_summary": "existing summary",
                "diary_source_hash": hash_18,  # hash matches computed hash -> skip
                "created_at": "",
                "updated_at": "",
            },
            {
                "date": "2026-04-19",
                "mood": "happy",
                "importance": "important",
                "custom_tags": '["work"]',
                "ai_summary": "existing summary 2",
                "diary_source_hash": None,  # hash missing -> content changed, regenerate
                "created_at": "",
                "updated_at": "",
            },
        ]

    # 2026-04-18: existing_hash matches computed hash -> skip
    # 2026-04-19: existing_hash is None -> regenerate
    monkeypatch.setattr("lifeprism.server.services.diary_service.generate_diary_ai_summary", fake_generate_ai_summary)
    monkeypatch.setattr(diary_provider, "get_diaries_by_date_range", fake_get_diaries_by_date_range)

    def fake_read_content(date: str) -> str:
        if date == "2026-04-18":
            return content_18
        return "some different content"  # This will hash to something else
    monkeypatch.setattr("lifeprism.server.services.diary_service._read_diary_content", fake_read_content)

    client = TestClient(app)
    response = client.post(
        "/api/v2/diary/ai_summary/range",
        json={
            "start_date": "2026-04-18",
            "end_date": "2026-04-19",
            "existing_summary_mode": "regenerate_changed",
        },
    )
    assert response.status_code == 200
    # Only 2026-04-19 should be called since 2026-04-18 has matching hash
    assert called_dates == ["2026-04-19"]


@pytest.mark.core
def test_range_summary_mode_skip_existing_only_creates_missing_summaries(monkeypatch):
    """skip_existing should only create summaries for dates without existing summaries"""
    from lifeprism.server.providers.diary_provider import diary_provider

    called_dates = []

    async def fake_generate_ai_summary(date: str):
        called_dates.append(date)
        return {"content": f"summary for {date}"}

    def fake_get_diaries_by_date_range(start_date: str, end_date: str):
        return [
            {
                "date": "2026-04-18",
                "mood": "calm",
                "importance": "normal",
                "custom_tags": "[]",
                "ai_summary": "existing summary",  # has summary - skip
                "diary_source_hash": "abc123",
                "created_at": "",
                "updated_at": "",
            },
            {
                "date": "2026-04-19",
                "mood": "happy",
                "importance": "important",
                "custom_tags": '["work"]',
                "ai_summary": "existing summary 2",  # has summary - skip
                "diary_source_hash": "def456",
                "created_at": "",
                "updated_at": "",
            },
            {
                "date": "2026-04-20",
                "mood": None,
                "importance": None,
                "custom_tags": "[]",
                "ai_summary": None,  # no summary - create
                "diary_source_hash": None,
                "created_at": "",
                "updated_at": "",
            },
        ]

    monkeypatch.setattr("lifeprism.server.services.diary_service.generate_diary_ai_summary", fake_generate_ai_summary)
    monkeypatch.setattr(diary_provider, "get_diaries_by_date_range", fake_get_diaries_by_date_range)
    monkeypatch.setattr("lifeprism.server.services.diary_service._read_diary_content", lambda date: "some content")

    client = TestClient(app)
    response = client.post(
        "/api/v2/diary/ai_summary/range",
        json={
            "start_date": "2026-04-18",
            "end_date": "2026-04-20",
            "existing_summary_mode": "skip_existing",
        },
    )
    assert response.status_code == 200
    # Only 2026-04-20 should be called since only it has no existing summary
    assert called_dates == ["2026-04-20"]