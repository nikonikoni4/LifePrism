"""每日构建后只上传一次；失败重试复用当日索引。"""

import importlib
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.core


@pytest.mark.asyncio
async def test_failed_upload_retries_same_index_and_success_is_once_per_day(tmp_path):
    module = importlib.import_module("lifeprism.sync.rag_sync")
    calls = []
    manifest = SimpleNamespace(version="a" * 32, sha256="b" * 64)

    async def build(directories):
        calls.append("build")
        return manifest

    service = SimpleNamespace(root=tmp_path, current=lambda: manifest, build=build)

    async def upload(version):
        calls.append("upload")
        if calls.count("upload") == 1:
            raise ConnectionError("offline")
        return {"version": version.version, "sha256": version.sha256}

    job = module.DailyRagJob(service, upload)
    with pytest.raises(ConnectionError):
        await job.run("2026-10-08", ["user", "diary"])
    await job.run("2026-10-08", ["user", "diary"])
    await job.run("2026-10-08", ["user", "diary"])
    assert calls == ["build", "upload", "upload"]
    await job.run("2026-10-09", ["user", "diary"])
    assert calls == ["build", "upload", "upload", "build", "upload"]


@pytest.mark.asyncio
async def test_wrong_cloud_ack_does_not_mark_success(tmp_path):
    module = importlib.import_module("lifeprism.sync.rag_sync")
    manifest = SimpleNamespace(version="a" * 32, sha256="b" * 64)

    async def build(directories):
        return manifest

    async def upload(version):
        return {"version": "wrong", "sha256": version.sha256}

    service = SimpleNamespace(root=tmp_path, current=lambda: manifest, build=build)
    job = module.DailyRagJob(service, upload)
    with pytest.raises(ValueError):
        await job.run("2026-10-08", ["user"])
    assert job.state().get("synced_date") is None


@pytest.mark.asyncio
async def test_sync_sender_uses_tunnel_endpoint_and_streams_snapshot(tmp_path):
    import httpx

    module = importlib.import_module("lifeprism.sync.rag_sync")
    manifest = SimpleNamespace(
        version="a" * 32, sha256="b" * 64, model_dump_json=lambda: '{"version":"' + "a" * 32 + '"}'
    )
    path = tmp_path / "index.db"
    path.write_bytes(b"sqlite snapshot")
    received = []

    async def handler(request):
        received.append((str(request.url), request.headers["Authorization"], await request.aread()))
        return httpx.Response(200, json={"version": manifest.version, "sha256": manifest.sha256})

    service = SimpleNamespace(index_path=lambda version: path)
    sync = SimpleNamespace(_read_remote_url=lambda: "http://localhost:8102")
    sender = module.RagSyncSender(
        service, sync, lambda: "sync-key", transport=httpx.MockTransport(handler)
    )
    await sender.upload(manifest)
    assert received == [
        ("http://localhost:8102/api/sync/rag-index", "Bearer sync-key", b"sqlite snapshot")
    ]
