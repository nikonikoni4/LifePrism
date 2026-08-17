"""
AgentLoop CONFLICT_RESOLVE 处理测试（Issue 34 + Issue 3）

测试 seam:
- Seam 1: auto_compact 不为 CONFLICT_RESOLVE 持久化 session（仅 CHAT 类型 save_session）
- Seam 2: AgentLoop _process_msg 为 CONFLICT_RESOLVE 注册 tools=[]（Issue 3 改造）
  - 改造前：注册 6 个文件工具（ReadFileTool / WriteFileTool / EditFileTool / FileTreeTool / SearchFileTool / SearchStringTool）
  - 改造后：tools = []（与 CLASSIFY 分支一致），LLM 无任何文件工具
  - 理由：CONFLICT_RESOLVE 是纯文本合并任务，输入已在 InboundMessage.content 中提供，
          无需任何工具。消除 behavior.md 被破坏事件的根本风险。

TDD: 严格 red-green 循环
"""

from unittest.mock import AsyncMock, patch

import pytest

from lifeprism.llm.agent.loop import AgentLoop
from lifeprism.llm.bus import InboundMessage, MessageQueue, MessageType
from lifeprism.llm.providers import LLMResponse
from lifeprism.llm.session import Session

pytestmark = pytest.mark.core


@pytest.fixture
def agent_loop():
    """创建 AgentLoop 实例"""
    bus = MessageQueue()
    return AgentLoop(bus)


@pytest.fixture
def large_session():
    """创建包含足够多消息的 session 以触发压缩"""
    session = Session()
    for i in range(10):
        session.add_message("user", f"用户消息 {i}")
        session.add_message("assistant", f"助手回复 {i}")
    return session


# ==================== Seam 1: auto_compact save_session 守卫 ====================


class TestAutoCompactSaveSessionGuard:
    """Seam 1: auto_compact 仅对 CHAT 类型调用 save_session

    CONFLICT_RESOLVE 不保存到 session/*.jsonl，
    需在 auto_compact 内部的 save_session 调用前增加 if msg.type == MessageType.CHAT 判断。
    """

    @pytest.mark.asyncio
    async def test_auto_compact_saves_session_for_chat_type(self, agent_loop, large_session):
        """CHAT 类型触发压缩时应调用 save_session"""
        chat_msg = InboundMessage(type=MessageType.CHAT, content="测试")

        with (
            patch("lifeprism.llm.agent.loop.estimate_prompt_tokens", return_value=60000),
            patch("lifeprism.llm.agent.loop.create_llm_client") as mock_llm,
            patch("lifeprism.llm.agent.loop.session_manager") as mock_sm,
        ):
            mock_client = AsyncMock()
            mock_client.chat = AsyncMock(return_value=LLMResponse(content="压缩内容"))
            mock_llm.return_value = mock_client

            await agent_loop.auto_compact(large_session, [], chat_msg)

            # CHAT 类型应调用 save_session
            mock_sm.save_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_compact_does_not_save_session_for_conflict_resolve(
        self, agent_loop, large_session
    ):
        """CONFLICT_RESOLVE 类型触发压缩时不应调用 save_session"""
        conflict_msg = InboundMessage(
            type=MessageType.CONFLICT_RESOLVE,
            content="## 文件冲突需要解决",
            extra={"conflict_file_path": "diary/test.md", "system_prompt": "你是合并助手。"},
        )

        with (
            patch("lifeprism.llm.agent.loop.estimate_prompt_tokens", return_value=60000),
            patch("lifeprism.llm.agent.loop.create_llm_client") as mock_llm,
            patch("lifeprism.llm.agent.loop.session_manager") as mock_sm,
        ):
            mock_client = AsyncMock()
            mock_client.chat = AsyncMock(return_value=LLMResponse(content="压缩内容"))
            mock_llm.return_value = mock_client

            result_session = await agent_loop.auto_compact(large_session, [], conflict_msg)

            # CONFLICT_RESOLVE 类型不应调用 save_session
            mock_sm.save_session.assert_not_called()
            # session 对象照常使用（压缩逻辑仍然执行）
            assert result_session.last_compacted_loc > 0


# ==================== Seam 2: AgentLoop CONFLICT_RESOLVE 工具注册（Issue 3: tools=[]） ====================


