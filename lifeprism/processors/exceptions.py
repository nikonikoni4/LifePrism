"""Processors 模块异常定义。

Processors 模块所有异常继承自 ProcessorError(DataAccessError)，
由 API 层的全局异常处理器统一转换为 HTTP 500。
"""
from lifeprism.utils.exceptions import DataAccessError


class ProcessorError(DataAccessError):
    """Processors 模块基础异常。"""
    pass


class ClassificationError(ProcessorError):
    """分类处理失败（LLM 调用失败或分类结果无效）。"""

    def __init__(self, app_name: str, reason: str, cause: Exception = None):
        super().__init__(
            message=f"应用分类失败: {app_name} - {reason}",
            code="CLASSIFICATION_ERROR",
            details={
                "app": app_name,
                "reason": reason,
            },
            cause=cause,
        )


class CacheUpdateError(ProcessorError):
    """缓存更新或同步失败。"""

    def __init__(self, cache_name: str, reason: str, cause: Exception = None):
        super().__init__(
            message=f"缓存更新失败: {cache_name} - {reason}",
            code="CACHE_UPDATE_ERROR",
            details={
                "cache": cache_name,
                "reason": reason,
            },
            cause=cause,
        )
