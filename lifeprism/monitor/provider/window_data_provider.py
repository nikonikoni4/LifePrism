"""
Window 数据提供者
提供窗口事件相关的数据库操作
"""

import sqlite3

from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import DataAccessError

logger = get_logger(__name__)


class MonitorDataProvider(LWBaseDataProvider):
    """
    窗口事件数据提供者

    继承 LWBaseDataProvider，提供窗口事件的持久化操作
    """

    def __init__(self, db_manager=None):
        """
        初始化窗口事件提供者

        Args:
            db_manager: DatabaseManager 实例，None 则使用全局单例
        """
        super().__init__(db_manager)

    def save_event(self, timestamp: str, duration: float, app: str, title: str) -> bool:
        """
        保存窗口事件到数据库

        Args:
            timestamp: 事件发生的时间戳 (ISO格式)
            duration: 持续时长(秒)
            app: 应用程序名称
            title: 窗口标题

        Returns:
            bool: 是否保存成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            data = {"timestamp": timestamp, "duration": duration, "app": app, "title": title}

            # 使用 DatabaseManager 的 insert 方法执行插入操作
            # LWBaseDataProvider 通过 self.db 持有 DatabaseManager 的引用
            result = self.db.insert("window_events", data)

            logger.debug("窗口事件保存: app=%s, duration=%.1fs", app, duration)

            return result > 0

        except sqlite3.Error as exc:
            logger.error("保存窗口事件失败: %s", exc)
            raise DataAccessError(f"Failed to insert window event: {exc}") from exc
        except OSError as exc:
            logger.error("数据库 I/O 错误: %s", exc)
            raise DataAccessError(f"Database I/O error: {exc}") from exc
