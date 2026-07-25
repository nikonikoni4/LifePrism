"""初始化云端数据库：init_database + run_migrations"""
import os
import sys

# 设置云端环境变量
os.environ["LIFEPRISM_DATA_PATH"] = os.path.abspath("explore/LifePrism/localData")

from lifeprism.config.settings_manager import settings
settings._initialize()

from lifeprism.repository import lw_db_manager
from lifeprism.repository.lw_table_manager import LWTableManager
from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider
from lifeprism.repository.migrations.migration_runner import run_migrations

# 重置缓存
LWBaseDataProvider._TABLES_WITH_UPDATE_AT = None
LWBaseDataProvider._TABLES_WITH_TIMESTAMPS = None

# 1. init_database（创建缺失的表，如 deletion_log）
print("=" * 60)
print("Step 1: init_database")
print("=" * 60)
manager = LWTableManager(db_manager=lw_db_manager)
manager.init_database()
print("init_database completed")

# 2. run_migrations（添加 hash_id 列等）
print("\n" + "=" * 60)
print("Step 2: run_migrations")
print("=" * 60)
run_migrations(str(settings.lw_db_path))
print("run_migrations completed")

# 3. 验证
print("\n" + "=" * 60)
print("Step 3: Verify")
print("=" * 60)
import sqlite3
conn = sqlite3.connect(str(settings.lw_db_path))
c = conn.cursor()
c.execute("SELECT MAX(version) FROM schema_version")
print(f"Schema version: {c.fetchone()[0]}")
c.execute("PRAGMA table_info(timeline_custom_block)")
cols = [r[1] for r in c.fetchall()]
print(f"timeline_custom_block columns: {cols}")
print(f"  has hash_id: {'hash_id' in cols}")
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='deletion_log'")
print(f"deletion_log table exists: {c.fetchone() is not None}")
conn.close()
print("\nCloud DB initialization done.")
