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

    def get_segment_category_stats(
        self, 
        start_time: str, 
        end_time: str,
        segment_count: int
    ) -> List[Dict[str, Any]]:
        """
        获取分段统计与分类占比（统一输出）
        
        Args:
            start_time: 开始时间 YYYY-MM-DD HH:MM:SS
            end_time: 结束时间 YYYY-MM-DD HH:MM:SS
            segment_count: 切分段数
        
        Returns:
            List[Dict]: 每段的统计数据，包含：
                - segment_start: 开始时间
                - segment_end: 结束时间
                - segment_total_seconds: 分段总时长
                - categories: 主分类列表（含 idle）
                - sub_categories: 子分类列表
        """
        # 解析时间
        range_start = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        range_end = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        
        # 加载全部事件
        df = self._load_events_in_range(start_time, end_time)
        
        # 获取分类名称映射
        category_name_map, sub_category_name_map = self._get_category_name_maps()
        
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
            
            categories = []
            sub_categories = []
            
            if seg_df.empty:
                total_active = 0
            else:
                # 转换为秒
                seg_df = seg_df.copy()
                seg_df['duration_seconds'] = seg_df['duration_minutes'] * 60
                total_active = int(seg_df['duration_seconds'].sum())
                
                # 主分类统计
                cat_stats = seg_df.groupby('category_id').agg({
                    'duration_seconds': 'sum'
                }).reset_index()
                
                for _, row in cat_stats.iterrows():
                    cat_id = str(row['category_id']) if pd.notna(row['category_id']) else "uncategorized"
                    duration = int(row['duration_seconds'])
                    categories.append({
                        "id": cat_id,
                        "name": category_name_map.get(cat_id, "未分类"),
                        "duration": duration,
                        "percentage": round(duration / seg_total * 100, 2)
                    })
                
                # 子分类统计
                sub_cat_stats = seg_df.groupby('sub_category_id').agg({
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
                        "percentage": round(duration / seg_total * 100, 2)
                    })
            
            # 添加空闲时间
            idle_seconds = max(0, seg_total - total_active)
            if idle_seconds > 0:
                categories.append({
                    "id": "idle",
                    "name": "空闲",
                    "duration": idle_seconds,
                    "percentage": round(idle_seconds / seg_total * 100, 2)
                })
            
            # 按时长排序
            categories.sort(key=lambda x: x['duration'], reverse=True)
            sub_categories.sort(key=lambda x: x['duration'], reverse=True)
            
            results.append({
                "segment_start": seg_start.strftime("%Y-%m-%d %H:%M:%S"),
                "segment_end": seg_end.strftime("%Y-%m-%d %H:%M:%S"),
                "segment_total_seconds": seg_total,
                "categories": categories,
                "sub_categories": sub_categories
            })
        
        return results

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

    def get_daily_goal_trend(self, start_time: str, end_time: str) -> Optional[str]:
        """
        获取指定日期范围内每天的目标完成情况
        
        包含：每天在各个目标上投入的时间，以及关联任务的完成情况。
        
        Args:
            start_time: 开始日期 YYYY-MM-DD HH:MM:SS
            end_time: 结束日期 YYYY-MM-DD HH:MM:SS
        
        Returns:
            str: 格式化的每日目标统计
        """
        from collections import defaultdict
        from datetime import datetime, timedelta
        
        # 解析时间
        range_start = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        range_end = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        
        # 加载事件并切割到时间范围
        df = self._load_events_in_range(start_time, end_time)
        df = slice_events_by_time_range(df, range_start, range_end)
        
        if df.empty:
            return None
        
        # 过滤有 goal 的记录
        df = df[df['link_to_goal_id'].notna()]
        
        if df.empty:
            return None
        
        # 添加日期列
        df = df.copy()
        df['date'] = df['start_dt'].dt.date
        df['duration_seconds'] = df['duration_minutes'] * 60
        
        # 按 goal 和日期聚合
        # {goal_id: {date: duration_seconds}}
        goal_daily_stats = defaultdict(lambda: defaultdict(int))
        
        for _, row in df.iterrows():
            goal_id = str(row['link_to_goal_id'])
            date = row['date']
            duration = int(row['duration_seconds'])
            goal_daily_stats[goal_id][date] += duration
        
        # 获取目标名称
        goal_names = {}
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                for goal_id in goal_daily_stats.keys():
                    cursor.execute("SELECT name FROM goal WHERE id = ?", (goal_id,))
                    goal_row = cursor.fetchone()
                    goal_names[goal_id] = goal_row[0] if goal_row else "未知目标"
        except Exception as e:
            logger.error(f"获取目标名称失败: {e}")
            return None
        
        # 格式化输出
        output_lines = []
        
        for goal_id in sorted(goal_daily_stats.keys(), key=lambda x: goal_names.get(x, "")):
            goal_name = goal_names[goal_id]
            daily_durations = goal_daily_stats[goal_id]
            
            # 计算总时长
            total_seconds = sum(daily_durations.values())
            total_hours = total_seconds // 3600
            total_minutes = (total_seconds % 3600) // 60
            total_str = f"{total_hours}h {total_minutes}m" if total_hours > 0 else f"{total_minutes}m"
            
            # 获取日期范围
            dates = sorted(daily_durations.keys())
            date_range_start = dates[0].strftime("%Y-%m-%d")
            date_range_end = dates[-1].strftime("%Y-%m-%d")
            
            # 构建每日时长列表
            daily_list = []
            for date in dates:
                seconds = daily_durations[date]
                hours = seconds // 3600
                minutes = (seconds % 3600) // 60
                time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                daily_list.append(f"{date.strftime('%Y-%m-%d')}: {time_str}")
            
            # 输出格式
            output_lines.append(f"- {goal_name}: 总时长 {total_str}; 从{date_range_start}~{date_range_end}每天时长为：")
            for daily_item in daily_list:
                output_lines.append(f"  {daily_item}")
            output_lines.append("")  # 空行分隔
        
        return "\n".join(output_lines).strip()

    def get_daily_category_trend(self, start_time: str, end_time: str) -> Optional[str]:
        """
        获取指定日期范围内每天的主分类时长统计
        
        包含：每个主分类在整个时间范围内的总时长，以及每天的时长分布。
        
        Args:
            start_time: 开始日期 YYYY-MM-DD HH:MM:SS
            end_time: 结束日期 YYYY-MM-DD HH:MM:SS
        
        Returns:
            str: 格式化的每日主分类统计
        """
        from collections import defaultdict
        from datetime import datetime
        
        # 解析时间
        range_start = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        range_end = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        
        # 加载事件并切割到时间范围
        df = self._load_events_in_range(start_time, end_time)
        df = slice_events_by_time_range(df, range_start, range_end)
        
        if df.empty:
            return None
        
        # 添加日期列
        df = df.copy()
        df['date'] = df['start_dt'].dt.date
        df['duration_seconds'] = df['duration_minutes'] * 60
        
        # 过滤掉未分类的记录
        df = df[df['category_id'].notna()]
        
        if df.empty:
            return None
        
        # 按 category 和日期聚合
        # {category_id: {date: duration_seconds}}
        category_daily_stats = defaultdict(lambda: defaultdict(int))
        
        for _, row in df.iterrows():
            category_id = str(row['category_id'])
            date = row['date']
            duration = int(row['duration_seconds'])
            category_daily_stats[category_id][date] += duration
        
        # 获取分类名称
        category_name_map, _ = self._get_category_name_maps()
        
        # 格式化输出
        output_lines = []
        
        for category_id in sorted(category_daily_stats.keys(), key=lambda x: category_name_map.get(x, "未分类")):
            category_name = category_name_map.get(category_id, "未分类")
            daily_durations = category_daily_stats[category_id]
            
            # 计算总时长
            total_seconds = sum(daily_durations.values())
            total_hours = total_seconds // 3600
            total_minutes = (total_seconds % 3600) // 60
            total_str = f"{total_hours}h {total_minutes}m" if total_hours > 0 else f"{total_minutes}m"
            
            # 获取日期范围
            dates = sorted(daily_durations.keys())
            date_range_start = dates[0].strftime("%Y-%m-%d")
            date_range_end = dates[-1].strftime("%Y-%m-%d")
            
            # 构建每日时长列表
            daily_list = []
            for date in dates:
                seconds = daily_durations[date]
                hours = seconds // 3600
                minutes = (seconds % 3600) // 60
                time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                daily_list.append(f"{date.strftime('%Y-%m-%d')}: {time_str}")
            
            # 输出格式
            output_lines.append(f"- {category_name}: 总时长 {total_str}; 从{date_range_start}~{date_range_end}每天时长为：")
            for daily_item in daily_list:
                output_lines.append(f"  {daily_item}")
            output_lines.append("")  # 空行分隔
        
        return "\n".join(output_lines).strip()

    def get_user_focus_notes(
        self, 
        start_time: str, 
        end_time: str
    ) -> List[Dict[str, Any]]:
        """
        获取用户手动添加的时间块备注
        
        从 timeline_custom_block 表查询用户在指定时间范围内
        手动添加的活动记录，这些记录的 content 字段代表用户的备注。
        
        Args:
            start_time: 开始时间 YYYY-MM-DD HH:MM:SS
            end_time: 结束时间 YYYY-MM-DD HH:MM:SS
        
        Returns:
            List[Dict]: 用户备注列表，每条包含：
                - start_time: 开始时间
                - end_time: 结束时间
                - duration_minutes: 持续时间（分钟）
                - content: 备注内容
                - category_id: 关联的分类ID（可选）
                - sub_category_id: 关联的子分类ID（可选）
        """
        results = []
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 查询 timeline_custom_block
            # 时间格式为 ISO 格式如 2025-12-27T14:00:00
            # 需要转换 start_time/end_time 为 ISO 格式进行比较
            start_iso = start_time.replace(" ", "T")
            end_iso = end_time.replace(" ", "T")
            
            cursor.execute("""
                SELECT start_time, end_time, duration, content, category_id, sub_category_id
                FROM timeline_custom_block 
                WHERE start_time >= ? AND end_time <= ?
                   AND content IS NOT NULL AND content != ''
                ORDER BY start_time
            """, (start_iso, end_iso))
            
            for row in cursor.fetchall():
                results.append({
                    "start_time": row[0],
                    "end_time": row[1],
                    "duration_minutes": row[2],
                    "content": row[3],
                    "category_id": row[4] if row[4] else None,
                    "sub_category_id": row[5] if row[5] else None
                })
        
        return results

    def get_computer_usage_schedule(self, start_date: str, end_date: str) -> Optional[str]:
        """
        分析电脑使用时间以推断可能的作息时间
        
        每天的分析从 4:00 开始（而非 0:00），这样可以更准确地反映实际作息。
        例如：凌晨 2:00 的活动会被归入前一天。
        
        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
        
        Returns:
            str: 格式化的每日电脑使用时间分析
                格式示例：
                2026-01-03:
                  - 最早记录在 08:30，活动为 Chrome - 查看邮件
                  - 最晚记录在 23:45，活动为 VSCode - 编写代码
        """
        from collections import defaultdict
        from datetime import datetime, timedelta
        
        # 解析日期
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        # 扩展查询范围：从 start_date 的 4:00 开始，到 end_date+1 的 4:00 结束
        query_start = start_dt + timedelta(hours=4)
        query_end = end_dt + timedelta(days=1, hours=4)
        
        # 加载事件数据
        df = self._load_events_in_range(
            query_start.strftime("%Y-%m-%d %H:%M:%S"),
            query_end.strftime("%Y-%m-%d %H:%M:%S")
        )
        
        if df.empty:
            return None
        
        # 按"逻辑日期"分组（4:00 作为分界点）
        # 如果时间 < 4:00，归入前一天；否则归入当天
        def get_logical_date(dt):
            if dt.hour < 4:
                return (dt - timedelta(days=1)).date()
            else:
                return dt.date()
        
        df = df.copy()
        df['logical_date'] = df['start_dt'].apply(get_logical_date)
        
        # 按逻辑日期分组，找出每天的最早和最晚记录
        daily_schedule = defaultdict(lambda: {"earliest": None, "latest": None})
        
        for _, row in df.iterrows():
            logical_date = row['logical_date']
            start_dt = row['start_dt']
            
            # 构建活动描述
            app = row.get('app', '未知应用')
            title = row.get('title', '')
            if title and len(title) > 50:
                title = title[:50] + "..."
            activity = f"{app} - {title}" if title else app
            
            record = {
                "time": start_dt,
                "activity": activity
            }
            
            # 更新最早记录
            if daily_schedule[logical_date]["earliest"] is None or start_dt < daily_schedule[logical_date]["earliest"]["time"]:
                daily_schedule[logical_date]["earliest"] = record
            
            # 更新最晚记录
            if daily_schedule[logical_date]["latest"] is None or start_dt > daily_schedule[logical_date]["latest"]["time"]:
                daily_schedule[logical_date]["latest"] = record
        
        # 格式化输出
        output_lines = []
        
        for date in sorted(daily_schedule.keys()):
            schedule = daily_schedule[date]
            output_lines.append(f"{date.strftime('%Y-%m-%d')}:")
            
            if schedule["earliest"]:
                earliest_time = schedule["earliest"]["time"].strftime("%H:%M")
                earliest_activity = schedule["earliest"]["activity"]
                output_lines.append(f"  - 最早记录在 {earliest_time}，活动为 {earliest_activity}")
            
            if schedule["latest"]:
                latest_time = schedule["latest"]["time"].strftime("%H:%M")
                latest_activity = schedule["latest"]["activity"]
                output_lines.append(f"  - 最晚记录在 {latest_time}，活动为 {latest_activity}")
            
            output_lines.append("")  # 空行分隔
        
        return "\n".join(output_lines).strip()

    def get_focus_and_todos(self, start_time: str, end_time: str) -> Optional[str]:
        """
        获取指定日期范围的重点内容和待办事项
        
        Args:
            start_time: 开始日期 YYYY-MM-DD
            end_time: 结束日期 YYYY-MM-DD
        
        Returns:
            str: 格式化的每日摘要，包含重点和待办
        """
        from collections import defaultdict
        
        # 按日期存储数据
        daily_data = defaultdict(lambda: {"focus": "无", "todos": []})
        
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 1. 获取重点内容
                cursor.execute(
                    "SELECT date, content FROM daily_focus WHERE date BETWEEN ? AND ? ORDER BY date",
                    (start_time, end_time)
                )
                for date, content in cursor.fetchall():
                    if content:
                        daily_data[date]["focus"] = content
                
                # 2. 获取待办事项
                cursor.execute(
                    "SELECT date, content, state FROM todo_list WHERE state != 'inactive' AND date BETWEEN ? AND ? ORDER BY date",
                    (start_time, end_time)
                )
                for date, content, state in cursor.fetchall():
                    # 转换状态显示，根据用户要求使用 completed/not completed
                    is_completed = state == 'completed'
                    state_display = "completed" if is_completed else "not completed"
                    daily_data[date]["todos"].append({
                        "text": f"{content} {state_display}",
                        "completed": is_completed
                    })
            
            if not daily_data:
                return None
                
            # 格式化输出
            output_lines = []
            for date in sorted(daily_data.keys()):
                data = daily_data[date]
                output_lines.append(f"date: {date}")
                output_lines.append(f"- focus : {data['focus']}")
                
                todos = data["todos"]
                if todos:
                    completed_count = sum(1 for t in todos if t["completed"])
                    rate = int(completed_count / len(todos) * 100)
                    output_lines.append(f"- todos: {rate}%")
                    for i, todo in enumerate(todos, 1):
                        output_lines.append(f"  {i}. {todo['text']}")
                else:
                    output_lines.append("- todos:")
                    output_lines.append("  (无待办事项)")
                output_lines.append("") # 换行分隔
            
            return "\n".join(output_lines).strip()
            
        except Exception as e:
            logger.error(f"获取重点与待办内容失败: {e}")
            return None

llm_lw_data_provider = LazySingleton(LLMLWDataProvider)

if __name__ == "__main__":
    print("=== 电脑使用时间分析（作息推断） ===")
    print(llm_lw_data_provider.get_computer_usage_schedule("2025-12-25", "2025-12-30"))
    print("\n=== 重点与待办统计 ===")
    print(llm_lw_data_provider.get_focus_and_todos("2025-12-25 00:00:00", "2025-12-30 23:59:59"))
    print("=== 目标时长统计 ===")
    print(llm_lw_data_provider.get_daily_goal_trend("2025-12-25 00:00:00", "2025-12-30 23:59:59"))
    print("\n=== 主分类时长统计 ===")
    print(llm_lw_data_provider.get_daily_category_trend("2025-12-25 00:00:00", "2025-12-30 23:59:59"))
    print("\n=== 用户备注 ===")
    print(llm_lw_data_provider.get_user_focus_notes("2025-12-25 00:00:00", "2025-12-30 23:59:59"))
    print("\n=== 电脑使用时间分析（作息推断） ===")
    print(llm_lw_data_provider.get_computer_usage_schedule("2025-12-25", "2025-12-30"))
    