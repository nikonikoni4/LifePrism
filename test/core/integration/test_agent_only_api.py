"""
Agent Only FastAPI 服务集成测试

验证 Issue #24: 云端 FastAPI 服务启动。
测试 _run_agent_and_api() 函数的行为：
1. 启动时创建 FastAPI 实例并注册 sync_cloud_router
2. FastAPI 监听端口 8101
3. 只注册 sync_cloud_router，不注册其他业务路由
4. Agent Loop 和 WeChat Channel 同时启动
5. SIGINT/SIGTERM 正确停止所有任务

Mock 策略:
- Mock uvicorn（模块级）避免真实启动服务器
- Mock init_database_full() 避免数据库初始化
- Mock start_agent_and_channel() 和 stop_agent_and_channel() 避免真实启动
- 使用 asyncio.Event / 已完成任务控制函数执行流程
"""

import asyncio
import signal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.core


class TestAgentOnlyApi:
    """测试 _run_agent_and_api() 的 FastAPI + Agent Loop 启动行为"""

    # ==================== 辅助方法 ====================

    async def _setup_standard_mocks(
        self,
        mock_uvicorn: MagicMock,
        mock_init_db: MagicMock,
        mock_start_agent: AsyncMock,
        mock_stop_agent: AsyncMock,
    ):
        """设置标准 mock 环境，使 _run_agent_and_api() 能快速完成。

        - uvicorn.Server.serve() 模拟为检查 should_exit 的循环
        - start_agent_and_channel() 返回已完成的 loop_task
        - 返回 (mock_server, loop_task, mock_wechat)
        """
        # Mock uvicorn Server 和 Config
        mock_server = MagicMock()
        mock_server.should_exit = False

        async def _mock_serve():
            while not mock_server.should_exit:
                await asyncio.sleep(0.01)

        mock_server.serve = _mock_serve
        mock_uvicorn.Server.return_value = mock_server
        mock_uvicorn.Config.return_value = MagicMock()

        # Mock start_agent_and_channel - 返回已完成的 loop_task
        loop_task = asyncio.create_task(asyncio.sleep(0))
        await asyncio.sleep(0)  # 让 loop_task 完成
        mock_wechat = MagicMock()
        mock_start_agent.return_value = (loop_task, mock_wechat)

        return mock_server, loop_task, mock_wechat

    # ==================== 测试用例 ====================

    @patch("lifeprism.server.main_agent_only.stop_agent_and_channel", new_callable=AsyncMock)
    @patch("lifeprism.server.main_agent_only.start_agent_and_channel", new_callable=AsyncMock)
    @patch("lifeprism.server.main_agent_only.init_database_full")
    @patch("lifeprism.server.main_agent_only.uvicorn")
    async def test_agent_only_starts_fastapi(
        self,
        mock_uvicorn,
        mock_init_db,
        mock_start_agent,
        mock_stop_agent,
    ):
        """启动时创建 FastAPI 实例并注册 sync_cloud_router"""
        # Arrange
        await self._setup_standard_mocks(
            mock_uvicorn, mock_init_db, mock_start_agent, mock_stop_agent
        )

        # Act
        from lifeprism.server.main_agent_only import _run_agent_and_api

        await _run_agent_and_api()

        # Assert: uvicorn.Server 被调用（FastAPI 服务创建）
        mock_uvicorn.Server.assert_called_once()

        # Assert: FastAPI app 被创建并传给 uvicorn.Config
        config_call = mock_uvicorn.Config.call_args
        app = config_call.args[0]
        assert app is not None

        # Assert: sync_cloud_router 的路由已注册到 app
        route_paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/api/sync/pull" in route_paths
        assert "/api/sync/push" in route_paths
        assert "/api/sync/heartbeat" in route_paths

    @patch("lifeprism.server.main_agent_only.stop_agent_and_channel", new_callable=AsyncMock)
    @patch("lifeprism.server.main_agent_only.start_agent_and_channel", new_callable=AsyncMock)
    @patch("lifeprism.server.main_agent_only.init_database_full")
    @patch("lifeprism.server.main_agent_only.uvicorn")
    async def test_agent_only_fastapi_port_8101(
        self,
        mock_uvicorn,
        mock_init_db,
        mock_start_agent,
        mock_stop_agent,
    ):
        """FastAPI 监听端口 8101"""
        # Arrange
        await self._setup_standard_mocks(
            mock_uvicorn, mock_init_db, mock_start_agent, mock_stop_agent
        )

        # Act
        from lifeprism.server.main_agent_only import _run_agent_and_api

        await _run_agent_and_api()

        # Assert: uvicorn.Config 端口为 8101
        config_kwargs = mock_uvicorn.Config.call_args.kwargs
        assert config_kwargs.get("port") == 8101
        assert config_kwargs.get("host") == "0.0.0.0"

    @patch("lifeprism.server.main_agent_only.stop_agent_and_channel", new_callable=AsyncMock)
    @patch("lifeprism.server.main_agent_only.start_agent_and_channel", new_callable=AsyncMock)
    @patch("lifeprism.server.main_agent_only.init_database_full")
    @patch("lifeprism.server.main_agent_only.uvicorn")
    async def test_agent_only_registers_only_sync_router(
        self,
        mock_uvicorn,
        mock_init_db,
        mock_start_agent,
        mock_stop_agent,
    ):
        """只注册 sync_cloud_router，不注册其他业务路由"""
        # Arrange
        await self._setup_standard_mocks(
            mock_uvicorn, mock_init_db, mock_start_agent, mock_stop_agent
        )

        # Act
        from lifeprism.server.main_agent_only import _run_agent_and_api

        await _run_agent_and_api()

        # Assert: 获取 FastAPI app
        app = mock_uvicorn.Config.call_args.args[0]

        # 获取所有 API 路由（有 methods 属性的是 APIRoute，排除 Mount 如 /docs）
        api_routes = [r for r in app.routes if hasattr(r, "methods")]
        api_paths = {r.path for r in api_routes}

        # Assert: 所有 API 路由都在 /api/sync 下
        for path in api_paths:
            assert path.startswith("/api/sync"), "非同步路由被注册: %s" % path

        # Assert: sync 端点存在
        assert "/api/sync/pull" in api_paths
        assert "/api/sync/push" in api_paths
        assert "/api/sync/heartbeat" in api_paths
        assert "/api/sync/pull-files" in api_paths
        assert "/api/sync/push-files" in api_paths

        # Assert: 业务路由不存在
        for bp in ["/api/goals", "/api/diary", "/api/mood", "/api/todos"]:
            assert bp not in api_paths, "业务路由不应被注册: %s" % bp

    @patch("lifeprism.server.main_agent_only.stop_agent_and_channel", new_callable=AsyncMock)
    @patch("lifeprism.server.main_agent_only.start_agent_and_channel", new_callable=AsyncMock)
    @patch("lifeprism.server.main_agent_only.init_database_full")
    @patch("lifeprism.server.main_agent_only.uvicorn")
    async def test_agent_only_starts_agent_loop(
        self,
        mock_uvicorn,
        mock_init_db,
        mock_start_agent,
        mock_stop_agent,
    ):
        """Agent Loop 和 WeChat Channel 同时启动"""
        # Arrange
        _, loop_task, mock_wechat = await self._setup_standard_mocks(
            mock_uvicorn, mock_init_db, mock_start_agent, mock_stop_agent
        )

        # Act
        from lifeprism.server.main_agent_only import _run_agent_and_api

        await _run_agent_and_api()

        # Assert: 数据库初始化被调用
        mock_init_db.assert_called_once()

        # Assert: Agent Loop + Channel 启动被调用
        mock_start_agent.assert_called_once()

        # Assert: 优雅关闭被调用
        mock_stop_agent.assert_called_once()

        # Assert: stop_agent_and_channel 接收 loop_task 和 wechat_channel
        stop_args = mock_stop_agent.call_args.args
        assert stop_args[0] is loop_task
        assert stop_args[1] is mock_wechat

    @patch("lifeprism.server.main_agent_only.stop_agent_and_channel", new_callable=AsyncMock)
    @patch("lifeprism.server.main_agent_only.start_agent_and_channel", new_callable=AsyncMock)
    @patch("lifeprism.server.main_agent_only.init_database_full")
    @patch("lifeprism.server.main_agent_only.uvicorn")
    async def test_agent_only_signal_handling(
        self,
        mock_uvicorn,
        mock_init_db,
        mock_start_agent,
        mock_stop_agent,
    ):
        """SIGINT/SIGTERM 正确停止所有任务"""
        # Arrange: Mock uvicorn
        mock_server = MagicMock()
        mock_server.should_exit = False

        async def _mock_serve():
            while not mock_server.should_exit:
                await asyncio.sleep(0.01)

        mock_server.serve = _mock_serve
        mock_uvicorn.Server.return_value = mock_server
        mock_uvicorn.Config.return_value = MagicMock()

        # Arrange: loop_task 不会自行完成（模拟长期运行的 Agent Loop）
        loop_task = asyncio.create_task(asyncio.sleep(100))
        mock_wechat = MagicMock()
        mock_start_agent.return_value = (loop_task, mock_wechat)

        # Arrange: 捕获 signal.signal 注册的处理器
        captured_handlers: dict = {}

        def _fake_signal(sig, handler):
            captured_handlers[sig] = handler

        # 强制 add_signal_handler 抛出 NotImplementedError，走 signal.signal 回退
        loop = asyncio.get_running_loop()

        # Act
        from lifeprism.server.main_agent_only import _run_agent_and_api

        with patch.object(loop, "add_signal_handler", side_effect=NotImplementedError), \
             patch("lifeprism.server.main_agent_only.signal.signal", side_effect=_fake_signal):

            run_task = asyncio.create_task(_run_agent_and_api())

            # 等待信号处理器注册完成
            await asyncio.sleep(0.05)

            # 验证 SIGINT 处理器已注册
            assert signal.SIGINT in captured_handlers, "SIGINT 处理器应已注册"

            # 触发 SIGINT
            captured_handlers[signal.SIGINT](signal.SIGINT, None)

            # 等待函数完成
            await asyncio.wait_for(run_task, timeout=5)

        # Assert: 优雅关闭被调用（信号触发了停止流程）
        mock_stop_agent.assert_called_once()

        # 清理: 取消未完成的 loop_task
        loop_task.cancel()
        try:
            await loop_task
        except asyncio.CancelledError:
            pass
