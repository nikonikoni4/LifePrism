"""
存储模块
"""
from .database_manager import DatabaseManager
from lifewatch.config.settings_manager import settings
# ==================== 全局单例实例 ====================

# LifeWatch 数据库（读写，使用连接池）
lw_db_manager = DatabaseManager(
    DB_PATH=settings.lw_db_path,
    use_pool=True,
    pool_size=5
)

# ActivityWatch 数据库（只读，使用连接池）
aw_db_manager = DatabaseManager(
    DB_PATH=settings.aw_db_path,
    use_pool=True,
    pool_size=1,
    readonly=True
)

chat_history_db_manager = DatabaseManager(
    DB_PATH=settings.chat_db_path,
    use_pool=True,
    pool_size=2,
    readonly=True
)

# ==================== 基础数据提供者 ====================
from .base_providers import LWBaseDataProvider, AWBaseDataProvider

__all__ = [
    "DatabaseManager",
    "lw_db_manager",
    "aw_db_manager",
    "LWBaseDataProvider",
    "AWBaseDataProvider",
]