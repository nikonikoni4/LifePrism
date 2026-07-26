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
    # SSH 隧道生命周期方法（async，需 AsyncMock）
    client._start_ssh_tunnel = AsyncMock(return_value=None)
    client._stop_ssh_tunnel = AsyncMock(return_value=None)
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


# ==================== Seam 8: SSH 隧道集成（Issue 05） ====================


def _make_ssh_mock_settings(
    run_mode: str = "full",
    connection_mode: str = "ssh",
    private_key: str | None = "fake-private-key",
    remote_url: str = "http://real-cloud.example.com:8102",
    local_port: int = 8102,
):
    """构造 mock settings 对象，用于 SSH 隧道测试

    Args:
        run_mode: 部署模式（full / agent_only / web_demo）
        connection_mode: 连接方式（http / ssh）
        private_key: 私钥值，None 表示无私钥
        remote_url: sync.remote_url 配置值
        local_port: SSH 隧道本地监听端口

    Returns:
        MagicMock: 模拟 settings 单例
    """
    mock_settings = MagicMock()
    mock_settings.run_mode = run_mode

    def get_side_effect(key, default=None):
        values = {
            "sync.connection_mode": connection_mode,
            "sync.remote_url": remote_url,
            "sync.ssh_tunnel.host": "example.com",
            "sync.ssh_tunnel.port": 22,
            "sync.ssh_tunnel.username": "testuser",
            "sync.ssh_tunnel.local_port": local_port,
            "sync.ssh_tunnel.remote_host": "127.0.0.1",
            "sync.ssh_tunnel.remote_port": 8102,
            "sync.last_sync_time": "",
        }
        return values.get(key, default)

    mock_settings.get.side_effect = get_side_effect
    mock_settings.get_storage_key.return_value = private_key
    return mock_settings


