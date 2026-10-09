"""手动索引状态、真实候选库发布与失败保护。"""

import asyncio
import threading
from types import SimpleNamespace

import httpx
import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from lifeprism.rag.service import RagService
from lifeprism.utils.exceptions import LWBaseError

pytestmark = pytest.mark.core


class MemorySettings:
    run_mode = "full"

    def __init__(self):
        self.values = {}
        self.keys = {}

    def get(self, name, default=None):
        return self.values.get(name, default)

    def set(self, name, value):
        self.values[name] = value

    def get_storage_key(self, name):
        return self.keys.get(name)

    def set_storage_key(self, name, value):
        self.keys[name] = value


@pytest.mark.asyncio
async def test_manual_index_status_duplicate_failure_and_no_upload(monkeypatch, tmp_path):
    from lifeprism.server.api import rag_settings_api as api

    config = MemorySettings()
    config.run_mode = "full"
    config.set("rag.enabled", True)
    config.set("rag.index_directories", ["user"])
    config.set_storage_key("rag_embedding_api_key", "synthetic")
    gate = threading.Event()
    fail = False

    class Embedding:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def embed(self, parts, dimensions=None):
            await asyncio.to_thread(gate.wait, 5)
            if fail:
                raise RuntimeError("synthetic provider failure with private details")
            vec = np.zeros(dimensions or 2048, dtype=np.float32)
            vec[0] = 1
            return SimpleNamespace(dense=vec)

    (tmp_path / "user").mkdir()
    (tmp_path / "user" / "profile.md").write_text("个人资料测试", encoding="utf-8")
    service = RagService(tmp_path, config, embedding_factory=Embedding)
    monkeypatch.setattr(api, "settings", config)
    monkeypatch.setattr(api, "get_rag_service", lambda: service)
    app = FastAPI()
    app.include_router(api.router)

    @app.exception_handler(LWBaseError)
    async def domain_error(request, exc):
        return JSONResponse(status_code=409, content={"message": exc.message})

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        from lifeprism.server.services.global_task_state import TaskState, global_task_state

        assert global_task_state.try_acquire(TaskState.CLOUD_SYNC, 0)
        try:
            assert (await client.post("/settings/rag/index")).status_code == 409
        finally:
            global_task_state.release()
        status = (await client.get("/settings/rag/index")).json()
        assert status == {
            "last_index_time": None,
            "building": False,
            "error": None,
            "can_build": True,
        }
        try:
            first = await client.post("/settings/rag/index")
            assert first.status_code == 202
            assert first.json()["building"]
            assert global_task_state.current_state == TaskState.LOCAL_TASK
            assert (await client.post("/settings/rag/index")).status_code == 409
        finally:
            gate.set()

        async def finished():
            async with asyncio.timeout(10):
                while True:
                    result = (await client.get("/settings/rag/index")).json()
                    if not result["building"]:
                        return result
                    await asyncio.sleep(0.02)

        successful = await finished()
        assert successful["last_index_time"]
        assert successful["error"] is None
        previous = service.current()
        assert not (service.root / "daily.json").exists()  # 手动构建不触发每日上传状态。
        fail = True
        assert (await client.post("/settings/rag/index")).status_code == 202
        failed = await finished()
        assert failed["last_index_time"] == successful["last_index_time"]
        assert failed["error"]
        assert "private details" not in failed["error"]
        assert service.current() == previous
        fail = False
        await service.build(["user"])
        assert service.index_status().error is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode,enabled,key",
    [
        ("agent_only", True, "key"),
        ("web_demo", True, "key"),
        ("full", False, "key"),
        ("full", True, ""),
    ],
)
async def test_manual_index_unavailable_without_local_enabled_config(
    monkeypatch, tmp_path, mode, enabled, key
):
    from lifeprism.server.api import rag_settings_api as api

    config = MemorySettings()
    config.run_mode = mode
    config.set("rag.enabled", enabled)
    config.set_storage_key("rag_embedding_api_key", key)
    service = RagService(tmp_path, config)
    monkeypatch.setattr(api, "settings", config)
    monkeypatch.setattr(api, "get_rag_service", lambda: service)
    app = FastAPI()
    app.include_router(api.router)

    @app.exception_handler(LWBaseError)
    async def domain_error(request, exc):
        return JSONResponse(status_code=422, content={"message": exc.message})

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert not (await client.get("/settings/rag/index")).json()["can_build"]
        assert (await client.post("/settings/rag/index")).status_code in {403, 422}
        assert service.current() is None
