"""消息路由逻辑集成测试 (Issue #19)

测试 seam: WechatChannel._handle_wechat_message() 的消息路由行为
- 本地在线时，云端跳过消息处理（不调用 bus.send），避免重复回复
- 本地离线时，云端正常处理消息
- 超时后云端接管
- 显式 offline 事件后云端立即接管
- 日志记录路由决策

参考:
- lifeprism/sync/heartbeat_manager.py
- lifeprism/llm/channel/wechat/channel.py
"""

import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest

pytestmark = pytest.mark.core


@pytest.fixture
def reset_heartbeat():
    """重置心跳单例状态，避免测试间互相影响"""
    from lifeprism.sync.heartbeat_manager import heartbeat_manager

    heartbeat_manager._last_heartbeat = None
    heartbeat_manager._last_event = None
    yield
    heartbeat_manager._last_heartbeat = None
    heartbeat_manager._last_event = None


@pytest.fixture
def wechat_channel():
    """创建最小化依赖的 WechatChannel 实例

    - bus 使用 AsyncMock，可断言 send 是否被调用
    - 不初始化 client/auth/media，使 send() 成为 no-op（client 为 None 时直接返回）
    - allow_from=["*"] 放行所有用户
    """
    from lifeprism.llm.bus.events import OutboundMessage
    from lifeprism.llm.channel.wechat.channel import WechatChannel
    from lifeprism.llm.channel.wechat.config import WechatConfig

    config = WechatConfig(allow_from=["*"])
    bus = AsyncMock()
    # bus.send 默认返回无 session_id 的 OutboundMessage，避免触发持久化分支
    bus.send.return_value = OutboundMessage()
    channel = WechatChannel(config, bus)
    return channel


@pytest.fixture
def cloud_mode():
    """Mock run_mode 为 agent_only（云端模式）

    心跳路由检查仅在云端模式（agent_only）下执行。
    本地模式（full）下 heartbeat_manager 从不被更新，直接处理所有消息。
    """
    with patch(
        "lifeprism.config.settings_manager.SettingsManager.run_mode",
        new_callable=PropertyMock,
        return_value="agent_only",
    ):
        yield


def _build_text_msg(content: str = "hello", from_user_id: str = "test_user") -> dict:
    """构造一条纯文本微信消息字典（与 WechatMessage.parse_message 解析格式一致）"""
    return {
        "from_user_id": from_user_id,
        "item_list": [{"type": 1, "text_item": {"text": content}}],
    }


