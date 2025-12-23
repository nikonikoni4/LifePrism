"""
从数据库中读取数据,计算统计指标,为前端显示提供数据支持
"""
import pandas as pd
from typing import Optional
from datetime import datetime
from lifewatch.storage import LWBaseDataProvider
from lifewatch.utils import get_logger
from lifewatch.config.database import get_table_columns

logger = get_logger(__name__)


class ServerLWDataProvider(LWBaseDataProvider):
    """
    Server 模块专用数据提供者
    
    继承 LWBaseDataProvider，提供前端 API 所需的统计和查询方法
    内部使用 self.db 访问数据库（来自父类）
    """
    
    def __init__(self, db_manager=None):
        super().__init__(db_manager)
        self._current_date = None
        self._start_time = None
        self._end_time = None
    
    @property
    def current_date(self):
        if not self._current_date:
            raise AttributeError("请先使用 self.current_date = 'YYYY-MM-DD' 设置日期。")
        return self._current_date

    @current_date.setter
    def current_date(self, value):
        start_time = datetime.strptime(value, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
        end_time = datetime.strptime(value, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        self._start_time = start_time.strftime("%Y-%m-%d %H:%M:%S")
        self._end_time = end_time.strftime("%Y-%m-%d %H:%M:%S")
        self._current_date = value

    def get_active_time(self,date) -> int:
        """
        获取指定日期的总活跃时长
        return 
            int, 活跃时长(秒)
        """
        self.current_date = date
        sql = """
        SELECT SUM(duration) 
        FROM user_app_behavior_log 
        WHERE start_time >= ? AND start_time <= ?
        """
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (self._start_time, self._end_time))
            result = cursor.fetchone()
            
        return result[0] if result and result[0] is not None else 0
    

    def get_top_applications(self,date,top_n) -> list[dict]:
        """
        获取指定日期的Top应用排行
        arg:
            date: 日期字符串 (YYYY-MM-DD)
            top_n: int, Top N
        return 
            list[dict], Top应用排行:
                name: str, 应用名称
                duration: int, 活跃时长(秒)
        """
        self.current_date = date
        sql = """
        SELECT app, CAST(SUM(duration) AS INTEGER) as total_duration
        FROM user_app_behavior_log
        WHERE start_time >= ? AND start_time <= ?
        GROUP BY app
        ORDER BY total_duration DESC
        LIMIT ?
        """
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (self._start_time, self._end_time, top_n))
            results = cursor.fetchall()
            
        return [{"name": row[0], "duration": row[1]} for row in results]

    def get_top_title(self, date,top_n) -> list[dict]:
        """
        获取指定日期的Top窗口标题排行
        arg:
            date: 日期字符串 (YYYY-MM-DD)
            top_n: int, Top N
        return 
            list[dict], Top窗口标题排行:
                name: str, 窗口标题
                duration: int, 活跃时长(秒)
        """
        self.current_date = date
        sql = """
        SELECT title, CAST(SUM(duration) AS INTEGER) as total_duration
        FROM user_app_behavior_log
        WHERE start_time >= ? AND start_time <= ?
        GROUP BY title
        ORDER BY total_duration DESC
        LIMIT ?
        """
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (self._start_time, self._end_time, top_n))
            results = cursor.fetchall()
            
        return [{"name": row[0], "duration": row[1]} for row in results]

    def get_category_stats(self, date: str, category_type: str = "category") -> list[dict]:
        """
        获取指定日期的分类统计（统一方法）
        
        Args:
            date: 日期字符串 (YYYY-MM-DD)
            category_type: 分类类型，"category" 表示主分类，"sub_category" 表示子分类
            
        Returns:
            list[dict]: 分类统计数据
                name: str, 分类名称
                id: str, 分类ID
                duration: int, 活跃时长(秒)
                color: str, 分类颜色 (仅主分类有)
                category_id: str, 所属主分类ID (仅子分类有)
        """
        # 通过 current_date setter 自动设置时间范围
        self.current_date = date
        
        # 验证 category_type 参数
        if category_type not in ("category", "sub_category"):
            raise ValueError(f"无效的 category_type: {category_type}，只支持 'category' 或 'sub_category'")
        
        # 使用 ID 字段分组（不再使用 name 字段）
        id_field = f"{category_type}_id"
        
        # 动态构建SQL查询（按 ID 分组）
        sql_data = f"""
        SELECT {id_field}, SUM(duration) as total_duration
        FROM user_app_behavior_log
        WHERE start_time >= ? AND start_time <= ? AND {id_field} IS NOT NULL
        GROUP BY {id_field}
        """
        
        # 根据类型选择元数据表
        if category_type == "category":
            sql_meta = "SELECT id, name, color FROM category"
        else:
            sql_meta = "SELECT id, name, category_id FROM sub_category"
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql_data, (self._start_time, self._end_time))
            results = cursor.fetchall()
            
            cursor.execute(sql_meta)
            meta_rows = cursor.fetchall()
        
        # 构建元数据字典（以 ID 为 key）
        if category_type == "category":
            meta_dict = {str(row[0]): {"name": row[1], "color": row[2]} for row in meta_rows}
            return [
                {
                    "id": str(row[0]),
                    "name": meta_dict.get(str(row[0]), {}).get("name", "未知"),
                    "duration": row[1],
                    "color": meta_dict.get(str(row[0]), {}).get("color", "#E8684A")
                } 
                for row in results if row[0] is not None
            ]
        else:
            meta_dict = {str(row[0]): {"name": row[1], "category_id": str(row[2])} for row in meta_rows}
            return [
                {
                    "id": str(row[0]),
                    "name": meta_dict.get(str(row[0]), {}).get("name", "未知"),
                    "duration": row[1],
                    "category_id": meta_dict.get(str(row[0]), {}).get("category_id", "")
                } 
                for row in results if row[0] is not None
            ]
    
    def get_activity_logs(
        self,
        date: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        category_id: Optional[str] = None,
        sub_category_id: Optional[str] = None,
        query_fields: Optional[list[str]] = None,
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
        # 1. 确定时间范围
        if date:
            # 使用 current_date setter 自动设置时间范围
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
        
        # 默认查询字段
        default_fields = ["id", "start_time", "end_time", "duration", "app", "title", 
                          "category_id", "sub_category_id"]
        
        if query_fields:
            # 验证字段是否有效
            invalid_fields = [f for f in query_fields if f not in valid_columns]
            if invalid_fields:
                raise ValueError(f"无效的查询字段: {invalid_fields}，有效字段: {valid_columns}")
            select_fields = query_fields
        else:
            select_fields = default_fields
        
        # 3. 构建 SELECT 子句（带表别名和 JOIN 字段）
        select_parts = []
        join_category = False
        join_sub_category = False
        
        for field in select_fields:
            # duration 字段需要转换为整数
            if field == "duration":
                select_parts.append(f"CAST(uabl.{field} AS INTEGER) as {field}")
            else:
                select_parts.append(f"uabl.{field}")
        
        # 添加关联字段
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
            
            # 获取总数
            cursor.execute(count_sql, params)
            total = cursor.fetchone()[0]
            
            # 获取数据
            cursor.execute(data_sql, params + pagination_params)
            results = cursor.fetchall()
            
            # 获取列名
            column_names = [description[0] for description in cursor.description]
        
        # 10. 转换为字典列表
        logs = []
        for row in results:
            log_item = {}
            for i, col_name in enumerate(column_names):
                value = row[i]
                # 将 ID 字段转换为字符串
                if col_name in ("id", "category_id", "sub_category_id") and value is not None:
                    value = str(value)
                log_item[col_name] = value
            logs.append(log_item)
        
        logger.debug(f"获取活动日志: {len(logs)} 条, 总数: {total}")
        return logs, total

    def get_range_active_time(self, start_date: str, end_date: str) -> int:
        """
        获取指定日期范围的活跃时长
        arg:
            start_date: str, 开始日期（YYYY-MM-DD 格式）
            end_date: str, 结束日期（YYYY-MM-DD 格式）
        return 
            int, 活跃时长（秒）
        """
        sql = """
        SELECT SUM(duration) as total_duration
        FROM user_app_behavior_log
        WHERE start_time >= ? AND start_time <= ?
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (start_date, end_date))
            result = cursor.fetchone()
        return result[0] if result[0] else 0
    
    def get_daily_active_time(self, start_date: str, end_date: str, category_id: str = None, sub_category_id: str = None) -> list[dict]:
        """
        获取指定日期范围内每天的活跃时长（只使用一次SQL查询）
        arg:
            start_date: str, 开始日期（YYYY-MM-DD 格式）
            end_date: str, 结束日期（YYYY-MM-DD 格式）
            category_id: str, 主分类ID筛选（可选）
            sub_category_id: str, 子分类ID筛选（可选）
        return 
            list[dict], 每天的活动数据:
                date: str, 日期（YYYY-MM-DD 格式）
                active_time_percentage: int, 活动时长占比（%）
        """
        # 构建动态SQL查询
        where_conditions = ["start_time >= ?", "start_time <= ?"]
        params = [start_date, end_date]
        
        if category_id:
            where_conditions.append("category_id = ?")
            params.append(category_id)
        
        if sub_category_id:
            where_conditions.append("sub_category_id = ?")
            params.append(sub_category_id)
        
        sql = f"""
        SELECT 
            DATE(start_time) as activity_date,
            SUM(duration) as total_duration,
            CAST((SUM(duration) * 100.0 / 86400) AS INTEGER) as active_time_percentage
        FROM user_app_behavior_log
        WHERE {' AND '.join(where_conditions)}
        GROUP BY DATE(start_time)
        ORDER BY activity_date
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            results = cursor.fetchall()
        
        # 转换为响应格式
        daily_activities = []
        for row in results:
            daily_activities.append({
                "date": row[0],
                "active_time_percentage": row[2]  # 直接使用计算好的百分比
            })
        
        return daily_activities
    
    def get_timeline_events_by_date(self, date: str, channel: str = 'pc') -> list[dict]:
        """
        获取指定日期的时间线事件数据（封装方法）
        
        内部调用 get_activity_logs，保留向后兼容性
        
        Args:
            date: str, 日期（YYYY-MM-DD 格式）
            channel: str, 数据通道 ('pc' 或 'mobile'，当前仅支持 'pc')
        
        Returns:
            list[dict]: 事件列表
        """
        # 调用统一方法
        logs, _ = self.get_activity_logs(
            date=date,
            query_fields=["id", "start_time", "end_time", "duration", "app", "title", 
                         "category_id", "sub_category_id"],
            order_desc=False  # 升序
        )
        
        # 转换为旧的返回格式
        events = []
        for log in logs:
            events.append({
                "id": log.get("id"),
                "start_time": log.get("start_time"),
                "end_time": log.get("end_time"),
                "duration": log.get("duration"),
                "app": log.get("app"),
                "title": log.get("title"),
                "category_id": log.get("category_id") or "",
                "category_name": log.get("category_name") or "",
                "sub_category_id": log.get("sub_category_id") or "",
                "sub_category_name": log.get("sub_category_name") or "",
                "app_description": "",  # 新方法不返回此字段
                "title_analysis": "",   # 新方法不返回此字段
                "device_type": "pc"
            })
        
        return events
    
    def get_activity_log_by_id(self, log_id: str) -> Optional[dict]:
        """
        根据 ID 获取单条活动日志
        
        Args:
            log_id: 日志ID
        
        Returns:
            dict: 日志详情，如果不存在返回 None
        """
        sql = """
        SELECT 
            uabl.id,
            uabl.start_time,
            uabl.end_time,
            uabl.duration,
            uabl.app,
            uabl.title,
            uabl.category_id,
            c.name as category_name,
            uabl.sub_category_id,
            sc.name as sub_category_name
        FROM user_app_behavior_log uabl
        LEFT JOIN category c ON uabl.category_id = c.id
        LEFT JOIN sub_category sc ON uabl.sub_category_id = sc.id
        WHERE uabl.id = ?
        """
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (log_id,))
            row = cursor.fetchone()
        
        if not row:
            return None
        
        return {
            "id": str(row[0]),
            "start_time": row[1],
            "end_time": row[2],
            "duration": row[3],
            "app": row[4],
            "title": row[5],
            "category_id": str(row[6]) if row[6] else None,
            "category_name": row[7],
            "sub_category_id": str(row[8]) if row[8] else None,
            "sub_category_name": row[9]
        }

    def update_event_category(self, event_id: str, category_id: str, sub_category_id: str = None) -> bool:
        """
        更新事件的分类信息
        
        Args:
            event_id: 事件ID
            category_id: 主分类ID
            sub_category_id: 子分类ID（可选）
        
        Returns:
            bool: 是否更新成功
        """
        sql = """
        UPDATE user_app_behavior_log 
        SET category_id = ?, sub_category_id = ?
        WHERE id = ?
        """
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (category_id, sub_category_id, event_id))
            conn.commit()
            return cursor.rowcount > 0

    def batch_update_event_category(self, event_ids: list[str], category_id: str, sub_category_id: str = None) -> int:
        """
        批量更新事件分类，返回更新数量
        
        Args:
            event_ids: 事件ID列表
            category_id: 主分类ID
            sub_category_id: 子分类ID（可选）
        
        Returns:
            int: 成功更新的数量
        """
        if not event_ids:
            return 0
        placeholders = ",".join("?" * len(event_ids))
        sql = f"""
        UPDATE user_app_behavior_log 
        SET category_id = ?, sub_category_id = ?
        WHERE id IN ({placeholders})
        """
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (category_id, sub_category_id, *event_ids))
            conn.commit()
            return cursor.rowcount

    def delete_event(self, event_id: str) -> bool:
        """
        删除单条事件
        
        Args:
            event_id: 事件ID
        
        Returns:
            bool: 是否删除成功
        """
        sql = "DELETE FROM user_app_behavior_log WHERE id = ?"
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (event_id,))
            conn.commit()
            return cursor.rowcount > 0

    def batch_delete_events(self, event_ids: list[str]) -> int:
        """
        批量删除事件，返回删除数量
        
        Args:
            event_ids: 事件ID列表
        
        Returns:
            int: 成功删除的数量
        """
        if not event_ids:
            return 0
        placeholders = ",".join("?" * len(event_ids))
        sql = f"DELETE FROM user_app_behavior_log WHERE id IN ({placeholders})"
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, event_ids)
            conn.commit()
            return cursor.rowcount


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
        
        with self.db.get_connection() as conn:
            df = pd.read_sql_query(sql, conn, params=params)
        
        return df


    def get_tokens_usage(self, date: str = None,
                            start_time: str = None, 
                            end_time: str = None) -> dict[str, dict]:
        """
        获取token使用汇总
        
        Args:
            date: 日期（YYYY-MM-DD 格式）
            start_time: 开始时间（可选，YYYY-MM-DD HH:MM:SS 格式）
            end_time: 结束时间（可选，YYYY-MM-DD HH:MM:SS 格式）
        
        Returns:
            dict[str, dict]: 日期到使用统计的映射，例如 
                {
                    "2025-12-20": {
                        "input_tokens": 800,
                        "output_tokens": 700,
                        "total_tokens": 1500,
                        "result_items_count": 25
                    }
                }
        """
        # 1. 确定时间范围
        if date:
            # 使用 current_date setter 自动设置时间范围
            self.current_date = date
            query_start_time = self._start_time
            query_end_time = self._end_time
        elif start_time and end_time:
            query_start_time = start_time
            query_end_time = end_time
        else:
            raise ValueError("必须提供 date 或 (start_time 和 end_time)")
        
        # 2. 构建SQL查询
        sql = """
        SELECT 
            DATE(created_at) as usage_date,
            SUM(input_tokens) as input_tokens,
            SUM(output_tokens) as output_tokens,
            SUM(total_tokens) as total_tokens,
            SUM(result_items_count) as result_items_count
        FROM tokens_usage_log
        WHERE created_at >= ? AND created_at <= ?
        GROUP BY DATE(created_at)
        ORDER BY usage_date
        """
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (query_start_time, query_end_time))
            results = cursor.fetchall()
        
        # 3. 转换为字典格式
        usage_dict = {}
        for row in results:
            usage_dict[row[0]] = {
                "input_tokens": row[1] if row[1] is not None else 0,
                "output_tokens": row[2] if row[2] is not None else 0,
                "total_tokens": row[3] if row[3] is not None else 0,
                "result_items_count": row[4] if row[4] is not None else 0
            }
        
        return usage_dict
    
    # ==================== category_map_cache 表 操作 ====================
    
    def update_category_map_cache_by_id(
        self, 
        record_id: int,
        category_id: str,
        sub_category_id: str | None,
        state: int
    ) -> bool:
        """
        通过 ID 更新单条 category_map_cache 记录的分类
        
        Args:
            record_id: 记录的自增主键 ID
            category_id: 新的主分类ID
            sub_category_id: 新的子分类ID
            state: 新状态（由 Service 层根据目标分类计算）
        
        Returns:
            bool: 是否更新成功
        """
        sql = """
        UPDATE category_map_cache 
        SET category_id = ?, sub_category_id = ?, state = ?
        WHERE id = ?
        """
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (category_id, sub_category_id, state, record_id))
            conn.commit()
            return cursor.rowcount > 0
    
    def batch_update_category_map_cache_by_ids(
        self, 
        record_ids: list[int],
        category_id: str,
        sub_category_id: str | None,
        state: int
    ) -> int:
        """
        批量通过 ID 更新 category_map_cache 记录的分类
        
        Args:
            record_ids: 记录的 ID 列表
            category_id: 新的主分类ID
            sub_category_id: 新的子分类ID
            state: 新状态（由 Service 层根据目标分类计算）
        
        Returns:
            int: 成功更新的数量
        """
        if not record_ids:
            return 0
        
        placeholders = ",".join("?" * len(record_ids))
        sql = f"""
        UPDATE category_map_cache 
        SET category_id = ?, sub_category_id = ?, state = ?
        WHERE id IN ({placeholders})
        """
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (category_id, sub_category_id, state, *record_ids))
            conn.commit()
            return cursor.rowcount
    
    def delete_category_map_cache_by_id(
        self, 
        record_id: int
    ) -> bool:
        """
        通过 ID 删除单条 category_map_cache 记录
        
        Args:
            record_id: 记录的自增主键 ID
        
        Returns:
            bool: 是否删除成功
        """
        sql = "DELETE FROM category_map_cache WHERE id = ?"
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (record_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def batch_delete_category_map_cache_by_ids(
        self, 
        record_ids: list[int]
    ) -> int:
        """
        批量通过 ID 删除 category_map_cache 记录
        
        Args:
            record_ids: 记录的 ID 列表
        
        Returns:
            int: 成功删除的数量
        """
        if not record_ids:
            return 0
        
        placeholders = ",".join("?" * len(record_ids))
        sql = f"DELETE FROM category_map_cache WHERE id IN ({placeholders})"
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, record_ids)
            conn.commit()
            return cursor.rowcount


