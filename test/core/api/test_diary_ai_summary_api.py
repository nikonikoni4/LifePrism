import pytest
from fastapi.testclient import TestClient

from lifeprism.server.main import app


@pytest.mark.core
def test_generate_diary_ai_summary_rejects_empty_content(monkeypatch):
    from lifeprism.server.providers.diary_provider import diary_provider

    stored = {
        "date": "2026-04-17",
        "mood": None,
        "importance": None,
        "custom_tags": "[]",
        "ai_summary": None,
        "created_at": "",
        "updated_at": "",
    }

    monkeypatch.setattr(diary_provider, "get_diary_by_date", lambda date: stored)
    monkeypatch.setattr("lifeprism.server.services.diary_service._read_diary_content", lambda date: "   \n")

    client = TestClient(app)
    response = client.post("/api/v2/diary/2026-04-17/ai_summary")
    assert response.status_code == 400
    assert response.json()["detail"] == "日记为空，无法总结"


@pytest.mark.core
def test_generate_diary_ai_summary_overwrites_existing_summary(monkeypatch):
    from lifeprism.server.providers.diary_provider import diary_provider

    stored = {
        "date": "2026-04-17",
        "mood": "calm",
        "importance": "normal",
        "custom_tags": '["阅读"]',
        "ai_summary": "旧总结",
        "created_at": "",
        "updated_at": "",
    }

    async def fake_ai_diary_summary(date, mood, importance, custom_tags):
        assert date == "2026-04-17"
        assert mood == "平静"
        assert importance == "一般"
        assert custom_tags == ["阅读"]
        return {"content": "新总结"}

    updated_payloads = []

    monkeypatch.setattr(diary_provider, "get_diary_by_date", lambda date: stored)
    monkeypatch.setattr("lifeprism.server.services.diary_service._read_diary_content", lambda date: "今天写了很多内容")
    monkeypatch.setattr("lifeprism.server.services.diary_service.ai_diary_summary", fake_ai_diary_summary)
    monkeypatch.setattr(diary_provider, "update_diary", lambda date, data: updated_payloads.append(data) or True)

    client = TestClient(app)
    response = client.post("/api/v2/diary/2026-04-17/ai_summary")
    assert response.status_code == 200
    assert response.json() == {"content": "新总结"}
    assert updated_payloads == [{"ai_summary": "新总结"}]


@pytest.mark.core
def test_generate_diary_ai_summary_does_not_overwrite_on_llm_failure(monkeypatch):
    from lifeprism.server.providers.diary_provider import diary_provider

    stored = {
        "date": "2026-04-17",
        "mood": "calm",
        "importance": "normal",
        "custom_tags": "[]",
        "ai_summary": "旧总结",
        "created_at": "",
        "updated_at": "",
    }
    update_called = False

    async def fake_ai_diary_summary(*args, **kwargs):
        raise RuntimeError("llm down")

    def fake_update_diary(*args, **kwargs):
        nonlocal update_called
        update_called = True
        return True

    monkeypatch.setattr(diary_provider, "get_diary_by_date", lambda date: stored)
    monkeypatch.setattr("lifeprism.server.services.diary_service._read_diary_content", lambda date: "今天写了很多内容")
    monkeypatch.setattr("lifeprism.server.services.diary_service.ai_diary_summary", fake_ai_diary_summary)
    monkeypatch.setattr(diary_provider, "update_diary", fake_update_diary)

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/api/v2/diary/2026-04-17/ai_summary")
    assert response.status_code == 500
    assert update_called is False
