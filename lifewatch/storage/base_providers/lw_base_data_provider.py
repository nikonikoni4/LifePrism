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
        
        # 日期/时间范围状态（供 get_activity_logs 等方法使用）
        self._current_date = None
        self._start_time = None
        self._end_time = None
    
    # ==================== 日期/时间范围属性 ====================
    
    @property
    def current_date(self):
        """当前查询日期"""
        if not self._current_date:
            raise AttributeError("请先使用 self.current_date = 'YYYY-MM-DD' 设置日期。")
        return self._current_date

    @current_date.setter
    def current_date(self, value):
        """设置当前日期，自动计算时间范围"""
        from datetime import datetime
        start_time = datetime.strptime(value, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
        end_time = datetime.strptime(value, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        self._start_time = start_time.strftime("%Y-%m-%d %H:%M:%S")
        self._end_time = end_time.strftime("%Y-%m-%d %H:%M:%S")
        self._current_date = value
    
    # ==================== 活动日志查询 ====================
    
    def get_activity_logs(
        self,
        date: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        category_id: Optional[str] = None,
        sub_category_id: Optional[str] = None,
        query_fields: Optional[List[str]] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        order_by: str = "start_time",
        order_desc: bool = True
    ) -> tuple[list[dict], int]:
        """
        统一的活动日志查询方法
        
        支持按日期或时间范围查询，支持分类过滤和分页，支持自定义返回字段
        
        Args:
            date: 查询日期 (YYYY-MM-DD 格式)，会自动设置 start_time 和 end_time 为当天范围
            start_time: 开始时间 (YYYY-MM-DD HH:MM:SS 格式)
            end_time: 结束时间 (YYYY-MM-DD HH:MM:SS 格式)
            category_id: 主分类ID筛选（可选）
            sub_category_id: 子分类ID筛选（可选）
            query_fields: 要查询的字段列表（可选，默认返回常用字段）
            page: 页码（从1开始，可选，不传则不分页）
            page_size: 每页数量（可选，不传则不分页）
            order_by: 排序字段（默认 start_time）
            order_desc: 是否降序（默认 True）
        
        Returns:
            tuple[list[dict], int]: (日志列表, 总记录数)
        
        Raises:
            ValueError: 如果 query_fields 包含无效字段
        """
        from lifewatch.config.database import get_table_columns
        
        # 1. 确定时间范围
        if date:
            self.current_date = date
            query_start_time = self._start_time
            query_end_time = self._end_time
        elif start_time and end_time:
            query_start_time = start_time
            query_end_time = end_time
        else:
            raise ValueError("必须提供 date 或 (start_time 和 end_time)")
        
        # 2. 验证并构建查询字段
        valid_columns = get_table_columns("user_app_behavior_log")
        default_fields = ["id", "start_time", "end_time", "duration", "app", "title", 
                          "category_id", "sub_category_id"]
        
        if query_fields:
            invalid_fields = [f for f in query_fields if f not in valid_columns]
            if invalid_fields:
                raise ValueError(f"无效的查询字段: {invalid_fields}，有效字段: {valid_columns}")
            select_fields = query_fields
        else:
            select_fields = default_fields
        
        # 3. 构建 SELECT 子句
        select_parts = []
        join_category = False
        join_sub_category = False
        
        for field in select_fields:
            if field == "duration":
                select_parts.append(f"CAST(uabl.{field} AS INTEGER) as {field}")
            else:
                select_parts.append(f"uabl.{field}")
        
        if "category_id" in select_fields:
            select_parts.append("c.name as category_name")
            join_category = True
        if "sub_category_id" in select_fields:
            select_parts.append("sc.name as sub_category_name")
            join_sub_category = True
        
        select_clause = ", ".join(select_parts)
        
        # 4. 构建 WHERE 条件
        where_conditions = ["uabl.start_time >= ?", "uabl.start_time <= ?"]
        params = [query_start_time, query_end_time]
        
        if category_id:
            where_conditions.append("uabl.category_id = ?")
            params.append(category_id)
        
        if sub_category_id:
            where_conditions.append("uabl.sub_category_id = ?")
            params.append(sub_category_id)
        
        where_clause = " AND ".join(where_conditions)
        
        # 5. 构建 JOIN 子句
        join_clause = ""
        if join_category:
            join_clause += " LEFT JOIN category c ON uabl.category_id = c.id"
        if join_sub_category:
            join_clause += " LEFT JOIN sub_category sc ON uabl.sub_category_id = sc.id"
        
        # 6. 构建 ORDER BY 子句
        order_direction = "DESC" if order_desc else "ASC"
        order_clause = f"ORDER BY uabl.{order_by} {order_direction}"
        
        # 7. 查询总数
        count_sql = f"""
        SELECT COUNT(*) 
        FROM user_app_behavior_log uabl
        WHERE {where_clause}
        """
        
        # 8. 构建数据查询 SQL
        data_sql = f"""
        SELECT {select_clause}
        FROM user_app_behavior_log uabl
        {join_clause}
        WHERE {where_clause}
        {order_clause}
        """
        
        # 9. 添加分页
        pagination_params = []
        if page is not None and page_size is not None:
            offset = (page - 1) * page_size
            data_sql += " LIMIT ? OFFSET ?"
            pagination_params = [page_size, offset]
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(count_sql, params)
            total = cursor.fetchone()[0]
            cursor.execute(data_sql, params + pagination_params)
            results = cursor.fetchall()
            column_names = [description[0] for description in cursor.description]
        
        # 10. 转换为字典列表
        logs = []
        for row in results:
            log_item = {}
            for i, col_name in enumerate(column_names):
                value = row[i]
                if col_name in ("id", "category_id", "sub_category_id") and value is not None:
                    value = str(value)
                log_item[col_name] = value
            logs.append(log_item)
        
        logger.debug(f"获取活动日志: {len(logs)} 条, 总数: {total}")
        return logs, total

    
    # ==================== category_map_cache 表 ====================
    
    def load_category_map_cache(
        self, 
        page: Optional[int] = None, 
        page_size: Optional[int] = None,
        search: Optional[str] = None,
        category_id: Optional[str] = None,
        sub_category_id: Optional[str] = None,
        state: Optional[int] = None,
        is_multipurpose_app: Optional[bool] = None
    ) -> Optional[pd.DataFrame] | tuple[Optional[pd.DataFrame], int]:
        """
        获取应用分类数据
        
        Args:
            page: 页码（从1开始，可选）
            page_size: 每页数量（可选）
            search: 搜索关键词（匹配 app 或 title，可选）
            category_id: 按主分类 ID 筛选（可选）
            sub_category_id: 按子分类 ID 筛选（可选）
            state: 按状态筛选（可选）
            is_multipurpose_app: 按多用途应用筛选（可选）
        
        Returns:
            - 无分页参数时: Optional[pd.DataFrame]
            - 有分页参数时: tuple[Optional[pd.DataFrame], int] (数据, 总数)
            
            DataFrame 包含以下列：
                - id（自增主键）
                - app, title, is_multipurpose_app
                - app_description, title_analysis
                - category_id, sub_category_id
                - state, created_at
        """
        # 查询列（包含 id 主键）
        columns = [
            'id', 'app', 'title', 'is_multipurpose_app',
            'app_description', 'title_analysis',
            'category_id', 'sub_category_id',
            'state', 'created_at'
        ]
        
        # 构建 WHERE 条件
        where_conditions = []
        params = []
        
        if search:
            where_conditions.append("(app LIKE ? OR title LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        
        if category_id is not None:
            where_conditions.append("category_id = ?")
            params.append(category_id)
        
        if sub_category_id is not None:
            where_conditions.append("sub_category_id = ?")
            params.append(sub_category_id)
        
        if state is not None:
            where_conditions.append("state = ?")
            params.append(state)
        
        if is_multipurpose_app is not None:
            where_conditions.append("is_multipurpose_app = ?")
            params.append(1 if is_multipurpose_app else 0)
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # 无分页参数时，保持原有行为
        if page is None or page_size is None:
            if where_conditions:
                # 有筛选条件时使用原生 SQL
                columns_str = ", ".join(columns)
                sql = f"SELECT {columns_str} FROM category_map_cache WHERE {where_clause}"
                with self.db.get_connection() as conn:
                    df = pd.read_sql_query(sql, conn, params=params)
                return df if not df.empty else None
            else:
                df = self.db.query('category_map_cache', columns=columns)
                return df if not df.empty else None
        
        # 有分页参数时，返回 (数据, 总数)
        columns_str = ", ".join(columns)
        
        # 查询总数
        count_sql = f"SELECT COUNT(*) FROM category_map_cache WHERE {where_clause}"
        
        # 查询数据
        offset = (page - 1) * page_size
        data_sql = f"""
        SELECT {columns_str} 
        FROM category_map_cache 
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(count_sql, params)
            total = cursor.fetchone()[0]
            
            df = pd.read_sql_query(data_sql, conn, params=params + [page_size, offset])
        
        return (df if not df.empty else None, total)
    
    def get_existing_apps(self) -> Set[str]:
        """
        获取已存在的单一用途应用集合
        
        Returns:
            Set[str]: 应用名称集合（不包括多用途应用）
        """
        try:
            df = self.db.query('category_map_cache', 
                              columns=['app'],
                              where={'is_multipurpose_app': 0})
            existing_apps = set(df['app'].dropna().tolist()) if not df.empty else set()
            logger.info(f"从数据库获取到 {len(existing_apps)} 个已有应用")
            return existing_apps
        except Exception as e:
            logger.error(f"获取已有应用失败: {e}")
            return set()
    
    def save_category_map_cache(self, ai_metadata_df: pd.DataFrame) -> int:
        """
        保存AI元数据到 category_map_cache 表
        
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
            
            # 使用 (app, title,state) 作为冲突列，因为是复合主键
            affected = self.db.upsert_many('category_map_cache', 
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

    def save_tokens_usage(self, tokens_usage_data: List[Dict]) -> int:
        """
        保存 token 使用数据到 tokens_usage_log 表
        
        Args:
            tokens_usage_data: Token 使用数据列表,每个字典应包含以下字段:
                - input_tokens: 输入 token 数
                - output_tokens: 输出 token 数
                - total_tokens: 总 token 数
                - search_count: 搜索次数(可选)
                - result_items_count: 结果项目数
                - mode: 模式(默认 'classification')
        
        Returns:
            int: 插入的行数
        """
        try:
            if not tokens_usage_data:
                logger.warning("Token 使用数据为空,跳过保存")
                return 0
            
            # 确保必需字段存在
            for data in tokens_usage_data:
                if 'mode' not in data:
                    data['mode'] = 'classification'
                if 'search_count' not in data:
                    data['search_count'] = 0
            
            # 使用 insert_many 插入数据
            affected = self.db.insert_many('tokens_usage_log', tokens_usage_data)
            logger.info(f"成功保存 {affected} 条 token 使用记录到数据库")
            return affected
            
        except Exception as e:
            logger.error(f"保存 token 使用数据失败: {e}")
            raise
