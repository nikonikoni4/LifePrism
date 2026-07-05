"""Config 模块异常定义。

Config 模块异常继承自 ConfigError(LWBaseError)，因为配置错误
不一定是数据库问题（可能是文件缺失、格式错误等），
不归属于 DataAccessError。
"""
from lifeprism.utils.exceptions import LWBaseError


from typing import Any


class ConfigError(LWBaseError):
    """配置模块基础异常。"""
    pass


class ConfigFileNotFoundError(ConfigError):
    """配置文件不存在。"""

    def __init__(self, config_path: str, cause: Exception = None):
        super().__init__(
            message=f"配置文件不存在: {config_path}",
            code="CONFIG_FILE_NOT_FOUND",
            details={"config_path": config_path},
            cause=cause,
        )


class InvalidConfigError(ConfigError):
    """配置值无效或格式错误。"""

    def __init__(self, key: str, expected: str, actual: Any):
        super().__init__(
            message=f"配置项 '{key}' 无效: 期望 {expected}，实际 {actual}",
            code="INVALID_CONFIG",
            details={
                "key": key,
                "expected": expected,
                "actual": str(actual),
            },
        )
