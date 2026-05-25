"""
m005_behavior_log_id_to_autoincrement - user_app_behavior_log.id 从 TEXT 迁移为 INTEGER AUTOINCREMENT

复用现有 migrate_behavior_log_id_to_autoincrement.py 的内部函数。
"""
VERSION = 5
NAME = "m005_behavior_log_id_to_autoincrement"


def check_if_applied(cursor) -> bool:
    """检查 user_app_behavior_log.id 是否已经是 INTEGER 类型"""
    cursor.execute("PRAGMA table_info(user_app_behavior_log)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    return columns.get('id') == 'INTEGER'


def upgrade(cursor) -> None:
    """执行迁移"""
    # 记录迁移前行数
    cursor.execute("SELECT COUNT(*) FROM user_app_behavior_log")
    count_before = cursor.fetchone()[0]

    # 1. 创建新表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_app_behavior_log_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            duration INTEGER,
            app TEXT NOT NULL,
            title TEXT,
            is_multipurpose_app INTEGER DEFAULT 0,
            category_id TEXT,
            sub_category_id TEXT,
            link_to_goal_id TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            UNIQUE(app, start_time),
            CHECK(end_time > start_time)
        )
    """)

    # 2. 复制数据（按 start_time 排序，让 id 按时间顺序递增）
    cursor.execute("""
        INSERT OR IGNORE INTO user_app_behavior_log_new (
            start_time, end_time, duration, app, title,
            is_multipurpose_app, category_id, sub_category_id,
            link_to_goal_id, created_at
        )
        SELECT
            start_time, end_time, duration, app, title,
            is_multipurpose_app, category_id, sub_category_id,
            link_to_goal_id, created_at
        FROM user_app_behavior_log
        ORDER BY start_time ASC
    """)
    copied_count = cursor.rowcount

    # 3. 删除旧表
    cursor.execute("DROP TABLE IF EXISTS user_app_behavior_log")

    # 4. 重命名新表
    cursor.execute("ALTER TABLE user_app_behavior_log_new RENAME TO user_app_behavior_log")

    # 5. 重建索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_app_start_time ON user_app_behavior_log(app, start_time)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_start_time ON user_app_behavior_log(start_time)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_end_time ON user_app_behavior_log(end_time)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_time_range ON user_app_behavior_log(start_time, end_time)")

    # 验证迁移结果
    cursor.execute("SELECT COUNT(*) FROM user_app_behavior_log")
    count_after = cursor.fetchone()[0]

    if count_after != count_before:
        raise RuntimeError(f"迁移验证失败: 行数不一致 (迁移前: {count_before}, 迁移后: {count_after})")
