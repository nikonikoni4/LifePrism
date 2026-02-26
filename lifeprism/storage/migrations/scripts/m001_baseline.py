"""
m001_baseline - 基线迁移

对已有数据库标记基线版本。新数据库由 init_database() 创建表结构，
此迁移仅用于版本追踪。
"""
VERSION = 1
NAME = "m001_baseline"


def check_if_applied(cursor) -> bool:
    """category 表存在即视为 baseline 已生效"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='category'")
    return cursor.fetchone() is not None


def upgrade(cursor) -> None:
    """baseline 无需操作，表结构由 init_database() 管理"""
    pass
