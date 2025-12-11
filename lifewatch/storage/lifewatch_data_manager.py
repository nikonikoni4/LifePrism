"""
LifeWatch 业务数据管理器
继承 DatabaseManager，实现 LifeWatch 项目特定的业务逻辑
"""
import pandas as pd
from typing import Set, Dict, Optional
import logging

from lifewatch.storage.database_manager import DatabaseManager
from lifewatch.config.database import TABLE_CONFIGS, LW_DB_PATH

logger = logging.getLogger(__name__)


class LifeWatchDataManager(DatabaseManager):
    """
    LifeWatch 数据管理器
    
    继承自 DatabaseManager，添加 LifeWatch 项目特定的业务逻辑
    包括应用分类管理、用户行为日志管理等
    """
    
    def __init__(self, LW_DB_PATH: str = LW_DB_PATH, use_pool: bool = True, pool_size: int = 5):
        """
        初始化 LifeWatch 数据管理器
        
        Args:
            LW_DB_PATH: 数据库文件路径
            use_pool: 是否启用连接池
            pool_size: 连接池大小
        """
        super().__init__(LW_DB_PATH, use_pool, pool_size)
    
    # ==================== 应用分类管理 ====================
    
    def get_existing_apps(self) -> Set[str]:
        """
        从app_purpose_category表获取已存在的单一用途应用集合
        
        Returns:
            Set[str]: 应用名称集合（不包括多用途应用）
        """
        try:
            df = self.query('app_purpose_category', 
                          columns=['app'],
                          where={'is_multipurpose_app': 0})
            existing_apps = set(df['app'].dropna().tolist()) if not df.empty else set()
            logger.info(f"从数据库获取到 {len(existing_apps)} 个已有应用")
            return existing_apps
        except Exception as e:
            logger.error(f"获取已有应用失败: {e}")
            return set()
    
    def load_app_purpose_category(self) -> Optional[pd.DataFrame]:
        """
        获取app_purpose_category表中的所有数据
        
        Returns:
            Optional[pd.DataFrame]: 包含所有应用分类数据的DataFrame，如果为空返回None
        """
        df = self.query('app_purpose_category')
        return df if not df.empty else None
    
    def save_app_purpose_category(self, ai_metadata_df: pd.DataFrame) -> int:
        """
        保存AI元数据到app_purpose_category表
        
        使用 UPSERT 策略：已存在的应用会被更新，新应用会被插入
        自动处理字段名映射：'class' -> 'sub_category'
        
        Args:
            ai_metadata_df: AI元数据DataFrame，应包含以下字段：
                - app: 应用名称（必需）
                - title: 应用标题（可选）
                - is_multipurpose_app: 是否多用途应用（可选）
                - app_description: 应用描述（可选）
                - title_description: 标题描述（可选）
                - class 或 sub_category: 分类（可选）
        
        Returns:
            int: 受影响的行数
        """
        try:
            data_list = ai_metadata_df.to_dict('records')
            
            # 映射字段名：'class' -> 'sub_category'
            for data in data_list:
                if 'class' in data and 'sub_category' not in data:
                    data['sub_category'] = data.pop('class')
            
            affected = self.upsert_many('app_purpose_category', 
                                       data_list, 
                                       conflict_columns=['app'])
            logger.info(f"成功保存 {len(data_list)} 行AI元数据到数据库")
            return affected
        except Exception as e:
            logger.error(f"保存AI元数据失败: {e}")
            raise
    
    def load_categories(self) -> Optional[pd.DataFrame]:
        """
        获取所有主分类
        
        Returns:
            Optional[pd.DataFrame]: 包含所有主分类数据的DataFrame，如果为空返回None
        """
        df = self.query('category', order_by='order_index ASC')
        return df if not df.empty else None
    
    def load_sub_categories(self) -> Optional[pd.DataFrame]:
        """
        获取所有子分类
        
        Returns:
            Optional[pd.DataFrame]: 包含所有子分类数据的DataFrame，如果为空返回None
        """
        df = self.query('sub_category', order_by='order_index ASC')
        return df if not df.empty else None

    
    # ==================== 用户行为日志管理 ====================
    
    def load_user_app_behavior_log(self, 
                                   start_time: str = None,
                                   end_time: str = None,
                                   app_filter: str = None) -> Optional[pd.DataFrame]:
        """
        从user_app_behavior_log表加载数据
        
        Args:
            start_time: 开始时间（可选），格式：'YYYY-MM-DD HH:MM:SS'
            end_time: 结束时间（可选）
            app_filter: 应用过滤（可选），只返回指定应用的记录
        
        Returns:
            Optional[pd.DataFrame]: 包含行为日志数据的DataFrame，如果为空返回None
        """
        where = {}
        if app_filter:
            where['app'] = app_filter
        
        # 如果有时间范围，需要使用原始SQL（因为需要范围查询）
        if start_time or end_time:
            sql = "SELECT * FROM user_app_behavior_log WHERE 1=1"
            params = []
            
            if app_filter:
                sql += " AND app = ?"
                params.append(app_filter)
            
            if start_time:
                sql += " AND start_time >= ?"
                params.append(start_time)
            
            if end_time:
                sql += " AND end_time <= ?"
                params.append(end_time)
            
            sql += " ORDER BY start_time DESC"
            
            with self.get_connection() as conn:
                df = pd.read_sql_query(sql, conn, params=params)
            return df if not df.empty else None
        else:
            df = self.query('user_app_behavior_log', 
                          where=where if where else None,
                          order_by='start_time DESC')
            return df if not df.empty else None
    
    def get_latest_end_time(self) -> Optional[str]:
        """
        获取数据库中最新的 end_time
        用于增量同步，获取上次同步的最后时间点
        
        Returns:
            Optional[str]: 最新的 end_time，格式：'YYYY-MM-DD HH:MM:SS'，如果表为空返回 None
        """
        try:
            sql = "SELECT MAX(end_time) as latest_end_time FROM user_app_behavior_log"
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                result = cursor.fetchone()
                latest_time = result[0] if result and result[0] else None
                
                if latest_time:
                    logger.info(f"数据库中最新的 end_time: {latest_time}")
                else:
                    logger.info("数据库为空，没有历史数据")
                
                return latest_time
        except Exception as e:
            logger.error(f"获取最新 end_time 失败: {e}")
            return None
    
    def save_user_app_behavior_log(self, cleaned_events_df: pd.DataFrame) -> int:
        """
        保存行为分类后的数据到user_app_behavior_log表
        
        使用 INSERT OR IGNORE 策略，避免插入重复记录（基于 UNIQUE(app, start_time) 约束）
        自动生成 event_id 如果不存在
        
        Args:
            cleaned_events_df: 清洗后的事件数据DataFrame，应包含以下字段：
                - start_time: 开始时间（必需）
                - end_time: 结束时间（必需）
                - app: 应用名称（必需）
                - id: 事件ID（可选，不存在会自动生成）
                - duration: 持续时间（可选）
                - title: 窗口标题（可选）
                - category: 默认分类（可选）
                - sub_category: 目标分类（可选）
                - is_multipurpose_app: 是否多用途应用（可选）
                - category_id: 主分类ID（可选）
                - sub_category_id: 子分类ID（可选）
        
        Returns:
            int: 实际插入的行数
        """
        try:
            data_list = []
            for _, row in cleaned_events_df.iterrows():
                # 确保id字段存在，自动生成如果缺失
                event_id = row.get('id', f"event_{row.get('start_time', '')}_{row.get('app', 'unknown')}")
                
                data_list.append({
                    'id': event_id,
                    'start_time': row['start_time'],
                    'end_time': row['end_time'],
                    'duration': row.get('duration'),
                    'app': row['app'],
                    'title': row.get('title'),
                    'category': row.get('category'),
                    'sub_category': row.get('sub_category'),
                    'is_multipurpose_app': int(row.get('is_multipurpose_app', False)),
                    'category_id': row.get('category_id'),
                    'sub_category_id': row.get('sub_category_id')
                })
            
            # 使用 INSERT OR IGNORE（基于 UNIQUE 约束）
            if not data_list:
                return 0
            
            columns = list(data_list[0].keys())
            columns_str = ', '.join(columns)
            placeholders = ', '.join(['?' for _ in columns])
            sql = f"INSERT OR IGNORE INTO user_app_behavior_log ({columns_str}) VALUES ({placeholders})"
            
            values_list = [
                [row.get(col) for col in columns]
                for row in data_list
            ]
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(sql, values_list)
                affected = cursor.rowcount
                logger.info(f"成功保存 {affected} 行清洗数据到数据库（共尝试 {len(data_list)} 行）")
                return affected
                
        except Exception as e:
            logger.error(f"保存清洗数据失败: {e}")
            raise
    
    # ==================== 统计分析 ====================
    
    def get_database_stats(self) -> Dict:
        """
        获取 LifeWatch 数据库统计信息
        
        Returns:
            Dict: 包含以下统计信息：
                - database_file: 数据库文件路径
                - app_purpose_category_rows: 应用分类表行数
                - user_app_behavior_log_rows: 行为日志表行数
                - unique_apps: 唯一应用数量
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                stats = {
                    'database_file': self.LW_DB_PATH
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
            return {'database_file': self.LW_DB_PATH, 'error': str(e)}
    
    def get_app_usage_summary(self, 
                             start_time: str = None, 
                             end_time: str = None) -> pd.DataFrame:
        """
        获取应用使用时长汇总
        
        Args:
            start_time: 开始时间（可选）
            end_time: 结束时间（可选）
        
        Returns:
            pd.DataFrame: 应用使用汇总，包含 app, total_duration, event_count
        """
        sql = """
        SELECT 
            app,
            SUM(duration) as total_duration,
            COUNT(*) as event_count
        FROM user_app_behavior_log
        WHERE 1=1
        """
        params = []
        
        if start_time:
            sql += " AND start_time >= ?"
            params.append(start_time)
        
        if end_time:
            sql += " AND end_time <= ?"
            params.append(end_time)
        
        sql += " GROUP BY app ORDER BY total_duration DESC"
        
        with self.get_connection() as conn:
            df = pd.read_sql_query(sql, conn, params=params)
        
        return df


# ==================== 向后兼容的便捷函数 ====================

def get_app_purpose_category() -> Optional[pd.DataFrame]:
    """
    便捷函数：获取应用用途分类
    
    Returns:
        Optional[pd.DataFrame]: 应用分类数据
    """
    db_manager = LifeWatchDataManager()
    return db_manager.load_app_purpose_category()


if __name__ == "__main__":
    # 测试业务数据管理器
    db = LifeWatchDataManager()
    stats = db.get_database_stats()
    print(db.get_existing_apps())
    print("数据库统计:", stats)
    
    # 测试应用分类
    apps = db.get_existing_apps()
    print(f"已有应用数量: {len(apps)}")
