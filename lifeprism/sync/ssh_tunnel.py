"""SSH 隧道封装 - 基于 asyncssh 的本地端口转发

职责：
- 建立 SSH 连接 + 本地端口转发（local port forwarding）
- 状态机管理（disconnected/connecting/connected/reconnecting/failed）
- 心跳保活 + 断线重连（指数退避 5s/10s/20s/30s 上限）
- 一次性测试连接（test_connection）

设计参考:
- Issue: .scratch/ssh-tunnel-integration/issues/03-sshtunnel-class.md
- PRD: .scratch/ssh-tunnel-integration/prd.md
- 错误处理规范: docs/coding-rules/backend-error-handling.md
"""

from __future__ import annotations

import asyncio
from enum import Enum
from typing import Any

import asyncssh
import httpx

from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import ExternalServiceError

logger = get_logger(__name__)

# 心跳间隔（秒）：keep-alive 循环每 30 秒检查一次连接状态
HEARTBEAT_INTERVAL_SECONDS = 30

# 重连退避序列（秒）：5s → 10s → 20s → 30s（上限）
BACKOFF_INTERVALS = (5, 10, 20, 30)

# 测试连接时验证远程端点的路径
REMOTE_HEALTH_PATH = "/api/sync/health"

# 测试连接时 HTTP 请求超时（秒）
TEST_CONNECTION_TIMEOUT = 10.0


