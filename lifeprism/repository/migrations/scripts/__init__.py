"""
迁移脚本注册表

显式注册所有迁移脚本（不做文件系统扫描，兼容 PyInstaller 打包）。
新增迁移时在此处 import 并追加到 MIGRATIONS 列表。
"""

from . import (
    m001_baseline,
    m002_todo_id_to_text,
    m003_value_keyword_to_keywords,
    m004_diary_source_hash,
    m005_behavior_log_id_to_autoincrement,
    m006_add_updated_at,
    m007_add_updated_at_supplement,
    m008_migrate_to_utc,
    m009_migrate_history_to_utc,
    m010_add_event_time,
    m011_add_event_time_to_mood,
    m012_add_updated_at_to_sync_tables,
)

MIGRATIONS = [
    m001_baseline,
    m002_todo_id_to_text,
    m003_value_keyword_to_keywords,
    m004_diary_source_hash,
    m005_behavior_log_id_to_autoincrement,
    m006_add_updated_at,
    m007_add_updated_at_supplement,
    m008_migrate_to_utc,
    m009_migrate_history_to_utc,
    m010_add_event_time,
    m011_add_event_time_to_mood,
    m012_add_updated_at_to_sync_tables,
]
