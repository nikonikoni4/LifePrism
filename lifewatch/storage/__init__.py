"""
存储模块
"""
from .database_manager import DatabaseManager
from lifewatch.config.database import LW_DB_PATH, ACTIVITYWATCH_DB_PATH

# ==================== 全局单例实例 ====================

# LifeWatch 数据库（读写，使用连接池）
lw_db_manager = DatabaseManager(
    LW_DB_PATH=LW_DB_PATH,
    use_pool=True,
    pool_size=5
)

# ActivityWatch 数据库（只读，使用连接池）
aw_db_manager = DatabaseManager(
    LW_DB_PATH=ACTIVITYWATCH_DB_PATH,
    use_pool=True,
    pool_size=3,
    readonly=True
)

__all__ = [
    "DatabaseManager",
    "lw_db_manager",
    "aw_db_manager",
]