class TestConflictResolveToolRegistration:
    """Seam 2: CONFLICT_RESOLVE 注册 tools=[]（Issue 3 改造）

    改造前：注册 6 个文件工具（ReadFileTool / WriteFileTool / EditFileTool / FileTreeTool / SearchFileTool / SearchStringTool）
    改造后：tools = []（与 CLASSIFY 分支一致），LLM 无任何文件工具

    - 验证 tools 列表长度为 0
    - 验证没有 ReadFileTool / WriteFileTool / EditFileTool / FileTreeTool / SearchFileTool / SearchStringTool 实例
    - 验证没有数据库工具实例（保持原有约束）
    - 参考 CLASSIFY 分支的测试模式
    """

    @pytest.mark.asyncio
    async def test_conflict_resolve_tools_length_is_zero(self, agent_loop):
        """CONFLICT_RESOLVE 应注册 tools=[]（长度为 0）

        参考 CLASSIFY 分支：tools = []
        """
        conflict_msg = InboundMessage(
            type=MessageType.CONFLICT_RESOLVE,
            content="## 文件冲突需要解决",
            extra={"conflict_file_path": "diary/test.md", "system_prompt": "你是合并助手"},
        )

        captured = {}

        async def mock_run_agent_loop(session, prefix_messages, tools, tool_registry):
            captured["tools"] = tools
            captured["registry"] = tool_registry
            return LLMResponse(content="合并后的内容"), []

        with (
            patch.object(agent_loop, "_run_agent_loop", side_effect=mock_run_agent_loop),
            patch("lifeprism.llm.agent.loop.session_manager") as mock_sm,
            patch(
                "lifeprism.llm.agent.loop.Context.build_prefix_messages",
                return_value=[{"role": "system", "content": "系统提示"}],
            ),
            patch.object(
                agent_loop, "auto_compact", new_callable=AsyncMock, return_value=Session()
            ),
        ):
            mock_sm.get_or_create_session.return_value = Session()
            await agent_loop._process_msg(conflict_msg)

        # 验证 tools 列表长度为 0
        assert captured["tools"] == []
        assert len(captured["tools"]) == 0

    @pytest.mark.asyncio
    async def test_conflict_resolve_does_not_register_file_tools(self, agent_loop):
        """CONFLICT_RESOLVE 不应注册任何文件工具（Issue 3 改造）

        改造前会注册：read_file, write_file, edit_file, file_tree_py, search_file_py, search_string_py
        改造后应全部不注册
        """
        conflict_msg = InboundMessage(
            type=MessageType.CONFLICT_RESOLVE,
            content="## 文件冲突需要解决",
            extra={"conflict_file_path": "diary/test.md", "system_prompt": "你是合并助手"},
        )

        captured = {}

        async def mock_run_agent_loop(session, prefix_messages, tools, tool_registry):
            captured["registry"] = tool_registry
            return LLMResponse(content="合并后的内容"), []

        with (
            patch.object(agent_loop, "_run_agent_loop", side_effect=mock_run_agent_loop),
            patch("lifeprism.llm.agent.loop.session_manager") as mock_sm,
            patch(
                "lifeprism.llm.agent.loop.Context.build_prefix_messages",
                return_value=[{"role": "system", "content": "系统提示"}],
            ),
            patch.object(
                agent_loop, "auto_compact", new_callable=AsyncMock, return_value=Session()
            ),
        ):
            mock_sm.get_or_create_session.return_value = Session()
            await agent_loop._process_msg(conflict_msg)

        # 验证文件工具未注册
        tool_names = captured["registry"].tool_names
        assert "read_file" not in tool_names
        assert "write_file" not in tool_names
        assert "edit_file" not in tool_names
        assert "file_tree_py" not in tool_names
        assert "search_file_py" not in tool_names
        assert "search_string_py" not in tool_names

    @pytest.mark.asyncio
    async def test_conflict_resolve_does_not_register_db_tools(self, agent_loop):
        """CONFLICT_RESOLVE 不应注册数据库工具（保持原有约束）"""
        conflict_msg = InboundMessage(
            type=MessageType.CONFLICT_RESOLVE,
            content="## 文件冲突需要解决",
            extra={"conflict_file_path": "diary/test.md", "system_prompt": "你是合并助手"},
        )

        captured = {}

        async def mock_run_agent_loop(session, prefix_messages, tools, tool_registry):
            captured["registry"] = tool_registry
            return LLMResponse(content="合并后的内容"), []

        with (
            patch.object(agent_loop, "_run_agent_loop", side_effect=mock_run_agent_loop),
            patch("lifeprism.llm.agent.loop.session_manager") as mock_sm,
            patch(
                "lifeprism.llm.agent.loop.Context.build_prefix_messages",
                return_value=[{"role": "system", "content": "系统提示"}],
            ),
            patch.object(
                agent_loop, "auto_compact", new_callable=AsyncMock, return_value=Session()
            ),
        ):
            mock_sm.get_or_create_session.return_value = Session()
            await agent_loop._process_msg(conflict_msg)

        # 验证数据库工具未注册
        tool_names = captured["registry"].tool_names
        assert "query_user_activity_summary" not in tool_names
        assert "query_user_activity_log" not in tool_names
        assert "create_or_update_user_behavior_note" not in tool_names
        assert "query_user_mood" not in tool_names
        assert "create_user_mood" not in tool_names

    @pytest.mark.asyncio
    async def test_conflict_resolve_registry_has_no_tools(self, agent_loop):
        """CONFLICT_RESOLVE 的 tool_registry 应没有任何注册的工具"""
        conflict_msg = InboundMessage(
            type=MessageType.CONFLICT_RESOLVE,
            content="## 文件冲突需要解决",
            extra={"conflict_file_path": "diary/test.md", "system_prompt": "你是合并助手"},
        )

        captured = {}

        async def mock_run_agent_loop(session, prefix_messages, tools, tool_registry):
            captured["registry"] = tool_registry
            return LLMResponse(content="合并后的内容"), []

        with (
            patch.object(agent_loop, "_run_agent_loop", side_effect=mock_run_agent_loop),
            patch("lifeprism.llm.agent.loop.session_manager") as mock_sm,
            patch(
                "lifeprism.llm.agent.loop.Context.build_prefix_messages",
                return_value=[{"role": "system", "content": "系统提示"}],
            ),
            patch.object(
                agent_loop, "auto_compact", new_callable=AsyncMock, return_value=Session()
            ),
        ):
            mock_sm.get_or_create_session.return_value = Session()
            await agent_loop._process_msg(conflict_msg)

        # 验证 tool_registry 完全为空
        assert len(captured["registry"].tool_names) == 0
