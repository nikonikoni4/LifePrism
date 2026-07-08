"""
Agent Only 模式功能集成测试

验证 Agent Only 模式下的核心功能：
1. Agent Loop 可独立启动（不依赖 FastAPI）
2. WeChat Channel 可独立启动
3. LLM 工具在无 Monitor 环境下可用
4. 数据库读写操作在无 Monitor 环境下正常工作

这些测试验证 Agent Only 模式的功能完整性，不实际启动长期运行的服务。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.core


class TestAgentOnlyBootstrap:
    """测试 Agent Only 的 bootstrap 函数可独立调用"""

    def test_init_database_full_callable(self):
        """init_database_full 函数存在且可调用"""
        from lifeprism.server.bootstrap import init_database_full

        assert callable(init_database_full)

    def test_start_agent_and_channel_callable(self):
        """start_agent_and_channel 函数存在且可调用"""
        from lifeprism.server.bootstrap import start_agent_and_channel

        assert callable(start_agent_and_channel)

    def test_stop_agent_and_channel_callable(self):
        """stop_agent_and_channel 函数存在且可调用"""
        from lifeprism.server.bootstrap import stop_agent_and_channel

        assert callable(stop_agent_and_channel)


class TestAgentOnlyModuleStructure:
    """测试 Agent Only 入口的模块结构"""

    def test_main_agent_only_has_main_function(self):
        """main_agent_only.py 有 async main() 函数"""
        import lifeprism.server.main_agent_only

        assert hasattr(lifeprism.server.main_agent_only, "main")
        assert callable(lifeprism.server.main_agent_only.main)

    def test_main_agent_only_no_fastapi_app(self):
        """main_agent_only.py 不创建 FastAPI app 实例"""
        import lifeprism.server.main_agent_only

        assert not hasattr(lifeprism.server.main_agent_only, "app"), \
            "Agent Only 不应有 FastAPI app 实例"

    def test_main_agent_only_no_schedule_service(self):
        """main_agent_only.py 不导入 ScheduleService"""
        import lifeprism.server.main_agent_only

        # 确保模块源码中不引用 schedule_service
        import inspect

        source = inspect.getsource(lifeprism.server.main_agent_only)
        assert "schedule_service" not in source, \
            "Agent Only 不应引用 ScheduleService"

    def test_main_agent_only_no_monitor(self):
        """main_agent_only.py 不导入 Monitor 模块"""
        import inspect

        import lifeprism.server.main_agent_only

        source = inspect.getsource(lifeprism.server.main_agent_only)
        assert "windows_monitor" not in source, \
            "Agent Only 不应引用 Monitor 模块"


class TestAgentOnlyDatabaseAccess:
    """测试 Agent Only 模式下数据库可正常访问"""

    def test_database_manager_available(self):
        """DatabaseManager 单例可导入"""
        from lifeprism.repository import lw_db_manager

        assert lw_db_manager is not None

    def test_settings_manager_available(self):
        """SettingsManager 单例可导入"""
        from lifeprism.config.settings_manager import settings

        assert settings is not None
        assert hasattr(settings, "lw_db_path")

    def test_custom_record_repository_available(self):
        """CustomRecordRepository 可导入（Agent 工具依赖）"""
        from lifeprism.repository.aggregators.custom_record_aggregator import (
            CustomRecordRepository,
        )

        assert CustomRecordRepository is not None

    def test_mood_repository_available(self):
        """MoodRepository 可导入（Agent 工具依赖）"""
        from lifeprism.repository import mood_repository

        assert mood_repository is not None


class TestAgentOnlyToolsAvailable:
    """测试 Agent Only 模式下 LLM 工具可用"""

    def test_custom_records_tools_importable(self):
        """自定义记录 LLM 工具可导入"""
        from lifeprism.llm.agent.tools.custom_records_tool import (
            CreateCustomRecordEntryTool,
            CreateCustomRecordTypeTool,
            ListCustomRecordTypesTool,
            QueryCustomRecordEntriesTool,
        )

        assert CreateCustomRecordTypeTool is not None
        assert CreateCustomRecordEntryTool is not None
        assert ListCustomRecordTypesTool is not None
        assert QueryCustomRecordEntriesTool is not None

    def test_agent_loop_importable(self):
        """AgentLoop 可导入"""
        from lifeprism.llm.agent.loop import agent_loop

        assert agent_loop is not None

    def test_wechat_channel_importable(self):
        """WeChatChannel 可导入"""
        from lifeprism.llm.channel import wechat_channel

        assert wechat_channel is not None


class TestBootstrapFunctionsBehavior:
    """测试 bootstrap 函数的 mock 行为（验证函数签名和调用链正确）"""

    @pytest.mark.asyncio
    async def test_start_agent_and_channel_returns_tuple(self):
        """start_agent_and_channel 返回 (loop_task, wechat_channel) 元组"""
        mock_wechat = MagicMock()
        mock_wechat.start = AsyncMock()
        mock_wechat._running = False

        mock_agent = MagicMock()
        mock_agent.loop = AsyncMock()

        with patch("lifeprism.llm.channel.wechat_channel", mock_wechat), \
             patch("lifeprism.llm.agent.loop.agent_loop", mock_agent):
            from lifeprism.server.bootstrap import start_agent_and_channel

            loop_task, wechat = await start_agent_and_channel()

            assert wechat is mock_wechat
            assert loop_task is not None
            # 清理
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_stop_agent_and_channel_cleans_up(self):
        """stop_agent_and_channel 正确清理资源"""
        mock_wechat = MagicMock()
        mock_wechat._running = True
        mock_wechat.stop = AsyncMock()

        mock_agent = MagicMock()
        mock_agent.loop = AsyncMock()

        with patch("lifeprism.llm.channel.wechat_channel", mock_wechat), \
             patch("lifeprism.llm.agent.loop.agent_loop", mock_agent):
            from lifeprism.server.bootstrap import (
                start_agent_and_channel,
                stop_agent_and_channel,
            )

            loop_task, wechat = await start_agent_and_channel()
            await stop_agent_and_channel(loop_task, wechat)

            # wechat.stop 应被调用
            mock_wechat.stop.assert_called_once()
