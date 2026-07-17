"""
SyncClient 启动同步 + 定时同步集成测试（Issue 36）

测试 seam:
- Seam 1: 启动时立即调用 sync_once()（通过 asyncio.to_thread 在独立线程中执行）
- Seam 2: 启动时调用 start_scheduled_sync(600)（10 分钟间隔）
- Seam 3: 仅在 run_mode == "full" 时启动定时同步
- Seam 4: 启动同步失败不阻塞应用启动（日志记录 ERROR）
- Seam 5: 并发控制——启动同步通过 try_start_sync() 原子锁判断
- Seam 6: lifespan 集成——lifespan 调用 _start_sync_on_startup

Mock 策略:
- Mock SyncClient 的 sync_once() / start_scheduled_sync() / try_start_sync() / finish_sync()
- Mock settings.run_mode 控制 full / 非 full 模式
- Mock asyncio.to_thread 避免真实线程切换

参考: test/core/integration/sync/test_scheduled_sync.py
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture
def mock_sync_client():
    """创建 mock SyncClient

    默认行为：
    - try_start_sync() 返回 True（成功获取同步锁）
    - sync_once() 成功返回
    - start_scheduled_sync() 返回 mock asyncio.Task
    """
    client = MagicMock()
    client.is_syncing = False
    client.try_start_sync = MagicMock(return_value=True)
    client.finish_sync = MagicMock()
    client.sync_once = MagicMock(return_value=None)
    client.start_scheduled_sync = MagicMock(return_value=MagicMock())
    return client


@pytest.fixture
def mock_app(mock_sync_client):
    """创建 mock FastAPI app，含 state.sync_client"""
    app = MagicMock()
    app.state.sync_client = mock_sync_client
    return app


@pytest.fixture
def full_run_mode():
    """Mock settings.run_mode == 'full'"""
    with patch("lifeprism.server.main.settings") as mock_settings:
        mock_settings.run_mode = "full"
        yield mock_settings


@pytest.fixture
def non_full_run_mode():
    """Mock settings.run_mode != 'full'（云端模式）"""
    with patch("lifeprism.server.main.settings") as mock_settings:
        mock_settings.run_mode = "cloud"
        yield mock_settings


# ==================== Seam 1: 启动时立即调用 sync_once() ====================


class TestStartupSyncOnce:
    """Seam 1: 启动时立即同步一次"""

    async def test_calls_sync_once_on_startup(self, mock_app, mock_sync_client, full_run_mode):
        """启动同步：_start_sync_on_startup 调用 sync_once()"""
        from lifeprism.server.main import _start_sync_on_startup

        await _start_sync_on_startup(mock_app)

        mock_sync_client.sync_once.assert_called_once()

    async def test_calls_sync_once_via_to_thread(self, mock_app, mock_sync_client, full_run_mode):
        """启动同步通过 asyncio.to_thread 在独立线程中执行（不阻塞 lifespan）"""
        from lifeprism.server.main import _start_sync_on_startup

        with patch("lifeprism.server.main.asyncio.to_thread", new=AsyncMock()) as mock_to_thread:
            await _start_sync_on_startup(mock_app)

            mock_to_thread.assert_called_once_with(mock_sync_client.sync_once)

    async def test_logs_start_and_complete(self, mock_app, mock_sync_client, full_run_mode, caplog):
        """启动同步日志：开始 + 完成"""
        from lifeprism.server.main import _start_sync_on_startup

        caplog.set_level(logging.INFO, logger="lifeprism.server.main")
        await _start_sync_on_startup(mock_app)

        info_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
        assert any("启动同步开始" in m for m in info_messages), (
            f"未找到 '启动同步开始' INFO 日志，实际: {info_messages}"
        )
        assert any("启动同步完成" in m for m in info_messages), (
            f"未找到 '启动同步完成' INFO 日志，实际: {info_messages}"
        )


# ==================== Seam 2: 启动时调用 start_scheduled_sync(600) ====================


class TestStartupScheduledSync:
    """Seam 2: 启动定时同步循环"""

    async def test_calls_start_scheduled_sync_with_600(
        self, mock_app, mock_sync_client, full_run_mode
    ):
        """启动定时同步：调用 start_scheduled_sync(interval=600)"""
        from lifeprism.server.main import _start_sync_on_startup

        await _start_sync_on_startup(mock_app)

        mock_sync_client.start_scheduled_sync.assert_called_once_with(600)

    async def test_start_scheduled_sync_after_sync_once(
        self, mock_app, mock_sync_client, full_run_mode
    ):
        """start_scheduled_sync 在 sync_once 之后调用（顺序约束）"""
        from lifeprism.server.main import _start_sync_on_startup

        # 用 MagicMock 的副作用记录调用顺序
        call_order = []

        def _sync_once_side_effect(*args, **kwargs):
            call_order.append("sync_once")
            return None

        def _start_scheduled_side_effect(*args, **kwargs):
            call_order.append("start_scheduled_sync")
            return MagicMock()

        mock_sync_client.sync_once.side_effect = _sync_once_side_effect
        mock_sync_client.start_scheduled_sync.side_effect = _start_scheduled_side_effect

        await _start_sync_on_startup(mock_app)

        assert call_order == ["sync_once", "start_scheduled_sync"], (
            f"启动同步应在定时同步启动之前执行，实际顺序: {call_order}"
        )


# ==================== Seam 3: 仅在 run_mode == "full" 时启动定时同步 ====================


class TestRunModeGuard:
    """Seam 3: run_mode != "full" 时不启动定时同步"""

    async def test_skips_sync_once_when_not_full_mode(
        self, mock_app, mock_sync_client, non_full_run_mode
    ):
        """run_mode != 'full' 时不调用 sync_once"""
        from lifeprism.server.main import _start_sync_on_startup

        await _start_sync_on_startup(mock_app)

        mock_sync_client.sync_once.assert_not_called()

    async def test_skips_start_scheduled_sync_when_not_full_mode(
        self, mock_app, mock_sync_client, non_full_run_mode
    ):
        """run_mode != 'full' 时不调用 start_scheduled_sync"""
        from lifeprism.server.main import _start_sync_on_startup

        await _start_sync_on_startup(mock_app)

        mock_sync_client.start_scheduled_sync.assert_not_called()

    async def test_logs_skip_when_not_full_mode(
        self, mock_app, mock_sync_client, non_full_run_mode, caplog
    ):
        """非 full 模式时记录跳过日志"""
        from lifeprism.server.main import _start_sync_on_startup

        caplog.set_level(logging.INFO, logger="lifeprism.server.main")
        await _start_sync_on_startup(mock_app)

        info_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
        assert any("跳过" in m and "run_mode" in m for m in info_messages), (
            f"未找到跳过同步的 INFO 日志，实际: {info_messages}"
        )


# ==================== Seam 4: 启动同步失败不阻塞应用启动 ====================


class TestStartupSyncFailureHandling:
    """Seam 4: 启动同步失败不阻塞应用启动"""

    async def test_does_not_raise_on_sync_once_failure(
        self, mock_app, mock_sync_client, full_run_mode
    ):
        """sync_once 抛异常时 _start_sync_on_startup 不抛出"""
        from lifeprism.server.main import _start_sync_on_startup

        mock_sync_client.sync_once.side_effect = RuntimeError("网络错误")

        # 不抛出异常即可
        await _start_sync_on_startup(mock_app)

    async def test_still_starts_scheduled_sync_after_failure(
        self, mock_app, mock_sync_client, full_run_mode
    ):
        """sync_once 失败后仍启动定时同步（不阻塞后续流程）"""
        from lifeprism.server.main import _start_sync_on_startup

        mock_sync_client.sync_once.side_effect = RuntimeError("网络错误")

        await _start_sync_on_startup(mock_app)

        mock_sync_client.start_scheduled_sync.assert_called_once_with(600)

    async def test_logs_error_on_sync_once_failure(
        self, mock_app, mock_sync_client, full_run_mode, caplog
    ):
        """sync_once 失败时记录 ERROR 日志"""
        from lifeprism.server.main import _start_sync_on_startup

        caplog.set_level(logging.ERROR, logger="lifeprism.server.main")
        mock_sync_client.sync_once.side_effect = RuntimeError("连接超时")

        await _start_sync_on_startup(mock_app)

        error_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
        assert any("启动同步失败" in m for m in error_messages), (
            f"未找到 '启动同步失败' ERROR 日志，实际: {error_messages}"
        )


# ==================== Seam 5: 并发控制 - try_start_sync() 原子锁 ====================


class TestStartupSyncConcurrencyControl:
    """Seam 5: 启动同步与定时同步的并发控制"""

    async def test_calls_try_start_sync_before_sync_once(
        self, mock_app, mock_sync_client, full_run_mode
    ):
        """启动同步前调用 try_start_sync() 获取锁"""
        from lifeprism.server.main import _start_sync_on_startup

        await _start_sync_on_startup(mock_app)

        mock_sync_client.try_start_sync.assert_called_once()

    async def test_calls_finish_sync_after_sync_once(
        self, mock_app, mock_sync_client, full_run_mode
    ):
        """启动同步完成后调用 finish_sync() 释放锁"""
        from lifeprism.server.main import _start_sync_on_startup

        await _start_sync_on_startup(mock_app)

        mock_sync_client.finish_sync.assert_called_once()

    async def test_calls_finish_sync_even_on_failure(
        self, mock_app, mock_sync_client, full_run_mode
    ):
        """sync_once 抛异常后仍调用 finish_sync() 释放锁"""
        from lifeprism.server.main import _start_sync_on_startup

        mock_sync_client.sync_once.side_effect = RuntimeError("网络错误")

        await _start_sync_on_startup(mock_app)

        mock_sync_client.finish_sync.assert_called_once()

    async def test_skips_sync_once_when_lock_unavailable(
        self, mock_app, mock_sync_client, full_run_mode
    ):
        """try_start_sync() 返回 False 时跳过 sync_once（上次同步未完成）"""
        from lifeprism.server.main import _start_sync_on_startup

        mock_sync_client.try_start_sync.return_value = False

        await _start_sync_on_startup(mock_app)

        mock_sync_client.sync_once.assert_not_called()
        # 锁未获取，不应调用 finish_sync
        mock_sync_client.finish_sync.assert_not_called()

    async def test_still_starts_scheduled_sync_when_lock_unavailable(
        self, mock_app, mock_sync_client, full_run_mode
    ):
        """启动同步被跳过时，定时同步仍然启动"""
        from lifeprism.server.main import _start_sync_on_startup

        mock_sync_client.try_start_sync.return_value = False

        await _start_sync_on_startup(mock_app)

        mock_sync_client.start_scheduled_sync.assert_called_once_with(600)


# ==================== Seam 6: 无 SyncClient 时跳过 ====================


class TestNoSyncClient:
    """Seam 6: SyncClient 未创建时跳过启动同步"""

    async def test_skips_when_sync_client_is_none(self, mock_app, full_run_mode):
        """app.state.sync_client 为 None 时不抛异常"""
        from lifeprism.server.main import _start_sync_on_startup

        mock_app.state.sync_client = None

        # 不抛出异常即可
        await _start_sync_on_startup(mock_app)


# ==================== Seam 7: lifespan 集成 ====================


class TestLifespanIntegration:
    """Seam 7: lifespan 调用 _start_sync_on_startup

    由于 lifespan 函数依赖大量模块（数据库、channel、agent_loop 等），
    此处通过源码检查验证 lifespan 调用了 _start_sync_on_startup，
    配合 _start_sync_on_startup 的单元测试覆盖完整行为。
    """

    def test_lifespan_calls_start_sync_on_startup(self):
        """lifespan 函数体中用 await 调用 _start_sync_on_startup"""
        import inspect

        from lifeprism.server.main import lifespan

        source = inspect.getsource(lifespan)
        assert "await _start_sync_on_startup" in source, (
            "lifespan 函数体中未用 await 调用 _start_sync_on_startup"
        )

    def test_lifespan_calls_start_sync_after_sync_client_creation(self):
        """lifespan 中 _start_sync_on_startup 在 SyncClient 创建之后调用"""
        import inspect

        from lifeprism.server.main import lifespan

        source = inspect.getsource(lifespan)
        sync_client_pos = source.find("SyncClient created")
        start_sync_pos = source.find("_start_sync_on_startup")

        assert sync_client_pos != -1, "lifespan 中未找到 SyncClient 创建日志"
        assert start_sync_pos != -1, "lifespan 中未找到 _start_sync_on_startup 调用"
        assert start_sync_pos > sync_client_pos, (
            "_start_sync_on_startup 应在 SyncClient 创建之后调用"
        )
