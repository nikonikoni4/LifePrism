"""发布期间旧请求保留版本，路径不能逃出数据根。"""

import pytest
from test_rag_service import Embedding, source

pytestmark = pytest.mark.core


@pytest.mark.asyncio
async def test_active_version_is_kept_until_lease_released(tmp_path):
    from lifeprism.rag.service import RagService

    (tmp_path / "user").mkdir()
    (tmp_path / "user" / "profile.md").write_text("LifePrism", encoding="utf-8")
    service = RagService(tmp_path, source(), embedding_factory=Embedding)
    first = await service.build(["user"])
    with service.lease():
        for _ in range(3):
            await service.build(["user"])
        assert service.index_path(first.version).exists()
    await service.build(["user"])
    assert not service.index_path(first.version).exists()


@pytest.mark.asyncio
async def test_cancelled_build_does_not_release_writer_while_thread_running(tmp_path):
    import asyncio
    import threading

    from lifeprism.rag.service import RagService

    started, release = threading.Event(), threading.Event()

    class Slow(Embedding):
        async def embed(self, parts, dimensions=None):
            started.set()
            await asyncio.to_thread(release.wait)
            return await super().embed(parts, dimensions)

    (tmp_path / "user").mkdir()
    (tmp_path / "user" / "profile.md").write_text("LifePrism", encoding="utf-8")
    service = RagService(tmp_path, source(), embedding_factory=Slow)
    task = asyncio.create_task(service.build(["user"]))
    assert await asyncio.to_thread(started.wait, 10), "构建未进入嵌入阶段"
    task.cancel()
    await asyncio.sleep(0.02)
    try:
        assert service.build_lock.locked()
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
