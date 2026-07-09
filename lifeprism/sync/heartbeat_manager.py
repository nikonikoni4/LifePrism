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

    通过心跳时间戳和生命周期事件判断本地是否在线。
    - update_heartbeat() 仅更新时间戳，不改变 _last_event
    - set_event("offline") 立即生效，优先于超时判断
    - set_event("online") 重置状态为在线

    Attributes:
        _last_heartbeat: 最近一次心跳时间
        _last_event: 最近一次生命周期事件 ('online' | 'offline')
        _lock: 线程安全锁
    """

    def __init__(self):
        """初始化心跳管理器，状态为未连接。"""
        self._last_heartbeat: datetime | None = None
        self._last_event: str | None = None  # 'online' | 'offline'
        self._lock = Lock()

    def update_heartbeat(self):
        """更新心跳时间（每次 sync/pull 时调用）。

        仅更新 _last_heartbeat，不改变 _last_event。
        若当前为显式 offline 状态，调用此方法不会恢复在线。
        """
        with self._lock:
            self._last_heartbeat = datetime.now(timezone.utc)
            logger.debug("心跳已更新，时间: %s", self._last_heartbeat)

    def set_event(self, event: str):
        """设置生命周期事件（'online' | 'offline'）。

        同时更新 _last_event 和 _last_heartbeat。
        - 'offline': 立即生效，is_local_online() 返回 False
        - 'online': 重置状态为在线

        Args:
            event: 生命周期事件，可选值: online, offline
        """
        with self._lock:
            self._last_event = event
            self._last_heartbeat = datetime.now(timezone.utc)
            logger.info("生命周期事件设置为: %s", event)

    def is_local_online(self) -> bool:
        """判断本地是否在线。

        判断优先级：
        1. 显式 offline 事件 -> False（立即生效，不等超时）
        2. 从未连接（_last_heartbeat 为 None）-> False
        3. 心跳超时（超过 HEARTBEAT_TIMEOUT_SECONDS 秒）-> False
        4. 其他情况 -> True

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
