"""
配置模块
"""

from . import (
    crawler,  # noqa: F401
    database,  # noqa: F401
)
from .provider_manager import (
    ProviderManager,
    provider_manager,
)
from .settings_manager import (
    ALLOWED_DIRS,
    SettingsManager,
    get_all_settings,
    get_api_key,
    get_setting,
    set_setting,
    settings,
)

try:
    from tzlocal import get_localzone

    LOCAL_TIMEZONE = str(get_localzone())
except ImportError:
    # 如果没有安装 tzlocal，使用默认值
    LOCAL_TIMEZONE = "Asia/Shanghai"


def get_user_timezone() -> str:
    """获取用户配置的时区，优先读 settings，fallback 到 LOCAL_TIMEZONE

    用于所有需要用户本地时区的场景（日期字段生成、时间范围转换等）。
    运行时从 settings.yaml 动态读取，修改后无需重启即可生效。
    """
    try:
        from lifeprism.config.settings_manager import settings

        tz = settings.get("timezone")
        return tz if tz else LOCAL_TIMEZONE
    except Exception:
        return LOCAL_TIMEZONE


__all__ = [
    "settings",
    "database",
    "crawler",
    "SettingsManager",
    "get_setting",
    "set_setting",
    "get_api_key",
    "get_all_settings",
    "provider_manager",
    "ProviderManager",
    "ALLOWED_DIRS",
    "LOCAL_TIMEZONE",
    "get_user_timezone",
]
