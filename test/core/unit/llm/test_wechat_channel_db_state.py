"""微信账户状态字段隔离持久化与 stop 不覆盖测试

测试 seam（真实实现，不使用替身）:

- ``WechatReplyStore.remember`` / ``.get_token``：只读写 context_token 字段
- ``WechatSessionReferences.set`` / ``.get``：只读写 last_session_id 字段
- ``WechatChannel.stop()``：不覆盖两侧已及时保存的最新字段，也不写 account.json

两侧字段各自及时落库，互不覆盖；数据库指向 ``tmp_path`` 临时文件，不触碰生产库。

参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md 决策 4
"""

from pathlib import Path

import pytest

from lifeprism.llm.channel.wechat.reply_store import WechatReplyStore
from lifeprism.llm.conversation.references import WechatSessionReferences
from lifeprism.llm.conversation.types import ConversationRoute
from lifeprism.repository.database_manager import DatabaseManager
from lifeprism.repository.lw_table_manager import LWTableManager
from lifeprism.repository.providers.wechat_account_state_provider import (
    WechatAccountStateProvider,
)

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture(scope="module")
def initialized_settings():
    """初始化 settings，使 WechatChannel 能解析 channel_path。"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()
    yield settings


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


@pytest.fixture
def references(provider: WechatAccountStateProvider) -> WechatSessionReferences:
    """使用临时 Provider 的会话引用存储，隔离生产账号状态。"""
    return WechatSessionReferences(repository=provider)


@pytest.fixture
def channel(initialized_settings, store, tmp_path):
    """创建 WechatChannel 实例（不调用 start()），account.json 指向临时目录。"""
    from lifeprism.llm.bus.queue import MessageQueue
    from lifeprism.llm.channel.wechat import WechatChannel, WechatConfig

    config = WechatConfig(enabled=True, allow_from=["*"])
    bus = MessageQueue()
    channel = WechatChannel(config, bus, reply_store=store)
    # 把 state_file 重定向到临时目录，确保 stop() 不写 account.json 的断言隔离生产路径
    channel.state_file = tmp_path / "account.json"
    return channel


def _route(recipient: str) -> ConversationRoute:
    """构造微信路由，recipient_id 作为 wechat_account_state 主键。"""
    return ConversationRoute(channel="wechat", recipient_id=recipient, transport_id="wechat")


# ==================== Seam: 字段隔离保存 ====================


class TestFieldIsolatedSave:
    """Seam: context_token 与 last_session_id 各自及时落库，互不覆盖"""

    def test_save_multiple_users_to_db(self, store, references, provider):
        """两侧字段各自保存多个用户的数据到 DB"""
        # Act: 凭据侧写 context_token，引用侧写 last_session_id
        store.remember("user_a", "ctx_a")
        references.set(_route("user_a"), "sess_a")
        store.remember("user_b", "ctx_b")
        references.set(_route("user_b"), "sess_b")

        # Assert: DB 中有两条记录，两个字段都正确
        state_a = provider.get_state("user_a")
        assert state_a is not None
        assert state_a["context_token"] == "ctx_a"
        assert state_a["last_session_id"] == "sess_a"

        state_b = provider.get_state("user_b")
        assert state_b is not None
        assert state_b["context_token"] == "ctx_b"
        assert state_b["last_session_id"] == "sess_b"

    def test_save_empty_token_does_nothing(self, store, provider):
        """空 token 视为无效凭据，不执行任何 DB 操作"""
        # Act: 保存空 token（不应抛出异常，也不写库）
        store.remember("user_empty", "")

        # Assert: DB 中无记录
        assert provider.get_all_states() == []

    def test_save_overwrites_existing_record(self, store, provider):
        """保存已有用户时覆盖该字段自身，但不触碰另一字段（字段隔离）"""
        # Arrange: DB 中先插入一条记录
        provider.save_state(
            wechat_user_id="user_c",
            context_token="old_token",
            last_session_id="old_session",
        )

        # Act: 凭据侧写入新 token
        store.remember("user_c", "new_token")

        # Assert: context_token 已被覆盖，last_session_id 保持不变
        state_c = provider.get_state("user_c")
        assert state_c is not None
        assert state_c["context_token"] == "new_token"
        assert state_c["last_session_id"] == "old_session", "覆盖凭据不应清空会话引用"


# ==================== Seam: 字段隔离读取 ====================


class TestLoadUserDataFromDb:
    """Seam: 从 DB 分别读取 context_token 与 last_session_id"""

    def test_load_multiple_users_from_db(self, store, references, provider):
        """两侧 seam 各自从 DB 读取多个用户的数据"""
        # Arrange: DB 中插入两条记录
        provider.save_state("user_x", "ctx_x", "sess_x")
        provider.save_state("user_y", "ctx_y", None)

        # Assert: 凭据侧读 context_token，引用侧读 last_session_id
        assert store.get_token("user_x") == "ctx_x"
        assert references.get(_route("user_x")) == "sess_x"

        assert store.get_token("user_y") == "ctx_y"
        # None 值应保留为 None
        assert references.get(_route("user_y")) is None

    def test_load_empty_db_results_in_empty_user_data(self, store, references):
        """DB 为空时两侧读取都为空"""
        # Assert: 无记录时凭据侧返回空串，引用侧返回 None
        assert store.get_token("stale") == ""
        assert references.get(_route("stale")) is None


# ==================== Seam: stop() 不覆盖最新字段 ====================


class TestStopDoesNotClobber:
    """Seam: stop() 不覆盖两侧已保存的最新字段，也不写 account.json"""

    @pytest.mark.asyncio
    async def test_stop_does_not_overwrite_latest_fields(
        self, channel, store, references, provider
    ):
        """两侧字段及时保存后，stop() 不覆盖已落库的最新字段"""
        # Arrange: 两侧各自及时保存最新字段
        store.remember("stop_user", "stop_ctx")
        references.set(_route("stop_user"), "stop_sess")
        channel._running = True

        # Act: 调用 stop()
        await channel.stop()

        # Assert: DB 中仍是最新字段，stop 未覆盖
        state = provider.get_state("stop_user")
        assert state is not None
        assert state["context_token"] == "stop_ctx"
        assert state["last_session_id"] == "stop_sess"

    @pytest.mark.asyncio
    async def test_stop_does_not_write_account_json(self, channel, provider):
        """stop() 不再写入 account.json 文件，也不触发 DB 写入"""
        # Arrange: 确保 account.json 不存在
        assert not channel.state_file.exists()
        channel._running = True

        # Act: 调用 stop()
        await channel.stop()

        # Assert: account.json 未被创建
        assert not channel.state_file.exists(), "stop() 不应创建 account.json 文件"

        # Assert: stop() 不触发任何 DB 写入
        assert provider.get_all_states() == []
