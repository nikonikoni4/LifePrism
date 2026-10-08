"""完整候选索引构建、原子版本发布与检索生命周期。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import tempfile
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import sqlite_vec
from pydantic import BaseModel, ConfigDict, Field

from lifeprism.rag.config import (
    DIMENSIONS,
    EMBEDDING_BASE_URL,
    EMBEDDING_MODEL,
    KEYS,
    RERANK_BASE_URL,
    RERANK_MODEL,
    SettingsSource,
    read_settings,
    validate_directories,
)
from lifeprism.repository import rag_repository
from lifeprism.utils import get_logger

logger = get_logger(__name__)
MAX_INDEX_BYTES = 512 * 1024 * 1024


class IndexManifest(BaseModel):
    """网络可传输的版本契约，不包含 API Key。"""

    model_config = ConfigDict(extra="forbid")
    version: str = Field(pattern=r"^[0-9a-f]{32}$")
    schema_version: int = Field(default=1, ge=1, le=1)
    embedding_model: str = Field(default=EMBEDDING_MODEL, pattern="^doubao-embedding-vision$")
    dimensions: int = Field(default=DIMENSIONS, ge=DIMENSIONS, le=DIMENSIONS)
    sqlite_vec_version: str
    created_at: datetime
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size: int = Field(gt=0, le=MAX_INDEX_BYTES)
    chunk_count: int = Field(ge=0)
    source_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    directories: list[str]
    max_token: int = Field(default=384, ge=384, le=384)
    min_tokens: int = Field(default=50, ge=50, le=50)


def file_hash(path: Path) -> str:
    """流式计算文件摘要，避免把整库加载进内存。"""
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    """同目录临时文件原子替换；崩溃不留下半份状态。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class RagService:
    """构建和查询使用各自连接；活跃查询固定索引版本。"""

    def __init__(
        self,
        data_root: Path,
        config: SettingsSource,
        embedding_factory: Callable | None = None,
        rerank_factory: Callable | None = None,
    ):
        self.data_root = data_root.resolve()
        self.root = self.data_root / "rag"
        self.config = config
        self.embedding_factory = embedding_factory or self._embedding
        self.rerank_factory = rerank_factory or self._reranker
        self.build_lock = asyncio.Lock()
        self.publish_lock = threading.RLock()
        self._leases: dict[str, int] = {}

    def _embedding(self):
        """显式指定固定模型/地址，缺少凭据时不使用环境兜底。"""
        from simple_rag.config import DoubaoAPIConfig
        from simple_rag.embedding_api.doubao import DoubaoEmbeddingVision

        key = self.config.get_storage_key(KEYS["embedding"])
        if not key:
            raise ValueError("embedding API Key 未配置")
        return DoubaoEmbeddingVision(
            DoubaoAPIConfig(api_base=EMBEDDING_BASE_URL, api_key=key, model=EMBEDDING_MODEL),
            max_retries=5,
            retry_base_wait=5,
        )

    def _reranker(self):
        """只支持已验证的阿里云原生 rerank 契约。"""
        from simple_rag.config import AliyunRerankAPIConfig
        from simple_rag.rerank_api import AliyunReranker

        key = self.config.get_storage_key(KEYS["rerank"])
        if not key:
            raise ValueError("rerank API Key 未配置")
        return AliyunReranker(
            AliyunRerankAPIConfig(api_base=RERANK_BASE_URL, api_key=key, model=RERANK_MODEL)
        )

    def index_path(self, version: str) -> Path:
        """仅接收本模块生成的 UUID，不接受远端文件路径。"""
        if len(version) != 32 or any(c not in "0123456789abcdef" for c in version):
            raise ValueError("非法 RAG 索引版本")
        path = self.root / "versions" / version / "index.db"
        if not path.resolve().is_relative_to(self.root.resolve()):
            raise ValueError("RAG 索引路径越界")
        return path

    def current(self) -> IndexManifest | None:
        """当前版本指针；没有构建过时返回 None。"""
        path = self.root / "current.json"
        return (
            IndexManifest.model_validate_json(path.read_text(encoding="utf-8"))
            if path.exists()
            else None
        )

    @contextmanager
    def lease(self) -> Iterator[IndexManifest]:
        """固定版本直至查询结束，发布不会移除仍被读取的旧库。"""
        with self.publish_lock:
            manifest = self.current()
            if manifest is None:
                raise ValueError("RAG 索引尚未生成，请等待每日索引任务")
            self._leases[manifest.version] = self._leases.get(manifest.version, 0) + 1
        try:
            yield manifest
        finally:
            with self.publish_lock:
                self._leases[manifest.version] -= 1
                if not self._leases[manifest.version]:
                    del self._leases[manifest.version]

    def install(self, snapshot: Path, manifest: IndexManifest) -> None:
        """校验快照后原子发布；重复发布相同版本幂等。"""
        if snapshot.stat().st_size != manifest.size or file_hash(snapshot) != manifest.sha256:
            raise ValueError("RAG 索引大小或摘要校验失败")
        if manifest.sqlite_vec_version != sqlite_vec.__version__:
            raise ValueError("本地与云端 sqlite-vec 版本不一致")
        validate_directories(manifest.directories)
        if manifest.created_at.tzinfo is None:
            raise ValueError("RAG 索引生成时间缺少时区")
        count = rag_repository.validate(snapshot, manifest.dimensions)
        if count != manifest.chunk_count:
            raise ValueError("RAG 索引 chunk 数量不一致")
        with self.publish_lock:
            current = self.current()
            if current and current.version == manifest.version:
                if current != manifest:
                    raise ValueError("同一索引版本不能对应不同内容")
                return
            if current and current.created_at > manifest.created_at:
                raise ValueError("不能发布比当前更旧的 RAG 索引")
            target = self.index_path(manifest.version)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and file_hash(target) != manifest.sha256:
                raise ValueError("RAG 索引版本已存在且内容不同")
            if not target.exists():
                temporary = target.with_suffix(".tmp")
                shutil.copyfile(snapshot, temporary)
                os.replace(temporary, target)
            atomic_json(target.parent / "manifest.json", manifest.model_dump(mode="json"))
            atomic_json(self.root / "current.json", manifest.model_dump(mode="json"))
            self._cleanup()

    def _cleanup(self) -> None:
        """保留最新三版以及正在使用的版本。"""
        directories = sorted(
            (self.root / "versions").iterdir(), key=lambda p: p.stat().st_mtime, reverse=True
        )
        current = self.current()
        for folder in directories[3:]:
            if folder.name in self._leases or (current and folder.name == current.version):
                continue
            if (
                folder.is_dir()
                and not folder.is_symlink()
                and folder.resolve().parent == (self.root / "versions").resolve()
            ):
                shutil.rmtree(folder)

    def _copy_sources(self, directories: list[str], destination: Path) -> tuple[list[Path], str]:
        """复制稳定语料；每个来源都使用数据根相对路径。"""
        files: list[Path] = []
        digest = hashlib.sha256()
        for relative in validate_directories(directories):
            folder = self.data_root / relative
            if not folder.resolve().is_relative_to(self.data_root):
                raise ValueError("索引目录通过符号链接越界")
            if folder.exists() and not folder.is_dir():
                raise ValueError("索引来源必须是目录")
            for path in sorted(folder.rglob("*.md"), key=lambda p: p.as_posix()):
                if not path.resolve().is_relative_to(self.data_root):
                    raise ValueError("索引文件通过符号链接越界")
                before = path.stat()
                content = path.read_bytes()
                after = path.stat()
                if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
                    raise ValueError("索引文件读取期间发生修改，请重试")
                name = path.relative_to(self.data_root)
                copied = destination / name
                copied.parent.mkdir(parents=True, exist_ok=True)
                copied.write_bytes(content)
                digest.update(name.as_posix().encode() + b"\0" + hashlib.sha256(content).digest())
                files.append(copied)
        return files, digest.hexdigest()

    async def build(self, directories: list[str]) -> IndexManifest:
        """完整重建候选库；嵌入或校验失败不修改当前指针。"""
        async with self.build_lock:
            worker = asyncio.create_task(
                asyncio.to_thread(lambda: asyncio.run(self._build(directories)))
            )
            try:
                return await asyncio.shield(worker)
            except asyncio.CancelledError:
                # to_thread 不能停止已有线程。先等线程释放连接再交还写锁。
                try:
                    await worker
                except Exception:
                    logger.warning("取消 RAG 构建时工作线程失败")
                raise

    async def _build(self, directories: list[str]) -> IndexManifest:
        """工作线程内创建连接和网络客户端，避免跨线程使用 sqlite。"""
        from simple_rag.chunking.structured_file.md_chunk_by_title import chunk_by_title

        self.root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="build-", dir=self.root) as workspace:
            work = Path(workspace)
            sources = work / "sources"
            files, fingerprint = self._copy_sources(directories, sources)
            candidate = work / "candidate.db"
            snapshot = work / "snapshot.db"
            async with self.embedding_factory() as embedding:
                with rag_repository.open(candidate) as conn:
                    pipeline = rag_repository.pipeline(conn, embedding)
                    drafts = []
                    for path in files:
                        drafts.extend(
                            chunk_by_title(
                                path, 384, 0, source_name=path.relative_to(sources).as_posix()
                            )
                        )
                    merged = pipeline.merge(drafts)
                    # 外部合并器会丢弃唯一短块；LifePrism 不能因此漏掉整份用户资料。
                    if drafts and not merged:
                        merged = drafts
                    pipeline.store(await pipeline.embedding(merged))
                    rag_repository.snapshot(conn, snapshot)
            manifest = IndexManifest(
                version=uuid4().hex,
                sqlite_vec_version=sqlite_vec.__version__,
                created_at=datetime.now(UTC),
                sha256=file_hash(snapshot),
                size=snapshot.stat().st_size,
                chunk_count=rag_repository.validate(snapshot),
                source_fingerprint=fingerprint,
                directories=directories,
            )
            self.install(snapshot, manifest)
            logger.info(
                "RAG 索引已发布: version=%s chunks=%d", manifest.version, manifest.chunk_count
            )
            return manifest

    async def search(self, query: str, k: int = 5, use_bm25: bool = False) -> list:
        """查询固定版本；rerank 故障保留粗排结果。"""
        if not query.strip() or not 1 <= k <= 20 or not isinstance(use_bm25, bool):
            raise ValueError("检索参数无效，k 范围为 1–20")
        options = read_settings(self.config)
        if not options.enabled:
            raise ValueError("RAG 未开启")
        with (
            self.lease() as manifest,
            rag_repository.open(self.index_path(manifest.version), readonly=True) as conn,
        ):
            async with self.embedding_factory() as embedding:
                retriever = rag_repository.retriever(conn, embedding, use_bm25, max(20, k))
                results = await retriever.search(query, max(20, k) if options.rerank_enabled else k)
            if results and options.rerank_enabled:
                try:
                    from simple_rag.rerank_api import RerankDocument

                    async with self.rerank_factory() as reranker:
                        hits = await reranker.rerank(
                            query,
                            [RerankDocument(chunk_id=r.chunk_id, text=r.content) for r in results],
                            top_n=k,
                        )
                    by_id = {r.chunk_id: r for r in results}
                    reranked = [by_id[h.chunk_id] for h in hits if h.chunk_id in by_id]
                    if not reranked:
                        raise ValueError("rerank 返回为空")
                    return reranked[:k]
                except Exception as exc:
                    logger.warning("RAG rerank 失败，回退粗排: %s", type(exc).__name__)
            return results[:k]


_services: dict[str, RagService] = {}


def get_rag_service() -> RagService:
    """按 SettingsManager 的数据根获得服务，支持数据目录迁移。"""
    from lifeprism.config.settings_manager import settings

    root = Path(settings.lifeprism_data_path).resolve()
    key = str(root)
    if key not in _services:
        _services[key] = RagService(root, settings)
    return _services[key]
