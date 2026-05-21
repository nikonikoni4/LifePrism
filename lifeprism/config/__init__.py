"""
配置模块
"""
from .database import *
from .crawler import *
from .settings_manager import (
    SettingsManager,
    settings,
    get_setting,
    set_setting,
    get_api_key,
    get_all_settings,
    ALLOWED_DIRS
)
from .provider_manager import (
    ProviderManager,
    provider_manager,
)

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
]