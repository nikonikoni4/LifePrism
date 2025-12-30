"""
LLM 模块专用数据提供者
继承 LWBaseDataProvider，添加 LLM 分类特定的数据库操作
"""
import pandas as pd
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from lifewatch.storage import LWBaseDataProvider
from lifewatch.utils import LazySingleton
from lifewatch.server.services.timeline_builder import slice_events_by_time_range

logger = logging.getLogger(__name__)


class LLMLWDataProvider(LWBaseDataProvider):
    """
    LLM 模块专用数据提供者
    
    继承 LWBaseDataProvider，添加 LLM 分类流程专用的数据库操作
    """
    
    def __init__(self, db_manager=None):
        """
        初始化 LLM 数据提供者
        
        Args:
            db_manager: DatabaseManager 实例，None 则使用全局单例
        """
        super().__init__(db_manager)
    
    # ==================== LLM 专用方法 ====================
    
    def _load_events_in_range(self, start_time: str, end_time: str) -> pd.DataFrame:
        """
        加载指定时间范围的事件数据
        
        Args:
            start_time: 开始时间 YYYY-MM-DD HH:MM:SS
            end_time: 结束时间 YYYY-MM-DD HH:MM:SS
        
        Returns:
            pd.DataFrame: 预处理后的事件 DataFrame（含 start_dt, end_dt）
        """
        df = self.load_user_app_behavior_log(start_time=start_time, end_time=end_time)
        
        if df is None or df.empty:
            return pd.DataFrame()
        
        # 预处理时间字段
        df['start_dt'] = pd.to_datetime(df['start_time'])
        df['end_dt'] = pd.to_datetime(df['end_time'])
        
        return df
    
    def _get_category_name_maps(self) -> tuple[Dict[str, str], Dict[str, tuple]]:
        """
        获取分类名称映射
        
        Returns:
            tuple: (主分类 id->name 映射, 子分类 id->(name, category_id) 映射)
        """
        category_map = {}
        sub_category_map = {}
        
        # 主分类
        categories_df = self.load_categories()
        if categories_df is not None and not categories_df.empty:
            category_map = {str(row['id']): row['name'] for _, row in categories_df.iterrows()}
        
        # 子分类
        sub_categories_df = self.load_sub_categories()
        if sub_categories_df is not None and not sub_categories_df.empty:
            sub_category_map = {
                str(row['id']): (row['name'], str(row['category_id'])) 
                for _, row in sub_categories_df.iterrows()
            }
        
        return category_map, sub_category_map

    def get_stats_by_time_segments(
        self, 
        start_time: str, 
        end_time: str, 
        segment_count: int
    ) -> List[Dict[str, Any]]:
        """
        获取分段时间统计数据
        
        Args:
            start_time: 开始时间 YYYY-MM-DD HH:MM:SS
            end_time: 结束时间 YYYY-MM-DD HH:MM:SS
            segment_count: 切分段数
        
        Returns:
            List[Dict]: 每段的统计数据，包含：
                - segment_start: 开始时间
                - segment_end: 结束时间
                - segment_total_seconds: 分段总时长
                - active_seconds: 活跃时长
                - active_percentage: 活跃百分比
                - idle_seconds: 空闲时长
                - idle_percentage: 空闲百分比
        """
        # 解析时间
        range_start = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        range_end = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        
        # 加载全部事件
        df = self._load_events_in_range(start_time, end_time)
        
        # 计算每段时长
        total_seconds = (range_end - range_start).total_seconds()
        segment_seconds = total_seconds / segment_count
        
        results = []
        for i in range(segment_count):
            seg_start = range_start + timedelta(seconds=i * segment_seconds)
            seg_end = range_start + timedelta(seconds=(i + 1) * segment_seconds)
            seg_total = int(segment_seconds)
            
            # 切割事件到分段范围
            seg_df = slice_events_by_time_range(df, seg_start, seg_end)
            
            # 计算活跃时长
            if seg_df.empty:
                active_seconds = 0
            else:
                active_seconds = int(seg_df['duration_minutes'].sum() * 60)
            
            idle_seconds = max(0, seg_total - active_seconds)
            
            results.append({
                "segment_start": seg_start.strftime("%Y-%m-%d %H:%M:%S"),
                "segment_end": seg_end.strftime("%Y-%m-%d %H:%M:%S"),
                "segment_total_seconds": seg_total,
                "active_seconds": active_seconds,
                "active_percentage": round(active_seconds / seg_total * 100, 2) if seg_total > 0 else 0,
                "idle_seconds": idle_seconds,
                "idle_percentage": round(idle_seconds / seg_total * 100, 2) if seg_total > 0 else 0
            })
        
        return results

    def get_category_distribution(
        self, 
        start_time: str, 
        end_time: str
    ) -> Dict[str, Any]:
        """
        获取分类占比分布
        
        Args:
            start_time: 开始时间 YYYY-MM-DD HH:MM:SS
            end_time: 结束时间 YYYY-MM-DD HH:MM:SS
        
        Returns:
            Dict: 分类分布数据：
                - segment_total_seconds: 分段总时长（分母）
                - categories: 主分类列表（含 idle）
                - sub_categories: 子分类列表
        """
        # 解析时间
        range_start = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        range_end = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        
        segment_total_seconds = int((range_end - range_start).total_seconds())
        
        # 加载事件并切割到时间范围
        df = self._load_events_in_range(start_time, end_time)
        df = slice_events_by_time_range(df, range_start, range_end)
        
        # 获取分类名称映射
        category_name_map, sub_category_name_map = self._get_category_name_maps()
        
        categories = []
        sub_categories = []
        
        if df.empty:
            total_active = 0
        else:
            # 转换为秒
            df = df.copy()
            df['duration_seconds'] = df['duration_minutes'] * 60
            total_active = int(df['duration_seconds'].sum())
            
            # 主分类统计
            cat_stats = df.groupby('category_id').agg({
                'duration_seconds': 'sum'
            }).reset_index()
            
            for _, row in cat_stats.iterrows():
                cat_id = str(row['category_id']) if pd.notna(row['category_id']) else "uncategorized"
                duration = int(row['duration_seconds'])
                categories.append({
                    "id": cat_id,
                    "name": category_name_map.get(cat_id, "未分类"),
                    "duration": duration,
                    "percentage": round(duration / segment_total_seconds * 100, 2)
                })
            
            # 子分类统计
            sub_cat_stats = df.groupby('sub_category_id').agg({
                'duration_seconds': 'sum'
            }).reset_index()
            
            for _, row in sub_cat_stats.iterrows():
                sub_id = str(row['sub_category_id']) if pd.notna(row['sub_category_id']) else None
                if sub_id is None or sub_id == "None":
                    continue
                duration = int(row['duration_seconds'])
                sub_info = sub_category_name_map.get(sub_id, ("未分类", ""))
                sub_categories.append({
                    "id": sub_id,
                    "name": sub_info[0],
                    "category_id": sub_info[1],
                    "duration": duration,
                    "percentage": round(duration / segment_total_seconds * 100, 2)
                })
        
        # 添加空闲时间
        idle_seconds = max(0, segment_total_seconds - total_active)
        if idle_seconds > 0:
            categories.append({
                "id": "idle",
                "name": "空闲",
                "duration": idle_seconds,
                "percentage": round(idle_seconds / segment_total_seconds * 100, 2)
            })
        
        # 按时长排序
        categories.sort(key=lambda x: x['duration'], reverse=True)
        sub_categories.sort(key=lambda x: x['duration'], reverse=True)
        
        return {
            "segment_total_seconds": segment_total_seconds,
            "categories": categories,
            "sub_categories": sub_categories
        }

    def get_longest_activities(
        self, 
        start_time: str, 
        end_time: str, 
        segment_count: int = 1,
        top_percentage: float = 0.1,
        max_count: int = 5
    ) -> List[Dict[str, Any]]:
        """
        获取时间段内最长的活动记录
        
        根据每个时段的密度取前 n%，最多 max_count 条
        
        Args:
            start_time: 开始时间 YYYY-MM-DD HH:MM:SS
            end_time: 结束时间 YYYY-MM-DD HH:MM:SS
            segment_count: 切分段数
            top_percentage: 取前多少比例，默认 0.1 (10%)
            max_count: 每段最多返回条数，默认 5
        
        Returns:
            List[Dict]: 每条记录包含 app, title, duration, start_time, end_time, segment_index
        """
        # 解析时间
        range_start = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        range_end = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        
        # 加载全部事件
        df = self._load_events_in_range(start_time, end_time)
        
        if df.empty:
            return []
        
        # 计算每段时长
        total_seconds = (range_end - range_start).total_seconds()
        segment_seconds = total_seconds / segment_count
        
        results = []
        for i in range(segment_count):
            seg_start = range_start + timedelta(seconds=i * segment_seconds)
            seg_end = range_start + timedelta(seconds=(i + 1) * segment_seconds)
            
            # 切割事件到分段范围
            seg_df = slice_events_by_time_range(df, seg_start, seg_end)
            
            if seg_df.empty:
                continue
            
            # 按时长排序
            seg_df = seg_df.sort_values('duration_minutes', ascending=False)
            
            # 计算取多少条
            total_count = len(seg_df)
            count = min(max(1, int(total_count * top_percentage)), max_count)
            
            # 取 top 记录
            top_df = seg_df.head(count)
            
            for _, row in top_df.iterrows():
                results.append({
                    "segment_index": i,
                    "app": row.get('app', ''),
                    "title": row.get('title', ''),
                    "duration_seconds": int(row['duration_minutes'] * 60),
                    "start_time": row['start_dt'].strftime("%Y-%m-%d %H:%M:%S"),
                    "end_time": row['end_dt'].strftime("%Y-%m-%d %H:%M:%S"),
                    "category_id": str(row.get('category_id', '')) if pd.notna(row.get('category_id')) else None,
                    "sub_category_id": str(row.get('sub_category_id', '')) if pd.notna(row.get('sub_category_id')) else None
                })
        
        return results

    def get_goal_time_spent(
        self, 
        start_time: str, 
        end_time: str, 
        goal_id: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        获取 goal 花费的时间
        
        Args:
            start_time: 开始时间 YYYY-MM-DD HH:MM:SS
            end_time: 结束时间 YYYY-MM-DD HH:MM:SS
            goal_id: 目标ID（可选），不传则返回所有目标
        
        Returns:
            Dict[goal_id, {"name": str, "duration_seconds": int}]
        """
        # 解析时间
        range_start = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        range_end = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        
        # 加载事件并切割
        df = self._load_events_in_range(start_time, end_time)
        df = slice_events_by_time_range(df, range_start, range_end)
        
        if df.empty:
            return {}
        
        # 过滤有 goal 的记录
        df = df[df['link_to_goal_id'].notna()]
        
        if goal_id:
            df = df[df['link_to_goal_id'] == goal_id]
        
        if df.empty:
            return {}
        
        # 转换为秒
        df = df.copy()
        df['duration_seconds'] = df['duration_minutes'] * 60
        
        # 按 goal 聚合
        goal_stats = df.groupby('link_to_goal_id').agg({
            'duration_seconds': 'sum'
        }).reset_index()
        
        # 获取 goal 名称
        results = {}
        for _, row in goal_stats.iterrows():
            gid = str(row['link_to_goal_id'])
            duration = int(row['duration_seconds'])
            
            # 查询 goal 名称
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM goal WHERE id = ?", (gid,))
                goal_row = cursor.fetchone()
                goal_name = goal_row[0] if goal_row else "未知目标"
            
            results[gid] = {
                "name": goal_name,
                "duration_seconds": duration
            }
        
        return results

    def get_user_focus_notes(
        self, 
        start_time: str, 
        end_time: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取用户 focus 备注
        
        Args:
            start_time: 开始时间 YYYY-MM-DD HH:MM:SS
            end_time: 结束时间 YYYY-MM-DD HH:MM:SS
        
        Returns:
            Dict:
                - daily_focus: 日焦点列表
                - weekly_focus: 周焦点列表
        """
        # 解析日期范围
        start_date = start_time.split(" ")[0]  # YYYY-MM-DD
        end_date = end_time.split(" ")[0]
        
        daily_focus = []
        weekly_focus = []
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 查询 daily_focus
            cursor.execute("""
                SELECT date, content 
                FROM daily_focus 
                WHERE date >= ? AND date <= ? AND content IS NOT NULL AND content != ''
                ORDER BY date
            """, (start_date, end_date))
            
            for row in cursor.fetchall():
                daily_focus.append({
                    "date": row[0],
                    "content": row[1]
                })
            
            # 解析年月周范围（用于 weekly_focus）
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            start_year = start_dt.year
            end_year = end_dt.year
            start_month = start_dt.month
            end_month = end_dt.month
            
            # 查询 weekly_focus
            cursor.execute("""
                SELECT year, month, week_num, content 
                FROM weekly_focus 
                WHERE ((year > ? OR (year = ? AND month >= ?)) 
                   AND (year < ? OR (year = ? AND month <= ?)))
                   AND content IS NOT NULL AND content != ''
                ORDER BY year, month, week_num
            """, (start_year, start_year, start_month, end_year, end_year, end_month))
            
            for row in cursor.fetchall():
                weekly_focus.append({
                    "year": row[0],
                    "month": row[1],
                    "week_num": row[2],
                    "content": row[3]
                })
        
        return {
            "daily_focus": daily_focus,
            "weekly_focus": weekly_focus
        }


llm_lw_data_provider = LazySingleton(LLMLWDataProvider)