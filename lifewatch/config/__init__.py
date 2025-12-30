"""
配置模块
"""
from .settings import *
from .database import *
from .crawler import *
from .settings_manager import (
    SettingsManager,
    settings,
    get_setting,
    set_setting,
    get_api_key,
    get_all_settings,
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
]