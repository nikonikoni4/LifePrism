"""微信旧 account.json → wechat_account_state 数据库迁移测试

测试 seam（真实实现，不使用替身）:

- ``WechatReplyStore.migrate_legacy(path)``：把旧 account.json 的用户数据迁移到
  真实 SQLite 数据库。数据库指向 ``tmp_path`` 临时文件，不触碰生产库。
  - account.json 存在且用户未入库 → 迁移该用户，完成后重命名为 .bak
  - account.json 存在但部分用户已在库 → 逐用户检查，已存在用户不覆盖，缺失用户仍迁移
  - account.json 不存在 → 不操作、不重命名
  - 旧格式 context_tokens → 迁移 context_token，last_session_id 为 None

参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md 决策 4
"""

import json
from pathlib import Path

import pytest

from lifeprism.llm.channel.wechat.reply_store import WechatReplyStore
from lifeprism.repository.database_manager import DatabaseManager
from lifeprism.repository.lw_table_manager import LWTableManager
from lifeprism.repository.providers.wechat_account_state_provider import (
    WechatAccountStateProvider,
)

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture
def provider(tmp_path: Path) -> WechatAccountStateProvider:
    """构造指向临时 SQLite 文件、已建表的真实 Provider（不触碰生产库）。"""
    db_manager = DatabaseManager(DB_PATH=str(tmp_path / "lw_test.db"))
    LWTableManager(db_manager=db_manager).init_database()
    return WechatAccountStateProvider(db_manager=db_manager)


@pytest.fixture
def store(provider: WechatAccountStateProvider) -> WechatReplyStore:
    """使用临时 Provider 的凭据存储，隔离生产账号状态。"""
    return WechatReplyStore(repository=provider)


def _write_account_json(path: Path, data: dict) -> None:
    """写入 account.json 文件"""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ==================== Seam: WechatReplyStore.migrate_legacy() ====================


class TestMigrateLegacyAccountJson:
    """Seam: WechatReplyStore.migrate_legacy() 迁移方法"""

    def test_migrate_when_account_json_exists_and_db_empty(self, store, provider, tmp_path):
        """account.json 存在且 DB 无记录 → 迁移到 DB + 重命名为 .bak"""
        # Arrange: 写入 account.json（新格式 user_data）
        legacy = tmp_path / "account.json"
        _write_account_json(
            legacy,
            {
                "user_data": {
                    "user_001": {
                        "context_token": "ctx_token_001",
                        "last_session_id": "session_001",
                    },
                    "user_002": {
                        "context_token": "ctx_token_002",
                        "last_session_id": None,
                    },
                }
            },
        )

        # Act: 执行迁移
        store.migrate_legacy(legacy)

        # Assert: account.json 已重命名为 .bak
        assert not legacy.exists(), "account.json 应已被重命名"
        assert legacy.with_suffix(".json.bak").exists(), "account.json.bak 应存在"

        # Assert: DB 中有两条记录
        state_001 = provider.get_state("user_001")
        assert state_001 is not None
        assert state_001["context_token"] == "ctx_token_001"
        assert state_001["last_session_id"] == "session_001"

        state_002 = provider.get_state("user_002")
        assert state_002 is not None
        assert state_002["context_token"] == "ctx_token_002"
        assert state_002["last_session_id"] is None

    def test_existing_user_not_overwritten_and_new_user_migrated(self, store, provider, tmp_path):
        """逐用户检查：已在库用户不覆盖，缺失用户仍迁移，完成后重命名"""
        # Arrange: DB 中先插入一条记录
        provider.save_state(
            wechat_user_id="existing_user",
            context_token="existing_token",
            last_session_id="existing_session",
        )

        # Arrange: 写入 account.json，同时含已存在用户与缺失用户
        legacy = tmp_path / "account.json"
        _write_account_json(
            legacy,
            {
                "user_data": {
                    "existing_user": {
                        "context_token": "should_not_overwrite",
                        "last_session_id": "should_not_overwrite",
                    },
                    "new_user": {
                        "context_token": "new_token",
                        "last_session_id": "new_session",
                    },
                }
            },
        )

        # Act: 执行迁移
        store.migrate_legacy(legacy)

        # Assert: 已存在用户保持原值，未被覆盖
        existing = provider.get_state("existing_user")
        assert existing is not None
        assert existing["context_token"] == "existing_token"
        assert existing["last_session_id"] == "existing_session"

        # Assert: 缺失用户已迁移
        new = provider.get_state("new_user")
        assert new is not None
        assert new["context_token"] == "new_token"
        assert new["last_session_id"] == "new_session"

        # Assert: 迁移完成后 account.json 已重命名为 .bak
        assert not legacy.exists(), "account.json 应已被重命名"
        assert legacy.with_suffix(".json.bak").exists(), "account.json.bak 应存在"

    def test_skip_migration_when_account_json_not_exists(self, store, provider, tmp_path):
        """account.json 不存在 → 不操作、不重命名"""
        # Arrange: account.json 不存在
        legacy = tmp_path / "account.json"

        # Act: 执行迁移
        store.migrate_legacy(legacy)

        # Assert: .bak 文件不存在，DB 未被写入
        assert not legacy.with_suffix(".json.bak").exists(), "account.json.bak 不应存在"
        assert provider.get_all_states() == [], "DB 不应有任何记录"

    def test_migrate_old_format_context_tokens(self, store, provider, tmp_path):
        """旧格式 context_tokens 自动迁移到新格式"""
        # Arrange: 写入旧格式 account.json
        legacy = tmp_path / "account.json"
        _write_account_json(
            legacy,
            {
                "context_tokens": {
                    "old_user_001": "old_ctx_token_001",
                    "old_user_002": "old_ctx_token_002",
                }
            },
        )

        # Act: 执行迁移
        store.migrate_legacy(legacy)

        # Assert: account.json 已重命名为 .bak
        assert not legacy.exists(), "account.json 应已被重命名"

        # Assert: DB 中有两条记录，context_token 正确，last_session_id 为 None
        state_001 = provider.get_state("old_user_001")
        assert state_001 is not None
        assert state_001["context_token"] == "old_ctx_token_001"
        assert state_001["last_session_id"] is None, "旧格式迁移 last_session_id 应为 None"

        state_002 = provider.get_state("old_user_002")
        assert state_002 is not None
        assert state_002["context_token"] == "old_ctx_token_002"
        assert state_002["last_session_id"] is None, "旧格式迁移 last_session_id 应为 None"
