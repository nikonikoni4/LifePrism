"""
从数据库中读取数据,计算统计指标,为前端显示提供数据支持
"""
import pandas as pd
from typing import Optional
from datetime import datetime
from lifewatch.storage import LWBaseDataProvider


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
    

    def get_top_applications(self,top_n) -> list[dict]:
        """
        获取指定日期的Top应用排行
        arg:
            top_n: int, Top N
        return 
            list[dict], Top应用排行:
                name: str, 应用名称
                duration: int, 活跃时长(秒)
        """
        if not self._current_date:
            raise AttributeError("请先使用 self.current_date = 'YYYY-MM-DD' 设置日期。")
        sql = """
        SELECT app, SUM(duration) as total_duration
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

    def get_top_title(self, top_n) -> list[dict]:
        """
        获取指定日期的Top窗口标题排行
        arg:
            top_n: int, Top N
        return 
            list[dict], Top窗口标题排行:
                name: str, 窗口标题
                duration: int, 活跃时长(秒)
        """
        if not self._current_date:
            raise AttributeError("请先使用 self.current_date = 'YYYY-MM-DD' 设置日期。")
        sql = """
        SELECT title, SUM(duration) as total_duration
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
                id: int, 分类ID
                duration: int, 活跃时长(秒)
                color: str, 分类颜色 (仅主分类有)
                category_id: int, 所属主分类ID (仅子分类有)
        """
        # 通过 current_date setter 自动设置时间范围
        self.current_date = date
        
        # 验证 category_type 参数
        if category_type not in ("category", "sub_category"):
            raise ValueError(f"无效的 category_type: {category_type}，只支持 'category' 或 'sub_category'")
        
        # 动态构建SQL查询
        sql_data = f"""
        SELECT {category_type}, SUM(duration) as total_duration
        FROM user_app_behavior_log
        WHERE start_time >= ? AND start_time <= ? AND {category_type} IS NOT NULL
        GROUP BY {category_type}
        """
        
        # 根据类型选择元数据表
        if category_type == "category":
            sql_meta = "SELECT name, id, color FROM category"
        else:
            sql_meta = "SELECT name, id, category_id FROM sub_category"
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql_data, (self._start_time, self._end_time))
            results = cursor.fetchall()
            
            cursor.execute(sql_meta)
            meta_rows = cursor.fetchall()
        
        # 构建元数据字典
        if category_type == "category":
            meta_dict = {row[0]: {"id": row[1], "color": row[2]} for row in meta_rows}
            return [
                {
                    "name": row[0], 
                    "duration": row[1],
                    "id": meta_dict.get(row[0], {}).get("id", -1),
                    "color": meta_dict.get(row[0], {}).get("color", "#E8684A")
                } 
                for row in results if row[0] is not None
            ]
        else:
            meta_dict = {row[0]: {"id": row[1], "category_id": row[2]} for row in meta_rows}
            return [
                {
                    "name": row[0], 
                    "duration": row[1],
                    "id": meta_dict.get(row[0], {}).get("id", -1),
                    "category_id": meta_dict.get(row[0], {}).get("category_id", -1)
                } 
                for row in results if row[0] is not None
            ]
    
    def get_events_by_time_range(self, date: str, start_hour: float, end_hour: float) -> list[dict]:
        """
        获取指定日期和时间范围内的事件数据（用于 Timeline Overview）
        
        Args:
            date: 日期 (YYYY-MM-DD)
            start_hour: 开始小时 (浮点数，如 12.5 = 12:30)
            end_hour: 结束小时 (浮点数)
        
        Returns:
            list[dict]: 事件列表，包含 category_id, category_name, sub_category_id, 
                       sub_category_name, duration (重新计算的重叠时长), start_time, end_time, app
        """
        from datetime import datetime
        
        # 计算精确时间范围
        start_min = int((start_hour % 1) * 60)
        end_min = int((end_hour % 1) * 60)
        start_time_str = f"{date} {int(start_hour):02d}:{start_min:02d}:00"
        end_time_str = f"{date} {int(end_hour):02d}:{end_min:02d}:00"
        
        # 修改 SQL：查找所有与时间范围有重叠的事件
        # 条件：事件开始时间 < 范围结束时间 AND 事件结束时间 > 范围开始时间
        sql = """
        SELECT 
            uabl.id,
            uabl.start_time,
            uabl.end_time,
            uabl.duration,
            uabl.app,
            uabl.category_id,
            c.name as category_name,
            uabl.sub_category_id,
            sc.name as sub_category_name
        FROM user_app_behavior_log uabl
        LEFT JOIN category c ON uabl.category_id = c.id
        LEFT JOIN sub_category sc ON uabl.sub_category_id = sc.id
        WHERE uabl.start_time < ? AND uabl.end_time > ?
        ORDER BY uabl.start_time ASC
        """
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # 注意参数顺序：start_time < end_time_str AND end_time > start_time_str
            cursor.execute(sql, (end_time_str, start_time_str))
            results = cursor.fetchall()
        
        # 解析范围边界时间
        range_start = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
        range_end = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")
        
        events = []
        for row in results:
            event_start_str = row[1]
            event_end_str = row[2]
            
            # 解析事件时间
            event_start = datetime.strptime(event_start_str, "%Y-%m-%d %H:%M:%S")
            event_end = datetime.strptime(event_end_str, "%Y-%m-%d %H:%M:%S")
            
            # 计算实际重叠时长（秒）
            overlap_start = max(event_start, range_start)
            overlap_end = min(event_end, range_end)
            overlap_duration = max(0, (overlap_end - overlap_start).total_seconds())
            
            # 只添加有实际重叠的事件
            if overlap_duration > 0:
                events.append({
                    "id": row[0],
                    "start_time": event_start_str,
                    "end_time": event_end_str,
                    "duration": int(overlap_duration),  # 使用重叠时长
                    "app": row[4],
                    "category_id": row[5] or "",
                    "category_name": row[6] or "",
                    "sub_category_id": row[7] or "",
                    "sub_category_name": row[8] or ""
                })
        
        return events

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
        获取指定日期的时间线事件数据
        
        Args:
            date: str, 日期（YYYY-MM-DD 格式）
            channel: str, 数据通道 ('pc' 或 'mobile'，当前仅支持 'pc')
        
        Returns:
            list[dict], 事件列表:
                id: str, 事件ID
                start_time: str, 开始时间（ISO格式）
                end_time: str, 结束时间（ISO格式）
                duration: int, 持续时间（秒）
                app: str, 应用名称
                title: str, 窗口标题
                category_id: str, 主分类ID
                category_name: str, 主分类名称
                sub_category_id: str, 子分类ID
                sub_category_name: str, 子分类名称
                app_description: str, 应用描述
                title_analysis: str, 标题描述
                device_type: str, 设备类型（'pc' 或 'mobile'）
        """
        # 设置日期范围
        self.current_date = date
        
        # TODO: 未来根据 channel 参数从不同数据源获取数据
        # 当前阶段仅实现 PC 端数据，忽略 channel 参数
        
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
            sc.name as sub_category_name,
            apc.app_description,
            apc.title_analysis
        FROM user_app_behavior_log uabl
        LEFT JOIN category c ON uabl.category_id = c.id
        LEFT JOIN sub_category sc ON uabl.sub_category_id = sc.id
        LEFT JOIN app_purpose_category apc ON uabl.app = apc.app
        WHERE uabl.start_time >= ? AND uabl.start_time <= ?
        ORDER BY uabl.start_time ASC
        """
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (self._start_time, self._end_time))
            results = cursor.fetchall()
        
        # 转换为字典列表
        events = []
        for row in results:
            events.append({
                "id": row[0],
                "start_time": row[1],
                "end_time": row[2],
                "duration": row[3],
                "app": row[4],
                "title": row[5],
                "category_id": row[6] or "",
                "category_name": row[7] or "",
                "sub_category_id": row[8] or "",
                "sub_category_name": row[9] or "",
                "app_description": row[10] or "",
                "title_analysis": row[11] or "",
                "device_type": "pc"  # 当前阶段固定为 'pc'
            })
        
        return events

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


# ==================== 模块级单例 ====================
server_lw_data_provider = ServerLWDataProvider()


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
