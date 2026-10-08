"""回归：RAG 接收路由必须挂在实际 agent-only 入口，而非测试自建应用。"""

import asyncio
import socket
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import numpy as np
import pytest
import pytest_asyncio
import uvicorn
from fastapi.responses import JSONResponse

pytestmark = pytest.mark.regression


@pytest_asyncio.fixture
async def cloud_app(monkeypatch):
    from lifeprism.config.settings_manager import settings

    # 入口模块导入会设置部署模式，隔离共享 settings 避免污染其他测试。
    monkeypatch.setattr(settings, "_runtime_config", {"run_mode": "agent_only"})
    from lifeprism.server import main_agent_only as entry

    with monkeypatch.context() as startup:
        config = MagicMock()
        server = MagicMock(serve=AsyncMock())
        startup.setattr(entry.uvicorn, "Config", config)
        startup.setattr(entry.uvicorn, "Server", lambda *args: server)
        startup.setattr(entry, "init_database_full", lambda: None)
        loop_task = asyncio.create_task(asyncio.sleep(0))
        await loop_task
        startup.setattr(entry, "start_agent_and_channel", AsyncMock(return_value=(loop_task, None)))
        startup.setattr(entry, "stop_agent_and_channel", AsyncMock())
        startup.setattr(asyncio.get_running_loop(), "add_signal_handler", lambda *args: None)
        await entry._run_agent_and_api()
    assert config.call_args.kwargs["port"] == 8102
    return config.call_args.args[0]


@pytest.mark.asyncio
async def test_real_cloud_entry_registers_authenticated_rag_receiver(cloud_app):
    routes = {(route.path, method) for route in cloud_app.routes for method in route.methods}
    assert ("/api/sync/rag-index", "POST") in routes
    assert ("/api/sync/rag-index", "GET") in routes
    assert all(path.startswith("/api/sync/") for path, _ in routes)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=cloud_app), base_url="http://cloud"
    ) as client:
        response = await client.post("/api/sync/rag-index", content=b"x")
    assert response.status_code == 422  # 使用云端实际 LWBaseError → HTTP 状态映射。


class IsolatedSettings:
    def __init__(self, root, mode):
        self.lifeprism_data_path = str(root)
        self.run_mode = mode
        self.auto_summary_session = False
        self.auto_update_memory = False
        self.auto_diary_summary = False
        self.values = {"rag.enabled": True}
        self.keys = {
            "sync_api_key": "synthetic-sync",
            "rag_embedding_api_key": "synthetic-embedding",
        }

    def get(self, name, default=None):
        return self.values.get(name, default)

    def get_storage_key(self, name):
        return self.keys.get(name)


class SyntheticEmbedding:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def embed(self, parts, dimensions=None):
        vector = np.zeros(dimensions or 2048, dtype=np.float32)
        vector[0] = 1
        return SimpleNamespace(dense=vector)


@pytest_asyncio.fixture
async def cloud_http(cloud_app):
    """实际 TCP/HTTP，应用来自生产云端入口；不启动真实 Agent 或访问模型。"""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        listener.listen()
        server = uvicorn.Server(
            uvicorn.Config(cloud_app, log_config=None, log_level="error", lifespan="off")
        )
        task = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            async with asyncio.timeout(5):
                while not server.started:
                    if task.done():
                        await task
                        raise AssertionError("接收服务提前退出")
                    await asyncio.sleep(0.01)
            yield cloud_app, port
        finally:
            server.should_exit = True
            await asyncio.wait_for(task, timeout=5)


