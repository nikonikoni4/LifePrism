"""
监控提供者模块
"""

from lifeprism.monitor.provider.screenshot_data_provider import ScreenshotDataProvider
from lifeprism.monitor.provider.window_data_provider import MonitorDataProvider

__all__ = ["MonitorDataProvider", "ScreenshotDataProvider"]