class ConnectionState(Enum):
    """SSH 隧道状态机枚举

    状态转换：
    - disconnected ──connect()──→ connecting ──成功──→ connected
    -                                    │                  │
    -                                    失败               断开
    -                                    ↓                  ↓
    -                                 failed            reconnecting
    -                                    │                  │
    -                                 close()          重试成功 → connected
    -                                                       │
    -                                                   close() → disconnected
    """

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class SSHTunnel:
    """SSH 隧道封装（基于 asyncssh 的本地端口转发）

    将本地端口通过 SSH 加密通道映射到远程主机的目标端口，
    SyncClient 访问 ``http://localhost:{local_port}`` 即可走 SSH 加密通道。

    状态机：
    - ``DISCONNECTED``: 初始状态 / close 后
    - ``CONNECTING``: connect() 调用中
    - ``CONNECTED``: SSH 连接 + 端口转发已建立
    - ``RECONNECTING``: 连接断开后重连中（keep-alive 循环检测到断开）
    - ``FAILED``: 连接失败（close 后可重新 connect）

    重连策略：
    - 心跳间隔：30 秒
    - 重连退避：5s → 10s → 20s → 30s（上限）
    - 无最大重试次数限制，直到 close() 被调用

    Attributes:
        host: SSH 服务器地址
        port: SSH 服务器端口
        username: SSH 用户名
        private_key: SSH 私钥（PEM 格式字符串）
        local_port: 本地监听端口
        remote_host: 远程目标主机（通常是 127.0.0.1）
        remote_port: 远程目标端口
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        private_key: str,
        local_port: int,
        remote_host: str,
        remote_port: int,
    ) -> None:
        """初始化 SSH 隧道配置

        Args:
            host: SSH 服务器地址
            port: SSH 服务器端口
            username: SSH 用户名
            private_key: SSH 私钥（PEM 格式字符串）
            local_port: 本地监听端口
            remote_host: 远程目标主机（通常是 127.0.0.1）
            remote_port: 远程目标端口
        """
        self.host = host
        self.port = port
        self.username = username
        self.private_key = private_key
        self.local_port = local_port
        self.remote_host = remote_host
        self.remote_port = remote_port

        self._state: ConnectionState = ConnectionState.DISCONNECTED
        self._connection: asyncssh.SSHClientConnection | None = None
        self._forwarder: asyncssh.SSHListener | None = None
        self._reconnect_attempts: int = 0
        # 控制保活循环退出的标志：close() 时置为 True
        self._closed: bool = False

    @property
    def is_connected(self) -> bool:
        """当前是否已连接（state == CONNECTED）"""
        return self._state == ConnectionState.CONNECTED

    @property
    def connection_state(self) -> ConnectionState:
        """当前状态机状态"""
        return self._state

    async def connect(self) -> None:
        """建立 SSH 连接 + 启动本地端口转发

        状态转换：disconnected/failed → connecting → connected (成功) / failed (失败)

        Raises:
            ExternalServiceError: SSH 连接或端口转发失败，错误码区分原因：
                - ``SSH_KEY_REJECTED``: 密钥被拒绝（PermissionDenied）
                - ``SSH_NETWORK_UNREACHABLE``: 网络不通（OSError / ConnectionLost）
                - ``SSH_LOCAL_PORT_IN_USE``: 本地端口被占用（ChannelListenError）
                - ``SSH_CONNECT_FAILED``: 其他 asyncssh 错误
                - ``SSH_FORWARD_FAILED``: 其他端口转发错误
        """
        # 重置 closed 标志，允许 connect() 后再启动 keep-alive
        self._closed = False
        self._state = ConnectionState.CONNECTING
        logger.info(
            "SSH 隧道 connecting: host=%s, port=%d, username=%s, local_port=%d -> %s:%d",
            self.host,
            self.port,
            self.username,
            self.local_port,
            self.remote_host,
            self.remote_port,
        )

        # ===== 阶段 1：建立 SSH 连接 =====
        # 将 PEM 字符串转为 SSHKey 对象（asyncssh 的 client_keys 不接受原始 PEM 字符串）
        try:
            key_obj = asyncssh.import_private_key(self.private_key)
        except Exception as e:
            self._state = ConnectionState.FAILED
            logger.error("SSH 私钥解析失败: %s", e)
            raise ExternalServiceError(
                message=f"SSH 私钥解析失败: {e}",
                code="SSH_KEY_INVALID",
                details={"error": str(e)},
                cause=e,
            ) from e

        try:
            self._connection = await asyncssh.connect(
                host=self.host,
                port=self.port,
                username=self.username,
                client_keys=[key_obj],
                known_hosts=None,  # 信任主机密钥（生产应使用 known_hosts 文件）
                # 显式禁用 GSSAPI：asyncssh 在 Windows 默认初始化 GSSClient 会触发
                # sspi → win32timezone 导入链，PyInstaller 打包环境未收集该 pywin32 子模块
                # 导致 ModuleNotFoundError。asyncssh connection.py 的 try/except 只捕获
                # GSSError 不捕获 ModuleNotFoundError，异常直接冒泡使连接失败。
                # gss_host='' 利用 connection.py:3314 的 `if gss_host:` 短路判断（空字符串
                # 为 falsy）跳过 GSSClient 实例化。项目用密钥认证，无需 GSSAPI。
                # 详见 docs/flows/2026-07-26-ssh-tunnel-flow.md 反常设计 5
                options=asyncssh.SSHClientConnectionOptions(gss_host=""),
            )
        except asyncssh.PermissionDenied as e:
            self._state = ConnectionState.FAILED
            logger.error("SSH 连接失败：密钥被拒绝: %s", e)
            raise ExternalServiceError(
                message="SSH 密钥被拒绝，请检查私钥是否正确以及云端 authorized_keys 是否配置",
                code="SSH_KEY_REJECTED",
                details={"host": self.host, "username": self.username},
                cause=e,
            ) from e
        except (OSError, asyncssh.ConnectionLost) as e:
            self._state = ConnectionState.FAILED
            logger.error("SSH 连接失败：网络不通: %s", e)
            raise ExternalServiceError(
                message=f"SSH 连接网络不通: {e}",
                code="SSH_NETWORK_UNREACHABLE",
                details={"host": self.host, "port": self.port},
                cause=e,
            ) from e
        except asyncssh.Error as e:
            self._state = ConnectionState.FAILED
            logger.error("SSH 连接失败: %s", e)
            raise ExternalServiceError(
                message=f"SSH 连接失败: {e}",
                code="SSH_CONNECT_FAILED",
                details={"host": self.host, "port": self.port, "error": str(e)},
                cause=e,
            ) from e

        # ===== 阶段 2：启动本地端口转发 =====
        try:
            self._forwarder = await self._connection.forward_local_port(
                listen_host="127.0.0.1",
                listen_port=self.local_port,
                dest_host=self.remote_host,
                dest_port=self.remote_port,
            )
        except asyncssh.ChannelListenError as e:
            # 本地端口被占用：关闭已建立的 SSH 连接，避免资源泄漏
            self._state = ConnectionState.FAILED
            await self._close_resources()
            logger.error("本地端口转发失败：端口 %d 被占用: %s", self.local_port, e)
            raise ExternalServiceError(
                message=f"本地端口 {self.local_port} 已被其他程序占用",
                code="SSH_LOCAL_PORT_IN_USE",
                details={"local_port": self.local_port},
                cause=e,
            ) from e
        except asyncssh.Error as e:
            self._state = ConnectionState.FAILED
            await self._close_resources()
            logger.error("本地端口转发失败: %s", e)
            raise ExternalServiceError(
                message=f"SSH 端口转发失败: {e}",
                code="SSH_FORWARD_FAILED",
                details={
                    "local_port": self.local_port,
                    "remote_host": self.remote_host,
                    "remote_port": self.remote_port,
                    "error": str(e),
                },
                cause=e,
            ) from e

        self._state = ConnectionState.CONNECTED
        self._reconnect_attempts = 0
        logger.info(
            "SSH 隧道 connected: 127.0.0.1:%d -> %s:%d (via %s@%s:%d)",
            self.local_port,
            self.remote_host,
            self.remote_port,
            self.username,
            self.host,
            self.port,
        )

    async def close(self) -> None:
        """优雅关闭 SSH 连接和端口转发，状态变为 disconnected

        幂等：多次调用不抛异常。
        通知 start_keep_alive_loop 退出（设置 _closed = True）。
        """
        self._closed = True
        await self._close_resources()
        self._state = ConnectionState.DISCONNECTED
        logger.info("SSH 隧道 disconnected")

    async def _close_resources(self) -> None:
        """关闭底层 SSH 连接和端口转发资源（幂等）

        关闭顺序：forwarder → connection（先关转发再关连接，避免连接被关闭时转发卡死）
        异常处理：辅助操作兜底，单个资源关闭失败不影响其他资源
        """
        if self._forwarder is not None:
            try:
                self._forwarder.close()
                await self._forwarder.wait_closed()
            except Exception as e:
                # LEGITIMATE: 辅助操作兜底，关闭 forwarder 失败不应阻塞 close() 流程
                logger.warning("关闭端口转发时出错（忽略）: %s", e)
            self._forwarder = None
        if self._connection is not None:
            try:
                self._connection.close()
                await self._connection.wait_closed()
            except Exception as e:
                # LEGITIMATE: 辅助操作兜底，关闭 SSH 连接失败不应阻塞 close() 流程
                logger.warning("关闭 SSH 连接时出错（忽略）: %s", e)
            self._connection = None

    async def start_keep_alive_loop(self) -> None:
        """后台心跳保活 + 断线重连循环

        - 每 ``HEARTBEAT_INTERVAL_SECONDS`` 秒检查连接状态
        - 连接断开时进入 ``RECONNECTING`` 状态，调用 ``_reconnect_with_backoff``
        - 退出条件：``close()`` 被调用（_closed == True）

        通常通过 ``asyncio.create_task(tunnel.start_keep_alive_loop())`` 启动为后台任务。
        """
        while not self._closed:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            if self._closed:
                break

            # 检查连接是否还活着
            if self._connection is None or self._connection.is_closed():
                logger.warning("SSH 隧道连接已断开，进入 reconnecting 状态，开始尝试重连")
                self._state = ConnectionState.RECONNECTING
                await self._reconnect_with_backoff()

    async def _reconnect_with_backoff(self) -> None:
        """按指数退避策略重连

        退避序列：5s → 10s → 20s → 30s（上限），无最大重试次数
        退出条件：
        - 重连成功（state → CONNECTED）
        - ``close()`` 被调用（_closed == True）
        """
        while not self._closed:
            backoff = BACKOFF_INTERVALS[min(self._reconnect_attempts, len(BACKOFF_INTERVALS) - 1)]
            logger.info(
                "SSH 隧道 reconnect 尝试 %d，等待 %ds 后重试",
                self._reconnect_attempts + 1,
                backoff,
            )
            await asyncio.sleep(backoff)
            if self._closed:
                break

            try:
                # 在 connect() 重置计数前保存实际尝试次数（connect 成功后会清零）
                attempts = self._reconnect_attempts + 1
                # connect() 成功会将 state 置为 CONNECTED 并重置 _reconnect_attempts
                await self.connect()
                logger.info(
                    "SSH 隧道 reconnect 成功（经过 %d 次尝试）",
                    attempts,
                )
                return
            except ExternalServiceError as e:
                self._reconnect_attempts += 1
                # connect() 失败时已将 state 置为 FAILED，重连场景下保持 RECONNECTING
                self._state = ConnectionState.RECONNECTING
                logger.warning(
                    "SSH 隧道 reconnect 失败（第 %d 次）: %s",
                    self._reconnect_attempts,
                    e.message,
                )

    async def test_connection(self) -> dict[str, Any]:
        """一次性测试连接：建立 SSH 隧道 + 验证远程端点可达 + 关闭

        封装"建立 → 验证 → 关闭"完整测试逻辑，供 SSH 隧道管理 API 的
        POST /test 端点调用，避免 API 层重复组合 connect/close。

        验证远程可达的方式：通过已建立的本地端口转发访问
        ``http://127.0.0.1:{local_port}/api/sync/health``。

        Returns:
            成功时: ``{"status": "ok", "remote_response": {...}}``
            失败时: ``{"status": "error", "error": "<错误消息>", "code": "<错误码>"}``，
            错误码同 ``connect()``，外加 ``REMOTE_UNREACHABLE``（远程端点不可达）
        """
        # 阶段 1：建立 SSH 连接 + 端口转发
        try:
            await self.connect()
        except ExternalServiceError as e:
            return {
                "status": "error",
                "error": e.message,
                "code": e.code or "SSH_CONNECT_FAILED",
            }

        # 阶段 2：通过本地端口转发访问远程健康端点
        try:
            # 使用 asyncio.to_thread 包装同步 httpx.get，避免阻塞事件循环
            # 与 sync_client.py 的同步 httpx 调用风格一致
            response = await asyncio.to_thread(
                httpx.get,
                url=f"http://127.0.0.1:{self.local_port}{REMOTE_HEALTH_PATH}",
                timeout=TEST_CONNECTION_TIMEOUT,
            )
            response.raise_for_status()
            return {
                "status": "ok",
                "remote_response": response.json(),
            }
        except (httpx.HTTPError, OSError) as e:
            logger.error(
                "SSH 隧道 test_connection 远程端点 %s 不可达: %s",
                REMOTE_HEALTH_PATH,
                e,
            )
            return {
                "status": "error",
                "error": f"远程端点 {REMOTE_HEALTH_PATH} 不可达: {e}",
                "code": "REMOTE_UNREACHABLE",
            }
        finally:
            # 阶段 3：无论成功或失败都关闭连接（不留半开连接）
            await self.close()
