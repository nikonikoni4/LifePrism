"""
SQLite数据库操作模块
用于管理LifeWatch-AI项目的本地数据存储

完全重构版本，使用配置驱动的设计模式
"""
import sqlite3
import pandas as pd
from pathlib import Path
from typing import Set, Dict, List, Tuple, Optional, Any
from contextlib import contextmanager
from queue import Queue, Empty
import threading
import atexit
import logging

from lifewatch.config.database import (
    TABLE_CONFIGS, 
    get_table_config, 
    get_table_columns,
    LW_DB_PATH as DEFAULT_LW_DB_PATH
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库管理器 - 配置驱动的增强版"""
    
    def __init__(self, LW_DB_PATH: str = None, use_pool: bool = False, pool_size: int = 5, readonly: bool = False):
        """
        初始化数据库管理器
        
        Args:
            LW_DB_PATH: 数据库文件路径，默认使用配置文件中的路径
            use_pool: 是否启用连接池（默认 False，保持向后兼容）
            pool_size: 连接池大小（默认 5）
            readonly: 是否只读模式（用于外部数据库，默认 False）
        """
        self.LW_DB_PATH = LW_DB_PATH 
        self.use_pool = use_pool
        self.pool_size = pool_size
        self.readonly = readonly
        
        # 连接池相关
        self._connection_pool = None
        self._pool_lock = threading.Lock()
        
        if self.use_pool:
            self._init_connection_pool()
            # 注册程序退出时关闭连接池
            atexit.register(self._close_connection_pool)
        
        # 只读模式下跳过数据库初始化（外部数据库不需要创建表）
        if not self.readonly:
            self.init_database()
    
    def _init_connection_pool(self):
        """初始化连接池"""
        logger.info(f"初始化连接池，大小: {self.pool_size}")
        self._connection_pool = Queue(maxsize=self.pool_size)
        
        # 预先创建连接
        for _ in range(self.pool_size):
            conn = self._create_connection()
            self._connection_pool.put(conn)
    
    def _create_connection(self) -> sqlite3.Connection:
        """创建新的数据库连接"""
        if self.readonly:
            # 只读模式打开数据库（用于外部数据库如 ActivityWatch）
            conn = sqlite3.connect(f"file:{self.LW_DB_PATH}?mode=ro", uri=True, check_same_thread=False)
        else:
            conn = sqlite3.connect(self.LW_DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # 启用字典式访问
        return conn
    
    def _get_pooled_connection(self) -> sqlite3.Connection:
        """
        从连接池获取连接
        
        Returns:
            sqlite3.Connection: 数据库连接对象
        """
        try:
            # 尝试从池中获取连接（超时1秒）
            conn = self._connection_pool.get(timeout=1.0)
            # 检查连接是否有效
            try:
                conn.execute("SELECT 1")
                return conn
            except sqlite3.Error:
                # 连接失效，创建新连接
                logger.warning("连接池中的连接失效，创建新连接")
                return self._create_connection()
        except Empty:
            # 池中无可用连接，创建临时连接
            logger.warning("连接池已满，创建临时连接")
            return self._create_connection()
    
    def _return_pooled_connection(self, conn: sqlite3.Connection):
        """
        将连接归还到连接池
        
        Args:
            conn: 数据库连接对象
        """
        try:
            # 尝试归还到池中
            self._connection_pool.put_nowait(conn)
        except:
            # 池已满，关闭连接
            conn.close()
    
    def _close_connection_pool(self):
        """关闭连接池，释放所有连接"""
        if self._connection_pool is None:
            return
        
        logger.info("关闭连接池...")
        closed_count = 0
        
        while not self._connection_pool.empty():
            try:
                conn = self._connection_pool.get_nowait()
                conn.close()
                closed_count += 1
            except Empty:
                break
        
        logger.info(f"连接池已关闭，共关闭 {closed_count} 个连接")
        self._connection_pool = None
    
    @contextmanager
    def get_connection(self):
        """
        获取数据库连接的上下文管理器
        
        自动选择使用连接池或创建新连接
        
        Yields:
            sqlite3.Connection: 数据库连接对象
        """
        if self.use_pool:
            # 使用连接池
            conn = self._get_pooled_connection()
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"数据库操作失败，已回滚: {e}")
                raise
            finally:
                # 归还连接到池
                self._return_pooled_connection(conn)
        else:
            # 不使用连接池，传统方式
            conn = self._create_connection()
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"数据库操作失败，已回滚: {e}")
                raise
            finally:
                conn.close()
    
    def init_database(self):
        """初始化数据库，根据配置创建所有表"""
        try:
            with self.get_connection() as conn:
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
            
            # 添加注释（SQLite不支持行内注释，记录在文档中）
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
    
    # ==================== 通用查询操作 (READ) ====================
    
    def query(self, 
              table_name: str, 
              columns: List[str] = None,
              where: Dict[str, Any] = None,
              order_by: str = None,
              limit: int = None) -> pd.DataFrame:
        """
        通用查询方法
        
        Args:
            table_name: 表名
            columns: 要查询的列名列表，None 表示所有列
            where: 查询条件字典，例如 {'app': 'chrome.exe', 'is_multipurpose_app': 0}
            order_by: 排序字段，例如 'timestamp DESC'
            limit: 限制返回行数
            
        Returns:
            pd.DataFrame: 查询结果
            
        Example:
            df = db.query('app_purpose_category', 
                         columns=['app', 'category'],
                         where={'is_multipurpose_app': 0},
                         order_by='app ASC',
                         limit=100)
        """
        try:
            # 构建 SQL 语句
            select_cols = ', '.join(columns) if columns else '*'
            sql = f"SELECT {select_cols} FROM {table_name}"
            params = []
            
            # 添加 WHERE 子句
            if where:
                where_clauses = []
                for key, value in where.items():
                    where_clauses.append(f"{key} = ?")
                    params.append(value)
                sql += " WHERE " + " AND ".join(where_clauses)
            
            # 添加 ORDER BY 子句
            if order_by:
                sql += f" ORDER BY {order_by}"
            
            # 添加 LIMIT 子句
            if limit:
                sql += f" LIMIT {limit}"
            
            with self.get_connection() as conn:
                df = pd.read_sql_query(sql, conn, params=params)
                # logger.debug(f"查询成功，返回 {len(df)} 行数据")
                logger.info(f"查询成功，返回 {len(df)} 行数据")
                return df if not df.empty else pd.DataFrame()
                
        except Exception as e:
            logger.error(f"查询失败: {e}")
            logger.info(f"查询失败: {e}")
            raise
    
    def get_by_id(self, table_name: str, id_column: str, id_value: Any) -> Optional[Dict]:
        """
        根据ID查询单条记录
        
        Args:
            table_name: 表名
            id_column: ID列名（例如 'app' 或 'id'）
            id_value: ID值
            
        Returns:
            Optional[Dict]: 记录字典，如果不存在返回 None
        """
        df = self.query(table_name, where={id_column: id_value}, limit=1)
        if df.empty:
            return None
        return df.iloc[0].to_dict()
    
    # ==================== 通用插入操作 (CREATE) ====================
    
    def insert(self, table_name: str, data: Dict[str, Any]) -> int:
        """
        插入单条记录
        
        Args:
            table_name: 表名
            data: 数据字典
            
        Returns:
            int: 受影响的行数
        """
        try:
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?' for _ in data])
            sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, list(data.values()))
                logger.debug(f"插入成功: {table_name}")
                return cursor.rowcount
                
        except Exception as e:
            logger.error(f"插入失败: {e}")
            raise
    
    def insert_many(self, table_name: str, data_list: List[Dict[str, Any]]) -> int:
        """
        批量插入记录（高效）
        
        Args:
            table_name: 表名
            data_list: 数据字典列表
            
        Returns:
            int: 受影响的行数
        """
        if not data_list:
            return 0
        
        try:
            # 使用第一条数据确定列名
            columns = list(data_list[0].keys())
            columns_str = ', '.join(columns)
            placeholders = ', '.join(['?' for _ in columns])
            sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
            
            # 准备数据
            values_list = [
                [row.get(col) for col in columns]
                for row in data_list
            ]
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(sql, values_list)
                logger.info(f"批量插入成功: {table_name}, {cursor.rowcount} 行")
                return cursor.rowcount
                
        except Exception as e:
            logger.error(f"批量插入失败: {e}")
            raise
    
    def upsert(self, 
               table_name: str, 
               data: Dict[str, Any],
               conflict_columns: List[str] = None) -> int:
        """
        UPSERT操作（存在则更新，不存在则插入）
        
        Args:
            table_name: 表名
            data: 数据字典
            conflict_columns: 冲突列（用于判断是否存在），None 则使用主键
            
        Returns:
            int: 受影响的行数
        """
        try:
            columns = list(data.keys())
            columns_str = ', '.join(columns)
            placeholders = ', '.join(['?' for _ in columns])
            
            # 构建 UPDATE 子句（排除冲突列）
            if conflict_columns:
                update_columns = [col for col in columns if col not in conflict_columns]
            else:
                update_columns = columns
            
            update_str = ', '.join([f"{col} = excluded.{col}" for col in update_columns])
            
            # 对于有更新时间戳的表，自动更新 updated_at
            config = get_table_config(table_name)
            if config.get('timestamps') and table_name == 'app_purpose_category':
                update_str += ", updated_at = CURRENT_TIMESTAMP"
            
            sql = f"""
            INSERT INTO {table_name} ({columns_str}) 
            VALUES ({placeholders})
            ON CONFLICT DO UPDATE SET {update_str}
            """
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, list(data.values()))
                logger.debug(f"UPSERT成功: {table_name}")
                return cursor.rowcount
                
        except Exception as e:
            logger.error(f"UPSERT失败: {e}")
            raise
    
    def upsert_many(self, 
                    table_name: str, 
                    data_list: List[Dict[str, Any]],
                    conflict_columns: List[str] = None) -> int:
        """
        批量UPSERT操作
        
        Args:
            table_name: 表名
            data_list: 数据字典列表
            conflict_columns: 冲突列
            
        Returns:
            int: 受影响的行数
        """
        if not data_list:
            return 0
        
        total_affected = 0
        try:
            # 使用第一条数据确定列名
            columns = list(data_list[0].keys())
            columns_str = ', '.join(columns)
            placeholders = ', '.join(['?' for _ in columns])
            
            # 构建 UPDATE 子句
            if conflict_columns:
                update_columns = [col for col in columns if col not in conflict_columns]
            else:
                update_columns = columns
            
            update_str = ', '.join([f"{col} = excluded.{col}" for col in update_columns])
            
            # 自动更新时间戳
            config = get_table_config(table_name)
            if config.get('timestamps') and table_name == 'app_purpose_category':
                update_str += ", updated_at = CURRENT_TIMESTAMP"
            
            sql = f"""
            INSERT INTO {table_name} ({columns_str}) 
            VALUES ({placeholders})
            ON CONFLICT DO UPDATE SET {update_str}
            """
            
            # 准备数据
            values_list = [
                [row.get(col) for col in columns]
                for row in data_list
            ]
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(sql, values_list)
                total_affected = cursor.rowcount
                logger.info(f"批量UPSERT成功: {table_name}, {total_affected} 行")
                return total_affected
                
        except Exception as e:
            logger.error(f"批量UPSERT失败: {e}")
            raise
    
    # ==================== 通用更新操作 (UPDATE) ====================
    
    def update(self, 
               table_name: str, 
               data: Dict[str, Any],
               where: Dict[str, Any]) -> int:
        """
        根据条件更新记录
        
        Args:
            table_name: 表名
            data: 要更新的数据字典
            where: 条件字典
            
        Returns:
            int: 受影响的行数
        """
        try:
            # 构建 SET 子句
            set_clauses = [f"{key} = ?" for key in data.keys()]
            set_str = ', '.join(set_clauses)
            
            # 构建 WHERE 子句
            where_clauses = [f"{key} = ?" for key in where.keys()]
            where_str = ' AND '.join(where_clauses)
            
            sql = f"UPDATE {table_name} SET {set_str} WHERE {where_str}"
            params = list(data.values()) + list(where.values())
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                logger.debug(f"更新成功: {table_name}, {cursor.rowcount} 行")
                return cursor.rowcount
                
        except Exception as e:
            logger.error(f"更新失败: {e}")
            raise
    
    def update_by_id(self, 
                     table_name: str, 
                     id_column: str,
                     id_value: Any,
                     data: Dict[str, Any]) -> int:
        """
        根据ID更新记录
        
        Args:
            table_name: 表名
            id_column: ID列名
            id_value: ID值
            data: 要更新的数据字典
            
        Returns:
            int: 受影响的行数
        """
        return self.update(table_name, data, where={id_column: id_value})
    
    # ==================== 通用删除操作 (DELETE) ====================
    
    def delete(self, table_name: str, where: Dict[str, Any]) -> int:
        """
        根据条件删除记录
        
        Args:
            table_name: 表名
            where: 条件字典
            
        Returns:
            int: 受影响的行数
        """
        try:
            where_clauses = [f"{key} = ?" for key in where.keys()]
            where_str = ' AND '.join(where_clauses)
            
            sql = f"DELETE FROM {table_name} WHERE {where_str}"
            params = list(where.values())
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                logger.info(f"删除成功: {table_name}, {cursor.rowcount} 行")
                return cursor.rowcount
                
        except Exception as e:
            logger.error(f"删除失败: {e}")
            raise
    
    def delete_by_id(self, 
                     table_name: str, 
                     id_column: str,
                     id_value: Any) -> int:
        """
        根据ID删除记录
        
        Args:
            table_name: 表名
            id_column: ID列名
            id_value: ID值
            
        Returns:
            int: 受影响的行数
        """
        return self.delete(table_name, where={id_column: id_value})
    
    def truncate(self, table_name: str):
        """
        清空表（删除所有记录）
        
        Args:
            table_name: 表名
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"DELETE FROM {table_name}")
                logger.warning(f"表 '{table_name}' 已清空, {cursor.rowcount} 行被删除")
                
        except Exception as e:
            logger.error(f"清空表失败: {e}")
            raise



if __name__ == "__main__":
    # 测试数据库功能
    db = DatabaseManager()
    stats = db.get_database_stats()
    print("数据库统计:", stats)