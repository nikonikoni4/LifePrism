"""
m007_add_updated_at_supplement - 补充 3 张遗漏同步表的 updated_at

P2 数据同步方案中 goal_journal / daily_focus / weekly_focus 是同步表
（见 PRD 第 297-298 行），但 m006 创建时遗漏了这 3 张表。
本迁移为它们补充 updated_at 列和索引。
"""

VERSION = 7
NAME = "m007_add_updated_at_supplement"

TABLES_TO_MIGRATE = [
    "goal_journal",
    "daily_focus",
    "weekly_focus",
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
    """为 3 张表添加 updated_at 列和索引"""
    for table in TABLES_TO_MIGRATE:
        # 检查表是否已存在
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        if not cursor.fetchone():
            continue

        # 检查是否已有 updated_at 列（幂等）
        cursor.execute(f'PRAGMA table_info("{table}")')
        columns = {row[1] for row in cursor.fetchall()}
        if "updated_at" in columns:
            continue

        # 添加列
        cursor.execute(f'ALTER TABLE "{table}" ADD COLUMN updated_at TIMESTAMP')

        # backfill 现有行
        cursor.execute(
            f"UPDATE \"{table}\" SET updated_at = datetime('now', 'localtime') "
            f"WHERE updated_at IS NULL"
        )

        # 创建索引
        index_name = f"idx_{table}_updated_at"
        cursor.execute(f'CREATE INDEX IF NOT EXISTS {index_name} ON "{table}"(updated_at)')
