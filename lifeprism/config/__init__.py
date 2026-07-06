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
]
