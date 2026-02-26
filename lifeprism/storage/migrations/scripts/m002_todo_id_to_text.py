"""
m002_todo_id_to_text - Todo ID 从 INTEGER 迁移为 TEXT

复用现有 migrate_todo_id_to_text.py 的内部函数。
"""
VERSION = 2
NAME = "m002_todo_id_to_text"


def check_if_applied(cursor) -> bool:
    """检查 todo_list.id 是否已经是 TEXT 类型"""
    cursor.execute("PRAGMA table_info(todo_list)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    return columns.get('id') == 'TEXT'


def upgrade(cursor) -> None:
    """调用现有迁移脚本的内部函数"""
    from lifeprism.storage.migrations.migrate_todo_id_to_text import (
        _create_id_map, _rebuild_timeline_custom_block,
        _rebuild_todo_list, _rebuild_indexes, _verify_migration
    )

    # 记录迁移前行数
    cursor.execute("SELECT COUNT(*) FROM todo_list")
    todo_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM timeline_custom_block")
    timeline_count = cursor.fetchone()[0]

    _create_id_map(cursor)
    _rebuild_timeline_custom_block(cursor)
    _rebuild_todo_list(cursor)
    _rebuild_indexes(cursor)
    cursor.execute("DROP TABLE IF EXISTS _todo_id_map")
    _verify_migration(cursor, todo_count, timeline_count)
