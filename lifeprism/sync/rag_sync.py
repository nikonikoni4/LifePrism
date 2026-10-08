"""每日索引更新后独立单向发布，复用现有认证和隧道连接。"""

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import Awaitable, Callable

import httpx

from lifeprism.rag.service import IndexManifest, RagService, atomic_json


class RagSyncSender:
    """只发送完整索引快照，不参与业务数据库同步。"""

    def __init__(
        self,
        service: RagService,
        sync_client: object,
        api_key: Callable[[], str | None],
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.service = service
        self.sync_client = sync_client
        self.api_key = api_key
        self.transport = transport

    async def upload(self, manifest: IndexManifest) -> dict:
        """通过 SyncClient 的统一地址入口流式上传已发布索引。"""
        remote = self.sync_client._read_remote_url()
        key = self.api_key()
        if not remote or not key:
            raise ValueError("RAG 云端地址、认证或 SSH 隧道尚未就绪")
        path = self.service.index_path(manifest.version)

        async def content():
            with path.open("rb") as handle:
                while chunk := await asyncio.to_thread(handle.read, 1024 * 1024):
                    yield chunk

        encoded = base64.b64encode(manifest.model_dump_json().encode()).decode("ascii")
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(300, connect=15), transport=self.transport
        ) as client:
            response = await client.post(
                f"{remote.rstrip('/')}/api/sync/rag-index",
                content=content(),
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(path.stat().st_size),
                    "X-RAG-Manifest": encoded,
                },
            )
            response.raise_for_status()
            return response.json()


class DailyRagJob:
    """构建日期与云端确认日期分开，重试不重复消耗 embedding。"""

    def __init__(self, service: RagService, upload: Callable[[IndexManifest], Awaitable[dict]]):
        self.service = service
        self.upload = upload
        self.lock = asyncio.Lock()

    def state(self) -> dict:
        """读取崩溃恢复状态，记录不包含密钥。"""
        path = self.service.root / "daily.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    async def run(self, today: str, directories: list[str]) -> None:
        """每天更新后单独同步一次，仅远端正确确认才提交成功日期。"""
        async with self.lock:
            state = self.state()
            if state.get("synced_date") == today:
                return
            manifest = self.service.current()
            if (
                state.get("built_date") != today
                or manifest is None
                or state.get("version") != manifest.version
            ):
                manifest = await self.service.build(directories)
                state.update(built_date=today, version=manifest.version)
                atomic_json(self.service.root / "daily.json", state)
            receipt = await self.upload(manifest)
            if (
                receipt.get("version") != manifest.version
                or receipt.get("sha256") != manifest.sha256
            ):
                raise ValueError("云端未确认当前 RAG 索引版本")
            state.update(synced_date=today, sha256=manifest.sha256)
            atomic_json(self.service.root / "daily.json", state)
