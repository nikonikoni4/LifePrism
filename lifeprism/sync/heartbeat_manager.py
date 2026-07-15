"""心跳状态管理器 - 纯内存的本地在线状态管理

职责：
- 管理本地心跳时间戳和生命周期事件
- 判断本地是否在线（超时 15 分钟或显式 offline）
- 线程安全（threading.Lock）

不使用数据库，所有状态保存在内存中。
"""

from datetime import datetime, timezone
from threading import Lock

from lifeprism.utils import get_logger

logger = get_logger(__name__)

# 心跳超时阈值：15 分钟 = 900 秒
HEARTBEAT_TIMEOUT_SECONDS = 900


class HeartbeatManager:
    """本地在线状态管理（纯内存）

    状态机制：
    - 初始默认在线（云端启动 15min 窗口等待本地首次同步）
    - update_heartbeat() 无条件置为在线（同步即在线）
    - set_event("offline") 立即生效，优先于超时判断
    - set_event("online") 更新心跳时间戳，与同步请求一样受 15min 超时约束

    Attributes:
        _last_heartbeat: 最近一次心跳时间
        _last_event: 生命周期事件 ('online' | 'offline' | None)
        _lock: 线程安全锁
    """

    def __init__(self):
        """初始化心跳管理器，默认假定本地在线。

        云端启动时不应立即接管微信消息处理。
        设置 15 分钟初始窗口，本地在此期间发送同步/心跳即确认为在线，
        超时无响应则自动接管。
        """
        self._last_heartbeat: datetime | None = datetime.now(timezone.utc)
        self._last_event: str | None = None  # 'online' | 'offline' | None
        self._lock = Lock()

    def update_heartbeat(self):
        """更新心跳并置为在线（每次 sync/pull/push 时调用）。

        能发起同步请求即证明本地在线，无条件清除 _last_event，
        确保 is_local_online() 返回 True。
        """
        with self._lock:
            was_offline = self._last_event == "offline"
            self._last_event = None
            self._last_heartbeat = datetime.now(timezone.utc)
            if was_offline:
                logger.info("心跳恢复: 检测到本地同步请求，清除 offline → 云端不再接管微信消息")
            else:
                logger.debug("心跳已更新，时间: %s", self._last_heartbeat)

    def set_event(self, event: str):
        """设置生命周期事件（'online' | 'offline'）。

        同时更新 _last_event 和 _last_heartbeat。
        - 'offline': 立即生效，is_local_online() 返回 False → 云端接管微信
        - 'online': 重置状态为在线 → 云端停止处理微信

        Args:
            event: 生命周期事件，可选值: online, offline
        """
        with self._lock:
            self._last_event = event
            self._last_heartbeat = datetime.now(timezone.utc)
            if event == "offline":
                logger.info("收到 offline 事件 → 云端接管微信消息处理")
            elif event == "online":
                logger.info("收到 online 事件 → 云端停止处理微信消息")

    def is_local_online(self) -> bool:
        """判断本地是否在线。

        判断优先级：
        1. 显式 offline 事件 -> False（立即生效，不等超时）
        2. 从未连接（_last_heartbeat 为 None）-> False
        3. 心跳超时（超过 HEARTBEAT_TIMEOUT_SECONDS 秒）-> False
        4. 其他情况 -> True

        online 事件更新心跳时间戳，与同步请求一样走时间基准判断，
        不永久有效。避免本地发 online 后崩溃导致云端永久不接管。

        Returns:
            True 表示本地在线，False 表示离线
        """
        with self._lock:
            if self._last_event == "offline":
                return False  # 显式 offline，优先判断
            if self._last_heartbeat is None:
                return False  # 从未连接
            elapsed = (datetime.now(timezone.utc) - self._last_heartbeat).total_seconds()
            return elapsed < HEARTBEAT_TIMEOUT_SECONDS


# 单例
heartbeat_manager = HeartbeatManager()
