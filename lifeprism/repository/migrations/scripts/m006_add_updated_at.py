"""
m006_add_updated_at - 为 7 张旧表补充 updated_at 列 + 索引

TABLE_CONFIGS 中已将这 7 张表的 update_at 设为 True，
但旧数据库的表结构缺少 updated_at 列，导致 init_database() 创建索引时报错。

本迁移为这些表 ALTER TABLE ADD COLUMN updated_at，并创建对应索引。
"""

VERSION = 6
NAME = "m006_add_updated_at"

# 需要补充 updated_at 列的表及其索引名
TABLES_TO_MIGRATE = [
    "behavior_analysis",
    "category",
    "sub_category",
    "todo_list",
    "goal",
    "mood_entries",
    "user_app_behavior_log",
]


def check_if_applied(cursor) -> bool:
    """检查所有目标表是否都已包含 updated_at 列"""
    for table in TABLES_TO_MIGRATE:
        cursor.execute(f'PRAGMA table_info("{table}")')
        columns = {row[1] for row in cursor.fetchall()}
        if "updated_at" not in columns:
            return False
    return True


def upgrade(cursor) -> None:
    """为 7 张表添加 updated_at 列和索引

    SQLite ALTER TABLE ADD COLUMN 不支持非常量默认值（如 datetime('now')），
    因此先加无默认值的列，再 backfill 现有行，最后建索引。
    """
    for table in TABLES_TO_MIGRATE:
        # 检查表是否已存在（旧数据库可能没有某些表）
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        if not cursor.fetchone():
            continue

        # 检查是否已有 updated_at 列
        cursor.execute(f'PRAGMA table_info("{table}")')
        columns = {row[1] for row in cursor.fetchall()}
        if "updated_at" in columns:
            continue

        # 添加 updated_at 列（无常量默认值，SQLite 限制）
        cursor.execute(f'ALTER TABLE "{table}" ADD COLUMN updated_at TIMESTAMP')

        # backfill：为现有行设置当前时间
        cursor.execute(
            f"UPDATE \"{table}\" SET updated_at = datetime('now', 'localtime') "
            f"WHERE updated_at IS NULL"
        )

        # 创建索引（使用 TABLE_CONFIGS 中的命名规范）
        index_name = f"idx_{table}_updated_at"
        cursor.execute(f'CREATE INDEX IF NOT EXISTS {index_name} ON "{table}"(updated_at)')
