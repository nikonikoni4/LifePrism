"""
LLM 模块专用数据提供者
继承 LWBaseDataProvider，添加 LLM 分类特定的数据库操作
"""
import pandas as pd
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta

from lifeprism.storage import LWBaseDataProvider
from lifeprism.utils import LazySingleton
from lifeprism.server.services.timeline_builder import slice_events_by_time_range

logger = logging.getLogger(__name__)


class LLMLWDataProvider(LWBaseDataProvider):
    """
    LLM 模块专用数据提供者
    
    继承 LWBaseDataProvider，添加 LLM 分类流程专用的数据库操作
    """
    
    # time_paradoxes mode 中文映射
    MODE_MAP = {
        "past": "我曾经是谁",
        "present": "我现在是谁",
        "future": "我要成为什么样的人"
    }
    
    def __init__(self, db_manager=None):
        """
        初始化 LLM 数据提供者
        
        Args:
            db_manager: DatabaseManager 实例，None 则使用全局单例
        """
        super().__init__(db_manager)
        
        # 缓存映射（延迟初始化）
        self._category_map: Optional[Dict[str, str]] = None      # category_id -> name
        self._sub_category_map: Optional[Dict[str, str]] = None  # sub_category_id -> name
        self._goal_map: Optional[Dict[str, str]] = None          # goal_id -> name
    
    # ==================== 缓存映射方法 ====================
    
    def _ensure_category_maps(self) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        确保分类映射已初始化（延迟加载，带缓存）
        
        Returns:
            Tuple: (category_map, sub_category_map)
        """
        if self._category_map is None or self._sub_category_map is None:
            self._category_map = {}
            self._sub_category_map = {}
            
            # 加载主分类
            categories_df = self.load_categories()
            if categories_df is not None and not categories_df.empty:
                self._category_map = {
                    str(row['id']): row['name'] 
                    for _, row in categories_df.iterrows()
                }
            
            # 加载子分类
            sub_categories_df = self.load_sub_categories()
            if sub_categories_df is not None and not sub_categories_df.empty:
                self._sub_category_map = {
                    str(row['id']): row['name'] 
                    for _, row in sub_categories_df.iterrows()
                }
            
            logger.debug(f"分类映射已加载: {len(self._category_map)} 个主分类, {len(self._sub_category_map)} 个子分类")
        
        return self._category_map, self._sub_category_map
    
    def _ensure_goal_map(self) -> Dict[str, str]:
        """
        确保目标映射已初始化（延迟加载，带缓存）
        
        Returns:
            Dict: goal_id -> goal_name 映射
        """
        if self._goal_map is None:
            self._goal_map = {}
            
            goals_df = self.db.query('goal', columns=['id', 'name'])
            if not goals_df.empty:
                self._goal_map = {
                    str(row['id']): row['name'] 
                    for _, row in goals_df.iterrows()
                }
            
            logger.debug(f"目标映射已加载: {len(self._goal_map)} 个目标")
        
        return self._goal_map
    
    def get_category_name(self, category_id: str) -> str:
        """获取主分类名称"""
        category_map, _ = self._ensure_category_maps()
        return category_map.get(str(category_id), "未知分类")
    
    def get_sub_category_name(self, sub_category_id: str) -> str:
        """获取子分类名称"""
        _, sub_category_map = self._ensure_category_maps()
        return sub_category_map.get(str(sub_category_id), "未知子分类")
    
    def get_goal_name(self, goal_id: str) -> str:
        """获取目标名称"""
        goal_map = self._ensure_goal_map()
        return goal_map.get(str(goal_id), "")
    
    # ==================== 基础查询方法 ====================
    
    def query_behavior_logs(
        self,
        start_time: str,
        end_time: str,
        limit: int = None,
        order_by: str = "start_time DESC",
        category_id: Optional[str] = None,
        sub_category_id: Optional[str] = None
    ) -> List[Dict]:
        """
        查询用户行为日志
        
        Args:
            start_time: 开始时间 YYYY-MM-DD HH:MM:SS
            end_time: 结束时间 YYYY-MM-DD HH:MM:SS
            limit: 返回记录数限制
            order_by: 排序方式，默认按开始时间降序
            category_id: 主分类ID，用于筛选特定分类的记录
            sub_category_id: 子分类ID，用于筛选特定子分类的记录
            
        Returns:
            List[Dict]: 包含以下字段:
                - start_time: 开始时间
                - end_time: 结束时间
                - duration: 持续时间(秒)
                - app: 应用名称
                - title: 窗口标题
                - category_name: 主分类名称
                - sub_category_name: 子分类名称
                - goal_name: 目标名称（如无则为空字符串）
        """
        try:
            # 构建查询条件
            conditions = [
                ('start_time', '>=', start_time),
                ('end_time', '<=', end_time)
            ]
            
            # 添加分类筛选条件
            if category_id:
                conditions.append(('category_id', '=', category_id))
            if sub_category_id:
                conditions.append(('sub_category_id', '=', sub_category_id))
            
            df = self.db.query_advanced(
                table_name='user_app_behavior_log',
                columns=['start_time', 'end_time', 'duration', 'app', 'title', 
                         'category_id', 'sub_category_id', 'link_to_goal_id'],
                conditions=conditions,
                order_by=order_by,
                limit=limit
            )
            
            if df.empty:
                return []
            
            # 确保映射已加载
            self._ensure_category_maps()
            self._ensure_goal_map()
            
            results = []
            for _, row in df.iterrows():
                results.append({
                    'start_time': row['start_time'],
                    'end_time': row['end_time'],
                    'duration': row['duration'],
                    'app': row['app'],
                    'title': row['title'],
                    'category_name': self.get_category_name(row.get('category_id', '')),
                    'sub_category_name': self.get_sub_category_name(row.get('sub_category_id', '')),
                    'goal_name': self.get_goal_name(row.get('link_to_goal_id', ''))
                })
            
            logger.debug(f"查询行为日志: {start_time} ~ {end_time}, 返回 {len(results)} 条记录")
            return results
            
        except Exception as e:
            logger.error(f"查询行为日志失败: {e}")
            return []
    
    def query_goals(self) -> List[str]:
        """
        查询所有 active 状态的目标名称，并刷新 goal_id -> name 映射缓存
        
        Returns:
            List[str]: active 状态的目标名称列表
        """
        try:
            df = self.db.query(
                table_name='goal',
                columns=['id', 'name', 'status'],
                order_by='order_index ASC'
            )
            
            if df.empty:
                self._goal_map = {}
                return []
            
            # 刷新缓存（包含所有目标）
            self._goal_map = {
                str(row['id']): row['name'] 
                for _, row in df.iterrows()
            }
            
            # 只返回 active 状态的目标名称
            active_goal_names = [
                row['name']
                for _, row in df.iterrows()
                if row['status'] == 'active'
            ]
            
            logger.debug(f"查询目标: 返回 {len(active_goal_names)} 个 active 目标")
            return active_goal_names
            
        except Exception as e:
            logger.error(f"查询目标失败: {e}")
            return []
    
    # ==================== stats专用方法 ====================
    
    def get_pc_active_time(self, start_time: str, end_time: str) -> List[float]:
        """
        分析以1小时为单位的电脑活跃时间占比
        
        将一天24小时分成24个1小时的时间段（0-1h, 1-2h, ..., 23-24h），
        计算每个时间段内电脑活跃时间占该时间段总时长的比例。
        
        Args:
            start_time: 开始时间 YYYY-MM-DD HH:MM:SS
            end_time: 结束时间 YYYY-MM-DD HH:MM:SS
        
        Returns:
            List[float]: 24个时间段的活跃占比列表，每个值为0.0-1.0之间的浮点数
        """
        from datetime import datetime, timedelta
        
        # 解析时间
        range_start = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        range_end = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        
        # 加载事件数据
        df = self._load_events_in_range(start_time, end_time)
        
        # 初始化24个1小时时间段的活跃时间（秒）
        # 索引0代表0-1h，索引1代表1-2h，...，索引23代表23-24h
        segment_active_seconds = [0] * 24
        segment_total_seconds = [0] * 24
        
        # 遍历时间范围内的每一天
        current_date = range_start.date()
        end_date = range_end.date()
        
        while current_date <= end_date:
            # 计算当天的实际开始和结束时间
            day_start = datetime.combine(current_date, datetime.min.time())
            day_end = day_start + timedelta(days=1)
            
            # 如果是第一天，从 range_start 开始
            if current_date == range_start.date():
                day_start = range_start
            
            # 如果是最后一天，到 range_end 结束
            if current_date == range_end.date():
                day_end = range_end
            
            # 计算每个1小时时间段在当天的实际时长
            for i in range(24):
                segment_start_hour = i
                segment_end_hour = i + 1
                
                segment_start = datetime.combine(current_date, datetime.min.time()) + timedelta(hours=segment_start_hour)
                segment_end = datetime.combine(current_date, datetime.min.time()) + timedelta(hours=segment_end_hour)
                
                # 计算与当天实际时间范围的交集
                actual_start = max(segment_start, day_start)
                actual_end = min(segment_end, day_end)
                
                if actual_start < actual_end:
                    segment_duration = (actual_end - actual_start).total_seconds()
                    segment_total_seconds[i] += segment_duration
                    
                    # 计算该时间段内的活跃时间
                    if not df.empty:
                        segment_df = slice_events_by_time_range(df, actual_start, actual_end)
                        if not segment_df.empty:
                            active_seconds = segment_df['duration_minutes'].sum() * 60
                            segment_active_seconds[i] += active_seconds
            
            # 移动到下一天
            current_date += timedelta(days=1)
        
        # 计算每个时间段的活跃占比
        ratios = []
        for i in range(24):
            if segment_total_seconds[i] > 0:
                ratio = segment_active_seconds[i] / segment_total_seconds[i]
                ratios.append(round(ratio, 2))
            else:
                ratios.append(0.0)
        
        return ratios
    
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
        获取分类名称映射（兼容旧接口，内部使用缓存）
        
        Returns:
            tuple: (主分类 id->name 映射, 子分类 id->(name, category_id) 映射)
        """
        # 使用缓存的映射
        category_map, sub_category_map_simple = self._ensure_category_maps()
        
        # 为了兼容旧接口，需要将 sub_category_map 转换为 (name, category_id) 格式
        # 但这需要额外查询 category_id，所以我们需要重新加载子分类数据
        sub_category_map = {}
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
                "name": "电脑空闲时间",
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
        segment_count: int,
        idle:bool=True,
    ) -> List[Dict[str, Any]]:
        """
        获取分段统计与分类占比（统一输出）
        
        Args:
            start_time: 开始时间 YYYY-MM-DD HH:MM:SS
            end_time: 结束时间 YYYY-MM-DD HH:MM:SS
            segment_count: 切分段数
            idle: 是否包含空闲时间
        
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
                
                # 确定分母
                calc_base = seg_total if idle else total_active
                if calc_base == 0:
                    calc_base = 1
                
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
                        "percentage": round(duration / calc_base * 100, 2)
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
                        "percentage": round(duration / calc_base * 100, 2)
                    })
            
            # 添加空闲时间
            if idle:
                idle_seconds = max(0, seg_total - total_active)
                if idle_seconds > 0:
                    categories.append({
                        "id": "idle",
                        "name": "电脑空闲时间",
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
        
        # 确保 goal 映射已加载
        self._ensure_goal_map()
        
        # 获取 goal 名称（使用缓存）
        results = {}
        for _, row in goal_stats.iterrows():
            gid = str(row['link_to_goal_id'])
            duration = int(row['duration_seconds'])
            goal_name = self.get_goal_name(gid)
            
            results[gid] = {
                "name": goal_name if goal_name else "未知目标",
                "duration_seconds": duration
            }
        
        return results

    def get_daily_goal_trend(self, start_time: str, end_time: str) -> Optional[List[Dict[str, Any]]]:
        """
        获取指定日期范围内每天的目标完成情况
        
        包含：每天在各个目标上投入的时间，以及关联任务的完成情况。
        
        Args:
            start_time: 开始日期 YYYY-MM-DD HH:MM:SS
            end_time: 结束日期 YYYY-MM-DD HH:MM:SS
        
        Returns:
            List[Dict]: 每个目标的统计数据，包含：
                - goal_id: 目标ID
                - goal_name: 目标名称
                - total_seconds: 总时长（秒）
                - date_range_start: 开始日期
                - date_range_end: 结束日期
                - daily_durations: {date_str: duration_seconds} 每日时长字典
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
        
        # 确保 goal 映射已加载
        self._ensure_goal_map()
        
        # 构建结果
        results = []
        for goal_id in sorted(goal_daily_stats.keys(), key=lambda x: self.get_goal_name(x) or ""):
            daily_durations = goal_daily_stats[goal_id]
            goal_name = self.get_goal_name(goal_id) or "未知目标"
            
            # 计算总时长
            total_seconds = sum(daily_durations.values())
            
            # 获取日期范围
            dates = sorted(daily_durations.keys())
            date_range_start = dates[0].strftime("%Y-%m-%d")
            date_range_end = dates[-1].strftime("%Y-%m-%d")
            
            # 转换日期为字符串键
            daily_durations_str = {
                date.strftime("%Y-%m-%d"): duration
                for date, duration in daily_durations.items()
            }
            
            results.append({
                "goal_id": goal_id,
                "goal_name": goal_name,
                "total_seconds": total_seconds,
                "date_range_start": date_range_start,
                "date_range_end": date_range_end,
                "daily_durations": daily_durations_str
            })
        
        return results

    def get_daily_category_trend(self, start_time: str, end_time: str) -> Optional[List[Dict[str, Any]]]:
        """
        获取指定日期范围内每天的主分类时长统计
        
        包含：每个主分类在整个时间范围内的总时长，以及每天的时长分布。
        
        Args:
            start_time: 开始日期 YYYY-MM-DD HH:MM:SS
            end_time: 结束日期 YYYY-MM-DD HH:MM:SS
        
        Returns:
            List[Dict]: 每个分类的统计数据，包含：
                - category_id: 分类ID
                - category_name: 分类名称
                - total_seconds: 总时长（秒）
                - date_range_start: 开始日期
                - date_range_end: 结束日期
                - daily_durations: {date_str: duration_seconds} 每日时长字典
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
        
        # 确保分类映射已加载
        self._ensure_category_maps()
        
        # 构建结果
        results = []
        for category_id in sorted(category_daily_stats.keys(), key=lambda x: self.get_category_name(x)):
            daily_durations = category_daily_stats[category_id]
            category_name = self.get_category_name(category_id)
            
            # 计算总时长
            total_seconds = sum(daily_durations.values())
            
            # 获取日期范围
            dates = sorted(daily_durations.keys())
            date_range_start = dates[0].strftime("%Y-%m-%d")
            date_range_end = dates[-1].strftime("%Y-%m-%d")
            
            # 转换日期为字符串键
            daily_durations_str = {
                date.strftime("%Y-%m-%d"): duration
                for date, duration in daily_durations.items()
            }
            
            results.append({
                "category_id": category_id,
                "category_name": category_name,
                "total_seconds": total_seconds,
                "date_range_start": date_range_start,
                "date_range_end": date_range_end,
                "daily_durations": daily_durations_str
            })
        
        return results

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

    def get_computer_usage_schedule(self, start_date: str, end_date: str) -> Optional[List[Dict[str, Any]]]:
        """
        分析电脑使用时间以推断可能的作息时间
        
        每天的分析从 4:00 开始（而非 0:00），这样可以更准确地反映实际作息。
        例如：凌晨 2:00 的活动会被归入前一天。
        
        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
        
        Returns:
            List[Dict]: 每日电脑使用时间统计，包含：
                - date: 日期字符串
                - earliest_time: 最早活动时间 HH:MM
                - earliest_activity: 最早活动描述
                - latest_time: 最晚活动时间 HH:MM
                - latest_activity: 最晚活动描述
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
        
        # 构建结果
        results = []
        for logical_date in sorted(daily_schedule.keys()):
            schedule = daily_schedule[logical_date]
            result = {"date": logical_date.strftime("%Y-%m-%d")}
            
            if schedule["earliest"]:
                t = schedule["earliest"]["time"]
                time_str = t.strftime("%H:%M")
                # 如果实际日期晚于逻辑日期，说明是次日凌晨
                if t.date() > logical_date:
                    time_str = f"(+1 day) {time_str}"
                result["earliest_time"] = time_str
                result["earliest_activity"] = schedule["earliest"]["activity"]
            
            if schedule["latest"]:
                t = schedule["latest"]["time"]
                time_str = t.strftime("%H:%M")
                # 如果实际日期晚于逻辑日期，说明是次日凌晨
                if t.date() > logical_date:
                    time_str = f"(+1 day) {time_str}"
                result["latest_time"] = time_str
                result["latest_activity"] = schedule["latest"]["activity"]
            
            results.append(result)
        
        return results

    def get_focus_and_todos(self, date:str = None, start_time: str = None, end_time: str = None) -> Optional[List[Dict[str, Any]]]:
        """
        获取指定日期范围的重点内容和待办事项
        
        Args:
            date: 日期 YYYY-MM-DD
            start_time: 开始时间 YYYY-MM-DD HH:MM:SS
            end_time: 结束时间 YYYY-MM-DD HH:MM:SS
        
        Returns:
            List[Dict]: 每日摘要数据，包含：
                - date: 日期
                - focus: 重点内容
                - todos: 待办事项列表
                - completion_rate: 完成率（0-100）
        """
        from collections import defaultdict
        if not date and not start_time and not end_time:
            raise ValueError("date, start_time, end_time must be provided")
        
        # 按日期存储数据
        daily_data = defaultdict(lambda: {"focus": "无", "todos": []})
        
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 转换日期时间格式为日期格式（如果需要）
                if start_time and end_time:
                    # 从 "YYYY-MM-DD HH:MM:SS" 提取 "YYYY-MM-DD"
                    start_date = start_time.split()[0] if ' ' in start_time else start_time
                    end_date = end_time.split()[0] if ' ' in end_time else end_time
                
                # 1. 获取重点内容
                if date : 
                    cursor.execute(
                    "SELECT date, content FROM daily_focus WHERE date = ? ORDER BY date",
                    (date,)
                )
                else:
                    cursor.execute(
                    "SELECT date, content FROM daily_focus WHERE date BETWEEN ? AND ? ORDER BY date",
                    (start_date, end_date)
                )
                for date_str, content in cursor.fetchall():
                    if content:
                        daily_data[date_str]["focus"] = content
                
                # 2. 获取待办事项
                if date : 
                    cursor.execute(
                    "SELECT date, content, state FROM todo_list WHERE state != 'inactive' AND date = ? ORDER BY date",
                    (date,)
                )
                else:
                    cursor.execute(
                    "SELECT date, content, state FROM todo_list WHERE state != 'inactive' AND date BETWEEN ? AND ? ORDER BY date",
                    (start_date, end_date)
                )
                for date_str, content, state in cursor.fetchall():
                    is_completed = state == 'completed'
                    daily_data[date_str]["todos"].append({
                        "content": content,
                        "state": state,
                        "completed": is_completed
                    })
            
            if not daily_data:
                return None
                
            # 构建结果
            results = []
            for date_str in sorted(daily_data.keys()):
                data = daily_data[date_str]
                todos = data["todos"]
                
                # 计算完成率
                if todos:
                    completed_count = sum(1 for t in todos if t["completed"])
                    completion_rate = int(completed_count / len(todos) * 100)
                else:
                    completion_rate = 0
                
                results.append({
                    "date": date_str,
                    "focus": data["focus"],
                    "todos": todos,
                    "completion_rate": completion_rate
                })
            
            return results
            
        except Exception as e:
            logger.error(f"获取重点与待办内容失败: {e}")
            return None

    def get_logs_by_time(self, date: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        按时间段（每小时）获取活动日志
        
        每个小时内筛选时长大于1分钟的日志，按时长降序排序，最多返回3条。
        如果某个小时没有数据，则不返回该时间段。
        
        Args:
            date: 日期 YYYY-MM-DD
        
        Returns:
            Dict[str, List[Dict]]: 按小时分组的日志数据
                格式: {
                    "08:00-09:00": [
                        {
                            "start_time": "2026-01-05 08:15:30",
                            "end_time": "2026-01-05 08:25:30",
                            "duration": 600,  # 秒
                            "app": "Chrome",
                            "title": "..."
                        },
                        ...
                    ],
                    ...
                }
        """
        from datetime import datetime, timedelta
        from collections import defaultdict
        
        # 解析日期
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        
        # 获取当天所有活动日志，包含 category_id 用于统计
        logs, _ = self.get_activity_logs(
            date=date,
            query_fields=["id", "start_time", "end_time", "duration", "app", "title", "category_id"],
            order_by="start_time",
            order_desc=False  # 升序排序
        )
        
        if not logs:
            return {}
        
        # 获取分类名称映射
        category_name_map, _ = self._get_category_name_maps()
        
        # 按小时分组
        hourly_logs = defaultdict(list)
        
        for log in logs:
            # 筛选时长大于1分钟（60秒）的记录
            duration = log.get('duration', 0)
            if duration <= 60:
                continue
            
            # 解析开始时间，确定所属小时
            start_time_str = log.get('start_time', '')
            try:
                start_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                # 如果时间格式不匹配，尝试其他格式或跳过
                continue
            
            # 构建小时段标识，例如 "08:00-09:00"
            hour_start = start_dt.replace(minute=0, second=0, microsecond=0)
            hour_end = hour_start + timedelta(hours=1)
            hour_key = f"{hour_start.strftime('%H:%M')}-{hour_end.strftime('%H:%M')}"
            
            # 添加到对应小时段
            hourly_logs[hour_key].append(log)
        
        # 对每个小时段的日志进行处理
        result = {}
        for hour_key in sorted(hourly_logs.keys()):
            logs_in_hour = hourly_logs[hour_key]
            
            # 按时长降序排序，选择top3
            sorted_logs = sorted(logs_in_hour, key=lambda x: x.get('duration', 0), reverse=True)
            top3_logs = sorted_logs[:3]
            
            # 计算该小时的主分类统计
            category_stats = defaultdict(int)
            for log in logs_in_hour:
                category_id = log.get('category_id')
                if category_id:
                    category_id = str(category_id)
                    category_stats[category_id] += log.get('duration', 0)
            
            # 转换为带名称的统计列表
            category_list = []
            for cat_id, total_duration in category_stats.items():
                category_list.append({
                    "id": cat_id,
                    "name": category_name_map.get(cat_id, "未分类"),
                    "duration": total_duration
                })
            
            # 按时长降序排序
            category_list.sort(key=lambda x: x['duration'], reverse=True)
            
            # 移除 category_id 字段，只保留需要的字段
            cleaned_logs = []
            for log in top3_logs:
                cleaned_logs.append({
                    "id": log.get("id"),
                    "start_time": log.get("start_time"),
                    "end_time": log.get("end_time"),
                    "duration": log.get("duration"),
                    "app": log.get("app"),
                    "title": log.get("title")
                })
            
            result[hour_key] = {
                "logs": cleaned_logs,
                "category_stats": category_list
            }
        
        return result

    def query_time_paradoxes(self) -> List[Dict]:
        """
        查询用户的时间悖论测试结果（每个 mode 的最新版本）
        
        Args:
            user_id: 用户ID，默认为1
                
            Returns:
                List[Dict]: 包含:
                    - mode: 模式（past/present/future）
                    - mode_name: 模式中文名称
                    - ai_abstract: AI总结
            """
        user_id = 1 # 默认用户ID
        try:
            results = []
            
            for mode in ['past', 'present', 'future']:
                # 查询每个 mode 的最新版本
                df = self.db.query_advanced(
                    table_name='time_paradoxes',
                    columns=['mode', 'ai_abstract', 'version'],
                    conditions=[
                        ('user_id', '=', user_id),
                        ('mode', '=', mode)
                    ],
                    order_by='version DESC',
                    limit=1
                )
                
                if not df.empty:
                    row = df.iloc[0]
                    results.append({
                        'mode': mode,
                        'mode_name': self.MODE_MAP.get(mode, mode),
                        'ai_abstract': row.get('ai_abstract', '')
                    })
            
            logger.debug(f"查询时间悖论: user_id={user_id}, 返回 {len(results)} 条记录")
            return results
            
        except Exception as e:
            logger.error(f"查询时间悖论失败: {e}")
            return []

    # ==================== 周报/月报规律性总结专用方法 ====================
    
    def get_daily_breakdown(
        self, 
        start_date: str, 
        end_date: str
    ) -> List[Dict[str, Any]]:
        """
        获取每日分解数据，包含使用时长、分类占比、电脑启用/结束时间
        
        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
        
        Returns:
            List[Dict]: 每天的分解数据，包含：
                - date: 日期
                - total_duration_hours: 总使用时长（小时）
                - categories: 分类占比列表 [{name, percentage}]
                - pc_start_time: 电脑启用时间 HH:MM
                - pc_end_time: 电脑结束时间 HH:MM
        """
        from datetime import datetime, timedelta
        
        # 获取电脑使用时间表（包含启用/结束时间）
        usage_schedule = self.get_computer_usage_schedule(start_date, end_date)
        usage_map = {item['date']: item for item in usage_schedule}
        
        results = []
        current_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        while current_date <= end_dt:
            date_str = current_date.strftime("%Y-%m-%d")
            
            # 获取当天的分类分布 (遵循逻辑一天: 04:00 ~ 次日 04:00)
            # 这与 get_computer_usage_schedule 的逻辑保持一致
            logical_start = current_date + timedelta(hours=4)
            logical_end = current_date + timedelta(days=1, hours=4)
            day_start = logical_start.strftime("%Y-%m-%d %H:%M:%S")
            day_end = logical_end.strftime("%Y-%m-%d %H:%M:%S")
            
            distribution = self.get_category_distribution(day_start, day_end)
            
            # 提取主分类占比（排除 idle）
            categories = []
            total_active_seconds = 0
            for cat in distribution.get('categories', []):
                if cat['id'] != 'idle':
                    categories.append({
                        'name': cat['name'],
                        'percentage': cat['percentage'],
                        'duration_seconds': cat['duration']
                    })
                    total_active_seconds += cat['duration']
            
            # 获取电脑启用/结束时间
            usage_info = usage_map.get(date_str, {})
            
            results.append({
                'date': date_str,
                'total_duration_hours': round(total_active_seconds / 3600, 1),
                'categories': categories,
                'pc_start_time': usage_info.get('earliest_time', '-'),
                'pc_end_time': usage_info.get('latest_time', '-')
            })
            
            current_date += timedelta(days=1)
        
        return results
    
    def get_weekly_focus(
        self,
        year: int,
        month: int,
        week_num: int
    ) -> Optional[str]:
        """
        获取指定周的焦点内容
        
        Args:
            year: 年份
            month: 月份（1-12）
            week_num: 周序号（1-4）
        
        Returns:
            Optional[str]: 周焦点内容，不存在返回 None
        """
        try:
            df = self.db.query_advanced(
                table_name='weekly_focus',
                columns=['content'],
                conditions=[
                    ('year', '=', year),
                    ('month', '=', month),
                    ('week_num', '=', week_num)
                ],
                limit=1
            )
            
            if not df.empty:
                return df.iloc[0]['content']
            return None
            
        except Exception as e:
            logger.error(f"获取周焦点失败: {e}")
            return None
    
    def get_daily_summaries(
        self,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """
        获取每日报告的 AI 摘要列表
        
        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
        
        Returns:
            List[Dict]: 每天的摘要数据，包含：
                - date: 日期
                - ai_summary_abstract: AI 摘要
        """
        try:
            df = self.db.query_advanced(
                table_name='daily_report',
                columns=['date', 'ai_summary_abstract'],
                conditions=[
                    ('date', '>=', start_date),
                    ('date', '<=', end_date)
                ],
                order_by='date ASC'
            )
            
            if df.empty:
                return []
            
            results = []
            for _, row in df.iterrows():
                summary = row.get('ai_summary_abstract')
                if summary:  # 只返回有摘要的日期
                    results.append({
                        'date': row['date'],
                        'ai_summary_abstract': summary
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"获取每日摘要失败: {e}")
            return []

llm_lw_data_provider = LazySingleton(LLMLWDataProvider)

if __name__ == "__main__":
    from lifeprism.llm.llm_classify.utils.data_base_format import (
        format_hourly_logs,
        format_daily_goal_trend,
        format_daily_category_trend,
        format_computer_usage_schedule,
        format_focus_and_todos
    )
    
    print(format_hourly_logs(llm_lw_data_provider.get_logs_by_time("2026-01-05")))
    print("\n=== 重点与待办统计 ===")
    print(format_focus_and_todos(llm_lw_data_provider.get_focus_and_todos(start_time="2026-01-01 00:00:00", end_time="2026-01-05 23:59:59")))
    print("=== 目标时长统计 ===")
    print(format_daily_goal_trend(llm_lw_data_provider.get_daily_goal_trend("2025-12-25 00:00:00", "2025-12-30 23:59:59")))
    print("\n=== 主分类时长统计 ===")
    print(format_daily_category_trend(llm_lw_data_provider.get_daily_category_trend("2025-12-25 00:00:00", "2025-12-30 23:59:59")))
    print("\n=== 电脑使用时间分析（作息推断） ===")
    print(format_computer_usage_schedule(llm_lw_data_provider.get_computer_usage_schedule("2025-12-25", "2025-12-30")))
    