"""
WechatChannel 数据库状态读写测试

测试 seam:
- Seam: _save_user_data_to_db() / _load_user_data_from_db()
  - _save_user_data_to_db() 将 _user_data 写入 DB
  - _load_user_data_from_db() 从 DB 加载到 _user_data
  - stop() 调用 _save_user_data_to_db() 而非 auth.save_state()
  - start() 先迁移再从 DB 加载 _user_data

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

    # 清理
    if channel.state_file.exists():
        channel.state_file.unlink()
    bak_file = channel.state_file.with_suffix(".json.bak")
    if bak_file.exists():
        bak_file.unlink()

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


# ==================== Seam: _save_user_data_to_db() ====================


class TestSaveUserDataToDb:
    """Seam: _save_user_data_to_db() 将 _user_data 写入 DB"""

    def test_save_multiple_users_to_db(
        self, wechat_channel, clean_account_state_table
    ):
        """_save_user_data_to_db() 将多个用户数据写入 DB"""
        # Arrange: 设置 _user_data
        wechat_channel._user_data = {
            "user_a": {"context_token": "ctx_a", "last_session_id": "sess_a"},
            "user_b": {"context_token": "ctx_b", "last_session_id": "sess_b"},
        }

        # Act: 保存到 DB
        wechat_channel._save_user_data_to_db()

        # Assert: DB 中有两条记录
        state_a = wechat_channel._account_state_provider.get_state("user_a")
        assert state_a is not None
        assert state_a["context_token"] == "ctx_a"
        assert state_a["last_session_id"] == "sess_a"

        state_b = wechat_channel._account_state_provider.get_state("user_b")
        assert state_b is not None
        assert state_b["context_token"] == "ctx_b"
        assert state_b["last_session_id"] == "sess_b"

    def test_save_empty_user_data_does_nothing(
        self, wechat_channel, clean_account_state_table
    ):
        """_user_data 为空时不执行任何 DB 操作"""
        # Arrange: _user_data 为空
        wechat_channel._user_data = {}

        # Act: 保存到 DB（不应抛出异常）
        wechat_channel._save_user_data_to_db()

        # Assert: DB 中无记录
        with wechat_channel._db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM wechat_account_state")
            count = cursor.fetchone()[0]
        assert count == 0

    def test_save_overwrites_existing_record(
        self, wechat_channel, clean_account_state_table
    ):
        """save 时如果 DB 已有该用户记录，应覆盖（INSERT OR REPLACE 语义）"""
        # Arrange: DB 中先插入一条记录
        wechat_channel._account_state_provider.save_state(
            wechat_user_id="user_c",
            context_token="old_token",
            last_session_id="old_session",
        )

        # Arrange: _user_data 中有该用户的新数据
        wechat_channel._user_data = {
            "user_c": {"context_token": "new_token", "last_session_id": "new_session"},
        }

        # Act: 保存到 DB
        wechat_channel._save_user_data_to_db()

        # Assert: DB 中的记录已被更新
        state_c = wechat_channel._account_state_provider.get_state("user_c")
        assert state_c is not None
        assert state_c["context_token"] == "new_token"
        assert state_c["last_session_id"] == "new_session"


# ==================== Seam: _load_user_data_from_db() ====================


class TestLoadUserDataFromDb:
    """Seam: _load_user_data_from_db() 从 DB 加载到 _user_data"""

    def test_load_multiple_users_from_db(
        self, wechat_channel, clean_account_state_table
    ):
        """_load_user_data_from_db() 从 DB 加载多个用户数据"""
        # Arrange: DB 中插入两条记录
        wechat_channel._account_state_provider.save_state(
            wechat_user_id="user_x",
            context_token="ctx_x",
            last_session_id="sess_x",
        )
        wechat_channel._account_state_provider.save_state(
            wechat_user_id="user_y",
            context_token="ctx_y",
            last_session_id=None,
        )

        # Act: 从 DB 加载
        wechat_channel._user_data = {}  # 清空当前数据
        wechat_channel._load_user_data_from_db()

        # Assert: _user_data 包含两条记录
        assert "user_x" in wechat_channel._user_data
        assert wechat_channel._user_data["user_x"]["context_token"] == "ctx_x"
        assert wechat_channel._user_data["user_x"]["last_session_id"] == "sess_x"

        assert "user_y" in wechat_channel._user_data
        assert wechat_channel._user_data["user_y"]["context_token"] == "ctx_y"
        # None 值应保留为 None（或可能不存在该 key）
        last_session = wechat_channel._user_data["user_y"].get("last_session_id")
        assert last_session is None

    def test_load_empty_db_results_in_empty_user_data(
        self, wechat_channel, clean_account_state_table
    ):
        """DB 为空时 _user_data 也为空"""
        # Arrange: DB 为空（依赖 clean_account_state_table）

        # Act: 从 DB 加载
        wechat_channel._user_data = {"stale": {"context_token": "should_be_cleared"}}
        wechat_channel._load_user_data_from_db()

        # Assert: _user_data 为空
        assert wechat_channel._user_data == {}


# ==================== Seam: stop() 保存到 DB ====================


class TestStopSavesToDb:
    """Seam: stop() 调用 _save_user_data_to_db() 而非 auth.save_state()"""

    @pytest.mark.asyncio
    async def test_stop_saves_user_data_to_db(
        self, wechat_channel, clean_account_state_table
    ):
        """stop() 将 _user_data 保存到 DB"""
        # Arrange: 设置 _user_data（不设置 auth/client，避免文件保存）
        wechat_channel._user_data = {
            "stop_user": {"context_token": "stop_ctx", "last_session_id": "stop_sess"},
        }
        wechat_channel._running = True

        # Act: 调用 stop()
        await wechat_channel.stop()

        # Assert: DB 中有记录
        state = wechat_channel._account_state_provider.get_state("stop_user")
        assert state is not None
        assert state["context_token"] == "stop_ctx"
        assert state["last_session_id"] == "stop_sess"

    @pytest.mark.asyncio
    async def test_stop_does_not_write_account_json(
        self, wechat_channel, clean_account_state_table
    ):
        """stop() 不再写入 account.json 文件"""
        # Arrange: 确保 account.json 不存在
        if wechat_channel.state_file.exists():
            wechat_channel.state_file.unlink()

        wechat_channel._user_data = {
            "no_file_user": {
                "context_token": "no_file_ctx",
                "last_session_id": "no_file_sess",
            },
        }
        wechat_channel._running = True

        # Act: 调用 stop()
        await wechat_channel.stop()

        # Assert: account.json 未被创建
        assert not wechat_channel.state_file.exists(), (
            "stop() 不应创建 account.json 文件"
        )

        # Assert: DB 中有记录（数据已保存到 DB）
        state = wechat_channel._account_state_provider.get_state("no_file_user")
        assert state is not None
