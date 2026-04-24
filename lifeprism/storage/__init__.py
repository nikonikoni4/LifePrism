"""
Storage Layer - 数据访问层统一入口

架构设计：
- Provider: 单表数据访问（内部实现）
- Aggregator: 多表数据聚合（内部实现）
- Store: 统一对外接口（使用 as 重命名）

使用方式：
    from lifeprism.storage import diary_store, habit_store

    # 统一的 store 接口，无需区分 provider 或 aggregator
    diaries = diary_store.query_diaries(options)
    habits = habit_store.get_habits_with_challenges()

参考文档：docs/temp/Investigation/2026-04-24-provider-aggregator-architecture-research.md
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

# ==================== 单表 Store（内部是 Provider）====================
from lifeprism.storage.providers import diary_provider as diary_store
from lifeprism.storage.providers import todo_provider as todo_store
from lifeprism.storage.providers import timeline_provider as timeline_store
from lifeprism.storage.providers import plan_doc_provider as plan_doc_store
from lifeprism.storage.providers import tokens_usage_provider as tokens_usage_store

# ==================== 多表 Store（内部是 Aggregator）====================
from lifeprism.storage.aggregators import habit_aggregator as habit_store
from lifeprism.storage.aggregators import mood_aggregator as mood_store
from lifeprism.storage.aggregators import goal_aggregator as goal_store
from lifeprism.storage.aggregators import habit_chain_aggregator as habit_chain_store
from lifeprism.storage.aggregators import category_aggregator as category_store
from lifeprism.storage.aggregators import map_cache_aggregator as map_cache_store

__all__ = [
    "DatabaseManager",
    "lw_db_manager",
    "aw_db_manager",
    "LWBaseDataProvider",
    "AWBaseDataProvider",
    # 单表 Store
    'diary_store',
    'todo_store',
    'timeline_store',
    'plan_doc_store',
    'tokens_usage_store',
    # 多表 Store
    'habit_store',
    'mood_store',
    'goal_store',
    'habit_chain_store',
    'category_store',
    'map_cache_store',
]