"""
配置模块
"""
from .settings import *
from .database import *
from .crawler import *

__all__ = [
    "settings",
    "database",
    "crawler",
]