@pytest.mark.asyncio
@pytest.mark.parametrize("connection_mode", ["http", "ssh"])
@pytest.mark.parametrize("lose_first_receipt", [False, True])
async def test_full_sender_to_real_cloud_entry_and_retry(
    monkeypatch, tmp_path, cloud_http, connection_mode, lose_first_receipt
):
    from lifeprism.config import settings_manager
    from lifeprism.rag import service as rag
    from lifeprism.server.api import rag_sync_api, sync_cloud_api
    from lifeprism.server.services import schedule_service as schedule
    from lifeprism.sync import sync_config
    from lifeprism.sync.sync_client import SyncClient

    app, port = cloud_http
    local_config = IsolatedSettings(tmp_path / "local", "full")
    cloud_config = IsolatedSettings(tmp_path / "cloud", "agent_only")
    local_config.values.update(
        {
            "sync.connection_mode": connection_mode,
            "sync.remote_url": f"http://127.0.0.1:{port}",
            "sync.ssh_tunnel.local_port": port,
        }
    )
    if connection_mode == "ssh":
        local_config.values["sync.remote_url"] = "https://must-not-be-used.invalid"
        local_config.keys["ssh_tunnel_private_key"] = "synthetic-private-key"
    monkeypatch.setattr(settings_manager, "settings", local_config)
    monkeypatch.setattr(settings_manager, "get_setting", local_config.get)
    monkeypatch.setattr(sync_config, "settings", local_config)
    monkeypatch.setattr(schedule, "settings", local_config)
    monkeypatch.setattr(rag_sync_api, "settings", cloud_config)
    monkeypatch.setattr(
        sync_cloud_api, "get_sync_api_key", lambda: cloud_config.get_storage_key("sync_api_key")
    )
    (tmp_path / "local" / "user").mkdir(parents=True)
    (tmp_path / "local" / "user" / "profile.md").write_text("LifePrism 个人资料", encoding="utf-8")
    local = rag.RagService(tmp_path / "local", local_config, embedding_factory=SyntheticEmbedding)
    cloud = rag.RagService(tmp_path / "cloud", cloud_config, embedding_factory=SyntheticEmbedding)
    local.build = AsyncMock(wraps=local.build)
    monkeypatch.setattr(rag, "get_rag_service", lambda: local)
    monkeypatch.setattr(rag_sync_api, "get_rag_service", lambda: cloud)
    requests = []

    @app.middleware("http")
    async def intercept_receipt(request, call_next):
        response = await call_next(request)
        if request.method == "POST" and request.url.path == "/api/sync/rag-index":
            requests.append((request.headers.get("authorization"), response.status_code))
            if lose_first_receipt and len(requests) == 1 and response.status_code == 200:
                # 数据已发布，模拟代理没有成功把确认交还本地。
                return JSONResponse({"detail": "temporary proxy failure"}, status_code=503)
        return response

    # 使用真实 SyncClient 地址选择方法，隔离其业务数据库与隧道网络初始化。
    client = object.__new__(SyncClient)
    client._ssh_tunnel = SimpleNamespace(is_connected=True)
    local_schedule = schedule.ScheduleService()
    local_schedule.configure_rag_sync(client)
    if connection_mode == "ssh":
        client._ssh_tunnel.is_connected = False
        await local_schedule.run_rag_daily(after_memory=True)
        assert requests == []
        assert cloud.current() is None
        assert local_schedule._rag_job.state().get("synced_date") is None
        client._ssh_tunnel.is_connected = True
    await local_schedule.run_rag_daily(after_memory=True)
    manifest = local.current()
    assert manifest is not None
    assert cloud.current() == manifest
    state = local_schedule._rag_job.state()
    assert state["built_date"]
    assert bool(state.get("synced_date")) is not lose_first_receipt
    if lose_first_receipt:
        await local_schedule.run_rag_daily(after_memory=True)
    state = local_schedule._rag_job.state()
    assert state["built_date"] == state["synced_date"]
    assert state["version"] == manifest.version
    assert state["sha256"] == manifest.sha256
    assert (
        local.index_path(manifest.version).read_bytes()
        == cloud.index_path(manifest.version).read_bytes()
    )
    assert await cloud.search("LifePrism", use_bm25=True)
    await local_schedule.run_rag_daily(after_memory=True)
    assert local.build.await_count == 1
    assert requests == [("Bearer synthetic-sync", 200)] * (2 if lose_first_receipt else 1)
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as http:
        assert (await http.get("/api/sync/rag-index")).status_code == 422
        current = await http.get(
            "/api/sync/rag-index", headers={"Authorization": "Bearer synthetic-sync"}
        )
        assert current.json()["manifest"]["version"] == manifest.version


@pytest.mark.asyncio
async def test_real_receiver_rejects_wrong_key_and_full_mode(monkeypatch, cloud_app):
    from lifeprism.server.api import rag_sync_api, sync_cloud_api

    monkeypatch.setattr(sync_cloud_api, "get_sync_api_key", lambda: "synthetic-sync")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=cloud_app), base_url="http://cloud"
    ) as client:
        response = await client.post(
            "/api/sync/rag-index", content=b"x", headers={"Authorization": "Bearer wrong"}
        )
        assert response.status_code == 422
        monkeypatch.setattr(rag_sync_api, "settings", SimpleNamespace(run_mode="full"))
        headers = {"Authorization": "Bearer synthetic-sync"}
        assert (
            await client.post("/api/sync/rag-index", headers=headers, content=b"x")
        ).status_code == 403
        assert (await client.get("/api/sync/rag-index", headers=headers)).status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["agent_only", "web_demo"])
async def test_cloud_and_demo_never_build_or_send(monkeypatch, tmp_path, mode):
    from lifeprism.server.services import schedule_service as schedule

    monkeypatch.setattr(schedule, "settings", IsolatedSettings(tmp_path, mode))
    service = schedule.ScheduleService()
    job = SimpleNamespace(run=AsyncMock())
    service._rag_job = job
    await service.run_rag_daily(after_memory=True)
    job.run.assert_not_awaited()
    assert not any(config["job_id"].startswith("rag_") for config in service._system_jobs)
