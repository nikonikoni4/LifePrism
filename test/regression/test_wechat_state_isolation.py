"""回归测试：微信账户状态字段隔离写入与 WechatReplyStore 凭据管理。

覆盖两类缺陷：
1. 保存 context_token 时误覆盖 last_session_id，反之亦然（字段串写）。
2. WechatReplyStore 空 token 覆盖、保存失败静默、旧 account.json 迁移覆盖已有用户。

参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md 决策 4
"""

import json
from pathlib import Path
from typing import Any

import pytest

from lifeprism.repository.database_manager import DatabaseManager
from lifeprism.repository.lw_table_manager import LWTableManager
from lifeprism.repository.providers.wechat_account_state_provider import (
    WechatAccountStateProvider,
)

pytestmark = pytest.mark.regression


def test_failed_legacy_save_keeps_source_for_retry(tmp_path):
    """旧用户保存失败时不可把唯一源文件当作成功迁移后归档。"""
    from unittest.mock import Mock

    from lifeprism.llm.channel.wechat.reply_store import WechatReplyStore

    path = tmp_path / "account.json"
    path.write_text(
        json.dumps({"user_data": {"alice": {"context_token": "old"}}}), encoding="utf-8"
    )
    repo = Mock()
    repo.get_state.return_value = None
    repo.save_state.return_value = False
    with pytest.raises(RuntimeError, match="迁移"):
        WechatReplyStore(repo).migrate_legacy(path)
    assert path.exists()
    assert not path.with_suffix(".json.bak").exists()


class _FakeStateRepo:
    """内存版 wechat_account_state repository，用于隔离测试 reply_store 行为。"""

    def __init__(
        self,
        states: dict[str, dict[str, Any]] | None = None,
        save_context_token_result: bool = True,
    ) -> None:
        self.states: dict[str, dict[str, Any]] = dict(states or {})
        self.save_context_token_result = save_context_token_result
        self.save_context_token_calls: list[tuple[str, str]] = []
        self.save_state_calls: list[tuple[str, str | None, str | None]] = []

    def get_state(self, wechat_user_id: str) -> dict[str, Any] | None:
        return self.states.get(wechat_user_id)

    def save_context_token(self, wechat_user_id: str, context_token: str) -> bool:
        self.save_context_token_calls.append((wechat_user_id, context_token))
        if not self.save_context_token_result:
            return False
        state = self.states.setdefault(
            wechat_user_id,
            {"wechat_user_id": wechat_user_id, "context_token": None, "last_session_id": None},
        )
        state["context_token"] = context_token
        return True

    def save_session_reference(self, wechat_user_id: str, session_id: str) -> bool:
        state = self.states.setdefault(
            wechat_user_id,
            {"wechat_user_id": wechat_user_id, "context_token": None, "last_session_id": None},
        )
        state["last_session_id"] = session_id
        return True

    def save_state(
        self,
        wechat_user_id: str,
        context_token: str | None,
        last_session_id: str | None,
    ) -> bool:
        self.save_state_calls.append((wechat_user_id, context_token, last_session_id))
        self.states[wechat_user_id] = {
            "wechat_user_id": wechat_user_id,
            "context_token": context_token,
            "last_session_id": last_session_id,
        }
        return True


@pytest.fixture
def sqlite_provider(tmp_path: Path) -> WechatAccountStateProvider:
    """构造指向临时 SQLite 文件、已建表的真实 Provider。"""
    db_manager = DatabaseManager(DB_PATH=str(tmp_path / "lw_test.db"))
    LWTableManager(db_manager=db_manager).init_database()
    return WechatAccountStateProvider(db_manager=db_manager)


# ==================== Provider 字段隔离 ====================


def test_save_context_token_preserves_existing_session(sqlite_provider) -> None:
    """只写凭据：新 context_token 生效，已有 last_session_id 保持不变。"""
    sqlite_provider.save_state("u1", "tok-old", "sess-1")

    assert sqlite_provider.save_context_token("u1", "tok-new") is True

    state = sqlite_provider.get_state("u1")
    assert state["context_token"] == "tok-new"
    assert state["last_session_id"] == "sess-1"


def test_save_session_reference_preserves_existing_token(sqlite_provider) -> None:
    """只写会话：新 last_session_id 生效，已有 context_token 保持不变。"""
    sqlite_provider.save_state("u1", "tok-1", None)

    assert sqlite_provider.save_session_reference("u1", "sess-9") is True

    state = sqlite_provider.get_state("u1")
    assert state["context_token"] == "tok-1"
    assert state["last_session_id"] == "sess-9"


def test_save_context_token_creates_missing_user(sqlite_provider) -> None:
    """用户不存在时只写凭据应补建记录，不抛异常。"""
    assert sqlite_provider.save_context_token("u-new", "tok-fresh") is True

    state = sqlite_provider.get_state("u-new")
    assert state["context_token"] == "tok-fresh"
    assert state["last_session_id"] is None


# ==================== WechatReplyStore ====================


