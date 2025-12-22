"""
LifeWatch 基础数据提供者
封装 LW 数据库的通用表操作，供各模块继承使用
"""
import pandas as pd
import logging
from typing import Set, Optional, List, Dict

logger = logging.getLogger(__name__)


class LWBaseDataProvider:
    """
    LifeWatch 基础数据提供者
    
    特点：
    - 内置全局单例，简化继承类的初始化
    - 提供所有通用表的读写方法
    - 各模块继承此类即可使用
    """
    
    def __init__(self, db_manager=None):
        """
        初始化基础数据提供者
        
        Args:
            db_manager: DatabaseManager 实例，None 则使用全局单例
        """
        if db_manager is None:
            from lifewatch.storage import lw_db_manager
            self.db = lw_db_manager
        else:
            self.db = db_manager
    
    # ==================== app_purpose_category 表 ====================
    
    def load_app_purpose_category(self) -> Optional[pd.DataFrame]:
        """
        获取应用分类数据
        
        Returns:
            Optional[pd.DataFrame]: 应用分类数据，包含以下列：
                - app, title, is_multipurpose_app
                - app_description, title_analysis
                - category_id, sub_category_id
                - state, created_at
            为空返回 None
        """
        # 只查询需要的列，不再查询已弃用的 category/sub_category 名称字段
        columns = [
            'app', 'title', 'is_multipurpose_app',
            'app_description', 'title_analysis',
            'category_id', 'sub_category_id',
            'state', 'created_at'
        ]
        df = self.db.query('app_purpose_category', columns=columns)
        return df if not df.empty else None
    
    def get_existing_apps(self) -> Set[str]:
        """
        获取已存在的单一用途应用集合
        
        Returns:
            Set[str]: 应用名称集合（不包括多用途应用）
        """
        try:
            df = self.db.query('app_purpose_category', 
                              columns=['app'],
                              where={'is_multipurpose_app': 0})
            existing_apps = set(df['app'].dropna().tolist()) if not df.empty else set()
            logger.info(f"从数据库获取到 {len(existing_apps)} 个已有应用")
            return existing_apps
        except Exception as e:
            logger.error(f"获取已有应用失败: {e}")
            return set()
    
    def save_app_purpose_category(self, ai_metadata_df: pd.DataFrame) -> int:
        """
        保存AI元数据到 app_purpose_category 表
        
        使用 UPSERT 策略：已存在的应用会被更新，新应用会被插入
        
        Args:
            ai_metadata_df: AI元数据DataFrame，应包含以下字段：
                - app: 应用名称（必需）
                - title: 应用标题（必需）
                - is_multipurpose_app: 是否多用途应用（可选）
                - app_description: 应用描述（可选）
                - title_analysis: 标题描述（可选）
                - category_id: 主分类ID（可选）
                - sub_category_id: 子分类ID（可选）
                - category: [已弃用] 分类名称，保留用于调试
                - sub_category: [已弃用] 子分类名称，保留用于调试
        
        Returns:
            int: 受影响的行数
        """
        try:
            data_list = ai_metadata_df.to_dict('records')
            
            # 使用 (app, title) 作为冲突列，因为是复合主键
            affected = self.db.upsert_many('app_purpose_category', 
                                       data_list, 
                                       conflict_columns=['app', 'title','state'])
            logger.info(f"成功保存 {len(data_list)} 行AI元数据到数据库")
            return affected
        except Exception as e:
            logger.error(f"保存AI元数据失败: {e}")
            raise
    
    # ==================== category 表 ====================
    
    def load_categories(self) -> Optional[pd.DataFrame]:
        """
        获取所有主分类
        
        Returns:
            Optional[pd.DataFrame]: 主分类数据，为空返回 None
        """
        df = self.db.query('category', order_by='order_index ASC')
        return df if not df.empty else None
    
    def load_sub_categories(self) -> Optional[pd.DataFrame]:
        """
        获取所有子分类
        
        Returns:
            Optional[pd.DataFrame]: 子分类数据，为空返回 None
        """
        df = self.db.query('sub_category', order_by='order_index ASC')
        return df if not df.empty else None
    
    # ==================== user_app_behavior_log 表 ====================
    
    def get_latest_end_time(self) -> Optional[str]:
        """
        获取数据库中最新的 end_time
        
        Returns:
            Optional[str]: 最新的 end_time，表为空返回 None
        """
        try:
            sql = "SELECT MAX(end_time) as latest_end_time FROM user_app_behavior_log"
            with self.db.get_connection() as conn:
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
    
    def load_user_app_behavior_log(self, 
                                   start_time: str = None,
                                   end_time: str = None,
                                   app_filter: str = None) -> Optional[pd.DataFrame]:
        """
        从 user_app_behavior_log 表加载数据
        
        Args:
            start_time: 开始时间（可选），格式：'YYYY-MM-DD HH:MM:SS'
            end_time: 结束时间（可选）
            app_filter: 应用过滤（可选）
        
        Returns:
            Optional[pd.DataFrame]: 行为日志数据，为空返回 None
        """
        where = {}
        if app_filter:
            where['app'] = app_filter
        
        # 如果有时间范围，需要使用原始 SQL
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
            
            with self.db.get_connection() as conn:
                df = pd.read_sql_query(sql, conn, params=params)
            return df if not df.empty else None
        else:
            df = self.db.query('user_app_behavior_log', 
                              where=where if where else None,
                              order_by='start_time DESC')
            return df if not df.empty else None
    
    def save_user_app_behavior_log(self, cleaned_events_df: pd.DataFrame) -> int:
        """
        保存行为日志数据（INSERT OR IGNORE）
        
        Args:
            cleaned_events_df: 清洗后的事件数据 DataFrame
        
        Returns:
            int: 实际插入的行数
        """
        try:
            data_list = []
            for _, row in cleaned_events_df.iterrows():
                event_id = row.get('id', f"event_{row.get('start_time', '')}_{row.get('app', 'unknown')}")
                
                data_list.append({
                    'id': event_id,
                    'start_time': row['start_time'],
                    'end_time': row['end_time'],
                    'duration': row.get('duration'),
                    'app': row['app'],
                    'title': row.get('title'),
                    'is_multipurpose_app': int(row.get('is_multipurpose_app', False)),
                    'category_id': row.get('category_id'),
                    'sub_category_id': row.get('sub_category_id')
                })
            
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
            
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(sql, values_list)
                affected = cursor.rowcount
                logger.info(f"成功保存 {affected} 行清洗数据到数据库（共尝试 {len(data_list)} 行）")
                return affected
                
        except Exception as e:
            logger.error(f"保存清洗数据失败: {e}")
            raise

    def save_tokens_usage(self, tokens_usage_df: pd.DataFrame) -> int:
        """
        保存 token 使用数据到 tokens_usage_log 表
        
        Args:
            tokens_usage_df: Token 使用数据 DataFrame，应包含以下字段：
                - input_tokens: 输入 token 数
                - output_tokens: 输出 token 数
                - total_tokens: 总 token 数
                - search_count: 搜索次数（可选）
                - result_items_count: 结果项目数
                - mode: 模式（默认 'classification'）
        
        Returns:
            int: 插入的行数
        """
        try:
            if tokens_usage_df.empty:
                logger.warning("Token 使用数据为空，跳过保存")
                return 0
            
            data_list = tokens_usage_df.to_dict('records')
            
            # 确保必需字段存在
            for data in data_list:
                if 'mode' not in data:
                    data['mode'] = 'classification'
                if 'search_count' not in data:
                    data['search_count'] = 0
            
            # 使用 insert_many 插入数据
            affected = self.db.insert_many('tokens_usage_log', data_list)
            logger.info(f"成功保存 {affected} 条 token 使用记录到数据库")
            return affected
            
        except Exception as e:
            logger.error(f"保存 token 使用数据失败: {e}")
            raise
