"""
LifeWatch 数据库表结构管理器
负责创建表、修改表结构等系统维护功能
"""

import logging
import sqlite3

from lifeprism.config.database import TABLE_CONFIGS

logger = logging.getLogger(__name__)


class LWTableManager:
    """
    LifeWatch 数据库表结构管理器

    负责数据库初始化、表结构创建和统计信息获取
    """

    def __init__(self, db_manager=None):
        """
        初始化表结构管理器

        Args:
            db_manager: DatabaseManager 实例，None 则使用全局单例
        """
        if db_manager is None:
            # 延迟导入避免循环依赖
            from lifeprism.repository import lw_db_manager

            self.db = lw_db_manager
        else:
            self.db = db_manager

    def init_database(self):
        """初始化数据库，根据配置创建所有表

        CREATE TABLE IF NOT EXISTS 对已存在的表是空操作（不会添加新列）。
        新列的添加由 migrations 迁移脚本负责，本方法仅负责建表和建索引。
        如果索引引用的列尚不存在（旧表未迁移），跳过该索引并记录 warning，
        待迁移脚本补列后，下次启动时自然会创建索引。
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            for _table_name, config in TABLE_CONFIGS.items():
                self._create_table_from_config(cursor, config)

            logger.info("数据库初始化成功，共创建 %s 个表", len(TABLE_CONFIGS))

    def _create_table_from_config(self, cursor: sqlite3.Cursor, config: dict):
        """
        根据配置创建表

        Args:
            cursor: 数据库游标
            config: 表配置字典
        """
        table_name = config["table_name"]
        columns = config["columns"]
        table_constraints = config.get("table_constraints", [])
        indexes = config.get("indexes", [])
        timestamps = config.get("timestamps", False)
        update_at = config.get("update_at", False)
        # 1. 构建列定义
        column_definitions = []
        for col_name, col_config in columns.items():
            col_type = col_config["type"]
            col_constraints = col_config.get("constraints", [])

            # 组装列定义
            col_def = f"{col_name} {col_type}"
            if col_constraints:
                col_def += " " + " ".join(col_constraints)

            column_definitions.append(col_def)

        # 2. 添加时间戳列（SQLite datetime('now') 返回 UTC 时间）
        if timestamps:
            column_definitions.append("created_at TIMESTAMP DEFAULT (datetime('now'))")
            if update_at:
                column_definitions.append("updated_at TIMESTAMP DEFAULT (datetime('now'))")

        # 3. 添加表级约束
        all_constraints = column_definitions + table_constraints

        # 4. 组装 CREATE TABLE 语句
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            {", ".join(all_constraints)}
        );
        """

        cursor.execute(create_table_sql)
        # logger.info(f"表 '{table_name}' 创建成功")

        # 5. 创建索引（跳过引用不存在列的索引，待迁移补列后下次启动创建）
        existing_columns = self._get_table_columns(cursor, table_name)
        for index in indexes:
            index_name = index["name"]
            index_columns = index["columns"]
            # 检查索引引用的列是否都存在（旧表可能尚未迁移）
            missing_cols = [c for c in index_columns if c not in existing_columns]
            if missing_cols:
                logger.warning(
                    "跳过索引 '%s' on %s：列 %s 不存在（待迁移脚本补列）",
                    index_name,
                    table_name,
                    missing_cols,
                )
                continue
            index_columns_str = ", ".join(index_columns)
            create_index_sql = f"""
            CREATE INDEX IF NOT EXISTS {index_name}
            ON {table_name}({index_columns_str});
            """
            cursor.execute(create_index_sql)
            logger.debug("索引 '%s' 创建成功", index_name)

    @staticmethod
    def _get_table_columns(cursor: sqlite3.Cursor, table_name: str) -> set[str]:
        """获取表已存在的列名集合"""
        cursor.execute(f'PRAGMA table_info("{table_name}")')
        return {row[1] for row in cursor.fetchall()}


# ==================== 便捷函数 ====================


def init_database():
    """
    便捷函数：初始化数据库

    在应用启动时调用此函数来创建所有表
    """
    LWTableManager().init_database()
