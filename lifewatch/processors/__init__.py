"""
数据模块
"""
from .provider.processor_aw_data_provider import ProcessorAWDataProvider
processor_aw_data_provider = ProcessorAWDataProvider()# 全局唯一实例
__all__ = [
    "processor_aw_data_provider"
]
