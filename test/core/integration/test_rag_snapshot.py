"""真实 vec0/WAL/own_bm25 快照的契约测试，不调用模型 API。"""

import importlib
import sqlite3

import numpy as np
import pytest
from simple_rag.db import Database
from simple_rag.repository.bm25 import create_bm25
from simple_rag.repository.chunk_store import ChunkStore
from simple_rag.repository.chunk_store import Schema as ChunkSchema
from simple_rag.repository.vec import Schema as VecSchema
from simple_rag.repository.vec import VecDB
from simple_rag.tokenization import TokenizerFactory

pytestmark = pytest.mark.core


def test_snapshot_preserves_wal_vectors_sources_and_bm25(tmp_path):
    module = importlib.import_module("lifeprism.repository.rag_storage")
    source, target = tmp_path / "source.db", tmp_path / "snapshot.db"
    with Database(source) as db:
        conn = db.connection
        conn.execute("pragma wal_autocheckpoint=0")
        vec = VecDB(conn)
        vec.create_table(VecSchema(dim=3, metric="cosine"))
        store = ChunkStore(conn)
        store.create_table(ChunkSchema())
        bm25 = create_bm25("own_bm25", tokenizer=TokenizerFactory.create("jieba"), conn=conn)
        bm25.open()
        vec.insert([{"chunk_id": "c1", "vector": np.array([1, 0, 0], dtype=np.float32)}])
        store.insert(
            [
                {
                    "chunk_id": "c1",
                    "sources": [{"path": "user/user.md", "start_line": 0, "end_line": 1}],
                    "content": "LifePrism 个人记录",
                }
            ]
        )
        bm25.insert([{"chunk_id": "c1", "text": "LifePrism 个人记录"}])
        assert source.with_suffix(".db-wal").stat().st_size > 0
        module.RagRepository().snapshot(conn, target)
        before = {
            row[0]: row[1]
            for row in conn.execute("select name, sql from sqlite_master where type='table'")
        }
    with Database(target) as copied:
        assert copied.connection.execute("pragma integrity_check").fetchone()[0] == "ok"
        after = {
            row[0]: row[1]
            for row in copied.connection.execute(
                "select name, sql from sqlite_master where type='table'"
            )
        }
        assert before == after
        vec = VecDB(copied.connection)
        vec.create_table(VecSchema(dim=3, metric="cosine"))
        assert vec.search(np.array([1, 0, 0], dtype=np.float32), 1)[0].chunk_id == "c1"
        store = ChunkStore(copied.connection)
        store.create_table(ChunkSchema())
        assert store.get("c1")[0].path == "user/user.md"
        bm25 = create_bm25(
            "own_bm25", tokenizer=TokenizerFactory.create("jieba"), conn=copied.connection
        )
        bm25.open()
        assert bm25.search("LifePrism", 1)[0].chunk_id == "c1"


def test_reject_incomplete_index_without_creating_missing_tables(tmp_path):
    module = importlib.import_module("lifeprism.repository.rag_storage")
    target = tmp_path / "incomplete.db"
    with sqlite3.connect(target) as conn:
        conn.execute("create table unrelated (id integer)")
    with pytest.raises(ValueError, match="索引"):
        module.RagRepository().validate(target)
    with sqlite3.connect(target) as conn:
        assert (
            conn.execute("select count(*) from sqlite_master where type='table'").fetchone()[0] == 1
        )
