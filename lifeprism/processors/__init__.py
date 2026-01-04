"""
数据模块
"""
from lifeprism.utils import LazySingleton
from .provider.processor_aw_data_provider import ProcessorAWDataProvider

# 懒加载单例（首次访问时才初始化）
processor_aw_data_provider = LazySingleton(ProcessorAWDataProvider)

__all__ = [
    "processor_aw_data_provider"
]