class TestMessageRouting:
    """消息路由测试"""

    @pytest.mark.asyncio
    async def test_cloud_skips_message_when_local_online(self, wechat_channel, reset_heartbeat, cloud_mode):
        """本地在线时，云端跳过消息处理（不调用 bus.send）"""
        # Arrange
        from lifeprism.sync.heartbeat_manager import heartbeat_manager

        heartbeat_manager.set_event("online")
        assert heartbeat_manager.is_local_online() is True
        msg = _build_text_msg("hello")

        # Act
        await wechat_channel._handle_wechat_message(msg)

        # Assert: 在线时不应触达消息总线
        wechat_channel.bus.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_cloud_processes_message_when_local_offline(self, wechat_channel, reset_heartbeat, cloud_mode):
        """本地离线时，云端正常处理消息（调用 bus.send）"""
        # Arrange
        from lifeprism.sync.heartbeat_manager import heartbeat_manager

        # 初始状态：从未连接 -> 离线
        assert heartbeat_manager.is_local_online() is False
        msg = _build_text_msg("hello")

        # Act: mock LLM 日志相关调用，避免文件/数据库副作用
        # 注意: llm_call_logger 是 LazySingleton 代理，需 patch 整个对象而非其方法属性
        with patch(
            "lifeprism.llm.channel.wechat.channel.Context.build_system_prompt",
            return_value="",
        ), patch("lifeprism.llm.channel.wechat.channel.llm_call_logger"):
            await wechat_channel._handle_wechat_message(msg)

        # Assert: 离线时云端接管，消息进入总线
        wechat_channel.bus.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_cloud_takeover_after_timeout(self, wechat_channel, reset_heartbeat, cloud_mode):
        """超时后云端接管（初始在线→超时后离线→处理消息）"""
        # Arrange
        from lifeprism.sync.heartbeat_manager import heartbeat_manager

        base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        timeout_time = base_time + timedelta(seconds=901)

        with patch("lifeprism.sync.heartbeat_manager.datetime") as mock_datetime:
            # 初始在线
            mock_datetime.now.return_value = base_time
            heartbeat_manager.set_event("online")
            assert heartbeat_manager.is_local_online() is True

            # 时间流逝超过 15 分钟（900 秒）阈值 -> 离线
            mock_datetime.now.return_value = timeout_time
            assert heartbeat_manager.is_local_online() is False

            msg = _build_text_msg("hello")

            # Act
            with patch(
                "lifeprism.llm.channel.wechat.channel.Context.build_system_prompt",
                return_value="",
            ), patch("lifeprism.llm.channel.wechat.channel.llm_call_logger"):
                await wechat_channel._handle_wechat_message(msg)

        # Assert: 超时后云端接管处理
        wechat_channel.bus.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_explicit_offline_takeover(self, wechat_channel, reset_heartbeat, cloud_mode):
        """显式 offline 事件后云端立即接管"""
        # Arrange
        from lifeprism.sync.heartbeat_manager import heartbeat_manager

        heartbeat_manager.set_event("online")
        assert heartbeat_manager.is_local_online() is True

        # 显式 offline 立即生效（不等超时）
        heartbeat_manager.set_event("offline")
        assert heartbeat_manager.is_local_online() is False

        msg = _build_text_msg("hello")

        # Act
        with patch(
            "lifeprism.llm.channel.wechat.channel.Context.build_system_prompt",
            return_value="",
        ), patch("lifeprism.llm.channel.wechat.channel.llm_call_logger"):
            await wechat_channel._handle_wechat_message(msg)

        # Assert: 显式离线后云端立即接管
        wechat_channel.bus.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_routing_logs_decision(self, wechat_channel, reset_heartbeat, cloud_mode, caplog):
        """日志记录路由决策（在线跳过 / 离线接管）"""
        # Arrange
        from lifeprism.sync.heartbeat_manager import heartbeat_manager

        channel_logger = "lifeprism.llm.channel.wechat.channel"
        msg = _build_text_msg("hello")

        # Act & Assert: 在线 -> 跳过云端处理日志
        heartbeat_manager.set_event("online")
        with caplog.at_level(logging.INFO, logger=channel_logger):
            await wechat_channel._handle_wechat_message(msg)
        assert any("跳过云端处理" in r.getMessage() for r in caplog.records)
        caplog.clear()

        # Act & Assert: 离线 -> 云端接管处理日志
        heartbeat_manager.set_event("offline")
        with caplog.at_level(logging.INFO, logger=channel_logger), patch(
            "lifeprism.llm.channel.wechat.channel.Context.build_system_prompt",
            return_value="",
        ), patch("lifeprism.llm.channel.wechat.channel.llm_call_logger"):
            await wechat_channel._handle_wechat_message(msg)
        assert any("云端接管处理" in r.getMessage() for r in caplog.records)

    @pytest.mark.asyncio
    async def test_local_always_processes_regardless_of_heartbeat(
        self, wechat_channel, reset_heartbeat
    ):
        """本地模式（full）下，无论心跳状态如何，始终处理消息

        验证 run_mode 守卫：本地模式下即使 heartbeat_manager 被误更新为在线，
        消息也不会被跳过。
        """
        from lifeprism.sync.heartbeat_manager import heartbeat_manager

        # 即使本地"在线"（heartbeat_manager 被误更新），本地模式仍处理消息
        heartbeat_manager.set_event("online")
        assert heartbeat_manager.is_local_online() is True

        msg = _build_text_msg("hello")

        # 默认 run_mode 为 "full"（本地模式），不使用 cloud_mode fixture
        with patch(
            "lifeprism.llm.channel.wechat.channel.Context.build_system_prompt",
            return_value="",
        ), patch("lifeprism.llm.channel.wechat.channel.llm_call_logger"):
            await wechat_channel._handle_wechat_message(msg)

        # Assert: 本地模式始终处理消息，不受心跳状态影响
        wechat_channel.bus.send.assert_called_once()
