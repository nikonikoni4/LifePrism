"""
LifeWatch 基础数据提供者
封装 LW 数据库的通用表操作，供各模块继承使用
"""
import pandas as pd
import logging
from typing import Set, Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


class LWBaseDataProvider:
    """
    LifeWatch 基础数据提供者

    特点：
    - 内置全局单例，简化继承类的初始化
    - 提供所有通用表的读写方法
    - 各模块继承此类即可使用
    - 提供通用 CRUD 方法，子类只需定义元数据即可使用

    SQLite 限制说明：
    ==================
    本实现仅支持 SQLite 数据库，使用了以下 SQLite 特定功能：

    1. SQL 函数：
       - datetime('now','localtime') - SQLite 日期时间函数
       - 其他数据库需使用 NOW() 或 CURRENT_TIMESTAMP

    2. 自增 ID 获取：
       - cursor.lastrowid - SQLite 特定方法
       - PostgreSQL 需使用 RETURNING id 子句
       - MySQL 需使用 LAST_INSERT_ID()

    3. 参数占位符：
       - 使用 ? 作为参数占位符（SQLite/SQLite3 风格）
       - PostgreSQL 使用 %s，其他数据库可能使用 :name 或 $1

    4. 数据类型：
       - SQLite 的动态类型系统
       - 其他数据库有严格的类型检查

    如需支持其他数据库，需要：
    - 抽象 SQL 方言差异（使用 SQLAlchemy 等 ORM）
    - 修改日期时间函数调用
    - 修改自增 ID 获取方式
    - 调整参数占位符格式
    """

    # ==================== 子类可选定义的元数据 ====================

    _TABLE_NAME: Optional[str] = None           # 表名
    _PRIMARY_KEY: str = "id"                    # 主键字段名（默认 'id'）
    _DATE_FIELD: Optional[str] = None           # 日期字段名（如 'date', 'created_at'）
    _TIME_FIELD: Optional[str] = None           # 时间字段名（如 'time', 'trigger_time'）
    _ON_CONFLICT: str = "replace"               # 冲突处理策略（默认 'replace'）
    _FILTER_FIELDS: Set[str] = set()            # 可筛选字段白名单
    _ORDER_FIELDS: Set[str] = set()             # 可排序字段白名单
    _SELECT_FIELDS: Set[str] = set()            # 可查询字段白名单
    _UPDATE_FIELDS: Set[str] = set()            # 可更新字段白名单

    # ==================== 类级别缓存 ====================

    _TABLES_WITH_UPDATE_AT: Optional[Set[str]] = None  # 需要自动更新 updated_at 的表名集合

    @classmethod
    def _init_update_at_cache(cls):
        """初始化 update_at 缓存，加载所有配置了 update_at=True 的表名"""
        if cls._TABLES_WITH_UPDATE_AT is None:
            from lifeprism.config.database import TABLE_CONFIGS
            cls._TABLES_WITH_UPDATE_AT = {
                table_name
                for table_name, config in TABLE_CONFIGS.items()
                if config.get('update_at', False)
            }
            logger.debug(f"初始化 update_at 缓存，共 {len(cls._TABLES_WITH_UPDATE_AT)} 个表需要自动更新时间戳")

    def __init__(self, db_manager=None):
        """
        初始化基础数据提供者

        Args:
            db_manager: DatabaseManager 实例，None 则使用全局单例
        """
        if db_manager is None:
            from lifeprism.repository import lw_db_manager
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
        from lifeprism.config.database import get_table_columns
        
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
    
    # def load_category_map_cache(
    #     self, 
    #     page: Optional[int] = None, 
    #     page_size: Optional[int] = None,
    #     search: Optional[str] = None,
    #     category_id: Optional[str] = None,
    #     sub_category_id: Optional[str] = None,
    #     state: Optional[int] = None,
    #     is_multipurpose_app: Optional[bool] = None
    # ) -> Optional[pd.DataFrame] | tuple[Optional[pd.DataFrame], int]:
    #     """
    #     获取应用分类数据
        
    #     Args:
    #         page: 页码（从1开始，可选）
    #         page_size: 每页数量（可选）
    #         search: 搜索关键词（匹配 app 或 title，可选）
    #         category_id: 按主分类 ID 筛选（可选）
    #         sub_category_id: 按子分类 ID 筛选（可选）
    #         state: 按状态筛选（可选）
    #         is_multipurpose_app: 按多用途应用筛选（可选）
        
    #     Returns:
    #         - 无分页参数时: Optional[pd.DataFrame]
    #         - 有分页参数时: tuple[Optional[pd.DataFrame], int] (数据, 总数)
            
    #         DataFrame 包含以下列：
    #             - id（自增主键）
    #             - app, title, is_multipurpose_app
    #             - app_description, title_analysis
    #             - category_id, sub_category_id
    #             - state, created_at
    #     """
    #     # 查询列（包含 id 主键）
    #     columns = [
    #         'id', 'app', 'title', 'is_multipurpose_app',
    #         'app_description', 'title_analysis',
    #         'category_id', 'sub_category_id', 'link_to_goal_id',
    #         'state', 'created_at'
    #     ]
        
    #     # 构建 WHERE 条件
    #     where_conditions = []
    #     params = []
        
    #     if search:
    #         where_conditions.append("(app LIKE ? OR title LIKE ?)")
    #         params.extend([f"%{search}%", f"%{search}%"])
        
    #     if category_id is not None:
    #         where_conditions.append("category_id = ?")
    #         params.append(category_id)
        
    #     if sub_category_id is not None:
    #         where_conditions.append("sub_category_id = ?")
    #         params.append(sub_category_id)
        
    #     if state is not None:
    #         where_conditions.append("state = ?")
    #         params.append(state)
        
    #     if is_multipurpose_app is not None:
    #         where_conditions.append("is_multipurpose_app = ?")
    #         params.append(1 if is_multipurpose_app else 0)
        
    #     where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
    #     # 无分页参数时，保持原有行为
    #     if page is None or page_size is None:
    #         if where_conditions:
    #             # 有筛选条件时使用原生 SQL
    #             columns_str = ", ".join(columns)
    #             sql = f"SELECT {columns_str} FROM category_map_cache WHERE {where_clause}"
    #             with self.db.get_connection() as conn:
    #                 df = pd.read_sql_query(sql, conn, params=params)
    #             return df if not df.empty else None
    #         else:
    #             df = self.db.query('category_map_cache', columns=columns)
    #             return df if not df.empty else None
        
    #     # 有分页参数时，返回 (数据, 总数)
    #     columns_str = ", ".join(columns)
        
    #     # 查询总数
    #     count_sql = f"SELECT COUNT(*) FROM category_map_cache WHERE {where_clause}"
        
    #     # 查询数据
    #     offset = (page - 1) * page_size
    #     data_sql = f"""
    #     SELECT {columns_str} 
    #     FROM category_map_cache 
    #     WHERE {where_clause}
    #     ORDER BY created_at DESC
    #     LIMIT ? OFFSET ?
    #     """
        
    #     with self.db.get_connection() as conn:
    #         cursor = conn.cursor()
    #         cursor.execute(count_sql, params)
    #         total = cursor.fetchone()[0]
            
    #         df = pd.read_sql_query(data_sql, conn, params=params + [page_size, offset])
        
    #     return (df if not df.empty else None, total)
    
    def load_category_map_cache_V2(
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
        获取应用分类数据（V2版本，从 multi_purpose_map_cache 和 single_purpose_map_cache 读取）
        
        使用 UNION ALL 将两个表的数据合并查询，输出格式与 load_category_map_cache 相同。
        
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
        # 构建 UNION ALL 视图查询
        # multi_purpose_map_cache: is_multipurpose_app = 1, 有 title_analysis
        # single_purpose_map_cache: is_multipurpose_app = 0, 无 title_analysis (用 NULL 填充)
        # id 已经是 TEXT 格式（m-xxx 或 s-xxx），直接读取
        union_query = """
        SELECT 
            id,
            app,
            title,
            1 as is_multipurpose_app,
            app_description,
            title_analysis,
            category_id,
            sub_category_id,
            link_to_goal_id,
            state,
            created_at
        FROM multi_purpose_map_cache
        
        UNION ALL
        
        SELECT 
            id,
            app,
            title,
            0 as is_multipurpose_app,
            app_description,
            NULL as title_analysis,
            category_id,
            sub_category_id,
            link_to_goal_id,
            state,
            created_at
        FROM single_purpose_map_cache
        """
        
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
            sql = f"""
            SELECT * FROM (
                {union_query}
            ) AS combined
            WHERE {where_clause}
            """
            with self.db.get_connection() as conn:
                df = pd.read_sql_query(sql, conn, params=params)
            return df if not df.empty else None
        
        # 有分页参数时，返回 (数据, 总数)
        
        # 查询总数
        count_sql = f"""
        SELECT COUNT(*) FROM (
            {union_query}
        ) AS combined
        WHERE {where_clause}
        """
        
        # 查询数据
        offset = (page - 1) * page_size
        data_sql = f"""
        SELECT * FROM (
            {union_query}
        ) AS combined
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
    
    def save_category_map_cache_V2(self, cache_df: pd.DataFrame) -> int:
        """
        保存app分类缓存数据到 multi_purpose_map_cache 表 和 single_purpose_map_cache 表
        
        使用 UPSERT 策略：已存在的应用会被更新，新应用会被插入
        ID 格式：m-{uuid[:8]} 表示多用途应用，s-{uuid[:8]} 表示单用途应用
        
        Args:
            cache_df: app分类缓存数据
            包含字段：
            - app: 应用名称（必需）
            - title: 应用标题（必需）
            - state: 状态
            - app_description: 应用描述（可选）
            - title_analysis: 标题描述（可选）
            - category_id: 主分类ID（可选） 
            - sub_category_id: 子分类ID（可选）
            - link_to_goal_id: 关联目标ID（可选）
            - is_multipurpose_app: 是否多用途应用（可选）
        Returns:
            int: 受影响的行数
        """
        import uuid
        
        # 分离多用途和单用途数据
        multi_df = cache_df[cache_df['is_multipurpose_app'] == 1].copy()
        single_df = cache_df[cache_df['is_multipurpose_app'] == 0].copy()
        
        # 删除不需要的列
        drop_cols_multi = ['is_multipurpose_app', 'category', 'sub_category']
        drop_cols_single = ['is_multipurpose_app', 'title_analysis', 'category', 'sub_category']
        
        multi_df = multi_df.drop(columns=[c for c in drop_cols_multi if c in multi_df.columns])
        single_df = single_df.drop(columns=[c for c in drop_cols_single if c in single_df.columns])
        
        # 为没有 id 的记录生成新 ID
        if not multi_df.empty:
            if 'id' not in multi_df.columns or multi_df['id'].isna().all():
                multi_df['id'] = [f"m-{str(uuid.uuid4())[:8]}" for _ in range(len(multi_df))]
            else:
                # 只为空的 id 生成新值
                multi_df['id'] = multi_df['id'].apply(
                    lambda x: f"m-{str(uuid.uuid4())[:8]}" if pd.isna(x) or x == '' else x
                )
        
        if not single_df.empty:
            if 'id' not in single_df.columns or single_df['id'].isna().all():
                single_df['id'] = [f"s-{str(uuid.uuid4())[:8]}" for _ in range(len(single_df))]
            else:
                # 只为空的 id 生成新值
                single_df['id'] = single_df['id'].apply(
                    lambda x: f"s-{str(uuid.uuid4())[:8]}" if pd.isna(x) or x == '' else x
                )
        
        multi_purpose_data = multi_df.to_dict('records') if not multi_df.empty else []
        single_purpose_data = single_df.to_dict('records') if not single_df.empty else []
        
        affected = 0
        try:
            if single_purpose_data:
                # 保存单用途，'app', 'state' 为冲突键
                affected += self.db.upsert_many('single_purpose_map_cache', single_purpose_data, conflict_columns=['app', 'state'])
            if multi_purpose_data:
                # 保存多用途，'app', 'title', 'state' 为冲突键
                affected += self.db.upsert_many('multi_purpose_map_cache', multi_purpose_data, conflict_columns=['app', 'title', 'state'])
            return affected
        except Exception as e:
            logger.error(f"保存AI元数据失败: {e}")
            return 0

    # def save_category_map_cache(self, ai_metadata_df: pd.DataFrame) -> int:
    #     """
    #     保存AI元数据到 category_map_cache 表
        
    #     使用 UPSERT 策略：已存在的应用会被更新，新应用会被插入
        
    #     Args:
    #         ai_metadata_df: AI元数据DataFrame，应包含以下字段：
    #             - app: 应用名称（必需）
    #             - title: 应用标题（必需）
    #             - is_multipurpose_app: 是否多用途应用（可选）
    #             - app_description: 应用描述（可选）
    #             - title_analysis: 标题描述（可选）
    #             - category_id: 主分类ID（可选）
    #             - sub_category_id: 子分类ID（可选）
    #             - category: [已弃用] 分类名称，保留用于调试
    #             - sub_category: [已弃用] 子分类名称，保留用于调试
        
    #     Returns:
    #         int: 受影响的行数
    #     """
    #     try:
    #         data_list = ai_metadata_df.to_dict('records')
            
    #         # 使用 (app, title,state) 作为冲突列，因为是复合主键
    #         affected = self.db.upsert_many('category_map_cache', 
    #                                    data_list, 
    #                                    conflict_columns=['app', 'title','state'])
    #         logger.info(f"成功保存 {len(data_list)} 行AI元数据到数据库")
    #         return affected
    #     except Exception as e:
    #         logger.error(f"保存AI元数据失败: {e}")
    #         raise
    
    # ==================== category 表 ====================
    
    def load_categories(self) -> Optional[pd.DataFrame]:
        """
        获取所有主分类
        
        Returns:
            Optional[pd.DataFrame]: 主分类数据，为空返回 None
        """
        df = self.db.query('category', order_by='created_at ASC')
        return df if not df.empty else None
    
    def load_sub_categories(self) -> Optional[pd.DataFrame]:
        """
        获取所有子分类
        
        Returns:
            Optional[pd.DataFrame]: 子分类数据，为空返回 None
        """
        df = self.db.query('sub_category', order_by='created_at ASC')
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
                    'sub_category_id': row.get('sub_category_id'),
                    'link_to_goal_id': row.get('link_to_goal_id')
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
    
    def get_session_tokens_usage(self, session_id: str) -> Optional[Dict]:
        """
        根据 session_id 获取已有的 token 使用量数据
        
        Args:
            session_id: 会话ID
        
        Returns:
            Optional[Dict]: 使用量数据，不存在返回 None
                - input_tokens: 输入 token 数
                - output_tokens: 输出 token 数
                - total_tokens: 总 token 数
                - search_count: 搜索次数
                - result_items_count: 结果项目数
        """
        try:
            sql = """
            SELECT input_tokens, output_tokens, total_tokens, search_count, result_items_count
            FROM tokens_usage_log
            WHERE session_id = ?
            """
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (session_id,))
                row = cursor.fetchone()
            
            if row:
                return {
                    "input_tokens": row[0] or 0,
                    "output_tokens": row[1] or 0,
                    "total_tokens": row[2] or 0,
                    "search_count": row[3] or 0,
                    "result_items_count": row[4] or 0
                }
            return None
            
        except Exception as e:
            logger.error(f"获取会话 {session_id} 的 token 使用数据失败: {e}")
            return None
    
    def upsert_session_tokens_usage(self, session_id: str, usage_data: Dict) -> int:
        """
        基于 session_id 更新或插入 token 使用量数据
        
        每个 session_id 只保留一条记录，存在则更新，不存在则插入
        使用 先查询再决定 INSERT 或 UPDATE 的方式
        
        Args:
            session_id: 会话ID
            usage_data: 使用量数据字典，应包含：
                - input_tokens: 输入 token 数
                - output_tokens: 输出 token 数
                - total_tokens: 总 token 数
                - search_count: 搜索次数(可选)
                - result_items_count: 结果项目数(可选)
                - mode: 模式(可选，默认 'chatbot')
        
        Returns:
            int: 受影响的行数
        """
        try:
            # 确保必需字段存在
            data = {
                'input_tokens': usage_data.get('input_tokens', 0),
                'output_tokens': usage_data.get('output_tokens', 0),
                'total_tokens': usage_data.get('total_tokens', 0),
                'search_count': usage_data.get('search_count', 0),
                'result_items_count': usage_data.get('result_items_count', 0),
                'mode': usage_data.get('mode', 'chatbot')
            }
            
            # 先查询是否存在
            existing = self.get_session_tokens_usage(session_id)
            if existing:
                # 存在则 UPDATE
                affected = self.db.update('tokens_usage_log', data, where={'session_id': session_id})
                logger.debug(f"更新会话 {session_id} 的 token 使用记录")
            else:
                # 不存在则 INSERT
                data['session_id'] = session_id
                affected = self.db.insert('tokens_usage_log', data)
                logger.debug(f"插入会话 {session_id} 的 token 使用记录")
            
            return affected
            
        except Exception as e:
            logger.error(f"保存会话 {session_id} 的 token 使用数据失败: {e}")
            raise


    # ==================== 通用 CRUD 方法 ====================

    def _validate_table_name(self):
        """
        验证表名格式，防止 SQL 注入

        Raises:
            NotImplementedError: 子类未定义 _TABLE_NAME
            ValueError: 表名格式不合法
        """
        if not self._TABLE_NAME:
            raise NotImplementedError(
                f"{self.__class__.__name__} 必须定义 _TABLE_NAME"
            )

        import re
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', self._TABLE_NAME):
            raise ValueError(
                f"Invalid table name: {self._TABLE_NAME}. "
                f"Table name must start with letter or underscore, "
                f"and contain only letters, numbers, and underscores."
            )

    def _generic_query(
        self,
        options: Optional['QueryOptions'] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        通用查询方法

        子类只需定义表名和白名单，即可使用此方法

        Args:
            options: 查询选项（QueryOptions 对象）

        Returns:
            (记录列表, 总记录数)

        Raises:
            NotImplementedError: 子类未定义 _TABLE_NAME
            ValueError: 字段白名单验证失败、不支持的查询类型
        """
        from lifeprism.repository.providers.common_query_options import QueryOptions

        if options is None:
            options = QueryOptions()

        # 验证表名
        self._validate_table_name()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # 1. 构建 SELECT 子句
            select_clause = self._build_select_clause(options)

            # 2. 构建 WHERE 子句
            where_clause, params = self._build_where_clause(options)

            # 3. 构建 ORDER BY 子句
            order_clause = self._build_order_clause(options)

            # 4. 构建 LIMIT 子句
            limit_clause = self._build_limit_clause(options)

            # 5. 执行查询
            query = f"""
                SELECT {select_clause}
                FROM {self._TABLE_NAME}
                WHERE {where_clause}
                {order_clause}
                {limit_clause}
            """
            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            results = [dict(zip(columns, row)) for row in rows]

            # 6. 查询总数
            count_query = f"""
                SELECT COUNT(*) as total
                FROM {self._TABLE_NAME}
                WHERE {where_clause}
            """
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]

            return results, total

    def _generic_insert(
        self,
        data: Dict[str, Any],
        id_prefix: Optional[str] = None,
        auto_order_index: bool = False,
        on_conflict: Optional[str] = None
    ) -> Optional[str]:
        """
        通用插入方法

        Args:
            data: 数据字典
            id_prefix: ID 前缀（如 't-'），None 则不生成 ID
            auto_order_index: 是否自动计算 order_index
            on_conflict: 冲突处理策略，None 则使用 self._ON_CONFLICT
                - 'abort': 遇到冲突时抛出异常
                - 'ignore': 遇到冲突时忽略，不插入
                - 'replace': 遇到冲突时替换已存在的记录

        Returns:
            新记录的 ID，'ignore' 模式下冲突时返回 None

        Raises:
            NotImplementedError: 子类未定义 _TABLE_NAME
            ValueError: 数据验证失败或 on_conflict 参数无效

        Examples:
            # 插入 todo（自动生成 ID 和 order_index）
            todo_id = self._generic_insert(
                data={'title': '测试任务', 'state': 'active'},
                id_prefix='t-',
                auto_order_index=True
            )

            # 插入 diary（使用自定义 ID）
            diary_id = self._generic_insert(
                data={'date': '2026-04-24', 'content': '日记内容'}
            )

            # 忽略冲突
            todo_id = self._generic_insert(
                data={'id': 't-12345678', 'title': '测试'},
                on_conflict='ignore'
            )
        """
        # 验证表名
        self._validate_table_name()

        # 0. 确定冲突处理策略
        conflict_strategy = on_conflict if on_conflict is not None else self._ON_CONFLICT
        valid_strategies = {'abort', 'ignore', 'replace'}
        if conflict_strategy not in valid_strategies:
            raise ValueError(
                f"Invalid on_conflict value: {conflict_strategy}. "
                f"Must be one of {valid_strategies}"
            )

        # 1. 生成 ID（如果需要）
        if id_prefix:
            import uuid
            data['id'] = f"{id_prefix}{uuid.uuid4().hex[:8]}"

        # 2. 计算 order_index（如果需要）
        if auto_order_index:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT MAX(order_index) FROM {self._TABLE_NAME}"
                )
                result = cursor.fetchone()
                max_order = result[0] if result and result[0] is not None else 0
                data['order_index'] = max_order + 1

        # 3. 构建 INSERT 语句
        columns = list(data.keys())
        placeholders = ','.join(['?'] * len(columns))
        values = [data[col] for col in columns]

        # 根据冲突策略构建不同的 SQL
        if conflict_strategy == 'abort':
            sql = f"""
                INSERT INTO {self._TABLE_NAME} ({', '.join(columns)})
                VALUES ({placeholders})
            """
        else:
            sql = f"""
                INSERT OR {conflict_strategy.upper()} INTO {self._TABLE_NAME} ({', '.join(columns)})
                VALUES ({placeholders})
            """

        # 4. 执行插入
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, values)
                conn.commit()

                # 对于 ignore 模式，如果发生冲突（rowcount=0），返回 None
                if conflict_strategy == 'ignore' and cursor.rowcount == 0:
                    logger.debug(f"Insert ignored due to conflict in {self._TABLE_NAME}")
                    return None

                return data.get('id', str(cursor.lastrowid))
        except Exception as e:
            logger.error(f"Failed to insert into {self._TABLE_NAME}: {e}")
            raise

    def _generic_update(
        self,
        record_id: str,
        data: Dict[str, Any]
    ) -> bool:
        """
        通用更新方法

        Args:
            record_id: 记录 ID
            data: 更新数据

        Returns:
            是否成功

        Raises:
            NotImplementedError: 子类未定义 _TABLE_NAME
            ValueError: 字段白名单验证失败

        Examples:
            # 更新 todo
            success = self._generic_update(
                record_id='t-12345678',
                data={'title': '新标题', 'state': 'completed'}
            )
        """
        # 验证表名
        self._validate_table_name()

        if not data:
            return True

        # 1. 白名单验证（如果定义了）
        if self._UPDATE_FIELDS:
            invalid_fields = set(data.keys()) - self._UPDATE_FIELDS
            if invalid_fields:
                raise ValueError(f"Invalid update fields: {invalid_fields}")

        # 2. 从缓存中查询该表是否需要自动更新 updated_at
        if self._TABLES_WITH_UPDATE_AT is None:
            self._init_update_at_cache()

        if self._TABLE_NAME in self._TABLES_WITH_UPDATE_AT and 'updated_at' not in data:
            from datetime import datetime
            data['updated_at'] = datetime.now().isoformat()

        # 3. 构建 UPDATE 语句
        set_clause = ', '.join([f"{key} = ?" for key in data.keys()])
        values = list(data.values()) + [record_id]

        sql = f"""
            UPDATE {self._TABLE_NAME}
            SET {set_clause}
            WHERE {self._PRIMARY_KEY} = ?
        """

        # 4. 执行更新
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, values)
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update {self._TABLE_NAME}: {e}")
            raise

    def _generic_delete(self, record_id: str) -> bool:
        """
        通用删除方法

        Args:
            record_id: 记录 ID

        Returns:
            是否成功

        Raises:
            NotImplementedError: 子类未定义 _TABLE_NAME

        Examples:
            # 删除 todo
            success = self._generic_delete('t-12345678')
        """
        # 验证表名
        self._validate_table_name()

        sql = f"DELETE FROM {self._TABLE_NAME} WHERE {self._PRIMARY_KEY} = ?"

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (record_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to delete from {self._TABLE_NAME}: {e}")
            raise

    # ==================== 辅助方法（构建 SQL 子句） ====================

    def _build_select_clause(self, options: 'QueryOptions') -> str:
        """构建 SELECT 子句（白名单验证）"""
        if options.fields:
            if self._SELECT_FIELDS:
                invalid_fields = set(options.fields) - self._SELECT_FIELDS
                if invalid_fields:
                    raise ValueError(f"Invalid select fields: {invalid_fields}")
            return ", ".join(options.fields)
        return "*"

    def _build_where_clause(
        self,
        options: 'QueryOptions'
    ) -> Tuple[str, List[Any]]:
        """构建 WHERE 子句（动态条件 + 白名单验证）"""
        conditions = []
        params = []

        # 日期范围（只有当表有日期字段时才处理）
        if options.date_range:
            if not self._DATE_FIELD:
                raise ValueError(
                    f"{self._TABLE_NAME} 表不支持日期范围查询（未定义 _DATE_FIELD）"
                )
            start_date, end_date = options.date_range
            if start_date:
                conditions.append(f"{self._DATE_FIELD} >= ?")
                params.append(start_date)
            if end_date:
                conditions.append(f"{self._DATE_FIELD} <= ?")
                params.append(end_date)

        # 时间范围（只有当表有时间字段时才处理）
        if options.time_range:
            if not self._TIME_FIELD:
                raise ValueError(
                    f"{self._TABLE_NAME} 表不支持时间范围查询（未定义 _TIME_FIELD）"
                )
            start_time, end_time = options.time_range
            if start_time:
                conditions.append(f"{self._TIME_FIELD} >= ?")
                params.append(start_time)
            if end_time:
                conditions.append(f"{self._TIME_FIELD} <= ?")
                params.append(end_time)

        # 通用筛选（白名单验证）
        if options.filters:
            # 强制要求定义白名单
            if not self._FILTER_FIELDS:
                raise NotImplementedError(
                    f"{self.__class__.__name__} 必须定义 _FILTER_FIELDS 才能使用 filters"
                )

            for field, value in options.filters.items():
                if field not in self._FILTER_FIELDS:
                    raise ValueError(f"Invalid filter field: {field}")

                if value is None:
                    conditions.append(f"{field} IS NULL")
                elif isinstance(value, (list, tuple)):
                    placeholders = ','.join('?' * len(value))
                    conditions.append(f"{field} IN ({placeholders})")
                    params.extend(value)
                else:
                    conditions.append(f"{field} = ?")
                    params.append(value)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        return where_clause, params

    def _build_order_clause(self, options: 'QueryOptions') -> str:
        """构建 ORDER BY 子句（白名单验证）"""
        # 如果没有指定排序，返回空字符串
        if options.order_by is None:
            return ""

        if self._ORDER_FIELDS and options.order_by not in self._ORDER_FIELDS:
            raise ValueError(f"Invalid order_by field: {options.order_by}")
        order_direction = "DESC" if options.order_desc else "ASC"
        return f"ORDER BY {options.order_by} {order_direction}"

    def _build_limit_clause(self, options: 'QueryOptions') -> str:
        """构建 LIMIT 子句"""
        if options.page and options.page_size:
            offset = (options.page - 1) * options.page_size
            return f"LIMIT {options.page_size} OFFSET {offset}"
        elif options.limit:
            return f"LIMIT {options.limit}"
        return ""


if __name__ == "__main__":
    lw_base_data_provider = LWBaseDataProvider()
    data = lw_base_data_provider.get_activity_logs(date="2025-12-31")[0][:10]
    print(data)