class TestSSHTunnelIntegration:
    """Seam 8: SyncClient SSH 隧道编排 + _read_remote_url() 拦截

    测试 SSH 隧道模式下的 SyncClient 行为：
    - 三层守卫判断（run_mode + connection_mode + 私钥存在性）
    - _read_remote_url() SSH 模式拦截
    - sync_once 在隧道未就绪时跳过 + WARNING
    - 隧道连接失败时记录 ERROR（不阻塞 SyncClient 启动）
    - HTTP 模式行为完全不变（向后兼容）

    参考:
    - Issue: .scratch/ssh-tunnel-integration/issues/05-syncclient-ssh-integration.md
    - 规则: docs/coding-rules/sync-remote-url-access-rules.md
    """

    @pytest.fixture
    def ssh_sync_client(self):
        """创建 SyncClient 实例，db 和 sync_repository 为 MagicMock

        用于测试 SSH 隧道编排逻辑，不依赖真实数据库。
        """
        from lifeprism.sync.sync_client import SyncClient

        client = SyncClient(
            db_manager=MagicMock(),
            sync_repository=MagicMock(),
        )
        return client

    # ===== Test 1: SSH 模式 + 隧道就绪 → sync_once 正常执行 + remote_url 为 localhost =====

    async def test_ssh_mode_tunnel_ready_sync_once_runs_with_localhost(
        self, ssh_sync_client, caplog
    ):
        """connection_mode=ssh + 隧道就绪 → sync_once 正常执行 + remote_url 为 localhost"""
        client = ssh_sync_client

        # 模拟隧道已就绪
        mock_tunnel = MagicMock()
        mock_tunnel.is_connected = True
        client._ssh_tunnel = mock_tunnel

        mock_settings = _make_ssh_mock_settings(connection_mode="ssh")

        with (
            patch("lifeprism.config.settings_manager.settings", mock_settings),
            patch(
                "lifeprism.sync.sync_config.get_sync_api_key",
                return_value="fake-api-key",
            ),
            patch.object(client, "_check_cloud_initialized", return_value=True),
            patch.object(client, "_pull_deletion_log"),
            patch.object(client, "pull_from_remote"),
            patch.object(client, "_push_deletion_log"),
            patch.object(client, "push_to_remote"),
            patch.object(client, "_sync_files_full_flow"),
            patch.object(client, "_cleanup_deletion_log"),
        ):
            # 1. 验证 _read_remote_url 返回 localhost
            remote_url = client._read_remote_url()
            assert remote_url == "http://localhost:8102", (
                f"SSH 模式 + 隧道就绪时应返回 localhost，实际: {remote_url}"
            )

            # 2. 验证 sync_once 正常执行（不抛异常、不跳过）
            client.sync_once(tables=[], directories=[])

            # 3. 验证内部同步方法被调用（说明 sync_once 正常执行，没有跳过）
            assert client.pull_from_remote.called, "sync_once 应正常调用 pull_from_remote"
            assert client.push_to_remote.called, "sync_once 应正常调用 push_to_remote"

    # ===== Test 2: SSH 模式 + 隧道连接失败 → sync_once 跳过 + 记录 ERROR =====

    async def test_ssh_mode_tunnel_failed_logs_error_and_skips_sync(
        self, ssh_sync_client, caplog
    ):
        """connection_mode=ssh + 隧道连接失败 → 记录 ERROR + sync_once 跳过"""
        client = ssh_sync_client
        caplog.set_level(logging.ERROR, logger="lifeprism.sync.sync_client")

        from lifeprism.utils.exceptions import ExternalServiceError

        mock_tunnel_cls = MagicMock()
        mock_tunnel_instance = MagicMock()
        mock_tunnel_instance.connect = AsyncMock(
            side_effect=ExternalServiceError(
                message="SSH 连接失败：密钥被拒绝",
                code="SSH_KEY_REJECTED",
            )
        )
        mock_tunnel_cls.return_value = mock_tunnel_instance

        mock_settings = _make_ssh_mock_settings(connection_mode="ssh")

        with (
            patch("lifeprism.config.settings_manager.settings", mock_settings),
            patch("lifeprism.sync.ssh_tunnel.SSHTunnel", mock_tunnel_cls),
        ):
            # 1. 启动隧道：不应抛异常（不阻塞 SyncClient）
            await client._start_ssh_tunnel()

            # 2. 验证 ERROR 日志
            error_messages = [
                r.getMessage() for r in caplog.records if r.levelno == logging.ERROR
            ]
            assert any("SSH 隧道启动失败" in m for m in error_messages), (
                f"未找到 'SSH 隧道启动失败' ERROR 日志，实际: {error_messages}"
            )

            # 3. 验证隧道未就绪 → sync_once 跳过
            assert client._is_tunnel_ready() is False, "隧道连接失败后 _is_tunnel_ready 应为 False"

    # ===== Test 3: HTTP 模式 → 不启动隧道 + 走原 remote_url =====

    async def test_http_mode_no_tunnel_original_remote_url(self, ssh_sync_client):
        """connection_mode=http → _should_use_ssh_tunnel 返回 False + 走原 remote_url"""
        client = ssh_sync_client
        mock_settings = _make_ssh_mock_settings(
            connection_mode="http",
            remote_url="http://real-cloud.example.com:8102",
        )

        with patch("lifeprism.config.settings_manager.settings", mock_settings):
            # 1. HTTP 模式不应启用 SSH 隧道
            assert client._should_use_ssh_tunnel() is False, (
                "HTTP 模式下 _should_use_ssh_tunnel 应返回 False"
            )

            # 2. _read_remote_url 应返回原 sync.remote_url 配置值
            remote_url = client._read_remote_url()
            assert remote_url == "http://real-cloud.example.com:8102", (
                f"HTTP 模式应返回原 remote_url，实际: {remote_url}"
            )

    # ===== Test 4: run_mode != full → 不启动隧道（云端守卫）=====

    async def test_non_full_mode_no_tunnel_cloud_guard(self, ssh_sync_client):
        """run_mode != full → _should_use_ssh_tunnel 返回 False（云端守卫）"""
        client = ssh_sync_client
        mock_settings = _make_ssh_mock_settings(
            run_mode="agent_only",
            connection_mode="ssh",
            remote_url="http://real-cloud.example.com:8102",
        )

        with patch("lifeprism.config.settings_manager.settings", mock_settings):
            # 1. 云端模式不应启用 SSH 隧道（三层守卫第 1 层）
            assert client._should_use_ssh_tunnel() is False, (
                "run_mode != full 时 _should_use_ssh_tunnel 应返回 False（云端守卫）"
            )

            # 2. _read_remote_url 应返回原 remote_url（不走 SSH 隧道）
            remote_url = client._read_remote_url()
            assert remote_url == "http://real-cloud.example.com:8102", (
                f"云端模式应返回原 remote_url，实际: {remote_url}"
            )

    # ===== Test 5: 隧道未就绪 → sync_once 跳过 + 记录 WARNING =====

    async def test_tunnel_not_ready_sync_once_skipped_with_warning(
        self, ssh_sync_client, caplog
    ):
        """SSH 模式 + 隧道未就绪 → sync_once 跳过 + 记录 WARNING"""
        client = ssh_sync_client
        # _ssh_tunnel 为 None（隧道未启动）
        client._ssh_tunnel = None
        caplog.set_level(logging.WARNING, logger="lifeprism.sync.sync_client")

        mock_settings = _make_ssh_mock_settings(connection_mode="ssh")

        with (
            patch("lifeprism.config.settings_manager.settings", mock_settings),
            patch(
                "lifeprism.sync.sync_config.get_sync_api_key",
                return_value="fake-api-key",
            ),
        ):
            # 1. 验证 _read_remote_url 返回空字符串
            remote_url = client._read_remote_url()
            assert remote_url == "", (
                f"SSH 模式 + 隧道未就绪时应返回空字符串，实际: {remote_url}"
            )

            # 2. 验证 sync_once 跳过（不抛 ValidationError）+ WARNING 日志
            client.sync_once(tables=[], directories=[])

            warning_messages = [
                r.getMessage() for r in caplog.records if r.levelno == logging.WARNING
            ]
            assert any("SSH 隧道未就绪" in m for m in warning_messages), (
                f"未找到 'SSH 隧道未就绪' WARNING 日志，实际: {warning_messages}"
            )

    # ===== Test 6: 隧道存在 → 调用 close() + 清理引用 =====

    async def test_stop_ssh_tunnel_closes_tunnel_when_active(self, ssh_sync_client):
        """隧道存在时调用 close()，验证 _ssh_tunnel 被置 None"""
        client = ssh_sync_client

        mock_tunnel = MagicMock()
        mock_tunnel.close = AsyncMock()
        client._ssh_tunnel = mock_tunnel
        client._ssh_tunnel_keep_alive_task = None

        await client._stop_ssh_tunnel()

        mock_tunnel.close.assert_awaited_once()
        assert client._ssh_tunnel is None, "_ssh_tunnel 应在 close() 后被置 None"

    # ===== Test 7: 隧道不存在 → 幂等返回 =====

    async def test_stop_ssh_tunnel_noop_when_no_tunnel(self, ssh_sync_client):
        """隧道不存在时调用不抛异常（幂等）"""
        client = ssh_sync_client
        client._ssh_tunnel = None
        client._ssh_tunnel_keep_alive_task = None

        # 不抛异常即可
        await client._stop_ssh_tunnel()

        assert client._ssh_tunnel is None
        assert client._ssh_tunnel_keep_alive_task is None

    # ===== Test 8: close() 抛异常 → 不阻塞 + 仍清理引用 =====

    async def test_stop_ssh_tunnel_handles_close_exception(
        self, ssh_sync_client, caplog
    ):
        """tunnel.close() 抛异常时不阻塞流程，_ssh_tunnel 仍被置 None"""
        client = ssh_sync_client
        caplog.set_level(logging.WARNING, logger="lifeprism.sync.sync_client")

        mock_tunnel = MagicMock()
        mock_tunnel.close = AsyncMock(side_effect=RuntimeError("close 失败"))
        client._ssh_tunnel = mock_tunnel
        client._ssh_tunnel_keep_alive_task = None

        # 不抛异常即可
        await client._stop_ssh_tunnel()

        # finally 块仍清理引用
        assert client._ssh_tunnel is None, (
            "close() 抛异常后 _ssh_tunnel 仍应被置 None（finally 兜底）"
        )

        warning_messages = [
            r.getMessage() for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any("关闭 SSH 隧道时出错" in m for m in warning_messages), (
            f"未找到 '关闭 SSH 隧道时出错' WARNING 日志，实际: {warning_messages}"
        )

    # ===== Test 9: keep-alive 任务存在 → 被等待退出 =====

    async def test_stop_ssh_tunnel_waits_for_keep_alive_task(self, ssh_sync_client):
        """keep-alive 任务存在时被等待退出"""
        client = ssh_sync_client

        mock_tunnel = MagicMock()
        mock_tunnel.close = AsyncMock()
        client._ssh_tunnel = mock_tunnel

        # 创建一个会快速完成的 keep-alive 任务
        async def quick_keep_alive():
            await asyncio.sleep(0.05)

        keep_alive_task = asyncio.create_task(quick_keep_alive())
        client._ssh_tunnel_keep_alive_task = keep_alive_task

        await client._stop_ssh_tunnel()

        # 验证 keep-alive 任务已退出（不再 pending）
        assert keep_alive_task.done(), "keep-alive 任务应被等待退出"
        assert client._ssh_tunnel_keep_alive_task is None, (
            "_ssh_tunnel_keep_alive_task 应在等待结束后被置 None"
        )

    # ===== Test 10: keep-alive 任务超时 → 强制取消 =====

    async def test_stop_ssh_tunnel_force_cancels_on_timeout(
        self, ssh_sync_client, caplog
    ):
        """keep-alive 任务超时未退出 → 被 force cancel"""
        client = ssh_sync_client
        caplog.set_level(logging.WARNING, logger="lifeprism.sync.sync_client")

        mock_tunnel = MagicMock()
        mock_tunnel.close = AsyncMock()
        client._ssh_tunnel = mock_tunnel

        # 创建一个真实的长时运行的 keep-alive 任务
        async def slow_keep_alive():
            await asyncio.sleep(60)

        keep_alive_task = asyncio.create_task(slow_keep_alive())
        client._ssh_tunnel_keep_alive_task = keep_alive_task

        # mock asyncio.wait_for 抛 TimeoutError 模拟 5s 超时
        with patch(
            "lifeprism.sync.sync_client.asyncio.wait_for",
            AsyncMock(side_effect=asyncio.TimeoutError()),
        ):
            await client._stop_ssh_tunnel()

        # 等待取消传播完成
        try:
            await keep_alive_task
        except asyncio.CancelledError:
            pass

        # 1. 验证 keep-alive 任务被取消
        assert keep_alive_task.cancelled(), "keep-alive 任务超时后应被 force cancel"

        # 2. 验证引用已清理
        assert client._ssh_tunnel_keep_alive_task is None, (
            "_ssh_tunnel_keep_alive_task 应在强制取消后被置 None"
        )

        # 3. 验证 WARNING 日志
        warning_messages = [
            r.getMessage() for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any("强制取消" in m for m in warning_messages), (
            f"未找到 '强制取消' WARNING 日志，实际: {warning_messages}"
        )


# ==================== Seam 9: _read_remote_url() 审计验证 ====================


class TestReadRemoteUrlAudit:
    """Seam 9: 验证 sync_client.py 中所有 remote_url 获取走 _read_remote_url()

    参考: docs/coding-rules/sync-remote-url-access-rules.md 审计表
    """

    def test_send_ping_uses_read_remote_url(self):
        """send_ping 方法通过 _read_remote_url() 获取 remote_url（审计项 sync_client.py:149）"""
        import inspect

        from lifeprism.sync.sync_client import SyncClient

        source = inspect.getsource(SyncClient.send_ping)
        assert "_read_remote_url" in source, (
            "send_ping 应通过 _read_remote_url() 获取 remote_url，"
            "禁止直接调用 get_setting('sync.remote_url')（参考 sync-remote-url-access-rules.md 规则 1）"
        )
        assert 'get_setting("sync.remote_url")' not in source, (
            "send_ping 禁止直接调用 get_setting('sync.remote_url')"
        )

    def test_sync_once_uses_read_remote_url(self):
        """sync_once 方法通过 _read_remote_url() 获取 remote_url（审计项 sync_client.py:269）"""
        import inspect

        from lifeprism.sync.sync_client import SyncClient

        source = inspect.getsource(SyncClient.sync_once)
        assert "_read_remote_url" in source, (
            "sync_once 应通过 _read_remote_url() 获取 remote_url，"
            "禁止直接调用 get_setting('sync.remote_url')（参考 sync-remote-url-access-rules.md 规则 1）"
        )
        assert 'get_setting("sync.remote_url")' not in source, (
            "sync_once 禁止直接调用 get_setting('sync.remote_url')"
        )

    def test_run_sync_loop_uses_read_remote_url(self):
        """_run_sync_loop 方法通过 _read_remote_url() 获取 remote_url（审计项 sync_client.py:206-208）"""
        import inspect

        from lifeprism.sync.sync_client import SyncClient

        source = inspect.getsource(SyncClient._run_sync_loop)
        assert "_read_remote_url" in source, (
            "_run_sync_loop 应通过 _read_remote_url() 获取 remote_url"
        )

    def test_read_remote_url_docstring_contains_warning(self):
        """_read_remote_url 方法的 docstring 包含 SSH 隧道警告（规则 6）"""
        from lifeprism.sync.sync_client import SyncClient

        docstring = SyncClient._read_remote_url.__doc__ or ""
        assert "警告" in docstring, (
            "_read_remote_url docstring 应包含 '警告' 关键字（参考规则 6）"
        )
        assert "get_setting" in docstring, (
            "_read_remote_url docstring 应说明禁止直接调用 get_setting（参考规则 6）"
        )
        assert "localhost" in docstring, (
            "_read_remote_url docstring 应说明 SSH 模式返回 localhost（参考规则 6）"
        )
        assert "空字符串" in docstring, (
            "_read_remote_url docstring 应说明 SSH 未就绪时返回空字符串（参考规则 6）"
        )

    def test_sync_client_has_ssh_tunnel_methods(self):
        """SyncClient 包含 5 个新增的 SSH 隧道方法（验收标准）"""
        from lifeprism.sync.sync_client import SyncClient

        required_methods = [
            "_ensure_tunnel_ready",
            "_should_use_ssh_tunnel",
            "_is_tunnel_ready",
            "_start_ssh_tunnel",
            "_stop_ssh_tunnel",
        ]
        for method_name in required_methods:
            assert hasattr(SyncClient, method_name), (
                f"SyncClient 应包含方法 {method_name}（验收标准）"
            )
