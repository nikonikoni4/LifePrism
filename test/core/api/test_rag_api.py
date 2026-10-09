"""RAG 设置与真实二进制上传协议，使用隔离配置和合成向量。"""

import base64
from types import SimpleNamespace

import httpx
import numpy as np
import pytest
from fastapi import FastAPI

pytestmark = pytest.mark.core


class MemorySettings:
    run_mode = "agent_only"

    def __init__(self):
        self.values = {}
        self.keys = {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def get_storage_key(self, key):
        return self.keys.get(key)

    def set_storage_key(self, key, value):
        self.keys[key] = value

    def delete_storage_key(self, key):
        self.keys.pop(key, None)

    def set(self, key, value):
        self.values[key] = value

    def update(self, values):
        self.values.update(values)


@pytest.mark.asyncio
async def test_settings_fixed_models_and_key_clear_disables_feature(monkeypatch):
    from lifeprism.server.api import rag_settings_api as module

    settings = MemorySettings()
    monkeypatch.setattr(module, "settings", settings)
    app = FastAPI()
    app.include_router(module.router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.patch("/settings/rag", json={"enabled": True})).status_code == 422
        assert (
            await client.patch("/settings/rag", json={"embedding_model": "wrong"})
        ).status_code == 422
        response = await client.put("/settings/rag/keys/embedding", json={"api_key": "rag-secret"})
        assert response.status_code == 200
        assert "rag-secret" not in response.text
        assert response.json()["embedding"]["configured"]
        assert (await client.patch("/settings/rag", json={"enabled": True})).json()["enabled"]
        response = await client.put("/settings/rag/keys/embedding", json={"api_key": ""})
        assert not response.json()["enabled"]
        assert not response.json()["embedding"]["configured"]


@pytest.mark.asyncio
async def test_editable_urls_fixed_models_and_independent_connection_tests(monkeypatch, tmp_path):
    from lifeprism.rag.service import RagService
    from lifeprism.server.api import rag_settings_api as api

    settings = MemorySettings()
    settings.run_mode = "full"
    settings.set_storage_key("rag_embedding_api_key", "synthetic-embed")
    settings.set_storage_key("rag_rerank_api_key", "synthetic-rerank")
    calls = []

    class Embedding:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def embed(self, parts, dimensions=None):
            calls.append("embedding")
            return SimpleNamespace(dense=np.ones(dimensions, dtype=np.float32))

    class Rerank:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def rerank(self, query, documents, top_n=None):
            calls.append("rerank")
            return [SimpleNamespace(chunk_id=documents[0].chunk_id)]

    service = RagService(tmp_path, settings, embedding_factory=Embedding, rerank_factory=Rerank)
    monkeypatch.setattr(api, "settings", settings)
    monkeypatch.setattr(api, "get_rag_service", lambda: service)
    app = FastAPI()
    app.include_router(api.router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.patch(
            "/settings/rag",
            json={
                "embedding_base_url": "https://embedding.example/api/v3",
                "rerank_base_url": "https://rerank.example/full-endpoint",
            },
        )
        assert result.status_code == 200
        assert result.json()["embedding"]["base_url"] == "https://embedding.example/api/v3"
        assert result.json()["embedding"]["model"] == "doubao-embedding-vision"
        assert (
            await client.patch("/settings/rag", json={"embedding_model": "other"})
        ).status_code == 422
        assert (
            await client.patch("/settings/rag", json={"rerank_base_url": "file:///x"})
        ).status_code == 422
        assert (await client.post("/settings/rag/test/rerank")).json()["success"]
        assert calls == ["rerank"]  # 不依赖 embedding，也不要求开启 RAG/rerank。
        assert (await client.post("/settings/rag/test/embedding")).json()["success"]
        assert calls == ["rerank", "embedding"]
        assert service.current() is None
        real_factory = RagService(tmp_path, settings)
        assert real_factory._embedding()._config.api_base == "https://embedding.example/api/v3"
        assert real_factory._reranker()._config.api_base == "https://rerank.example/full-endpoint"
        assert not settings.get("rag.enabled", False)


@pytest.mark.asyncio
async def test_connection_failure_is_explicit_redacted_and_does_not_require_embedding(
    tmp_path, caplog
):
    from lifeprism.rag.service import RagService

    settings = MemorySettings()
    settings.set_storage_key("rag_rerank_api_key", "private-rerank-key")

    class BrokenRerank:
        async def __aenter__(self):
            raise ConnectionError("connection refused private-rerank-key")

        async def __aexit__(self, *args):
            pass

    service = RagService(tmp_path, settings, rerank_factory=BrokenRerank)
    result = await service.test_connection("rerank")
    assert not result.success
    assert "connection refused" in result.message
    assert "private-rerank-key" not in result.message + caplog.text
    assert service.current() is None


@pytest.mark.asyncio
async def test_real_snapshot_upload_auth_validation_and_idempotence(monkeypatch, tmp_path):
    from lifeprism.rag.service import RagService
    from lifeprism.server.api import rag_sync_api as module
    from lifeprism.sync.rag_sync import RagSyncSender
    from lifeprism.utils.exceptions import ValidationError

    settings = MemorySettings()
    settings.set("rag.enabled", True)
    settings.set_storage_key("rag_embedding_api_key", "synthetic")

    class Embedding:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def embed(self, parts, dimensions=None):
            vec = np.zeros(dimensions or 2048, dtype=np.float32)
            vec[0] = 1
            return SimpleNamespace(dense=vec)

    (tmp_path / "local" / "user").mkdir(parents=True)
    (tmp_path / "local" / "user" / "user.md").write_text("个人资料测试", encoding="utf-8")
    local = RagService(tmp_path / "local", settings, embedding_factory=Embedding)
    cloud = RagService(tmp_path / "cloud", settings, embedding_factory=Embedding)
    manifest = await local.build(["user"])
    monkeypatch.setattr(module, "settings", settings)
    monkeypatch.setattr(module, "get_rag_service", lambda: cloud)
    # 保留真实认证依赖，仅替换期望密钥的来源。
    import lifeprism.server.api.sync_cloud_api as auth

    monkeypatch.setattr(auth, "get_sync_api_key", lambda: "sync-secret")
    app = FastAPI()
    app.include_router(module.router)
    from fastapi.responses import JSONResponse

    @app.exception_handler(ValidationError)
    async def unauthorized(request, exc):
        return JSONResponse(status_code=401, content={"error": exc.code})

    transport = httpx.ASGITransport(app=app)
    sender = RagSyncSender(
        local,
        SimpleNamespace(_read_remote_url=lambda: "http://test"),
        lambda: "sync-secret",
        transport,
    )
    assert await sender.upload(manifest) == {"version": manifest.version, "sha256": manifest.sha256}
    assert await sender.upload(manifest) == {"version": manifest.version, "sha256": manifest.sha256}
    assert await cloud.search("个人资料", 5, True)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.post("/api/sync/rag-index", content=b"x")).status_code == 401
        headers = {
            "Authorization": "Bearer sync-secret",
            "X-RAG-Manifest": base64.b64encode(manifest.model_dump_json().encode()).decode(),
        }
        assert (
            await client.post("/api/sync/rag-index", headers=headers, content=b"corrupt")
        ).status_code == 422
        assert cloud.current().version == manifest.version
        # 匹配摘要与长度、但并非 SQLite 的上传必须返回校验错误。
        import hashlib

        corrupt = b"not a sqlite database"
        corrupt_manifest = manifest.model_copy(
            update={
                "size": len(corrupt),
                "sha256": hashlib.sha256(corrupt).hexdigest(),
                "version": "a" * 32,
            }
        )
        headers["X-RAG-Manifest"] = base64.b64encode(
            corrupt_manifest.model_dump_json().encode()
        ).decode()
        assert (
            await client.post("/api/sync/rag-index", headers=headers, content=corrupt)
        ).status_code == 422
        assert cloud.current().version == manifest.version
        settings.run_mode = "full"
        assert (
            await client.post("/api/sync/rag-index", headers=headers, content=b"x")
        ).status_code == 403
