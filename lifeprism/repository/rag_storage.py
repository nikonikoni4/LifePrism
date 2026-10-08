"""独立 simple_rag 数据库适配；不进入业务表的 LWW 同步。"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import sqlite_vec
from simple_rag.db import Database
from simple_rag.indexing import RagIndexingPipeline, RagIndexStrategy
from simple_rag.repository.bm25 import create_bm25
from simple_rag.repository.chunk_store import TABLE_NAME as DATA_TABLE
from simple_rag.repository.chunk_store import ChunkStore
from simple_rag.repository.chunk_store import Schema as ChunkSchema
from simple_rag.repository.vec import TABLE_NAME as VEC_TABLE
from simple_rag.repository.vec import Schema as VecSchema
from simple_rag.repository.vec import VecDB
from simple_rag.retrieval.retrieval import RetrievalClient
from simple_rag.retrieval.types import RetrieverConfig
from simple_rag.tokenization import TokenizerFactory


class RagRepository:
    """通过外部模块公开接口装配索引；连接在创建它的线程关闭。"""

    def snapshot(self, source: sqlite3.Connection, target: Path) -> None:
        """备份全部页面（含 WAL 已提交数据与影子表），生成独立文件。"""
        with closing(sqlite3.connect(target)) as copied:
            source.backup(copied)
            copied.execute("pragma journal_mode=DELETE")

    @contextmanager
    def open(self, path: Path, *, readonly: bool = False) -> Iterator[sqlite3.Connection]:
        """加载当前平台 sqlite-vec，查询连接只读。"""
        if not readonly:
            with Database(path) as db:
                yield db.connection
            return
        conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
            conn.execute("pragma trusted_schema=OFF")
            yield conn
        finally:
            conn.close()

    def pipeline(
        self, conn: sqlite3.Connection, embedding: object, dimensions: int = 2048
    ) -> RagIndexingPipeline:
        """装配完整 vec 与 own_bm25 索引。"""
        return RagIndexingPipeline(
            RagIndexStrategy(
                use_vec=True,
                use_bm25=True,
                chunk_schema=ChunkSchema(),
                min_tokens=50,
                max_token=384,
                vec_schema=VecSchema(dim=dimensions, metric="cosine"),
                bm25_policy="own_bm25",
            ),
            SimpleNamespace(connection=conn),
            embedding,
            TokenizerFactory.create("jieba"),
        )

    def retriever(
        self,
        conn: sqlite3.Connection,
        embedding: object,
        use_bm25: bool,
        candidates: int,
        dimensions: int = 2048,
    ) -> RetrievalClient:
        """默认 vec，显式启用关键词通道时加入 own_bm25。"""
        store, vec = ChunkStore(conn), VecDB(conn)
        store.create_table(ChunkSchema())
        vec.create_table(VecSchema(dim=dimensions, metric="cosine"))
        bm25 = None
        configs = [RetrieverConfig(name="vec", config={"dimensions": dimensions})]
        if use_bm25:
            bm25 = create_bm25("own_bm25", tokenizer=TokenizerFactory.create("jieba"), conn=conn)
            bm25.open()
            configs.append(RetrieverConfig(name="bm25"))
        return RetrievalClient(
            store, configs, candidates, vec_db=vec, embedding_client=embedding, bm25_index=bm25
        )

    def validate(self, path: Path, dimensions: int = 2048) -> int:
        """只读校验结构、三通道 ID 一致性和实际 vec/BM25 查询。"""
        with self.open(path, readonly=True) as conn:
            tables = {
                r[0] for r in conn.execute("select name from sqlite_master where type='table'")
            }
            required = {
                DATA_TABLE,
                VEC_TABLE,
                "own_bm25_docs",
                "own_bm25_postings",
                "own_bm25_stats",
            }
            if not required <= tables:
                raise ValueError("RAG 索引缺少必要数据表")
            if conn.execute(
                "select count(*) from sqlite_master where type in ('trigger', 'view')"
            ).fetchone()[0]:
                raise ValueError("RAG 索引不能包含触发器或视图")
            if conn.execute("pragma integrity_check").fetchone()[0] != "ok":
                raise ValueError("RAG 索引完整性校验失败")
            ids = {r[0] for r in conn.execute(f"select distinct chunk_id from [{DATA_TABLE}]")}
            for table in (VEC_TABLE, "own_bm25_docs"):
                if {r[0] for r in conn.execute(f"select chunk_id from [{table}]")} != ids:
                    raise ValueError("RAG 索引通道数据不一致")
            vec = VecDB(conn)
            vec.create_table(VecSchema(dim=dimensions, metric="cosine"))
            store = ChunkStore(conn)
            store.create_table(ChunkSchema())
            bm25 = create_bm25("own_bm25", tokenizer=TokenizerFactory.create("jieba"), conn=conn)
            bm25.open()
            if ids:
                row = conn.execute(f"select embedding from [{VEC_TABLE}] limit 1").fetchone()
                vector = np.frombuffer(row[0], dtype=np.float32).copy()
                if (
                    vector.size != dimensions
                    or not np.isfinite(vector).all()
                    or not vec.search(vector, 1)
                ):
                    raise ValueError("RAG 索引向量查询校验失败")
                first = store.get(next(iter(ids)))[0]
                bm25.search(first.content[:100], 1)
            return len(ids)