# ==================== 模块级单例（懒加载） ====================
from lifewatch.utils import LazySingleton
server_lw_data_provider = LazySingleton(ServerLWDataProvider)


if __name__ == "__main__":
    sdp = server_lw_data_provider
    
    # 测试 Timeline 数据查询
    print("=== 测试 Timeline 数据查询 ===")
    date = "2025-12-02"
    events = sdp.get_timeline_events_by_date(date)
    print(f"日期: {date}")
    print(f"事件数量: {len(events)}")
    if events:
        print(f"第一个事件: {events[0]}")
    
    #测试新的每日活动数据查询方法
    print("\n=== 测试每日活动数据查询 ===")
    start_date = "2025-12-01"
    end_date = "2025-12-07"
    daily_data = sdp.get_daily_active_time(start_date, end_date)
    print(f"日期范围: {start_date} 到 {end_date}")
    print(f"查询结果数量: {len(daily_data)}")
    for activity in daily_data:
        print(f"日期: {activity['date']}, 活动占比: {activity['active_time_percentage']}%")
    
    print("\n=== 原有功能测试 ===")
    test_date = "2025-12-16"
    print(f"测试日期: {test_date}")
    print(f"主分类统计: {sdp.get_category_stats(test_date, 'category')}")
    print(f"子分类统计: {sdp.get_category_stats(test_date, 'sub_category')}")
    
    # 测试数据库连接
    with sdp.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("select distinct sub_category from user_app_behavior_log")
        result = cursor.fetchall()
    print(f"子分类数量: {len(result)}")
    for row in result:
        for sub_category in row:
            print(f"子分类: {sub_category}")
