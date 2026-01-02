"""
Report 服务层

提供日报告的业务逻辑，包括数据计算和缓存管理
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import pandas as pd

from lifewatch.server.schemas.report_schemas import (
    DailyReportResponse,
    TimeOverviewData,
    ChartSegment,
    TodoStatsData,
    GoalProgressData,
    GoalTodoItem,
)
from lifewatch.server.providers.report_provider import report_provider
from lifewatch.server.providers.todo_provider import todo_provider
from lifewatch.server.providers.goal_provider import goal_provider
from lifewatch.server.providers import server_lw_data_provider
from lifewatch.server.providers.category_color_provider import color_manager
from lifewatch.utils import get_logger

logger = get_logger(__name__)


class ReportService:
    """
    报告服务类
    
    提供日报告的获取和计算逻辑
    """
    
    def __init__(self):
        pass
    
    # ==================== 主要接口 ====================
    
    def get_daily_report(self, date: str, force_refresh: bool) -> DailyReportResponse:
        """
        获取日报告
        
        逻辑:
        1. 查询缓存
        2. 判断是否需要重新计算 (force_refresh 或 state != '1' 或无缓存)
        3. 需要时重新计算并保存
        4. 返回报告数据
        
        Args:
            date: 日期 YYYY-MM-DD
            force_refresh: 是否强制重新计算
            
        Returns:
            DailyReportResponse: 日报告数据
        """
        # 1. 查询缓存
        cached = report_provider.get_daily_report(date)
        
        # 2. 判断是否需要重新计算
        need_recalc = (
            force_refresh  # 强制刷新
            or cached is None  # 无缓存
            or cached.get('state') != '1'  # 未完成状态
        )
        
        if not need_recalc and cached:
            logger.info(f"返回缓存的日报告 {date}")
            return self._dict_to_response(cached)
        
        # 3. 重新计算各板块数据
        logger.info(f"重新计算日报告 {date}")
        
        sunburst_data = self._calc_sunburst_data(date)
        todo_data = self._calc_todo_stats(date)
        goal_data = self._calc_goal_progress(date)
        daily_trend_data = self._calc_daily_trend(date)
        
        # 4. 保存到数据库
        report_data = {
            'sunburst_data': sunburst_data.model_dump() if sunburst_data else None,
            'todo_data': todo_data.model_dump() if todo_data else None,
            'goal_data': [g.model_dump() for g in goal_data] if goal_data else None,
            'daily_trend_data': daily_trend_data,
            'state': '1'  # 标记为已完成
        }
        
        report_provider.upsert_daily_report(date, report_data)
        
        # 5. 返回报告数据
        return DailyReportResponse(
            date=date,
            sunburst_data=sunburst_data,
            todo_data=todo_data,
            goal_data=goal_data,
            daily_trend_data=daily_trend_data,
            state='1',
            data_version=1
        )
    
    # ==================== 数据计算方法 ====================
    
    def _calc_sunburst_data(self, date: str) -> Optional[TimeOverviewData]:
        """
        计算旭日图数据
        
        复用 activity_stats_builder 的逻辑，但简化为 report 需要的格式（无柱状图）
        """
        try:
            # 加载数据
            start_time = f"{date} 00:00:00"
            end_time = f"{date} 23:59:59"
            df = server_lw_data_provider.load_user_app_behavior_log(
                start_time=start_time, 
                end_time=end_time
            )
            
            if df is None or df.empty:
                return self._build_empty_sunburst(date)
            
            # 预计算时长（分钟）
            df['start_dt'] = pd.to_datetime(df['start_time'])
            df['end_dt'] = pd.to_datetime(df['end_time'])
            df['duration_minutes'] = (df['end_dt'] - df['start_dt']).dt.total_seconds() / 60
            
            # 获取分类名称映射
            categories_df = server_lw_data_provider.load_categories()
            category_name_map = {}
            if categories_df is not None and not categories_df.empty:
                category_name_map = {str(row['id']): row['name'] for _, row in categories_df.iterrows()}
            
            # 按分类聚合
            stats = df.groupby('category_id').agg({
                'duration_minutes': 'sum'
            }).reset_index()
            stats.columns = ['id', 'minutes']
            stats = stats.sort_values('minutes', ascending=False)
            
            total_minutes = int(stats['minutes'].sum())
            
            # 构建饼图数据
            pie_data = []
            for _, row in stats.iterrows():
                cat_id = str(row['id']) if pd.notna(row['id']) else "unknown"
                name = category_name_map.get(cat_id, "Uncategorized")
                minutes = int(row['minutes'])
                item_color = color_manager.get_main_category_color(cat_id)
                
                pie_data.append(ChartSegment(
                    key=cat_id,
                    name=name,
                    value=minutes,
                    color=item_color
                ))
            
            hours = total_minutes // 60
            mins = total_minutes % 60
            
            return TimeOverviewData(
                title="今日时间分布",
                sub_title=f"共计 {hours} 小时 {mins} 分钟",
                total_tracked_minutes=total_minutes,
                total_range_minutes=1440,  # 24小时
                pie_data=pie_data,
                details=None  # report 界面不需要钻取
            )
            
        except Exception as e:
            logger.error(f"计算旭日图数据失败: {e}")
            return self._build_empty_sunburst(date)
    
    def _calc_todo_stats(self, date: str) -> TodoStatsData:
        """
        计算 Todo 统计数据
        """
        try:
            # 获取当天的 todo (排除任务池中的 inactive 状态)
            todos = todo_provider.get_todos_by_date(date, include_cross_day=False)
            
            total = len(todos)
            completed = sum(1 for t in todos if t.get('state') == 'completed')
            pending = total - completed
            
            # 计算拖延率：当天未完成且过了预期日期的比例
            procrastination = sum(1 for t in todos if
                t.get('state') != 'completed' and
                t.get('expected_finished_at') and
                t['expected_finished_at'] < date
            )
            rate = (procrastination / total * 100) if total > 0 else 0
            
            return TodoStatsData(
                total=total,
                completed=completed,
                pending=pending,
                procrastination_rate=round(rate, 1)
            )
            
        except Exception as e:
            logger.error(f"计算 Todo 统计失败: {e}")
            return TodoStatsData(total=0, completed=0, pending=0, procrastination_rate=0)
    
    def _calc_goal_progress(self, date: str) -> List[GoalProgressData]:
        """
        计算 Goal 进度数据
        
        时间投入从 user_app_behavior_log 实时计算
        """
        try:
            # 获取所有活跃目标
            goals = goal_provider.get_active_goals()
            if not goals:
                return []
            
            result = []
            
            for goal in goals:
                goal_id = goal['id']
                
                # 获取关联的待办
                all_todos = todo_provider.get_todos_by_date(date, include_cross_day=True)
                goal_todos = [t for t in all_todos if t.get('link_to_goal_id') == goal_id]
                
                # 计算时间投入（从 user_app_behavior_log 实时计算）
                time_invested = self._calc_goal_time_invested(goal_id, date)
                
                # 构建待办列表
                todo_list = [
                    GoalTodoItem(
                        id=t['id'],
                        content=t['content'],
                        completed=t.get('state') == 'completed'
                    )
                    for t in goal_todos
                ]
                
                result.append(GoalProgressData(
                    goal_id=goal_id,
                    goal_name=goal.get('name', ''),
                    goal_color=goal.get('color', '#5B8FF9'),
                    time_invested=time_invested,
                    todo_total=len(goal_todos),
                    todo_completed=sum(1 for t in goal_todos if t.get('state') == 'completed'),
                    todo_list=todo_list
                ))
            
            return result
            
        except Exception as e:
            logger.error(f"计算 Goal 进度失败: {e}")
            return []
    
    def _calc_goal_time_invested(self, goal_id: str, date: str) -> int:
        """
        计算目标当天的时间投入（分钟）
        
        从 user_app_behavior_log 中查询 link_to_goal_id 匹配的记录
        """
        try:
            start_time = f"{date} 00:00:00"
            end_time = f"{date} 23:59:59"
            
            df = server_lw_data_provider.load_user_app_behavior_log(
                start_time=start_time,
                end_time=end_time
            )
            
            if df is None or df.empty:
                return 0
            
            # 筛选关联到该目标的记录
            goal_df = df[df['link_to_goal_id'] == goal_id]
            
            if goal_df.empty:
                return 0
            
            # 计算时长
            goal_df = goal_df.copy()
            goal_df['start_dt'] = pd.to_datetime(goal_df['start_time'])
            goal_df['end_dt'] = pd.to_datetime(goal_df['end_time'])
            goal_df['duration_minutes'] = (goal_df['end_dt'] - goal_df['start_dt']).dt.total_seconds() / 60
            
            return int(goal_df['duration_minutes'].sum())
            
        except Exception as e:
            logger.error(f"计算目标 {goal_id} 时间投入失败: {e}")
            return 0
    
    def _calc_daily_trend(self, date: str) -> List[Dict[str, Any]]:
        """
        计算24小时趋势数据
        
        按小时分组，统计各分类时长
        """
        try:
            start_time = f"{date} 00:00:00"
            end_time = f"{date} 23:59:59"
            
            df = server_lw_data_provider.load_user_app_behavior_log(
                start_time=start_time,
                end_time=end_time
            )
            
            if df is None or df.empty:
                return self._build_empty_trend()
            
            # 获取分类名称映射
            categories_df = server_lw_data_provider.load_categories()
            category_name_map = {}
            if categories_df is not None and not categories_df.empty:
                category_name_map = {str(row['id']): row['name'] for _, row in categories_df.iterrows()}
            
            # 预处理时间
            df['start_dt'] = pd.to_datetime(df['start_time'])
            df['end_dt'] = pd.to_datetime(df['end_time'])
            
            # 按小时统计各分类时长
            from collections import defaultdict
            hourly_data = defaultdict(lambda: defaultdict(int))
            
            for _, row in df.iterrows():
                start = row['start_dt']
                end = row['end_dt']
                cat_id = str(row['category_id']) if pd.notna(row['category_id']) else 'unknown'
                cat_name = category_name_map.get(cat_id, 'other')
                
                # 遍历每个小时
                for hour in range(24):
                    hour_start = start.replace(hour=hour, minute=0, second=0, microsecond=0)
                    hour_end = hour_start.replace(minute=59, second=59)
                    
                    overlap_start = max(start, hour_start)
                    overlap_end = min(end, hour_end)
                    
                    if overlap_start < overlap_end:
                        overlap_minutes = (overlap_end - overlap_start).total_seconds() / 60
                        hourly_data[hour][cat_name] += overlap_minutes
            
            # 收集所有出现过的分类名称
            all_categories = set()
            for hour_data in hourly_data.values():
                all_categories.update(hour_data.keys())
            
            # 构建结果 - 确保每个小时都包含所有分类字段
            result = []
            for hour in range(24):
                data_point = {'label': str(hour)}
                # 为所有分类设置值（没有数据的为 0）
                for cat_name in all_categories:
                    data_point[cat_name] = int(hourly_data[hour].get(cat_name, 0))
                result.append(data_point)
            
            return result
            
        except Exception as e:
            logger.error(f"计算24小时趋势失败: {e}")
            return self._build_empty_trend()
    
    # ==================== 辅助方法 ====================
    
    def _build_empty_sunburst(self, date: str) -> TimeOverviewData:
        """构建空的旭日图数据"""
        return TimeOverviewData(
            title="今日时间分布",
            sub_title=f"暂无 {date} 的活动数据",
            total_tracked_minutes=0,
            total_range_minutes=1440,
            pie_data=[],
            details=None
        )
    
    def _build_empty_trend(self) -> List[Dict[str, Any]]:
        """构建空的趋势数据"""
        return [{'label': str(h)} for h in range(24)]
    
    def _dict_to_response(self, data: Dict[str, Any]) -> DailyReportResponse:
        """将数据库记录转换为响应模型"""
        sunburst_data = None
        if data.get('sunburst_data'):
            sunburst_data = TimeOverviewData(**data['sunburst_data'])
        
        todo_data = None
        if data.get('todo_data'):
            todo_data = TodoStatsData(**data['todo_data'])
        
        goal_data = None
        if data.get('goal_data'):
            goal_data = [GoalProgressData(**g) for g in data['goal_data']]
        
        return DailyReportResponse(
            date=data['date'],
            sunburst_data=sunburst_data,
            todo_data=todo_data,
            goal_data=goal_data,
            daily_trend_data=data.get('daily_trend_data'),
            state=data.get('state', '0'),
            data_version=data.get('data_version', 1)
        )


# 创建全局单例
report_service = ReportService()
