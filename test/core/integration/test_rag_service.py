"""版本发布、删除重建、来源路径与 rerank 降级。"""

import hashlib
import importlib
from types import SimpleNamespace

import numpy as np
import pytest

pytestmark = pytest.mark.core


class Embedding:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def embed(self, parts, dimensions=None):
        vec = np.zeros(dimensions or 2048, dtype=np.float32)
        vec[hashlib.sha256(str(parts).encode()).digest()[0]] = 1
        return SimpleNamespace(dense=vec)


def source():
    return SimpleNamespace(
        get=lambda key, default=None: {"rag.enabled": True}.get(key, default),
        get_storage_key=lambda key: "test-key",
    )


@pytest.mark.asyncio
async def test_build_and_rebuild_remove_deleted_sources_with_relative_paths(tmp_path):
    module = importlib.import_module("lifeprism.rag.service")
    (tmp_path / "user").mkdir()
    document = tmp_path / "user" / "user.md"
    document.write_text("# Profile\n\nLifePrism 项目记录", encoding="utf-8")
    service = module.RagService(tmp_path, source(), embedding_factory=Embedding)
    first = await service.build(["user"])
    results = await service.search("LifePrism", 5, use_bm25=True)
    assert results
    assert {s.path for r in results for s in r.sources} == {"user/user.md"}
    document.unlink()
    second = await service.build(["user"])
    assert first.version != second.version
    assert second.chunk_count == 0
    assert await service.search("LifePrism", 5) == []


@pytest.mark.asyncio
async def test_failed_rebuild_preserves_previous_index(tmp_path):
    module = importlib.import_module("lifeprism.rag.service")
    (tmp_path / "user").mkdir()
    (tmp_path / "user" / "user.md").write_text("LifePrism 项目", encoding="utf-8")
    service = module.RagService(tmp_path, source(), embedding_factory=Embedding)
    first = await service.build(["user"])

    class Broken(Embedding):
        async def embed(self, *args, **kwargs):
            raise RuntimeError("embed unavailable")

    service.embedding_factory = Broken
    with pytest.raises(RuntimeError):
        await service.build(["user"])
    assert service.current().version == first.version


@pytest.mark.asyncio
async def test_reject_corrupt_upload_preserves_current_and_idempotent_install(tmp_path):
    module = importlib.import_module("lifeprism.rag.service")
    local = tmp_path / "local"
    (local / "user").mkdir(parents=True)
    (local / "user" / "profile.md").write_text("LifePrism", encoding="utf-8")
    service = module.RagService(local, source(), embedding_factory=Embedding)
    manifest = await service.build(["user"])
    cloud = module.RagService(tmp_path / "cloud", source(), embedding_factory=Embedding)
    payload = service.index_path(manifest.version).read_bytes()
    staged = tmp_path / "uploaded.db"
    staged.write_bytes(payload)
    cloud.install(staged, manifest)
    cloud.install(staged, manifest)
    assert cloud.current().version == manifest.version
    staged.write_bytes(b"corrupt")
    with pytest.raises(ValueError):
        cloud.install(staged, manifest)
    assert cloud.current().version == manifest.version


@pytest.mark.asyncio
async def test_rerank_failure_returns_vec_results(tmp_path):
    module = importlib.import_module("lifeprism.rag.service")
    (tmp_path / "user").mkdir()
    (tmp_path / "user" / "profile.md").write_text("LifePrism 项目", encoding="utf-8")

    class BrokenRerank(Embedding):
        async def rerank(self, *args, **kwargs):
            raise RuntimeError("rerank unavailable")

    config = source()
    config.get = lambda key, default=None: (
        True if key in ("rag.enabled", "rag.rerank_enabled") else default
    )
    service = module.RagService(
        tmp_path, config, embedding_factory=Embedding, rerank_factory=BrokenRerank
    )
    await service.build(["user"])
    assert await service.search("LifePrism", 5)
