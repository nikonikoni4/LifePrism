"""Monitor 模块异常定义。"""

from lifeprism.utils.exceptions import DataAccessError


class MonitorError(DataAccessError):
    """Monitor 模块基础异常。"""
    pass


class FatalError(MonitorError):
    """Monitor 致命错误（如 Windows API 初始化失败）。"""
    pass
