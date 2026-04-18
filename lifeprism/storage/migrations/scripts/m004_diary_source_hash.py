"""
m004_diary_source_hash - diary 表新增 diary_source_hash 字段

用于追踪 AI 总结时使用的正文 hash，判断总结是否需要刷新。
"""
VERSION = 4
NAME = "m004_diary_source_hash"


def check_if_applied(cursor) -> bool:
    """检查 diary 是否已经包含 diary_source_hash 字段"""
    cursor.execute("PRAGMA table_info(diary)")
    columns = {row[1] for row in cursor.fetchall()}
    return "diary_source_hash" in columns


def upgrade(cursor) -> None:
    """添加 diary_source_hash 字段"""
    cursor.execute("ALTER TABLE diary ADD COLUMN diary_source_hash TEXT DEFAULT NULL")
