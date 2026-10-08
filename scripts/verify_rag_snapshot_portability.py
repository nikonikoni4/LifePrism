"""使用合成数据验证同一 SQLite 快照跨 Windows/Linux 重开。

create 模式需 LifePrism 环境；verify 模式只需 simple_rag 及其依赖。
不读取用户语料、不调用 API。
"""

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np
import sqlite_vec
from simple_rag.db import Database
from simple_rag.repository.bm25 import create_bm25
from simple_rag.repository.chunk_store import ChunkStore
from simple_rag.repository.chunk_store import Schema as ChunkSchema
from simple_rag.repository.vec import Schema as VecSchema
from simple_rag.repository.vec import VecDB
from simple_rag.tokenization import TokenizerFactory


def inspect(path: Path) -> dict:
    """检验 KNN、来源和 BM25，并给出所有持久表的摘要。"""
    with Database(path) as db:
        conn = db.connection
        assert conn.execute("pragma integrity_check").fetchone()[0] == "ok"
        vec = VecDB(conn)
        vec.create_table(VecSchema(dim=3, metric="cosine"))
        hits = vec.search(np.array([1, 0, 0], dtype=np.float32), 2)
        store = ChunkStore(conn)
        store.create_table(ChunkSchema())
        bm25 = create_bm25("own_bm25", tokenizer=TokenizerFactory.create("jieba"), conn=conn)
        bm25.open()
        ranks = bm25.search("LifePrism", 2)
        tables = [
            r[0]
            for r in conn.execute("select name from sqlite_master where type='table' order by name")
        ]
        hashes = {}
        for table in tables:
            rows = list(conn.execute(f"select * from [{table}]"))
            hashes[table] = hashlib.sha256(repr(sorted(rows, key=repr)).encode()).hexdigest()
        return {
            "vec": [(hit.chunk_id, round(hit.distance, 6)) for hit in hits],
            "bm25": [(hit.chunk_id, round(hit.score, 6)) for hit in ranks],
            "sources": [row.path for row in store.get("c1")],
            "tables": hashes,
            "sqlite_vec": sqlite_vec.__version__,
        }


def create(path: Path) -> None:
    """在未 checkpoint 的 WAL 状态生成跨平台快照。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    original = path.with_suffix(".source.db")
    with Database(original) as db:
        conn = db.connection
        conn.execute("pragma wal_autocheckpoint=0")
        vec = VecDB(conn)
        vec.create_table(VecSchema(dim=3, metric="cosine"))
        vec.insert(
            [
                {"chunk_id": "c1", "vector": np.array([1, 0, 0], dtype=np.float32)},
                {"chunk_id": "c2", "vector": np.array([0, 1, 0], dtype=np.float32)},
            ]
        )
        store = ChunkStore(conn)
        store.create_table(ChunkSchema())
        store.insert(
            [
                {
                    "chunk_id": "c1",
                    "content": "LifePrism 项目记录",
                    "sources": [{"path": "user/user.md", "start_line": 0, "end_line": 1}],
                },
                {
                    "chunk_id": "c2",
                    "content": "旅行日记",
                    "sources": [{"path": "diary/2026-10-08.md", "start_line": 0, "end_line": 1}],
                },
            ]
        )
        bm25 = create_bm25("own_bm25", tokenizer=TokenizerFactory.create("jieba"), conn=conn)
        bm25.open()
        bm25.insert(
            [
                {"chunk_id": "c1", "text": "LifePrism 项目记录"},
                {"chunk_id": "c2", "text": "旅行日记"},
            ]
        )
        assert original.with_suffix(".db-wal").stat().st_size > 0
        with closing(sqlite3.connect(path)) as copied:
            conn.backup(copied)
            copied.execute("pragma journal_mode=DELETE")
    path.with_suffix(".expected.json").write_text(
        json.dumps(inspect(path), ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["create", "verify"])
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.mode == "create":
        create(args.path)
    actual = json.loads(json.dumps(inspect(args.path)))
    expected = json.loads(args.path.with_suffix(".expected.json").read_text(encoding="utf-8"))
    assert actual == expected, (actual, expected)
    print(
        json.dumps(
            {
                "verified": True,
                "sqlite_version": sqlite3.sqlite_version,
                "sqlite_vec_version": sqlite_vec.__version__,
                "table_count": len(actual["tables"]),
                "vec": actual["vec"],
                "bm25": actual["bm25"],
            },
            ensure_ascii=False,
        )
    )
