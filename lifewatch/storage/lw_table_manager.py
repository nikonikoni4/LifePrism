"""
LifeWatch 数据库表结构管理器
负责创建表、修改表结构等系统维护功能
"""
import sqlite3
import logging
from typing import Dict, Optional

from lifewatch.config.database import TABLE_CONFIGS

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
            from lifewatch.storage import lw_db_manager
            self.db = lw_db_manager
        else:
            self.db = db_manager
    
    def init_database(self):
        """初始化数据库，根据配置创建所有表"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 遍历所有表配置并创建表
                for table_name, config in TABLE_CONFIGS.items():
                    self._create_table_from_config(cursor, config)
                
                logger.info(f"数据库初始化成功，共创建 {len(TABLE_CONFIGS)} 个表")
                
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise
    
    def _create_table_from_config(self, cursor: sqlite3.Cursor, config: dict):
        """
        根据配置创建表
        
        Args:
            cursor: 数据库游标
            config: 表配置字典
        """
        table_name = config['table_name']
        columns = config['columns']
        table_constraints = config.get('table_constraints', [])
        indexes = config.get('indexes', [])
        timestamps = config.get('timestamps', False)
        
        # 1. 构建列定义
        column_definitions = []
        for col_name, col_config in columns.items():
            col_type = col_config['type']
            col_constraints = col_config.get('constraints', [])
            
            # 组装列定义
            col_def = f"{col_name} {col_type}"
            if col_constraints:
                col_def += " " + " ".join(col_constraints)
            
            column_definitions.append(col_def)
        
        # 2. 添加时间戳列
        if timestamps:
            column_definitions.append(
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            )
            # 只有首次创建时添加updated_at，某些表不需要
            if table_name == 'app_purpose_category':
                column_definitions.append(
                    "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                )
        
        # 3. 添加表级约束
        all_constraints = column_definitions + table_constraints
        
        # 4. 组装 CREATE TABLE 语句
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            {', '.join(all_constraints)}
        );
        """
        
        cursor.execute(create_table_sql)
        logger.info(f"表 '{table_name}' 创建成功")
        
        # 5. 创建索引
        for index in indexes:
            index_name = index['name']
            index_columns = ', '.join(index['columns'])
            create_index_sql = f"""
            CREATE INDEX IF NOT EXISTS {index_name} 
            ON {table_name}({index_columns});
            """
            cursor.execute(create_index_sql)
            logger.debug(f"索引 '{index_name}' 创建成功")
    
    def get_database_stats(self) -> Dict:
        """
        获取 LifeWatch 数据库统计信息
        
        Returns:
            Dict: 包含以下统计信息：
                - database_file: 数据库文件路径
                - {table_name}_rows: 各表行数
                - unique_apps: 唯一应用数量
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                stats = {
                    'database_file': self.db.DB_PATH
                }
                
                # 获取每个表的统计信息
                for table_name in TABLE_CONFIGS.keys():
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cursor.fetchone()[0]
                    stats[f'{table_name}_rows'] = count
                
                # 额外统计：唯一应用数量
                cursor.execute("SELECT COUNT(DISTINCT app) FROM app_purpose_category")
                stats['unique_apps'] = cursor.fetchone()[0]
                
                return stats
                
        except Exception as e:
            logger.error(f"获取数据库统计失败: {e}")    
            return {'database_file': self.db.DB_PATH, 'error': str(e)}


# ==================== 便捷函数 ====================

def init_database():
    """
    便捷函数：初始化数据库
    
    在应用启动时调用此函数来创建所有表
    """
    LWTableManager().init_database()


if __name__ == "__main__":
    # 测试表结构管理器
    manager = LWTableManager()
    manager.init_database()
    stats = manager.get_database_stats()
    print("数据库统计:", stats)
