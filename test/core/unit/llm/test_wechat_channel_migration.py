"""
WechatChannel account.json → 数据库迁移测试

测试 seam:
- Seam: _migrate_account_json_to_db() 迁移方法
  - account.json 存在且 DB 无记录 → 迁移到 DB + 重命名为 .bak
  - account.json 存在但 DB 已有记录 → 跳过迁移，不重命名
  - account.json 不存在 → 跳过迁移
  - 旧格式 context_tokens 自动迁移到新格式

参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md 决策 4
"""
import json

import pytest

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture(scope="module")
def initialized_db(test_data_path):
    """初始化数据库，创建所有表"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    from lifeprism.repository import lw_db_manager
    from lifeprism.repository.lw_table_manager import LWTableManager

    # 重置 update_at 缓存（确保测试使用最新配置）
    from lifeprism.repository.base_providers.lw_base_data_provider import (
        LWBaseDataProvider,
    )

    LWBaseDataProvider._TABLES_WITH_UPDATE_AT = None
    LWBaseDataProvider._TABLES_WITH_TIMESTAMPS = None

    manager = LWTableManager(db_manager=lw_db_manager)
    manager.init_database()

    yield lw_db_manager


@pytest.fixture
def wechat_channel(initialized_db):
    """创建 WechatChannel 实例（不调用 start()）"""
    from lifeprism.llm.bus.queue import MessageQueue
    from lifeprism.llm.channel.wechat import WechatChannel, WechatConfig

    config = WechatConfig(enabled=True, allow_from=["*"])
    bus = MessageQueue()
    channel = WechatChannel(config, bus)

    yield channel

    # 清理：删除可能残留的 account.json / account.json.bak
    if channel.state_file.exists():
        channel.state_file.unlink()
    bak_file = channel.state_file.with_suffix(".json.bak")
    if bak_file.exists():
        bak_file.unlink()

    # 清理 DB
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM wechat_account_state")
        conn.commit()


@pytest.fixture
def clean_account_state_table(initialized_db):
    """清理 wechat_account_state 表"""
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM wechat_account_state")
        conn.commit()
    yield


def _write_account_json(state_file, data):
    """写入 account.json 文件"""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))


# ==================== Seam: _migrate_account_json_to_db() ====================


class TestMigrateAccountJsonToDb:
    """Seam: _migrate_account_json_to_db() 迁移方法"""

    def test_migrate_when_account_json_exists_and_db_empty(
        self, wechat_channel, clean_account_state_table
    ):
        """account.json 存在且 DB 无记录 → 迁移到 DB + 重命名为 .bak"""
        # Arrange: 写入 account.json（新格式 user_data）
        _write_account_json(
            wechat_channel.state_file,
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
        result = wechat_channel._migrate_account_json_to_db()

        # Assert: 迁移成功
        assert result is True, "迁移应返回 True"

        # Assert: account.json 已重命名为 .bak
        assert not wechat_channel.state_file.exists(), "account.json 应已被重命名"
        bak_file = wechat_channel.state_file.with_suffix(".json.bak")
        assert bak_file.exists(), "account.json.bak 应存在"

        # Assert: DB 中有两条记录
        from lifeprism.repository.providers.wechat_account_state_provider import (
            WechatAccountStateProvider,
        )

        provider = WechatAccountStateProvider(db_manager=wechat_channel._db_manager)

        state_001 = provider.get_state("user_001")
        assert state_001 is not None
        assert state_001["context_token"] == "ctx_token_001"
        assert state_001["last_session_id"] == "session_001"

        state_002 = provider.get_state("user_002")
        assert state_002 is not None
        assert state_002["context_token"] == "ctx_token_002"
        assert state_002["last_session_id"] is None

    def test_skip_migration_when_db_already_has_records(
        self, wechat_channel, clean_account_state_table
    ):
        """account.json 存在但 DB 已有记录 → 跳过迁移，不重命名"""
        # Arrange: DB 中先插入一条记录
        from lifeprism.repository.providers.wechat_account_state_provider import (
            WechatAccountStateProvider,
        )

        provider = WechatAccountStateProvider(db_manager=wechat_channel._db_manager)
        provider.save_state(
            wechat_user_id="existing_user",
            context_token="existing_token",
            last_session_id="existing_session",
        )

        # Arrange: 写入 account.json
        _write_account_json(
            wechat_channel.state_file,
            {
                "user_data": {
                    "new_user": {
                        "context_token": "new_token",
                        "last_session_id": "new_session",
                    }
                }
            },
        )

        # Act: 执行迁移
        result = wechat_channel._migrate_account_json_to_db()

        # Assert: 跳过迁移
        assert result is False, "DB 已有记录时应跳过迁移返回 False"

        # Assert: account.json 未被重命名
        assert wechat_channel.state_file.exists(), "account.json 应仍存在（未迁移）"
        bak_file = wechat_channel.state_file.with_suffix(".json.bak")
        assert not bak_file.exists(), "account.json.bak 不应存在"

        # Assert: DB 中只有原有记录，新用户未被迁移
        assert provider.get_state("new_user") is None, "新用户不应被迁移到 DB"

    def test_skip_migration_when_account_json_not_exists(
        self, wechat_channel, clean_account_state_table
    ):
        """account.json 不存在 → 跳过迁移"""
        # Arrange: 确保 account.json 不存在
        if wechat_channel.state_file.exists():
            wechat_channel.state_file.unlink()

        # Act: 执行迁移
        result = wechat_channel._migrate_account_json_to_db()

        # Assert: 跳过迁移
        assert result is False, "account.json 不存在时应跳过迁移返回 False"

        # Assert: .bak 文件不存在
        bak_file = wechat_channel.state_file.with_suffix(".json.bak")
        assert not bak_file.exists(), "account.json.bak 不应存在"

    def test_migrate_old_format_context_tokens(
        self, wechat_channel, clean_account_state_table
    ):
        """旧格式 context_tokens 自动迁移到新格式"""
        # Arrange: 写入旧格式 account.json
        _write_account_json(
            wechat_channel.state_file,
            {
                "context_tokens": {
                    "old_user_001": "old_ctx_token_001",
                    "old_user_002": "old_ctx_token_002",
                }
            },
        )

        # Act: 执行迁移
        result = wechat_channel._migrate_account_json_to_db()

        # Assert: 迁移成功
        assert result is True, "迁移应返回 True"

        # Assert: account.json 已重命名为 .bak
        assert not wechat_channel.state_file.exists(), "account.json 应已被重命名"

        # Assert: DB 中有两条记录，context_token 正确，last_session_id 为 None
        from lifeprism.repository.providers.wechat_account_state_provider import (
            WechatAccountStateProvider,
        )

        provider = WechatAccountStateProvider(db_manager=wechat_channel._db_manager)

        state_001 = provider.get_state("old_user_001")
        assert state_001 is not None
        assert state_001["context_token"] == "old_ctx_token_001"
        assert state_001["last_session_id"] is None, "旧格式迁移 last_session_id 应为 None"

        state_002 = provider.get_state("old_user_002")
        assert state_002 is not None
        assert state_002["context_token"] == "old_ctx_token_002"
        assert state_002["last_session_id"] is None, "旧格式迁移 last_session_id 应为 None"
