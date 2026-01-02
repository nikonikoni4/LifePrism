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

    def update_logs_by_app_title(
        self,
        app: str,
        title: str | None,
        is_multipurpose_app: bool,
        category_id: str,
        sub_category_id: str | None = None,
        goal_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None
    ) -> int:
        """
        根据 app 和可选的 title 批量更新日志分类
        
        匹配逻辑：
        - 单用途应用 (is_multipurpose_app=False): 仅按 app 匹配
        - 多用途应用 (is_multipurpose_app=True): 按 app + title 匹配
        
        Args:
            app: 应用名称
            title: 窗口标题（多用途应用时必须提供）
            is_multipurpose_app: 是否为多用途应用
            category_id: 主分类ID
            sub_category_id: 子分类ID（可选）
            goal_id: 目标ID（None=不修改, ''=清除, 'goal-xxx'=设置）
            start_date: 开始日期 YYYY-MM-DD（可选）
            end_date: 结束日期 YYYY-MM-DD（可选）
        
        Returns:
            int: 成功更新的数量
        """
        # 构建 SET 子句
        set_parts = ["category_id = ?", "sub_category_id = ?"]
        params = [category_id, sub_category_id]
        
        # goal_id 处理：None=不修改，""=清除，"goal-xxx"=设置
        if goal_id is not None:
            set_parts.append("link_to_goal_id = ?")
            # ""空字符串转换为 None（清除）
            params.append(goal_id if goal_id else None)
        
        # 构建 WHERE 条件
        where_parts = ["app = ?"]
        where_params = [app]
        
        if is_multipurpose_app:
            # 多用途应用：匹配 app + title
            if title is None:
                raise ValueError("多用途应用必须提供 title 参数")
            where_parts.append("title = ?")
            where_params.append(title)
        
        # 日期范围过滤
        if start_date:
            where_parts.append("DATE(start_time) >= ?")
            where_params.append(start_date)
        if end_date:
            where_parts.append("DATE(start_time) <= ?")
            where_params.append(end_date)
        
        sql = f"""
        UPDATE user_app_behavior_log 
        SET {", ".join(set_parts)}
        WHERE {" AND ".join(where_parts)}
        """
        
        all_params = params + where_params
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, all_params)
            conn.commit()
            updated_count = cursor.rowcount
        
        date_range_msg = ""
        if start_date or end_date:
            date_range_msg = f" (范围: {start_date or '开始'} ~ {end_date or '至今'})"
        
        logger.info(f"根据 app='{app}' {'+ title' if is_multipurpose_app else ''}{date_range_msg} 更新了 {updated_count} 条日志")
        return updated_count


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
    
    def get_all_tokens_usage(self) -> dict:
        """
        获取全部token使用汇总（不限日期范围）
        
        Returns:
            dict: 全部使用统计
                {
                    "input_tokens": 总输入tokens,
                    "output_tokens": 总输出tokens,
                    "total_tokens": 总tokens,
                    "result_items_count": 总处理项目数
                }
        """
        sql = """
        SELECT 
            SUM(input_tokens) as input_tokens,
            SUM(output_tokens) as output_tokens,
            SUM(total_tokens) as total_tokens,
            SUM(result_items_count) as result_items_count
        FROM tokens_usage_log
        """
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            row = cursor.fetchone()
        
        return {
            "input_tokens": row[0] if row[0] is not None else 0,
            "output_tokens": row[1] if row[1] is not None else 0,
            "total_tokens": row[2] if row[2] is not None else 0,
            "result_items_count": row[3] if row[3] is not None else 0
        }
    
    def get_tokens_usage_by_mode(self, date: str = None,
                                  start_time: str = None, 
                                  end_time: str = None,
                                  mode: str = None) -> dict[str, dict]:
        """
        获取按 mode 分组的 token 使用汇总
        
        Args:
            date: 日期（YYYY-MM-DD 格式）
            start_time: 开始时间（可选，YYYY-MM-DD HH:MM:SS 格式）
            end_time: 结束时间（可选，YYYY-MM-DD HH:MM:SS 格式）
            mode: 筛选特定的 mode（可选，如 'classification'）
        
        Returns:
            dict[str, dict]: mode 到使用统计的映射，例如 
                {
                    "classification": {
                        "input_tokens": 800,
                        "output_tokens": 700,
                        "total_tokens": 1500,
                        "result_items_count": 25
                    }
                }
        """
        # 1. 确定时间范围
        params = []
        where_conditions = []
        
        if date:
            self.current_date = date
            where_conditions.append("created_at >= ? AND created_at <= ?")
            params.extend([self._start_time, self._end_time])
        elif start_time and end_time:
            where_conditions.append("created_at >= ? AND created_at <= ?")
            params.extend([start_time, end_time])
        # 如果都不提供，则查询全部数据
        
        if mode:
            where_conditions.append("mode = ?")
            params.append(mode)
        
        # 2. 构建SQL查询
        where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        sql = f"""
        SELECT 
            mode,
            SUM(input_tokens) as input_tokens,
            SUM(output_tokens) as output_tokens,
            SUM(total_tokens) as total_tokens,
            SUM(result_items_count) as result_items_count
        FROM tokens_usage_log
        {where_clause}
        GROUP BY mode
        """
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
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
    
    def get_all_tokens_usage_by_mode(self, mode: str = None) -> dict[str, dict]:
        """
        获取全部token使用汇总（不限日期范围），按 mode 分组
        
        Args:
            mode: 筛选特定的 mode（可选，如 'classification'）
        
        Returns:
            dict[str, dict]: mode 到使用统计的映射
        """
        return self.get_tokens_usage_by_mode(mode=mode)
    
    # ==================== category_map_cache 表 操作 ====================
    
    def update_category_map_cache_by_id(
        self, 
        record_id: str,
        update_fields: dict
    ) -> bool:
        """
        通过 ID 更新单条 category_map_cache 记录的分类
        
        根据 ID 前缀判断操作哪个表：
        - m-xxx: multi_purpose_map_cache
        - s-xxx: single_purpose_map_cache
        
        Args:
            record_id: 记录 ID（格式：m-xxx 或 s-xxx）
            update_fields: 需要更新的字段字典
                - 字段存在且值为 None：将该字段设为 NULL（清空）
                - 字段存在且值非 None：更新为新值
                - 字段不存在：不更新该字段
        
        Returns:
            bool: 是否更新成功
        """
        # 根据 ID 前缀判断表名
        if record_id.startswith('m-'):
            table_name = 'multi_purpose_map_cache'
        elif record_id.startswith('s-'):
            table_name = 'single_purpose_map_cache'
        else:
            logger.error(f"无效的 record_id 格式: {record_id}")
            return False
        
        # 动态构建 SET 子句 - 使用 'key in dict' 而不是 'is not None'
        set_parts = []
        params = []
        
        # 可更新的字段列表
        updatable_fields = ['category_id', 'sub_category_id', 'state', 'app_description', 'link_to_goal_id']
        
        for field in updatable_fields:
            if field in update_fields:
                set_parts.append(f"{field} = ?")
                params.append(update_fields[field])  # 值可以是 None，表示清空
        
        # title_analysis 只对 multi_purpose 表有效
        if 'title_analysis' in update_fields and table_name == 'multi_purpose_map_cache':
            set_parts.append("title_analysis = ?")
            params.append(update_fields['title_analysis'])
        
        # 如果没有任何字段需要更新，返回 False
        if not set_parts:
            return False
        
        params.append(record_id)
        
        sql = f"""
        UPDATE {table_name} 
        SET {", ".join(set_parts)}
        WHERE id = ?
        """
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return cursor.rowcount > 0
    
    def batch_update_category_map_cache_by_ids(
        self, 
        record_ids: list[str],
        update_fields: dict
    ) -> int:
        """
        批量通过 ID 更新 category_map_cache 记录的分类
        
        根据 ID 前缀分组后分别操作对应的表：
        - m-xxx: multi_purpose_map_cache
        - s-xxx: single_purpose_map_cache
        
        Args:
            record_ids: 记录的 ID 列表（格式：m-xxx 或 s-xxx）
            update_fields: 需要更新的字段字典
                - 字段存在且值为 None：将该字段设为 NULL（清空）
                - 字段存在且值非 None：更新为新值
                - 字段不存在：不更新该字段
        
        Returns:
            int: 成功更新的数量
        """
        if not record_ids:
            return 0
        
        # 按 ID 前缀分组
        multi_ids = [rid for rid in record_ids if rid.startswith('m-')]
        single_ids = [rid for rid in record_ids if rid.startswith('s-')]
        
        # 动态构建 SET 子句 - 使用 'key in dict' 而不是 'is not None'
        set_parts = []
        base_params = []
        
        # 可更新的字段列表
        updatable_fields = ['category_id', 'sub_category_id', 'state', 'app_description', 'link_to_goal_id']
        
        for field in updatable_fields:
            if field in update_fields:
                set_parts.append(f"{field} = ?")
                base_params.append(update_fields[field])  # 值可以是 None，表示清空
        
        # 如果没有任何字段需要更新，返回 0
        if not set_parts:
            return 0
        
        total_updated = 0
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 更新 multi_purpose_map_cache 表
            if multi_ids:
                params = base_params.copy()
                params.extend(multi_ids)
                placeholders = ",".join("?" * len(multi_ids))
                sql = f"""
                UPDATE multi_purpose_map_cache 
                SET {", ".join(set_parts)}
                WHERE id IN ({placeholders})
                """
                cursor.execute(sql, params)
                total_updated += cursor.rowcount
            
            # 更新 single_purpose_map_cache 表
            if single_ids:
                params = base_params.copy()
                params.extend(single_ids)
                placeholders = ",".join("?" * len(single_ids))
                sql = f"""
                UPDATE single_purpose_map_cache 
                SET {", ".join(set_parts)}
                WHERE id IN ({placeholders})
                """
                cursor.execute(sql, params)
                total_updated += cursor.rowcount
            
            conn.commit()
        
        return total_updated
    
    def delete_category_map_cache_by_id(
        self, 
        record_id: str
    ) -> bool:
        """
        通过 ID 删除单条 category_map_cache 记录
        
        根据 ID 前缀判断操作哪个表：
        - m-xxx: multi_purpose_map_cache
        - s-xxx: single_purpose_map_cache
        
        Args:
            record_id: 记录 ID（格式：m-xxx 或 s-xxx）
        
        Returns:
            bool: 是否删除成功
        """
        # 根据 ID 前缀判断表名
        if record_id.startswith('m-'):
            table_name = 'multi_purpose_map_cache'
        elif record_id.startswith('s-'):
            table_name = 'single_purpose_map_cache'
        else:
            logger.error(f"无效的 record_id 格式: {record_id}")
            return False
        
        sql = f"DELETE FROM {table_name} WHERE id = ?"
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (record_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def batch_delete_category_map_cache_by_ids(
        self, 
        record_ids: list[str]
    ) -> int:  
        """
        批量通过 ID 删除 category_map_cache 记录
        
        根据 ID 前缀分组后分别操作对应的表：
        - m-xxx: multi_purpose_map_cache
        - s-xxx: single_purpose_map_cache
        
        Args:
            record_ids: 记录的 ID 列表（格式：m-xxx 或 s-xxx）
        
        Returns:
            int: 成功删除的数量
        """
        if not record_ids:
            return 0
        
        # 按 ID 前缀分组
        multi_ids = [rid for rid in record_ids if rid.startswith('m-')]
        single_ids = [rid for rid in record_ids if rid.startswith('s-')]
        
        total_deleted = 0
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 删除 multi_purpose_map_cache 表中的记录
            if multi_ids:
                placeholders = ",".join("?" * len(multi_ids))
                sql = f"DELETE FROM multi_purpose_map_cache WHERE id IN ({placeholders})"
                cursor.execute(sql, multi_ids)
                total_deleted += cursor.rowcount
            
            # 删除 single_purpose_map_cache 表中的记录
            if single_ids:
                placeholders = ",".join("?" * len(single_ids))
                sql = f"DELETE FROM single_purpose_map_cache WHERE id IN ({placeholders})"
                cursor.execute(sql, single_ids)
                total_deleted += cursor.rowcount
            
            conn.commit()
        
        return total_deleted


if __name__ == "__main__":
    from lifewatch.server.providers import server_lw_data_provider
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
