"""
WechatAccountStateProvider 单元测试

测试 seam:
- Seam 1: wechat_account_state 表 DDL 在 TABLE_CONFIGS 中注册（timestamps=True）
- Seam 2: WechatAccountStateProvider.get_state() / save_state() CRUD
- Seam 3: wechat_account_state 加入 SYNC_TABLES
- Seam 4: channel/wechat/account.json 从 SYNC_DIRECTORIES 移除

参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md 决策 4
"""
import pytest

pytestmark = pytest.mark.core


# ==================== Seam 1: 表 DDL 配置 ====================


class TestWechatAccountStateTableConfig:
    """Seam 1: wechat_account_state 表 DDL 在 TABLE_CONFIGS 中注册"""

    def test_table_config_registered(self):
        """验证 wechat_account_state 在 TABLE_CONFIGS 中注册"""
        from lifeprism.config.database import TABLE_CONFIGS

        assert "wechat_account_state" in TABLE_CONFIGS, (
            "wechat_account_state 应在 TABLE_CONFIGS 中注册"
        )

    def test_table_config_timestamps_enabled(self):
        """验证 timestamps=True（用于 LWW 的 updated_at 自动管理）"""
        from lifeprism.config.database import TABLE_CONFIGS

        config = TABLE_CONFIGS["wechat_account_state"]
        assert config.get("timestamps") is True, (
            "wechat_account_state 应配置 timestamps=True"
        )
        assert config.get("update_at") is True, (
            "wechat_account_state 应配置 update_at=True 以自动管理 updated_at"
        )

    def test_table_config_columns(self):
        """验证表结构：wechat_user_id PK + context_token + last_session_id"""
        from lifeprism.config.database import TABLE_CONFIGS

        config = TABLE_CONFIGS["wechat_account_state"]
        columns = config["columns"]

        # wechat_user_id 主键
        assert "wechat_user_id" in columns, "应有 wechat_user_id 列"
        assert "PRIMARY KEY" in columns["wechat_user_id"]["constraints"]
        assert columns["wechat_user_id"]["type"] == "TEXT"

        # context_token 可空
        assert "context_token" in columns, "应有 context_token 列"
        assert columns["context_token"]["type"] == "TEXT"

        # last_session_id 可空
        assert "last_session_id" in columns, "应有 last_session_id 列"
        assert columns["last_session_id"]["type"] == "TEXT"

    def test_table_config_table_name(self):
        """验证 table_name 字段"""
        from lifeprism.config.database import TABLE_CONFIGS

        config = TABLE_CONFIGS["wechat_account_state"]
        assert config["table_name"] == "wechat_account_state"


# ==================== Seam 2: Provider CRUD ====================


@pytest.fixture(scope="module")
def initialized_db(test_data_path):
    """初始化数据库，创建所有表"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    from lifeprism.repository import lw_db_manager
    from lifeprism.repository.lw_table_manager import LWTableManager

    # 重置 update_at 缓存（确保测试使用最新配置）
    from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider

    LWBaseDataProvider._TABLES_WITH_UPDATE_AT = None
    LWBaseDataProvider._TABLES_WITH_TIMESTAMPS = None

    manager = LWTableManager(db_manager=lw_db_manager)
    manager.init_database()

    yield lw_db_manager


@pytest.fixture
def wechat_account_state_provider(initialized_db):
    """创建 WechatAccountStateProvider 实例"""
    from lifeprism.repository.providers.wechat_account_state_provider import (
        WechatAccountStateProvider,
    )

    provider = WechatAccountStateProvider(db_manager=initialized_db)
    yield provider

    # 清理：删除所有测试数据
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM wechat_account_state")
        conn.commit()


class TestWechatAccountStateProviderCRUD:
    """Seam 2: WechatAccountStateProvider.get_state() / save_state() CRUD"""

    def test_get_state_returns_none_when_not_exists(self, wechat_account_state_provider):
        """get_state 查询不存在的用户应返回 None"""
        result = wechat_account_state_provider.get_state("non_existent_user")
        assert result is None

    def test_save_state_creates_new_record(self, wechat_account_state_provider):
        """save_state 创建新记录"""
        success = wechat_account_state_provider.save_state(
            wechat_user_id="user_001",
            context_token="ctx_token_abc",
            last_session_id="session_xyz",
        )
        assert success is True

        # 验证记录已写入
        state = wechat_account_state_provider.get_state("user_001")
        assert state is not None
        assert state["context_token"] == "ctx_token_abc"
        assert state["last_session_id"] == "session_xyz"

    def test_save_state_updates_existing_record(self, wechat_account_state_provider):
        """save_state 更新已存在的记录（基于 wechat_user_id 主键 replace）"""
        # 第一次保存
        wechat_account_state_provider.save_state(
            wechat_user_id="user_002",
            context_token="token_v1",
            last_session_id="session_v1",
        )

        # 第二次保存（更新）
        wechat_account_state_provider.save_state(
            wechat_user_id="user_002",
            context_token="token_v2",
            last_session_id="session_v2",
        )

        # 验证只有一条记录，且为最新值
        state = wechat_account_state_provider.get_state("user_002")
        assert state is not None
        assert state["context_token"] == "token_v2"
        assert state["last_session_id"] == "session_v2"

    def test_save_state_with_none_values(self, wechat_account_state_provider):
        """save_state 接受 None 值的 context_token 和 last_session_id"""
        success = wechat_account_state_provider.save_state(
            wechat_user_id="user_003",
            context_token=None,
            last_session_id=None,
        )
        assert success is True

        state = wechat_account_state_provider.get_state("user_003")
        assert state is not None
        assert state["context_token"] is None
        assert state["last_session_id"] is None

    def test_get_state_returns_dict_with_updated_at(self, wechat_account_state_provider):
        """get_state 返回的字典应包含 updated_at 字段（ISO 8601 + UTC）"""
        wechat_account_state_provider.save_state(
            wechat_user_id="user_004",
            context_token="ctx",
            last_session_id="sess",
        )

        state = wechat_account_state_provider.get_state("user_004")
        assert state is not None
        assert "updated_at" in state
        assert state["updated_at"] is not None
        # ISO 8601 格式：包含 'T' 分隔符
        assert "T" in state["updated_at"], (
            f"updated_at 应为 ISO 8601 格式，实际值: {state['updated_at']}"
        )


# ==================== Seam 3: SYNC_TABLES 加入 ====================


class TestSyncTablesRegistration:
    """Seam 3: wechat_account_state 加入 SYNC_TABLES"""

    def test_wechat_account_state_in_sync_tables(self):
        """验证 wechat_account_state 在 SYNC_TABLES 中"""
        from lifeprism.sync.sync_client import SYNC_TABLES

        assert "wechat_account_state" in SYNC_TABLES, (
            "wechat_account_state 应在 SYNC_TABLES 中以走数据库同步"
        )


# ==================== Seam 4: SYNC_DIRECTORIES 移除 account.json ====================


class TestSyncDirectoriesAccountJsonRemoved:
    """Seam 4: channel/wechat/account.json 从 SYNC_DIRECTORIES 移除"""

    def test_account_json_not_in_sync_directories(self):
        """验证 channel/wechat/account.json 不在 SYNC_DIRECTORIES 中"""
        from lifeprism.sync.sync_client import SYNC_DIRECTORIES

        assert "channel/wechat/account.json" not in SYNC_DIRECTORIES, (
            "channel/wechat/account.json 应从 SYNC_DIRECTORIES 移除（改为数据库存储）"
        )