def test_remember_empty_token_does_not_overwrite() -> None:
    """空 token 不覆盖已有凭据，也不触发写库。"""
    from lifeprism.llm.channel.wechat.reply_store import WechatReplyStore

    repo = _FakeStateRepo(
        states={"u1": {"wechat_user_id": "u1", "context_token": "real", "last_session_id": None}}
    )
    store = WechatReplyStore(repository=repo)

    store.remember("u1", "")

    assert store.get_token("u1") == "real"
    assert repo.save_context_token_calls == []


def test_remember_save_failure_raises_runtime_error() -> None:
    """持久化返回 False 时必须抛 RuntimeError，不能静默成功。"""
    from lifeprism.llm.channel.wechat.reply_store import WechatReplyStore

    repo = _FakeStateRepo(save_context_token_result=False)
    store = WechatReplyStore(repository=repo)

    with pytest.raises(RuntimeError):
        store.remember("u1", "tok-x")


def test_get_token_prefers_memory_cache_over_repo() -> None:
    """刚收到的新凭据优先从内存缓存读取，不被库中旧值覆盖。"""
    from lifeprism.llm.channel.wechat.reply_store import WechatReplyStore

    repo = _FakeStateRepo(
        states={"u1": {"wechat_user_id": "u1", "context_token": "old", "last_session_id": None}}
    )
    store = WechatReplyStore(repository=repo)

    store.remember("u1", "fresh")
    repo.states["u1"]["context_token"] = "changed-in-db"

    assert store.get_token("u1") == "fresh"


def test_get_token_falls_back_to_repo_when_cache_miss() -> None:
    """内存无缓存时回落到 repository.get_state。"""
    from lifeprism.llm.channel.wechat.reply_store import WechatReplyStore

    repo = _FakeStateRepo(
        states={"u1": {"wechat_user_id": "u1", "context_token": "from-db", "last_session_id": None}}
    )
    store = WechatReplyStore(repository=repo)

    assert store.get_token("u1") == "from-db"
    assert store.get_token("missing") == ""


# ==================== migrate_legacy ====================


def test_migrate_legacy_skips_existing_users(tmp_path: Path) -> None:
    """迁移不覆盖已存在用户，只补写缺失用户，完成后重命名为 .bak。"""
    from lifeprism.llm.channel.wechat.reply_store import WechatReplyStore

    repo = _FakeStateRepo(
        states={
            "u1": {"wechat_user_id": "u1", "context_token": "keep", "last_session_id": "s-keep"}
        }
    )
    legacy = tmp_path / "account.json"
    legacy.write_text(
        json.dumps(
            {
                "user_data": {
                    "u1": {"context_token": "should-not-overwrite", "last_session_id": "x"},
                    "u2": {"context_token": "tok-2", "last_session_id": "sess-2"},
                }
            }
        ),
        encoding="utf-8",
    )

    WechatReplyStore(repository=repo).migrate_legacy(legacy)

    assert repo.states["u1"]["context_token"] == "keep"
    assert repo.states["u1"]["last_session_id"] == "s-keep"
    assert repo.states["u2"]["context_token"] == "tok-2"
    assert repo.states["u2"]["last_session_id"] == "sess-2"
    assert repo.save_state_calls == [("u2", "tok-2", "sess-2")]
    assert not legacy.exists()
    assert (tmp_path / "account.json.bak").exists()


def test_migrate_legacy_old_format_sets_no_session(tmp_path: Path) -> None:
    """旧格式 context_tokens 迁移时 last_session_id 为 None。"""
    from lifeprism.llm.channel.wechat.reply_store import WechatReplyStore

    repo = _FakeStateRepo()
    legacy = tmp_path / "account.json"
    legacy.write_text(json.dumps({"context_tokens": {"u9": "tok-9"}}), encoding="utf-8")

    WechatReplyStore(repository=repo).migrate_legacy(legacy)

    assert repo.states["u9"]["context_token"] == "tok-9"
    assert repo.states["u9"]["last_session_id"] is None
    assert (tmp_path / "account.json.bak").exists()


def test_migrate_legacy_missing_file_is_noop(tmp_path: Path) -> None:
    """文件不存在时不操作、不抛异常。"""
    from lifeprism.llm.channel.wechat.reply_store import WechatReplyStore

    repo = _FakeStateRepo()
    WechatReplyStore(repository=repo).migrate_legacy(tmp_path / "account.json")

    assert repo.save_state_calls == []
    assert not (tmp_path / "account.json.bak").exists()


def test_migrate_legacy_ignores_token_field(tmp_path: Path) -> None:
    """迁移不碰 token 字段（token 由原 auth 处理）。"""
    from lifeprism.llm.channel.wechat.reply_store import WechatReplyStore

    repo = _FakeStateRepo()
    legacy = tmp_path / "account.json"
    legacy.write_text(
        json.dumps({"token": "bot-secret", "user_data": {"u3": {"context_token": "tok-3"}}}),
        encoding="utf-8",
    )

    WechatReplyStore(repository=repo).migrate_legacy(legacy)

    assert repo.save_state_calls == [("u3", "tok-3", None)]
    bak = tmp_path / "account.json.bak"
    assert json.loads(bak.read_text(encoding="utf-8"))["token"] == "bot-secret"
