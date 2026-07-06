"""
m003_value_keyword_to_keywords - user_values 表字段迁移

复用现有 migrate_value_keyword_to_keywords.py 的内部函数。
"""

VERSION = 3
NAME = "m003_value_keyword_to_keywords"


def check_if_applied(cursor) -> bool:
    """检查 user_values 是否已经包含 keywords 字段"""
    cursor.execute("PRAGMA table_info(user_values)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    return "keywords" in columns and "content_positive" in columns


def upgrade(cursor) -> None:
    """调用现有迁移脚本的内部函数"""
    from lifeprism.repository.migrations.migrate_value_keyword_to_keywords import (
        _rebuild_user_values,
        _verify_migration,
    )

    # 记录迁移前行数
    cursor.execute("SELECT COUNT(*) FROM user_values")
    count_before = cursor.fetchone()[0]

    _rebuild_user_values(cursor)
    _verify_migration(cursor, count_before)
