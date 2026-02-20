"""
任务池 V2 数据库迁移脚本

迁移内容：
1. 在 todo_list 表添加 parent_id, plan_doc_id, source_anchor_id 字段
2. 状态值迁移：inactive -> pool, active -> scheduled
3. 创建新索引

使用方法：
    python -m lifeprism.storage.migrations.migrate_taskpool_v2
"""
import sqlite3
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_db_path() -> Path:
    """获取数据库文件路径"""
    # 从 settings 获取数据库路径
    from lifeprism.config.settings_manager import settings
    return Path(settings.lw_db_path)


def run_migration():
    """执行迁移"""
    db_path = get_db_path()
    
    if not db_path.exists():
        logger.error(f"数据库文件不存在: {db_path}")
        return False
    
    logger.info(f"开始迁移数据库: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. 检查并添加新字段
        logger.info("步骤 1: 添加新字段...")
        _add_new_columns(cursor)
        
        # 2. 迁移状态值
        logger.info("步骤 2: 迁移状态值...")
        _migrate_state_values(cursor)
        
        # 3. 创建新索引
        logger.info("步骤 3: 创建新索引...")
        _create_new_indexes(cursor)
        
        conn.commit()
        logger.info("迁移完成！")
        return True
        
    except Exception as e:
        logger.error(f"迁移失败: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()


def _get_existing_columns(cursor: sqlite3.Cursor, table_name: str) -> set:
    """获取表的现有列名"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def _add_new_columns(cursor: sqlite3.Cursor):
    """添加新字段到 todo_list 表"""
    existing_columns = _get_existing_columns(cursor, 'todo_list')
    
    new_columns = [
        ('parent_id', 'INTEGER DEFAULT NULL'),
        ('plan_doc_id', 'TEXT DEFAULT NULL'),
        ('source_anchor_id', 'TEXT DEFAULT NULL'),
    ]
    
    for col_name, col_def in new_columns:
        if col_name not in existing_columns:
            sql = f"ALTER TABLE todo_list ADD COLUMN {col_name} {col_def}"
            cursor.execute(sql)
            logger.info(f"  添加字段: {col_name}")
        else:
            logger.info(f"  字段已存在: {col_name}")


def _migrate_state_values(cursor: sqlite3.Cursor):
    """迁移状态值"""
    # inactive -> pool
    cursor.execute("UPDATE todo_list SET state = 'pool' WHERE state = 'inactive'")
    inactive_count = cursor.rowcount
    logger.info(f"  inactive -> pool: {inactive_count} 条记录")
    
    # active -> scheduled
    cursor.execute("UPDATE todo_list SET state = 'scheduled' WHERE state = 'active'")
    active_count = cursor.rowcount
    logger.info(f"  active -> scheduled: {active_count} 条记录")


def _create_new_indexes(cursor: sqlite3.Cursor):
    """创建新索引"""
    indexes = [
        ('idx_todo_list_parent_id', 'parent_id'),
        ('idx_todo_list_plan_doc_id', 'plan_doc_id'),
        ('idx_todo_list_source_anchor_id', 'source_anchor_id'),
    ]
    
    for index_name, column in indexes:
        try:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON todo_list({column})")
            logger.info(f"  创建索引: {index_name}")
        except sqlite3.OperationalError as e:
            logger.warning(f"  索引已存在或创建失败: {index_name} - {e}")


def check_migration_status():
    """检查迁移状态"""
    db_path = get_db_path()
    
    if not db_path.exists():
        print(f"数据库文件不存在: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查字段
        existing_columns = _get_existing_columns(cursor, 'todo_list')
        required_columns = {'parent_id', 'plan_doc_id', 'source_anchor_id'}
        missing = required_columns - existing_columns
        
        print("=== 迁移状态检查 ===")
        print(f"数据库路径: {db_path}")
        print(f"必需字段: {required_columns}")
        print(f"缺失字段: {missing if missing else '无'}")
        
        # 检查状态值
        cursor.execute("SELECT state, COUNT(*) FROM todo_list GROUP BY state")
        state_counts = cursor.fetchall()
        print(f"状态分布: {dict(state_counts)}")
        
        if not missing and 'inactive' not in dict(state_counts) and 'active' not in dict(state_counts):
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
