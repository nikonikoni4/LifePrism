"""测试 AgentLoop 命令处理功能"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def agent_loop():
    """创建 AgentLoop 实例"""
    # 延迟导入，避免模块级别的循环导入
    from lifeprism.llm.agent.loop import AgentLoop

    mock_bus = Mock()
    return AgentLoop(mock_bus)


@pytest.fixture
def mock_session_with_messages():
    """创建包含消息的模拟 session"""
    from lifeprism.llm.session import Session

    session = Mock(spec=Session)
    session.id = "test-session-123"
    session.messages = [
        {
            "role": "user",
            "content": "你好，我想了解一下 Python 的异步编程",
            "timestamp": datetime.now().isoformat(),
        },
        {
            "role": "assistant",
            "content": "您好！Python 的异步编程主要使用 asyncio 库...",
            "timestamp": datetime.now().isoformat(),
        },
        {"role": "user", "content": "能给我举个例子吗？", "timestamp": datetime.now().isoformat()},
        {
            "role": "assistant",
            "content": "当然可以！下面是一个简单的例子：\n```python\nasync def main():\n    await asyncio.sleep(1)\n```",
            "timestamp": datetime.now().isoformat(),
        },
    ]
    return session


@pytest.fixture
def mock_session_with_few_messages():
    """创建只有一条消息的模拟 session"""
    from lifeprism.llm.session import Session

    session = Mock(spec=Session)
    session.id = "test-session-456"
    session.messages = [
        {"role": "user", "content": "测试消息", "timestamp": datetime.now().isoformat()}
    ]
    return session


@pytest.fixture
def mock_session_with_multimodal():
    """创建包含多模态消息的模拟 session"""
    from lifeprism.llm.session import Session

    session = Mock(spec=Session)
    session.id = "test-session-789"
    session.messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "这是第一部分"},
                {"type": "text", "text": "这是第二部分"},
            ],
            "timestamp": datetime.now().isoformat(),
        },
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "我理解了，"},
                {"type": "text", "text": "让我回答你的问题"},
            ],
            "timestamp": datetime.now().isoformat(),
        },
    ]
    return session


@pytest.mark.core
class TestContinueCommand:
    """测试 /continue 命令"""

    def test_continue_with_last_two_rounds(self, agent_loop, mock_session_with_messages):
        """测试 /continue 命令返回最后两轮对话"""
        from lifeprism.llm.bus import ChannelType, InboundMessage, MessageType, OutboundMessage

        # 准备测试数据
        msg = InboundMessage(
            id="msg-001",
            channel=ChannelType.WECHAT,
            type=MessageType.CHAT,
            content=[{"type": "text", "text": "/continue test-session-123"}],
            session_id=None,
        )

        # Mock session_manager
        with patch("lifeprism.llm.agent.loop.session_manager") as mock_manager:
            mock_manager.show_session_list.return_value = ["test-session-123"]
            mock_manager.get_or_create_session.return_value = mock_session_with_messages

            # 执行
            result = agent_loop._process_cmd(msg)

            # 验证
            assert isinstance(result, OutboundMessage)
            assert result.session_id == "test-session-123"
            assert "[SUCCESS]" in result.response.content
            assert "继续会话 test-session-123" in result.response.content
            assert "最后两轮对话：" in result.response.content
            assert "能给我举个例子吗？" in result.response.content
            assert "当然可以！" in result.response.content

    def test_continue_with_few_messages(self, agent_loop, mock_session_with_few_messages):
        """测试 /continue 命令在消息少于两轮时的处理"""
        from lifeprism.llm.bus import ChannelType, InboundMessage, MessageType, OutboundMessage

        msg = InboundMessage(
            id="msg-002",
            channel=ChannelType.WECHAT,
            type=MessageType.CHAT,
            content=[{"type": "text", "text": "/continue test-session-456"}],
            session_id=None,
        )

        with patch("lifeprism.llm.agent.loop.session_manager") as mock_manager:
            mock_manager.show_session_list.return_value = ["test-session-456"]
            mock_manager.get_or_create_session.return_value = mock_session_with_few_messages

            result = agent_loop._process_cmd(msg)

            assert isinstance(result, OutboundMessage)
            assert "[SUCCESS]" in result.response.content
            assert "测试消息" in result.response.content

    def test_continue_with_multimodal_messages(self, agent_loop, mock_session_with_multimodal):
        """测试 /continue 命令处理多模态消息"""
        from lifeprism.llm.bus import ChannelType, InboundMessage, MessageType, OutboundMessage

        msg = InboundMessage(
            id="msg-003",
            channel=ChannelType.WECHAT,
            type=MessageType.CHAT,
            content=[{"type": "text", "text": "/continue test-session-789"}],
            session_id=None,
        )

        with patch("lifeprism.llm.agent.loop.session_manager") as mock_manager:
            mock_manager.show_session_list.return_value = ["test-session-789"]
            mock_manager.get_or_create_session.return_value = mock_session_with_multimodal

            result = agent_loop._process_cmd(msg)

            assert isinstance(result, OutboundMessage)
            assert "这是第一部分这是第二部分" in result.response.content
            assert "我理解了，让我回答你的问题" in result.response.content

    def test_continue_with_nonexistent_session(self, agent_loop):
        """测试 /continue 命令在 session 不存在时返回错误"""
        from lifeprism.llm.bus import ChannelType, InboundMessage, MessageType, OutboundMessage

        msg = InboundMessage(
            id="msg-004",
            channel=ChannelType.WECHAT,
            type=MessageType.CHAT,
            content=[{"type": "text", "text": "/continue nonexistent-session"}],
            session_id=None,
        )

        with patch("lifeprism.llm.agent.loop.session_manager") as mock_manager:
            mock_manager.show_session_list.return_value = ["session-1", "session-2"]

            result = agent_loop._process_cmd(msg)

            assert isinstance(result, OutboundMessage)
            assert "[ERROR]" in result.response.content
            assert "不存在" in result.response.content

    def test_continue_without_session_id(self, agent_loop):
        """测试 /continue 命令没有提供 session_id 时的错误"""
        from lifeprism.llm.bus import ChannelType, InboundMessage, MessageType, OutboundMessage

        msg = InboundMessage(
            id="msg-005",
            channel=ChannelType.WECHAT,
            type=MessageType.CHAT,
            content=[{"type": "text", "text": "/continue"}],
            session_id=None,
        )

        result = agent_loop._process_cmd(msg)

        assert isinstance(result, OutboundMessage)
        assert "[ERROR]" in result.response.content
        assert "请提供会话ID" in result.response.content


@pytest.mark.core
class TestNewCommand:
    """测试 /new 命令"""

    def test_new_with_previous_session(self, agent_loop):
        """测试 /new 命令在有上一个 session 时显示恢复提示"""
        from lifeprism.llm.bus import ChannelType, InboundMessage, MessageType, OutboundMessage

        msg = InboundMessage(
            id="msg-006",
            channel=ChannelType.WECHAT,
            type=MessageType.CHAT,
            content=[{"type": "text", "text": "/new"}],
            session_id="old-session-123",
        )

        with patch("lifeprism.llm.agent.loop.session_manager") as mock_manager:
            mock_new_session = Mock()
            mock_new_session.id = "new-session-456"
            mock_manager.get_or_create_session.return_value = mock_new_session

            result = agent_loop._process_cmd(msg)

            assert isinstance(result, OutboundMessage)
            assert result.session_id == "new-session-456"
            assert "[SUCCESS]" in result.response.content
            assert "新建会话 new-session-456" in result.response.content
            assert "恢复上一个会话" in result.response.content
            assert "/continue old-session-123" in result.response.content
            mock_manager.save_session.assert_called_once_with(mock_new_session)

    def test_new_without_previous_session(self, agent_loop):
        """测试 /new 命令在首次创建 session 时不显示恢复提示"""
        from lifeprism.llm.bus import ChannelType, InboundMessage, MessageType, OutboundMessage

        msg = InboundMessage(
            id="msg-007",
            channel=ChannelType.WECHAT,
            type=MessageType.CHAT,
            content=[{"type": "text", "text": "/new"}],
            session_id=None,
        )

        with patch("lifeprism.llm.agent.loop.session_manager") as mock_manager:
            mock_new_session = Mock()
            mock_new_session.id = "new-session-789"
            mock_manager.get_or_create_session.return_value = mock_new_session

            result = agent_loop._process_cmd(msg)

            assert isinstance(result, OutboundMessage)
            assert result.session_id == "new-session-789"
            assert "[SUCCESS]" in result.response.content
            assert "新建会话 new-session-789" in result.response.content
            # 不应该有恢复提示
            assert "恢复上一个会话" not in result.response.content
            assert (
                "/continue" not in result.response.content
                or "/continue old-session-123" not in result.response.content
            )


@pytest.mark.core
class TestCommandEdgeCases:
    """测试命令边界情况"""

    def test_continue_with_empty_session(self, agent_loop):
        """测试 /continue 命令在 session 没有消息时的处理"""
        from lifeprism.llm.bus import ChannelType, InboundMessage, MessageType, OutboundMessage
        from lifeprism.llm.session import Session

        msg = InboundMessage(
            id="msg-008",
            channel=ChannelType.WECHAT,
            type=MessageType.CHAT,
            content=[{"type": "text", "text": "/continue empty-session"}],
            session_id=None,
        )

        empty_session = Mock(spec=Session)
        empty_session.id = "empty-session"
        empty_session.messages = []

        with patch("lifeprism.llm.agent.loop.session_manager") as mock_manager:
            mock_manager.show_session_list.return_value = ["empty-session"]
            mock_manager.get_or_create_session.return_value = empty_session

            result = agent_loop._process_cmd(msg)

            assert isinstance(result, OutboundMessage)
            assert "[SUCCESS]" in result.response.content
            # 应该只有成功提示，没有"最后两轮对话"
            assert "继续会话 empty-session" in result.response.content

    def test_non_wechat_channel_returns_none(self, agent_loop):
        """测试非微信渠道的命令返回 None"""
        from lifeprism.llm.bus import ChannelType, InboundMessage, MessageType

        msg = InboundMessage(
            id="msg-009",
            channel=ChannelType.LOCAL,  # 非微信渠道
            type=MessageType.CHAT,
            content=[{"type": "text", "text": "/new"}],
            session_id=None,
        )

        result = agent_loop._process_cmd(msg)

        assert result is None
