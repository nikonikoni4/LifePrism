"""
Todo ID 重构迁移脚本：INTEGER 自增 → TEXT t-{uuid[:8]}

迁移内容：
1. 创建临时映射表 _todo_id_map(old_id INTEGER, new_id TEXT)
2. 填充映射：有 source_anchor_id → 用它，无 → t-{原id}
3. 重建 timeline_custom_block（先于 todo_list，因为需要查旧表的 todo_id 映射）
4. 重建 todo_list（id → TEXT, parent_id → TEXT, 去掉 source_anchor_id）
5. 重建索引（去掉 idx_todo_list_source_anchor_id）
6. 删除临时映射表
7. 迁移后验证

使用方法：
    python -m lifeprism.repository.migrations.migrate_todo_id_to_text
    python -m lifeprism.repository.migrations.migrate_todo_id_to_text --check
"""
import sqlite3
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_db_path() -> Path:
    from lifeprism.config.settings_manager import settings
    return settings.lw_db_path


def run_migration():
    db_path = get_db_path()
    if not db_path.exists():
        logger.error("数据库文件不存在: %s", db_path)
        return False

    logger.info("开始迁移数据库: %s", db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 先检查是否已经迁移过（id 列是否已经是 TEXT）
        cursor.execute("PRAGMA table_info(todo_list)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        if columns.get('id') == 'TEXT':
            logger.info("todo_list.id 已经是 TEXT 类型，跳过迁移")
            return True

        # 记录迁移前行数
        cursor.execute("SELECT COUNT(*) FROM todo_list")
        todo_count_before = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM timeline_custom_block")
        timeline_count_before = cursor.fetchone()[0]
        logger.info("迁移前: todo_list=%s 行, timeline_custom_block=%s 行", todo_count_before, timeline_count_before)

        # 步骤 1: 创建临时映射表
        logger.info("步骤 1: 创建 ID 映射表...")
        _create_id_map(cursor)

        # 步骤 2: 重建 timeline_custom_block（先于 todo_list）
        logger.info("步骤 2: 重建 timeline_custom_block...")
        _rebuild_timeline_custom_block(cursor)

        # 步骤 3: 重建 todo_list
        logger.info("步骤 3: 重建 todo_list...")
        _rebuild_todo_list(cursor)

        # 步骤 4: 重建索引
        logger.info("步骤 4: 重建索引...")
        _rebuild_indexes(cursor)

        # 步骤 5: 删除临时映射表
        logger.info("步骤 5: 清理临时表...")
        cursor.execute("DROP TABLE IF EXISTS _todo_id_map")

        # 步骤 6: 验证
        logger.info("步骤 6: 验证迁移结果...")
        _verify_migration(cursor, todo_count_before, timeline_count_before)

        conn.commit()
        logger.info("迁移完成！")
        return True

    except Exception as e:
        logger.error("迁移失败: error=%s", e)
        conn.rollback()
        return False
    finally:
        conn.close()


def _create_id_map(cursor: sqlite3.Cursor):
    """创建 old_id → new_id 映射表"""
    cursor.execute("DROP TABLE IF EXISTS _todo_id_map")
    cursor.execute("""
        CREATE TABLE _todo_id_map (
            old_id INTEGER PRIMARY KEY,
            new_id TEXT NOT NULL UNIQUE
        )
    """)
    cursor.execute("""
        INSERT INTO _todo_id_map (old_id, new_id)
        SELECT id,
            CASE
                WHEN source_anchor_id IS NOT NULL AND source_anchor_id != ''
                THEN source_anchor_id
                ELSE 't-' || CAST(id AS TEXT)
            END
        FROM todo_list
    """)
    mapped = cursor.rowcount
    logger.info("  映射 %s 条记录", mapped)


def _rebuild_timeline_custom_block(cursor: sqlite3.Cursor):
    """重建 timeline_custom_block，将 todo_id INTEGER → TEXT（通过映射表转换）"""
    # 检查 timeline_custom_block 是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='timeline_custom_block'")
    if not cursor.fetchone():
        logger.info("  timeline_custom_block 表不存在，跳过")
        return

    cursor.execute("""
        CREATE TABLE timeline_custom_block_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            duration INTEGER NOT NULL,
            content TEXT NOT NULL,
            todo_id TEXT,
            color TEXT NOT NULL,
            category_id TEXT,
            sub_category_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            CHECK(end_time > start_time),
            CHECK(duration > 0)
        )
    """)
    cursor.execute("""
        INSERT INTO timeline_custom_block_new
            (id, start_time, end_time, duration, content, todo_id, color,
             category_id, sub_category_id, created_at)
        SELECT
            t.id, t.start_time, t.end_time, t.duration, t.content,
            m.new_id,
            t.color, t.category_id, t.sub_category_id,
            t.created_at
        FROM timeline_custom_block t
        LEFT JOIN _todo_id_map m ON t.todo_id = m.old_id
    """)
    migrated = cursor.rowcount
    cursor.execute("DROP TABLE timeline_custom_block")
    cursor.execute("ALTER TABLE timeline_custom_block_new RENAME TO timeline_custom_block")
    logger.info("  迁移 %s 条 timeline 记录", migrated)


def _rebuild_todo_list(cursor: sqlite3.Cursor):
    """重建 todo_list，id/parent_id → TEXT，去掉 source_anchor_id"""
    cursor.execute("""
        CREATE TABLE todo_list_new (
            id TEXT PRIMARY KEY,
            order_index INTEGER NOT NULL DEFAULT 0,
            pool_order_index INTEGER DEFAULT NULL,
            content TEXT NOT NULL,
            color TEXT DEFAULT '#FFFFFF',
            state TEXT DEFAULT 'pool',
            link_to_goal_id TEXT,
            date TEXT,
            expected_finished_at TEXT,
            actual_finished_at TEXT,
            cross_day INTEGER DEFAULT 0,
            folder_id INTEGER DEFAULT NULL,
            parent_id TEXT DEFAULT NULL,
            plan_doc_id TEXT DEFAULT NULL,
            delay_days INTEGER DEFAULT NULL,
            delay_reason TEXT DEFAULT NULL,
            waid_order INTEGER DEFAULT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        INSERT INTO todo_list_new
            (id, order_index, pool_order_index, content, color, state,
             link_to_goal_id, date, expected_finished_at, actual_finished_at,
             cross_day, folder_id, parent_id, plan_doc_id,
             delay_days, delay_reason, waid_order, created_at)
        SELECT
            m.new_id,
            t.order_index, t.pool_order_index, t.content, t.color, t.state,
            t.link_to_goal_id, t.date, t.expected_finished_at, t.actual_finished_at,
            t.cross_day, t.folder_id,
            pm.new_id,
            t.plan_doc_id,
            t.delay_days, t.delay_reason, t.waid_order, t.created_at
        FROM todo_list t
        JOIN _todo_id_map m ON t.id = m.old_id
        LEFT JOIN _todo_id_map pm ON t.parent_id = pm.old_id
    """)
    migrated = cursor.rowcount
    cursor.execute("DROP TABLE todo_list")
    cursor.execute("ALTER TABLE todo_list_new RENAME TO todo_list")
    logger.info("  迁移 %s 条 todo 记录", migrated)


def _rebuild_indexes(cursor: sqlite3.Cursor):
    """重建索引（不再包含 source_anchor_id 索引）"""
    indexes = [
        ('idx_todo_list_date', 'todo_list', 'date'),
        ('idx_todo_list_cross_day_state', 'todo_list', 'cross_day, state'),
        ('idx_todo_list_link_to_goal_id', 'todo_list', 'link_to_goal_id'),
        ('idx_todo_list_state', 'todo_list', 'state'),
        ('idx_todo_list_parent_id', 'todo_list', 'parent_id'),
        ('idx_todo_list_plan_doc_id', 'todo_list', 'plan_doc_id'),
        ('idx_timeline_custom_block_start_time', 'timeline_custom_block', 'start_time'),
        ('idx_timeline_custom_block_end_time', 'timeline_custom_block', 'end_time'),
        ('idx_timeline_custom_block_time_range', 'timeline_custom_block', 'start_time, end_time'),
        ('idx_timeline_custom_block_todo_id', 'timeline_custom_block', 'todo_id'),
    ]
    for name, table, cols in indexes:
        cursor.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table}({cols})")
        logger.info("  创建索引: %s", name)


def _verify_migration(cursor: sqlite3.Cursor, todo_expected: int, timeline_expected: int):
    """验证迁移结果"""
    errors = []

    # 行数一致
    cursor.execute("SELECT COUNT(*) FROM todo_list")
    todo_actual = cursor.fetchone()[0]
    if todo_actual != todo_expected:
        errors.append(f"todo_list 行数不一致: 期望 {todo_expected}, 实际 {todo_actual}")

    cursor.execute("SELECT COUNT(*) FROM timeline_custom_block")
    timeline_actual = cursor.fetchone()[0]
    if timeline_actual != timeline_expected:
        errors.append(f"timeline_custom_block 行数不一致: 期望 {timeline_expected}, 实际 {timeline_actual}")

    # id 列类型
    cursor.execute("PRAGMA table_info(todo_list)")
    col_types = {row[1]: row[2] for row in cursor.fetchall()}
    if col_types.get('id') != 'TEXT':
        errors.append(f"todo_list.id 类型错误: {col_types.get('id')}")
    if col_types.get('parent_id') != 'TEXT':
        errors.append(f"todo_list.parent_id 类型错误: {col_types.get('parent_id')}")
    if 'source_anchor_id' in col_types:
        errors.append("todo_list 仍包含 source_anchor_id 列")

    # parent_id 引用完整性
    cursor.execute("""
        SELECT COUNT(*) FROM todo_list
        WHERE parent_id IS NOT NULL
          AND parent_id NOT IN (SELECT id FROM todo_list)
    """)
    orphan_count = cursor.fetchone()[0]
    if orphan_count > 0:
        errors.append(f"parent_id 引用不完整: {orphan_count} 条孤儿记录")

    # timeline todo_id 引用完整性
    cursor.execute("""
        SELECT COUNT(*) FROM timeline_custom_block
        WHERE todo_id IS NOT NULL
          AND todo_id NOT IN (SELECT id FROM todo_list)
    """)
    orphan_timeline = cursor.fetchone()[0]
    if orphan_timeline > 0:
        errors.append(f"timeline todo_id 引用不完整: {orphan_timeline} 条孤儿记录")

    if errors:
        for e in errors:
            logger.error("  验证失败: %s", e)
        raise RuntimeError("迁移验证失败: " + "; ".join(errors))

    logger.info("  验证通过: todo=%s, timeline=%s, 无孤儿引用", todo_actual, timeline_actual)


def check_migration_status():
    """检查迁移状态"""
    db_path = get_db_path()
    if not db_path.exists():
        print(f"数据库文件不存在: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(todo_list)")
        col_types = {row[1]: row[2] for row in cursor.fetchall()}

        print("=== Todo ID 迁移状态检查 ===")
        print(f"数据库路径: {db_path}")
        print(f"id 类型: {col_types.get('id', '未知')}")
        print(f"parent_id 类型: {col_types.get('parent_id', '未知')}")
        print(f"source_anchor_id 存在: {'source_anchor_id' in col_types}")

        cursor.execute("SELECT COUNT(*) FROM todo_list")
        print(f"todo 总数: {cursor.fetchone()[0]}")

        if col_types.get('id') == 'TEXT' and 'source_anchor_id' not in col_types:
            print("✓ 迁移已完成")
        else:
            print("✗ 需要执行迁移")
    finally:
        conn.close()


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--check':
        check_migration_status()
    else:
        run_migration()
