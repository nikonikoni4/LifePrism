"""失败诊断必须保留原因、调用链和阶段，并避免输出请求内容或密钥。"""

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

pytestmark = pytest.mark.regression


@pytest.mark.asyncio
async def test_manual_embedding_failure_has_stage_http_reason_and_redacted_stack(tmp_path, caplog):
    from lifeprism.rag.service import RagService

    key = "synthetic-private-api-key"
    config = SimpleNamespace(
        get=lambda name, default=None: True if name == "rag.enabled" else default,
        get_storage_key=lambda name: key,
    )

    class Embedding:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def embed(self, parts, dimensions=None):
            response = httpx.Response(
                401,
                request=httpx.Request("POST", "https://provider/v3"),
                json={
                    "error": {"code": "InvalidApiKey", "message": f"invalid key {key}"},
                    "input": "private-document-text",
                },
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError("embedding request failed") from exc

    (tmp_path / "user").mkdir()
    (tmp_path / "user" / "profile.md").write_text("private-document-text", encoding="utf-8")
    service = RagService(tmp_path, config, embedding_factory=Embedding)
    with caplog.at_level(logging.ERROR):
        task = service.start_manual_build()
        with pytest.raises(RuntimeError):
            await task
        await asyncio.sleep(0)
    assert "stage=embedding" in caplog.text
    assert "doubao-embedding-vision" in caplog.text
    assert "embedding request failed" in caplog.text
    assert "InvalidApiKey" in caplog.text
    assert "401" in caplog.text
    assert "embed" in caplog.text and "line" in caplog.text
    assert key not in caplog.text
    assert "private-document-text" not in caplog.text
    assert all(len(record.getMessage()) < 1900 for record in caplog.records)
    assert service.index_status().error


@pytest.mark.asyncio
async def test_daily_failure_keeps_actual_reason_and_traceback(monkeypatch, tmp_path, caplog):
    from lifeprism.server.services import schedule_service as module

    config = SimpleNamespace(
        run_mode="full",
        lifeprism_data_path=str(tmp_path),
        auto_summary_session=False,
        auto_update_memory=False,
        auto_diary_summary=False,
        get=lambda name, default=None: True if name == "rag.enabled" else default,
        get_storage_key=lambda name: None,
    )
    monkeypatch.setattr(module, "settings", config)
    service = module.ScheduleService()
    service._rag_data_root = tmp_path.resolve()

    async def failing_run(*args):
        raise PermissionError("index.db is locked by another process")

    service._rag_job = SimpleNamespace(run=AsyncMock(side_effect=failing_run))
    monkeypatch.setattr(module.global_task_state, "try_acquire", lambda *args: True)
    monkeypatch.setattr(module.global_task_state, "release", lambda: None)
    with caplog.at_level(logging.ERROR):
        await service.run_rag_daily(after_memory=True)
    assert "index.db is locked by another process" in caplog.text
    assert "failing_run" in caplog.text and "line" in caplog.text
