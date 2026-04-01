"""
存储模块
"""
from .database_manager import DatabaseManager
from lifeprism.config.settings_manager import settings
# ==================== 全局单例实例 ====================
import os

# 检查并创建数据库文件（如果不存在）
# 防止 readonly 模式下因文件不存在导致连接失败
for db_path in [settings.lw_db_path, settings.chat_db_path]:
    if db_path and not os.path.exists(db_path):
        print(f"Creating database file: {db_path}")
        # 确保目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with open(db_path, 'w') as f:
            pass

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
from .providers.window_data_provider import LWWindowDataProvider

__all__ = [
    "DatabaseManager",
    "lw_db_manager",
    "aw_db_manager",
    "LWBaseDataProvider",
    "AWBaseDataProvider",
    "LWWindowDataProvider",
]