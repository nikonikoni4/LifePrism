"""
测试 AgentLoop 的 auto_compact 功能

测试目标：
1. 验证 auto_compact 能正确记录 last_compacted_loc
2. 验证压缩后 session 能正确保存
3. 验证 get_history_message() 能从正确位置加载消息
"""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock
from lifeprism.llm.agent.loop import AgentLoop
from lifeprism.llm.session import Session, session_manager
from lifeprism.llm.bus import MessageQueue
from lifeprism.config import settings
from lifeprism.llm.providers import LLMResponse


@pytest.mark.core
class TestAutoCompact:
    """测试 auto_compact 功能"""

    @pytest.fixture
    def agent_loop(self):
        """创建 AgentLoop 实例"""
        bus = MessageQueue()
        return AgentLoop(bus)

    @pytest.fixture
    def test_session(self):
        """创建测试用的 session，包含足够多的消息"""
        session = Session()
        # 添加多条消息模拟长对话
        for i in range(10):
            session.add_message("user", f"用户消息 {i}")
            session.add_message("assistant", f"助手回复 {i}")
        return session

    @pytest.mark.asyncio
    async def test_auto_compact_records_position(self, agent_loop, test_session):
        """测试 auto_compact 能正确记录压缩位置"""
        # 记录压缩前的消息数量
        original_message_count = len(test_session.messages)
        original_last_compacted_loc = test_session.last_compacted_loc

        # Mock estimate_prompt_tokens 使其返回超过限制的值
        # Mock LLM 调用返回压缩内容
        with patch('lifeprism.llm.agent.loop.estimate_prompt_tokens', return_value=60000), \
             patch('lifeprism.llm.agent.loop.create_llm_client') as mock_llm:

            mock_client = AsyncMock()
            mock_client.chat = AsyncMock(return_value=LLMResponse(content="压缩后的内容"))
            mock_llm.return_value = mock_client

            # 执行压缩
            tools = []
            result_session = await agent_loop.auto_compact(test_session, tools)

        # 验证：last_compacted_loc 应该被更新为压缩前的消息数量
        assert result_session.last_compacted_loc == original_message_count
        assert result_session.last_compacted_loc > original_last_compacted_loc

    @pytest.mark.asyncio
    async def test_auto_compact_adds_compressed_message(self, agent_loop, test_session):
        """测试 auto_compact 会添加压缩后的消息"""
        original_message_count = len(test_session.messages)

        # Mock 使压缩触发
        with patch('lifeprism.llm.agent.loop.estimate_prompt_tokens', return_value=60000), \
             patch('lifeprism.llm.agent.loop.create_llm_client') as mock_llm:

            mock_client = AsyncMock()
            mock_client.chat = AsyncMock(return_value=LLMResponse(content="压缩后的内容"))
            mock_llm.return_value = mock_client

            # 执行压缩
            tools = []
            result_session = await agent_loop.auto_compact(test_session, tools)

        # 验证：应该添加了一条新的 user 消息（压缩内容）
        assert len(result_session.messages) == original_message_count + 1
        # 最后一条消息应该是 user 角色
        assert result_session.messages[-1]['role'] == 'user'
        assert result_session.messages[-1]['content'] == "压缩后的内容"

    @pytest.mark.asyncio
    async def test_auto_compact_saves_session(self, agent_loop, test_session):
        """测试 auto_compact 会保存 session"""
        session_id = test_session.id
        original_last_compacted_loc = test_session.last_compacted_loc

        # Mock 使压缩触发
        with patch('lifeprism.llm.agent.loop.estimate_prompt_tokens', return_value=60000), \
             patch('lifeprism.llm.agent.loop.create_llm_client') as mock_llm:

            mock_client = AsyncMock()
            mock_client.chat = AsyncMock(return_value=LLMResponse(content="压缩后的内容"))
            mock_llm.return_value = mock_client

            # 执行压缩
            tools = []
            await agent_loop.auto_compact(test_session, tools)

        # 重新加载 session，验证保存成功
        session_manager._cache.clear()
        reloaded_session = session_manager.get_or_create_session(session_id)

        # 验证：last_compacted_loc 被正确保存
        assert reloaded_session.last_compacted_loc > original_last_compacted_loc

    @pytest.mark.asyncio
    async def test_get_history_message_after_compact(self, agent_loop, test_session):
        """测试压缩后 get_history_message() 能从正确位置加载"""
        # Mock 使压缩触发
        with patch('lifeprism.llm.agent.loop.estimate_prompt_tokens', return_value=60000), \
             patch('lifeprism.llm.agent.loop.create_llm_client') as mock_llm:

            mock_client = AsyncMock()
            mock_client.chat = AsyncMock(return_value=LLMResponse(content="压缩后的内容"))
            mock_llm.return_value = mock_client

            # 执行压缩
            tools = []
            result_session = await agent_loop.auto_compact(test_session, tools)

        # 启用自动压缩模式
        result_session.auto_compact = True

        # 获取历史消息
        history_messages = result_session.get_history_message()

        # 验证：历史消息应该从 last_compacted_loc 开始
        expected_start_index = result_session.last_compacted_loc
        expected_message_count = len(result_session.messages) - expected_start_index

        assert len(history_messages) == expected_message_count
        # 第一条消息应该是压缩后的 user 消息
        assert history_messages[0]['role'] == 'user'
        assert history_messages[0]['content'] == "压缩后的内容"

    @pytest.mark.asyncio
    async def test_auto_compact_no_compression_when_under_limit(self, agent_loop):
        """测试当 token 未超限时不进行压缩"""
        # 创建一个消息很少的 session
        small_session = Session()
        small_session.add_message("user", "测试消息")
        small_session.add_message("assistant", "测试回复")

        original_message_count = len(small_session.messages)
        original_last_compacted_loc = small_session.last_compacted_loc

        # 执行压缩（不 mock，使用真实的 token 估算）
        tools = []
        result_session = await agent_loop.auto_compact(small_session, tools)

        # 验证：因为 token 未超限，不应该进行压缩
        assert result_session is not None
        assert len(result_session.messages) == original_message_count
        assert result_session.last_compacted_loc == original_last_compacted_loc

