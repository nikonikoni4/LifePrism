"""SSHTunnel 单元测试

测试 seam:
- Seam 1: 状态机转换（disconnected/connecting/connected/reconnecting/failed）
- Seam 2: connect() - 成功建立 SSH + 启动本地端口转发；不同失败原因映射到不同错误消息
- Seam 3: close() - 优雅关闭连接和转发
- Seam 4: start_keep_alive_loop() - 心跳保活 + 指数退避重连
- Seam 5: test_connection() - 一次性测试连接（成功 + 失败场景）
- Seam 6: is_connected / connection_state 属性

Mock 策略：
- patch('asyncssh.connect') 返回 AsyncMock 模拟 SSHClientConnection
- mock connection.forward_local_port 返回 AsyncMock 模拟 SSHListener
- patch('httpx.get') 模拟远程端点响应
- patch('asyncio.sleep') 加速重连退避时序测试

参考: .scratch/ssh-tunnel-integration/issues/03-sshtunnel-class.md
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import asyncssh
import httpx
import pytest

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture
def tunnel_kwargs():
    """SSHTunnel 构造参数"""
    return dict(
        host="example.com",
        port=22,
        username="testuser",
        private_key=(
            "-----BEGIN OPENSSH PRIVATE KEY-----\n"
            "fake_key_data\n"
            "-----END OPENSSH PRIVATE KEY-----\n"
        ),
        local_port=8102,
        remote_host="127.0.0.1",
        remote_port=8102,
    )


@pytest.fixture
def mock_connection():
    """Mock asyncssh.connect 返回的 SSHClientConnection

    Returns:
        tuple: (connection, forwarder) 两个 AsyncMock
    """
    conn = AsyncMock()
    forwarder = AsyncMock()
    conn.forward_local_port = AsyncMock(return_value=forwarder)
    conn.is_closed = MagicMock(return_value=False)
    # asyncssh 的 close 是同步方法，wait_closed 是协程
    conn.close = MagicMock()
    conn.wait_closed = AsyncMock()
    forwarder.close = MagicMock()
    forwarder.wait_closed = AsyncMock()
    return conn, forwarder


def _make_mock_httpx_response(json_data: dict) -> MagicMock:
    """构造 mock httpx.Response"""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=json_data)
    return response


# ==================== Seam 1 & 6: 状态机 + 属性 ====================


class TestStateMachine:
    """测试状态机所有转换路径 + is_connected / connection_state 属性"""

    async def test_initial_state_is_disconnected(self, tunnel_kwargs):
        """初始状态为 disconnected"""
        from lifeprism.sync.ssh_tunnel import ConnectionState, SSHTunnel

        tunnel = SSHTunnel(**tunnel_kwargs)
        assert tunnel.connection_state == ConnectionState.DISCONNECTED
        assert tunnel.is_connected is False

    async def test_connect_transitions_to_connected(self, tunnel_kwargs, mock_connection):
        """connect() 成功后状态变为 connected"""
        from lifeprism.sync.ssh_tunnel import ConnectionState, SSHTunnel

        conn, _ = mock_connection
        with patch("asyncssh.connect", new=AsyncMock(return_value=conn)):
            tunnel = SSHTunnel(**tunnel_kwargs)
            await tunnel.connect()
            assert tunnel.connection_state == ConnectionState.CONNECTED
            assert tunnel.is_connected is True

    async def test_connect_failure_sets_state_to_failed(self, tunnel_kwargs):
        """connect() 失败时状态变为 failed"""
        from lifeprism.sync.ssh_tunnel import ConnectionState, SSHTunnel

        with patch(
            "asyncssh.connect",
            new=AsyncMock(side_effect=asyncssh.PermissionDenied("key rejected")),
        ):
            tunnel = SSHTunnel(**tunnel_kwargs)
            with pytest.raises(Exception):
                await tunnel.connect()
            assert tunnel.connection_state == ConnectionState.FAILED
            assert tunnel.is_connected is False

    async def test_close_after_connect_returns_to_disconnected(
        self, tunnel_kwargs, mock_connection
    ):
        """connect() 成功后调用 close() 状态变为 disconnected"""
        from lifeprism.sync.ssh_tunnel import ConnectionState, SSHTunnel

        conn, _ = mock_connection
        with patch("asyncssh.connect", new=AsyncMock(return_value=conn)):
            tunnel = SSHTunnel(**tunnel_kwargs)
            await tunnel.connect()
            await tunnel.close()
            assert tunnel.connection_state == ConnectionState.DISCONNECTED
            assert tunnel.is_connected is False

    async def test_close_after_failure_sets_disconnected(self, tunnel_kwargs):
        """connect() 失败后调用 close() 状态变为 disconnected"""
        from lifeprism.sync.ssh_tunnel import ConnectionState, SSHTunnel

        with patch(
            "asyncssh.connect",
            new=AsyncMock(side_effect=asyncssh.PermissionDenied("key rejected")),
        ):
            tunnel = SSHTunnel(**tunnel_kwargs)
            with pytest.raises(Exception):
                await tunnel.connect()
            assert tunnel.connection_state == ConnectionState.FAILED
            await tunnel.close()
            assert tunnel.connection_state == ConnectionState.DISCONNECTED

    async def test_close_without_connect_sets_disconnected(self, tunnel_kwargs):
        """未调用 connect() 直接 close() 不抛异常，状态为 disconnected"""
        from lifeprism.sync.ssh_tunnel import ConnectionState, SSHTunnel

        tunnel = SSHTunnel(**tunnel_kwargs)
        await tunnel.close()
        assert tunnel.connection_state == ConnectionState.DISCONNECTED

    async def test_forwarder_failure_sets_state_to_failed(
        self, tunnel_kwargs, mock_connection
    ):
        """SSH 连接成功但端口转发失败时状态变为 failed"""
        from lifeprism.sync.ssh_tunnel import ConnectionState, SSHTunnel

        conn, _ = mock_connection
        conn.forward_local_port = AsyncMock(
            side_effect=asyncssh.ChannelListenError("Address already in use")
        )
        with patch("asyncssh.connect", new=AsyncMock(return_value=conn)):
            tunnel = SSHTunnel(**tunnel_kwargs)
            with pytest.raises(Exception):
                await tunnel.connect()
            assert tunnel.connection_state == ConnectionState.FAILED


# ==================== Seam 2: connect() 错误透明度 + 行为 ====================


class TestConnectErrorTransparency:
    """测试不同失败原因映射到不同错误消息（密钥被拒绝/网络不通/端口被占用）"""

    async def test_key_rejected_error_message(self, tunnel_kwargs):
        """密钥被拒绝时错误消息包含"密钥被拒绝"，code=SSH_KEY_REJECTED"""
        from lifeprism.sync.ssh_tunnel import SSHTunnel
        from lifeprism.utils.exceptions import ExternalServiceError

        with patch(
            "asyncssh.connect",
            new=AsyncMock(side_effect=asyncssh.PermissionDenied("key rejected")),
        ):
            tunnel = SSHTunnel(**tunnel_kwargs)
            with pytest.raises(ExternalServiceError) as exc_info:
                await tunnel.connect()
            assert "密钥被拒绝" in exc_info.value.message
            assert exc_info.value.code == "SSH_KEY_REJECTED"

    async def test_network_unreachable_error_message(self, tunnel_kwargs):
        """网络不通时错误消息包含"网络不通"，code=SSH_NETWORK_UNREACHABLE"""
        from lifeprism.sync.ssh_tunnel import SSHTunnel
        from lifeprism.utils.exceptions import ExternalServiceError

        with patch(
            "asyncssh.connect",
            new=AsyncMock(side_effect=OSError("Network is unreachable")),
        ):
            tunnel = SSHTunnel(**tunnel_kwargs)
            with pytest.raises(ExternalServiceError) as exc_info:
                await tunnel.connect()
            assert "网络不通" in exc_info.value.message
            assert exc_info.value.code == "SSH_NETWORK_UNREACHABLE"

    async def test_local_port_in_use_error_message(self, tunnel_kwargs, mock_connection):
        """本地端口被占用时错误消息包含"端口"+"占用"，code=SSH_LOCAL_PORT_IN_USE"""
        from lifeprism.sync.ssh_tunnel import SSHTunnel
        from lifeprism.utils.exceptions import ExternalServiceError

        conn, _ = mock_connection
        conn.forward_local_port = AsyncMock(
            side_effect=asyncssh.ChannelListenError("Address already in use")
        )
        with patch("asyncssh.connect", new=AsyncMock(return_value=conn)):
            tunnel = SSHTunnel(**tunnel_kwargs)
            with pytest.raises(ExternalServiceError) as exc_info:
                await tunnel.connect()
            assert "端口" in exc_info.value.message
            assert "占用" in exc_info.value.message
            assert str(tunnel_kwargs["local_port"]) in exc_info.value.message
            assert exc_info.value.code == "SSH_LOCAL_PORT_IN_USE"

    async def test_generic_ssh_error_falls_back_to_default_code(self, tunnel_kwargs):
        """其他 asyncssh 错误（非密钥/网络/端口）映射到 SSH_CONNECT_FAILED"""
        from lifeprism.sync.ssh_tunnel import SSHTunnel
        from lifeprism.utils.exceptions import ExternalServiceError

        # 使用 DisconnectError 作为通用 asyncssh.Error 子类
        # asyncssh.Error 基类需要 (code, reason) 构造参数
        generic_error = asyncssh.DisconnectError(
            asyncssh.DISC_PROTOCOL_ERROR,
            "generic ssh error",
        )
        with patch(
            "asyncssh.connect",
            new=AsyncMock(side_effect=generic_error),
        ):
            tunnel = SSHTunnel(**tunnel_kwargs)
            with pytest.raises(ExternalServiceError) as exc_info:
                await tunnel.connect()
            assert exc_info.value.code == "SSH_CONNECT_FAILED"

    async def test_connect_invokes_asyncssh_connect_with_correct_kwargs(
        self, tunnel_kwargs, mock_connection
    ):
        """connect() 使用正确的参数调用 asyncssh.connect"""
        from lifeprism.sync.ssh_tunnel import SSHTunnel

        conn, _ = mock_connection
        with patch("asyncssh.connect", new=AsyncMock(return_value=conn)) as mock_connect:
            tunnel = SSHTunnel(**tunnel_kwargs)
            await tunnel.connect()
            mock_connect.assert_awaited_once()
            call_kwargs = mock_connect.await_args.kwargs
            assert call_kwargs.get("host") == tunnel_kwargs["host"]
            assert call_kwargs.get("port") == tunnel_kwargs["port"]
            assert call_kwargs.get("username") == tunnel_kwargs["username"]

    async def test_connect_starts_local_port_forwarding(
        self, tunnel_kwargs, mock_connection
    ):
        """connect() 成功后启动本地端口转发，参数与构造参数一致"""
        from lifeprism.sync.ssh_tunnel import SSHTunnel

        conn, _ = mock_connection
        with patch("asyncssh.connect", new=AsyncMock(return_value=conn)):
            tunnel = SSHTunnel(**tunnel_kwargs)
            await tunnel.connect()
            conn.forward_local_port.assert_awaited_once()
            call_kwargs = conn.forward_local_port.await_args.kwargs
            assert call_kwargs.get("listen_port") == tunnel_kwargs["local_port"]
            assert call_kwargs.get("dest_host") == tunnel_kwargs["remote_host"]
            assert call_kwargs.get("dest_port") == tunnel_kwargs["remote_port"]

    async def test_connect_closes_ssh_connection_when_forward_fails(
        self, tunnel_kwargs, mock_connection
    ):
        """端口转发失败时已建立的 SSH 连接应被关闭，避免资源泄漏"""
        from lifeprism.sync.ssh_tunnel import SSHTunnel

        conn, _ = mock_connection
        conn.forward_local_port = AsyncMock(
            side_effect=asyncssh.ChannelListenError("Address already in use")
        )
        with patch("asyncssh.connect", new=AsyncMock(return_value=conn)):
            tunnel = SSHTunnel(**tunnel_kwargs)
            with pytest.raises(Exception):
                await tunnel.connect()
            # 验证 SSH 连接被关闭
            conn.close.assert_called_once()


# ==================== Seam 3: close() 优雅关闭 ====================


class TestClose:
    """测试 close() 优雅关闭连接和转发"""

    async def test_close_closes_forwarder_and_connection(
        self, tunnel_kwargs, mock_connection
    ):
        """close() 关闭 forwarder 和 SSH 连接（按顺序）"""
        from lifeprism.sync.ssh_tunnel import SSHTunnel

        conn, forwarder = mock_connection
        with patch("asyncssh.connect", new=AsyncMock(return_value=conn)):
            tunnel = SSHTunnel(**tunnel_kwargs)
            await tunnel.connect()
            await tunnel.close()
            forwarder.close.assert_called_once()
            forwarder.wait_closed.assert_awaited_once()
            conn.close.assert_called_once()
            conn.wait_closed.assert_awaited_once()

    async def test_close_is_idempotent(self, tunnel_kwargs, mock_connection):
        """多次调用 close() 不抛异常"""
        from lifeprism.sync.ssh_tunnel import SSHTunnel

        conn, _ = mock_connection
        with patch("asyncssh.connect", new=AsyncMock(return_value=conn)):
            tunnel = SSHTunnel(**tunnel_kwargs)
            await tunnel.connect()
            await tunnel.close()
            await tunnel.close()  # 第二次不应抛异常
            assert tunnel.connection_state.value == "disconnected"

    async def test_close_after_failure_does_not_raise(self, tunnel_kwargs):
        """连接失败后 close() 不抛异常"""
        from lifeprism.sync.ssh_tunnel import SSHTunnel

        with patch(
            "asyncssh.connect",
            new=AsyncMock(side_effect=asyncssh.PermissionDenied("key rejected")),
        ):
            tunnel = SSHTunnel(**tunnel_kwargs)
            with pytest.raises(Exception):
                await tunnel.connect()
            await tunnel.close()
            assert tunnel.connection_state.value == "disconnected"


# ==================== Seam 4: start_keep_alive_loop + 重连退避 ====================


class TestKeepAliveLoop:
    """测试心跳保活 + 断线重连（指数退避）"""

    async def test_keep_alive_detects_disconnect_and_reconnects_successfully(
        self, tunnel_kwargs, mock_connection
    ):
        """连接断开后 keep-alive 检测到并成功重连"""
        from lifeprism.sync.ssh_tunnel import ConnectionState, SSHTunnel

        conn, _ = mock_connection
        with patch("asyncssh.connect", new=AsyncMock(return_value=conn)):
            tunnel = SSHTunnel(**tunnel_kwargs)
            await tunnel.connect()
            assert tunnel.connection_state == ConnectionState.CONNECTED

            # 模拟原连接断开
            conn.is_closed = MagicMock(return_value=True)

            # 重连时返回新连接
            new_conn = AsyncMock()
            new_forwarder = AsyncMock()
            new_conn.forward_local_port = AsyncMock(return_value=new_forwarder)
            new_conn.is_closed = MagicMock(return_value=False)
            new_conn.close = MagicMock()
            new_conn.wait_closed = AsyncMock()
            new_forwarder.close = MagicMock()
            new_forwarder.wait_closed = AsyncMock()

            sleep_calls = []

            async def fake_sleep(seconds):
                sleep_calls.append(seconds)

            with patch("asyncssh.connect", new=AsyncMock(return_value=new_conn)):
                with patch("asyncio.sleep", new=fake_sleep):
                    task = asyncio.create_task(tunnel.start_keep_alive_loop())
                    # 让循环跑几轮（sleep 已 patch 立即返回）
                    for _ in range(10):
                        await asyncio.sleep(0)
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

            # 验证重连成功 -> CONNECTED
            assert tunnel.connection_state == ConnectionState.CONNECTED
            assert tunnel.is_connected is True

    async def test_exponential_backoff_sequence_5_10_20_30_cap(
        self, tunnel_kwargs
    ):
        """重连退避时序：5s → 10s → 20s → 30s（上限）"""
        from lifeprism.sync.ssh_tunnel import ConnectionState, SSHTunnel

        # 捕获真实的 asyncio.sleep，用于在测试中 yield 控制权
        real_asyncio_sleep = asyncio.sleep
        sleep_calls = []

        async def fake_sleep(seconds):
            # 记录退避时间，并通过真实 sleep(0) 让事件循环调度其他任务
            sleep_calls.append(seconds)
            await real_asyncio_sleep(0)

        # connect 始终失败，触发持续重连
        with patch(
            "asyncssh.connect",
            new=AsyncMock(side_effect=asyncssh.PermissionDenied("key rejected")),
        ):
            tunnel = SSHTunnel(**tunnel_kwargs)
            tunnel._state = ConnectionState.RECONNECTING

            with patch("asyncio.sleep", new=fake_sleep):
                task = asyncio.create_task(tunnel._reconnect_with_backoff())
                # 使用真实 sleep 让事件循环调度 _reconnect_with_backoff 任务
                for _ in range(30):
                    await real_asyncio_sleep(0)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # 验证退避序列：5, 10, 20, 30, 30, 30...
        assert sleep_calls[0] == 5, f"首次退避应为 5s, 实际: {sleep_calls[0]}"
        assert sleep_calls[1] == 10, f"第二次退避应为 10s, 实际: {sleep_calls[1]}"
        assert sleep_calls[2] == 20, f"第三次退避应为 20s, 实际: {sleep_calls[2]}"
        assert sleep_calls[3] == 30, f"第四次退避应为 30s, 实际: {sleep_calls[3]}"
        # 后续都是 30（上限）
        for s in sleep_calls[4:]:
            assert s == 30, f"上限后应保持 30s, 实际: {s}"

    async def test_reconnect_state_during_reconnect_failure(
        self, tunnel_kwargs, mock_connection
    ):
        """连接断开后重连持续失败时保持 reconnecting 状态"""
        from lifeprism.sync.ssh_tunnel import ConnectionState, SSHTunnel

        # 捕获真实的 asyncio.sleep，用于在测试中 yield 控制权
        real_asyncio_sleep = asyncio.sleep

        async def fake_sleep(seconds):
            # 不真正睡眠，但 yield 控制权让 keep_alive_loop 有机会运行
            await real_asyncio_sleep(0)

        conn, _ = mock_connection
        with patch("asyncssh.connect", new=AsyncMock(return_value=conn)):
            tunnel = SSHTunnel(**tunnel_kwargs)
            await tunnel.connect()
            # 模拟连接断开
            conn.is_closed = MagicMock(return_value=True)

            # 重连持续失败
            with patch(
                "asyncssh.connect",
                new=AsyncMock(side_effect=asyncssh.PermissionDenied("key rejected")),
            ):
                with patch("asyncio.sleep", new=fake_sleep):
                    task = asyncio.create_task(tunnel.start_keep_alive_loop())
                    # 使用真实 sleep 让事件循环调度 keep_alive_loop 任务
                    for _ in range(20):
                        await real_asyncio_sleep(0)
                    # 验证处于 RECONNECTING 状态
                    assert tunnel.connection_state == ConnectionState.RECONNECTING
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

    async def test_close_during_reconnecting_sets_disconnected(
        self, tunnel_kwargs
    ):
        """重连中调用 close() 状态变为 disconnected，重连循环退出"""
        from lifeprism.sync.ssh_tunnel import ConnectionState, SSHTunnel

        with patch(
            "asyncssh.connect",
            new=AsyncMock(side_effect=asyncssh.PermissionDenied("key rejected")),
        ):
            tunnel = SSHTunnel(**tunnel_kwargs)
            tunnel._state = ConnectionState.RECONNECTING

            with patch("asyncio.sleep", new=AsyncMock(return_value=None)):
                task = asyncio.create_task(tunnel._reconnect_with_backoff())
                for _ in range(5):
                    await asyncio.sleep(0)
                # 调用 close
                await tunnel.close()
                # 等任务退出
                try:
                    await asyncio.wait_for(task, timeout=1.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

            assert tunnel.connection_state == ConnectionState.DISCONNECTED

    async def test_keep_alive_loop_exits_on_close(self, tunnel_kwargs, mock_connection):
        """close() 被调用后 start_keep_alive_loop 正常退出（不需要 cancel）"""
        from lifeprism.sync.ssh_tunnel import ConnectionState, SSHTunnel

        conn, _ = mock_connection
        with patch("asyncssh.connect", new=AsyncMock(return_value=conn)):
            tunnel = SSHTunnel(**tunnel_kwargs)
            await tunnel.connect()

            with patch("asyncio.sleep", new=AsyncMock(return_value=None)):
                task = asyncio.create_task(tunnel.start_keep_alive_loop())
                for _ in range(3):
                    await asyncio.sleep(0)
                # 调用 close 后，循环应自行退出
                await tunnel.close()
                # 等待任务自然结束（不应需要 cancel）
                try:
                    await asyncio.wait_for(task, timeout=1.0)
                except asyncio.TimeoutError:
                    task.cancel()
                    await task
                    raise AssertionError("start_keep_alive_loop 在 close() 后未退出")
            # 验证状态最终为 DISCONNECTED
            assert tunnel.connection_state == ConnectionState.DISCONNECTED


# ==================== Seam 5: test_connection() ====================


class TestTestConnection:
    """测试 test_connection() 一次性测试连接"""

    async def test_success_returns_ok_with_remote_response(
        self, tunnel_kwargs, mock_connection
    ):
        """成功场景：SSH 隧道建立 + 远程 8102 健康端点可达"""
        from lifeprism.sync.ssh_tunnel import ConnectionState, SSHTunnel

        conn, _ = mock_connection
        mock_response = _make_mock_httpx_response({"status": "healthy"})

        with patch("asyncssh.connect", new=AsyncMock(return_value=conn)):
            with patch("httpx.get", return_value=mock_response):
                tunnel = SSHTunnel(**tunnel_kwargs)
                result = await tunnel.test_connection()

        assert result["status"] == "ok"
        assert result["remote_response"] == {"status": "healthy"}
        # 验证连接已关闭
        assert tunnel.connection_state == ConnectionState.DISCONNECTED

    async def test_key_rejected_returns_error_dict(self, tunnel_kwargs):
        """密钥被拒绝场景：返回 error dict，code=SSH_KEY_REJECTED"""
        from lifeprism.sync.ssh_tunnel import SSHTunnel

        with patch(
            "asyncssh.connect",
            new=AsyncMock(side_effect=asyncssh.PermissionDenied("key rejected")),
        ):
            tunnel = SSHTunnel(**tunnel_kwargs)
            result = await tunnel.test_connection()

        assert result["status"] == "error"
        assert "密钥被拒绝" in result["error"]
        assert result["code"] == "SSH_KEY_REJECTED"

    async def test_remote_unreachable_returns_error_dict(
        self, tunnel_kwargs, mock_connection
    ):
        """远程不可达场景：SSH 隧道建立成功但远程 8102 不可达"""
        from lifeprism.sync.ssh_tunnel import ConnectionState, SSHTunnel

        conn, _ = mock_connection
        with patch("asyncssh.connect", new=AsyncMock(return_value=conn)):
            with patch(
                "httpx.get",
                side_effect=httpx.ConnectError("Connection refused"),
            ):
                tunnel = SSHTunnel(**tunnel_kwargs)
                result = await tunnel.test_connection()

        assert result["status"] == "error"
        assert "不可达" in result["error"]
        assert result["code"] == "REMOTE_UNREACHABLE"
        # 即使远程不可达，连接也应关闭
        assert tunnel.connection_state == ConnectionState.DISCONNECTED

    async def test_network_unreachable_returns_error_dict(self, tunnel_kwargs):
        """网络不通场景：SSH 连接失败，错误码=SSH_NETWORK_UNREACHABLE"""
        from lifeprism.sync.ssh_tunnel import SSHTunnel

        with patch(
            "asyncssh.connect",
            new=AsyncMock(side_effect=OSError("Network is unreachable")),
        ):
            tunnel = SSHTunnel(**tunnel_kwargs)
            result = await tunnel.test_connection()

        assert result["status"] == "error"
        assert "网络不通" in result["error"]
        assert result["code"] == "SSH_NETWORK_UNREACHABLE"

    async def test_always_closes_connection_on_success(self, tunnel_kwargs, mock_connection):
        """test_connection 成功后必须关闭连接（不留下半开连接）"""
        from lifeprism.sync.ssh_tunnel import ConnectionState, SSHTunnel

        conn, forwarder = mock_connection
        mock_response = _make_mock_httpx_response({"status": "ok"})

        with patch("asyncssh.connect", new=AsyncMock(return_value=conn)):
            with patch("httpx.get", return_value=mock_response):
                tunnel = SSHTunnel(**tunnel_kwargs)
                await tunnel.test_connection()

        # 验证 close 被调用
        forwarder.close.assert_called_once()
        conn.close.assert_called_once()
        assert tunnel.connection_state == ConnectionState.DISCONNECTED

    async def test_remote_http_error_returns_error_dict(
        self, tunnel_kwargs, mock_connection
    ):
        """远程端点返回非 2xx 状态码"""
        from lifeprism.sync.ssh_tunnel import SSHTunnel

        conn, _ = mock_connection

        def raise_for_status():
            raise httpx.HTTPStatusError(
                "Internal Server Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            )

        mock_response = MagicMock()
        mock_response.raise_for_status = raise_for_status

        with patch("asyncssh.connect", new=AsyncMock(return_value=conn)):
            with patch("httpx.get", return_value=mock_response):
                tunnel = SSHTunnel(**tunnel_kwargs)
                result = await tunnel.test_connection()

        assert result["status"] == "error"
        assert result["code"] == "REMOTE_UNREACHABLE"
