"""
Monitor 模块平台隔离单元测试

验证 main.py 中 Monitor 启动逻辑的平台检查行为：
1. 非 Windows 平台 → 跳过 Monitor 启动 + 记录 warning
2. Windows 平台 → 正常启动 Monitor
3. Windows 平台但依赖缺失（ImportError）→ 优雅降级

通过 mock lifespan 的所有重依赖来隔离 Monitor 逻辑。
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lifeprism.config.settings_manager import settings

pytestmark = pytest.mark.core


@pytest.fixture
def mock_app():
    """Mock FastAPI app with state"""
    app = MagicMock()
    app.state = MagicMock()
    return app


@pytest.fixture
def mock_lifespan_deps():
    """
    Mock main.py lifespan 中的所有重依赖，使 lifespan 能快速运行完毕。

    策略：
    - 模块级导入（init_database 等）在 main.py 命名空间中 patch
    - 延迟导入（wechat_channel、agent_loop 等）用完整对象替换
    """
    # 创建 mock 对象
    mock_wechat = MagicMock()
    mock_wechat.start = AsyncMock()
    mock_wechat.stop = AsyncMock()
    mock_wechat._running = False

    mock_agent = MagicMock()
    mock_agent.loop = AsyncMock()

    mock_schedule = MagicMock()

    patches = [
        # --- 模块级导入：patch at lifeprism.server.main.<name> ---
        patch("lifeprism.server.main.init_database"),
        patch("lifeprism.server.main.run_migrations"),
        patch("lifeprism.server.main.initialize_default_data"),
        patch("lifeprism.server.main.initialize_category_colors"),
        patch("lifeprism.server.main.initialize_resources"),
        # --- 延迟导入：替换源模块中的对象 ---
        patch("lifeprism.utils.logger.enable_uvicorn_file_logging"),
        patch("lifeprism.llm.channel.wechat_channel", mock_wechat),
        patch("lifeprism.server.services.schedule_service.schedule_service", mock_schedule),
        patch("lifeprism.llm.agent.loop.agent_loop", mock_agent),
    ]

    for p in patches:
        p.start()

    yield

    for p in patches:
        p.stop()


class TestMonitorPlatformCheck:
    """测试 Monitor 启动的平台检查逻辑"""

    @pytest.mark.asyncio
    async def test_monitor_skipped_on_linux(self, mock_app, mock_lifespan_deps):
        """非 Windows 平台：monitor_type='lifeprism' 但跳过启动，记录 warning"""
        from lifeprism.server.main import lifespan

        with patch("sys.platform", "linux"), \
             patch.object(settings, "_config", {"monitor_type": "lifeprism"}):
            async with lifespan(mock_app):
                pass

        # Monitor 未启动
        assert mock_app.state.monitor_process is None

    @pytest.mark.asyncio
    async def test_monitor_skipped_on_darwin(self, mock_app, mock_lifespan_deps):
        """macOS 平台同样跳过 Monitor"""
        from lifeprism.server.main import lifespan

        with patch("sys.platform", "darwin"), \
             patch.object(settings, "_config", {"monitor_type": "lifeprism"}):
            async with lifespan(mock_app):
                pass

        assert mock_app.state.monitor_process is None

    @pytest.mark.asyncio
    async def test_monitor_started_on_windows(self, mock_app, mock_lifespan_deps):
        """Windows 平台：monitor_type='lifeprism' → 正常启动 Monitor"""
        from lifeprism.server.main import lifespan

        mock_process = MagicMock()
        mock_process.is_alive.return_value = False  # shutdown 时不需 terminate

        # 注入 mock 模块，使 from lifeprism.monitor.windows_monitor.main import start_monitor_process 可用
        mock_monitor_main = MagicMock()
        mock_monitor_main.start_monitor_process = MagicMock(return_value=mock_process)

        with patch("sys.platform", "win32"), \
             patch.object(settings, "_config", {"monitor_type": "lifeprism"}), \
             patch.dict(sys.modules, {
                 "lifeprism.monitor.windows_monitor": MagicMock(),
                 "lifeprism.monitor.windows_monitor.main": mock_monitor_main,
             }):
            async with lifespan(mock_app):
                pass

        # Monitor 启动成功
        assert mock_app.state.monitor_process is mock_process

    @pytest.mark.asyncio
    async def test_monitor_import_error_handled(self, mock_app, mock_lifespan_deps):
        """Windows 平台但 Monitor 依赖缺失（ImportError）→ 优雅降级"""
        from lifeprism.server.main import lifespan

        # 将模块设为 None 模拟 ImportError
        with patch("sys.platform", "win32"), \
             patch.object(settings, "_config", {"monitor_type": "lifeprism"}), \
             patch.dict(sys.modules, {
                 "lifeprism.monitor.windows_monitor": MagicMock(),
                 "lifeprism.monitor.windows_monitor.main": None,
             }):
            async with lifespan(mock_app):
                pass

        # 优雅降级：monitor_process 为 None，不崩溃
        assert mock_app.state.monitor_process is None

    @pytest.mark.asyncio
    async def test_monitor_not_configured(self, mock_app, mock_lifespan_deps):
        """monitor_type 不为 'lifeprism' → 不启动 Monitor（与平台无关）"""
        from lifeprism.server.main import lifespan

        with patch("sys.platform", "win32"), \
             patch.object(settings, "_config", {"monitor_type": "none"}):
            async with lifespan(mock_app):
                pass

        assert mock_app.state.monitor_process is None
