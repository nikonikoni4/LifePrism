"""手动测试命令增强功能

由于项目存在循环导入问题，无法在pytest中正常测试 AgentLoop。
本脚本通过直接调用 _process_cmd 方法进行手动测试。
"""
from unittest.mock import Mock, patch
from datetime import datetime


def test_continue_command():
    """测试 /continue 命令增强"""
    print("=== 测试 /continue 命令 ===\n")

    # 延迟导入，避免循环导入
    from lifeprism.llm.agent.loop import AgentLoop
    from lifeprism.llm.bus import InboundMessage, ChannelType, MessageType
    from lifeprism.llm.session import Session

    # 创建 AgentLoop
    mock_bus = Mock()
    agent_loop = AgentLoop(mock_bus)

    # 创建包含消息的模拟 session
    mock_session = Mock(spec=Session)
    mock_session.id = "test-session-123"
    mock_session.messages = [
        {
            "role": "user",
            "content": "你好，我想了解一下 Python 的异步编程",
            "timestamp": datetime.now().isoformat()
        },
        {
            "role": "assistant",
            "content": "您好！Python 的异步编程主要使用 asyncio 库...",
            "timestamp": datetime.now().isoformat()
        },
        {
            "role": "user",
            "content": "能给我举个例子吗？",
            "timestamp": datetime.now().isoformat()
        },
        {
            "role": "assistant",
            "content": "当然可以！下面是一个简单的例子：\n```python\nasync def main():\n    await asyncio.sleep(1)\n```",
            "timestamp": datetime.now().isoformat()
        }
    ]

    # 测试1：正常情况 - 显示最后两轮对话
    print("测试1：正常情况 - 显示最后两轮对话")
    msg = InboundMessage(
        id="msg-001",
        channel=ChannelType.WECHAT,
        type=MessageType.CHAT,
        content=[{"type": "text", "text": "/continue test-session-123"}],
        session_id=None
    )

    with patch('lifeprism.llm.agent.loop.session_manager') as mock_manager:
        mock_manager.show_session_list.return_value = ["test-session-123"]
        mock_manager.get_or_create_session.return_value = mock_session

        result = agent_loop._process_cmd(msg)
        print(f"返回内容：\n{result.response.content}\n")

        # 验证
        assert "[SUCCESS]" in result.response.content
        assert "继续会话 test-session-123" in result.response.content
        assert "最后两轮对话:" in result.response.content
        assert "能给我举个例子吗？" in result.response.content
        assert "当然可以！" in result.response.content
        print("✓ 测试通过：成功显示最后两轮对话\n")

    # 测试2：session 不存在
    print("测试2：session 不存在")
    msg = InboundMessage(
        id="msg-002",
        channel=ChannelType.WECHAT,
        type=MessageType.CHAT,
        content=[{"type": "text", "text": "/continue nonexistent"}],
        session_id=None
    )

    with patch('lifeprism.llm.agent.loop.session_manager') as mock_manager:
        mock_manager.show_session_list.return_value = ["session-1", "session-2"]

        result = agent_loop._process_cmd(msg)
        print(f"返回内容：\n{result.response.content}\n")

        assert "[ERROR]" in result.response.content
        assert "不存在" in result.response.content
        print("✓ 测试通过：正确返回错误信息\n")


def test_new_command():
    """测试 /new 命令增强"""
    print("=== 测试 /new 命令 ===\n")

    from lifeprism.llm.agent.loop import AgentLoop
    from lifeprism.llm.bus import InboundMessage, ChannelType, MessageType

    mock_bus = Mock()
    agent_loop = AgentLoop(mock_bus)

    # 测试1：有上一个 session
    print("测试1：有上一个 session - 显示恢复提示")
    msg = InboundMessage(
        id="msg-003",
        channel=ChannelType.WECHAT,
        type=MessageType.CHAT,
        content=[{"type": "text", "text": "/new"}],
        session_id="old-session-123"
    )

    with patch('lifeprism.llm.agent.loop.session_manager') as mock_manager:
        mock_new_session = Mock()
        mock_new_session.id = "new-session-456"
        mock_manager.get_or_create_session.return_value = mock_new_session

        result = agent_loop._process_cmd(msg)
        print(f"返回内容：\n{result.response.content}\n")

        assert "[SUCCESS]" in result.response.content
        assert "新建会话 new-session-456" in result.response.content
        assert "恢复上一个会话" in result.response.content
        assert "/continue old-session-123" in result.response.content
        print("✓ 测试通过：成功显示恢复提示\n")

    # 测试2：首次创建 session
    print("测试2：首次创建 session - 不显示恢复提示")
    msg = InboundMessage(
        id="msg-004",
        channel=ChannelType.WECHAT,
        type=MessageType.CHAT,
        content=[{"type": "text", "text": "/new"}],
        session_id=None
    )

    with patch('lifeprism.llm.agent.loop.session_manager') as mock_manager:
        mock_new_session = Mock()
        mock_new_session.id = "new-session-789"
        mock_manager.get_or_create_session.return_value = mock_new_session

        result = agent_loop._process_cmd(msg)
        print(f"返回内容：\n{result.response.content}\n")

        assert "[SUCCESS]" in result.response.content
        assert "新建会话 new-session-789" in result.response.content
        assert "恢复上一个会话" not in result.response.content
        print("✓ 测试通过：正确不显示恢复提示\n")


if __name__ == "__main__":
    try:
        test_continue_command()
        test_new_command()
        print("=" * 50)
        print("所有测试通过！✓")
        print("=" * 50)
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
    except Exception as e:
        print(f"\n✗ 测试出错: {e}")
        import traceback
        traceback.print_exc()
