"""
user_values 表字段迁移脚本：keyword → keywords, content → content_positive + content_negative

迁移内容：
1. 将 keyword 字段重命名为 keywords
2. 将 content 字段拆分为 content_positive 和 content_negative
3. 保持 UNIQUE 约束（防止重复）
4. 数据迁移：将单个关键词转换为分号分隔格式（兼容未来多关键词）

使用方法：
    python -m lifeprism.storage.migrations.migrate_value_keyword_to_keywords
    python -m lifeprism.storage.migrations.migrate_value_keyword_to_keywords --check
"""
import sqlite3
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_db_path() -> Path:
    from lifeprism.config.settings_manager import settings
    return Path(settings.lw_db_path)


def run_migration():
    db_path = get_db_path()
    if not db_path.exists():
        logger.error(f"数据库文件不存在: {db_path}")
        return False

    logger.info(f"开始迁移数据库: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 检查是否已经迁移过
        cursor.execute("PRAGMA table_info(user_values)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        if 'keywords' in columns and 'content_positive' in columns:
            logger.info("user_values 已完成迁移（keywords 和 content_positive 字段已存在），跳过迁移")
            return True

        if 'keyword' not in columns:
            logger.error("user_values.keyword 字段不存在，无法迁移")
            return False

        # 记录迁移前行数
        cursor.execute("SELECT COUNT(*) FROM user_values")
        count_before = cursor.fetchone()[0]
        logger.info(f"迁移前: user_values={count_before} 行")

        # 步骤 1: 重建表（keyword → keywords, content → content_positive + content_negative）
        logger.info("步骤 1: 重建 user_values 表...")
        _rebuild_user_values(cursor)

        # 步骤 2: 验证
        logger.info("步骤 2: 验证迁移结果...")
        _verify_migration(cursor, count_before)

        conn.commit()
        logger.info("迁移完成！")
        return True

    except Exception as e:
        logger.error(f"迁移失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def _rebuild_user_values(cursor: sqlite3.Cursor):
    """重建 user_values 表，将 keyword → keywords, content → content_positive + content_negative"""
    cursor.execute("""
        CREATE TABLE user_values_new (
            id TEXT PRIMARY KEY NOT NULL,
            keywords TEXT NOT NULL UNIQUE,
            content_positive TEXT,
            content_negative TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT NULL
        )
    """)

    # 数据迁移：keyword → keywords, content → content_positive（保持原值）
    cursor.execute("""
        INSERT INTO user_values_new
            (id, keywords, content_positive, content_negative, sort_order, created_at, updated_at)
        SELECT
            id, keyword, content, NULL, sort_order, created_at, updated_at
        FROM user_values
    """)
    migrated = cursor.rowcount

    cursor.execute("DROP TABLE user_values")
    cursor.execute("ALTER TABLE user_values_new RENAME TO user_values")
    logger.info(f"  迁移 {migrated} 条记录")


def _verify_migration(cursor: sqlite3.Cursor, expected_count: int):
    """验证迁移结果"""
    errors = []

    # 行数一致
    cursor.execute("SELECT COUNT(*) FROM user_values")
    actual_count = cursor.fetchone()[0]
    if actual_count != expected_count:
        errors.append(f"user_values 行数不一致: 期望 {expected_count}, 实际 {actual_count}")

    # 字段检查
    cursor.execute("PRAGMA table_info(user_values)")
    col_info = {row[1]: {'type': row[2], 'notnull': row[3], 'pk': row[5]} for row in cursor.fetchall()}

    if 'keywords' not in col_info:
        errors.append("user_values.keywords 字段不存在")
    elif col_info['keywords']['type'] != 'TEXT':
        errors.append(f"user_values.keywords 类型错误: {col_info['keywords']['type']}")
    elif col_info['keywords']['notnull'] != 1:
        errors.append("user_values.keywords 缺少 NOT NULL 约束")

    if 'keyword' in col_info:
        errors.append("user_values 仍包含旧的 keyword 字段")

    if 'content' in col_info:
        errors.append("user_values 仍包含旧的 content 字段")

    # UNIQUE 约束检查
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='user_values'")
    table_sql = cursor.fetchone()[0]
    if 'UNIQUE' not in table_sql.upper() or 'keywords' not in table_sql:
        errors.append("user_values.keywords 缺少 UNIQUE 约束")

    # 数据完整性检查
    cursor.execute("SELECT COUNT(*) FROM user_values WHERE keywords IS NULL OR keywords = ''")
    null_count = cursor.fetchone()[0]
    if null_count > 0:
        errors.append(f"存在空 keywords: {null_count} 条")

    if errors:
        for e in errors:
            logger.error(f"  验证失败: {e}")
        raise RuntimeError("迁移验证失败: " + "; ".join(errors))

    logger.info(f"  验证通过: 记录数={actual_count}, keywords/content_positive 字段正常, UNIQUE 约束存在")


def check_migration_status():
    """检查迁移状态"""
    db_path = get_db_path()
    if not db_path.exists():
        print(f"数据库文件不存在: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(user_values)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        print("=== user_values keyword → keywords, content → content_positive + content_negative 迁移状态检查 ===")
        print(f"数据库路径: {db_path}")
        print(f"keyword 字段存在: {'keyword' in columns}")
        print(f"keywords 字段存在: {'keywords' in columns}")
        print(f"content 字段存在: {'content' in columns}")
        print(f"content_positive 字段存在: {'content_positive' in columns}")
        print(f"content_negative 字段存在: {'content_negative' in columns}")

        if 'keywords' in columns:
            print(f"keywords 类型: {columns['keywords']}")
        if 'content_positive' in columns:
            print(f"content_positive 类型: {columns['content_positive']}")

        cursor.execute("SELECT COUNT(*) FROM user_values")
        print(f"记录总数: {cursor.fetchone()[0]}")

        if 'keywords' in columns and 'content_positive' in columns and 'keyword' not in columns and 'content' not in columns:
            print("✓ 迁移已完成")
        elif 'keyword' in columns and 'content' in columns:
            print("✗ 需要执行迁移")
        else:
            print("⚠ 状态异常（部分字段已迁移）")
    finally:
        conn.close()


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--check':
        check_migration_status()
    else:
        run_migration()
