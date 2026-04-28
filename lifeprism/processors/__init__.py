"""
数据模块
"""
from lifeprism.utils import LazySingleton
from .provider.processor_aw_data_provider import ProcessorAWDataProvider
from .provider.processor_monitor_data_provider import ProcessorMonitorDataProvider

# 懒加载单例（首次访问时才初始化）
processor_aw_data_provider:ProcessorAWDataProvider = LazySingleton(ProcessorAWDataProvider)
processor_monitor_data_provider:ProcessorMonitorDataProvider = LazySingleton(ProcessorMonitorDataProvider)

__all__ = [
    "processor_aw_data_provider",
    "processor_monitor_data_provider"
]
