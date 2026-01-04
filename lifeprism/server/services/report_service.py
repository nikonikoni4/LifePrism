"""
Report 服务层

提供日报告和周报告的业务逻辑，包括数据计算和缓存管理

重构说明:
1. 使用纯函数实现，不使用类
2. 合并日报和周报的相同计算逻辑，通过 start_date 和 end_date 参数区分
3. 保留两个独立的趋势计算函数（日报按小时，周报按天）
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd

from lifeprism.server.schemas.report_schemas import (
    DailyReportResponse,
    WeeklyReportResponse,
    MonthlyReportResponse,
    TimeOverviewData,
    ChartSegment,
    BarConfig,
    TodoStatsData,
    GoalProgressData,
    GoalTodoItem,
    HeatmapDataItem,
)
from lifeprism.server.providers.report_provider import daily_report_provider, weekly_report_provider, monthly_report_provider
from lifeprism.server.providers.todo_provider import todo_provider
from lifeprism.server.providers.goal_provider import goal_provider
from lifeprism.server.providers import server_lw_data_provider
from lifeprism.server.providers.category_color_provider import color_manager, get_log_color
from lifeprism.utils import get_logger

logger = get_logger(__name__)


# ==================== 主要接口 ====================

def get_daily_report(date: str, force_refresh: bool) -> DailyReportResponse:
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
    cached = daily_report_provider.get_daily_report(date)
    
    # 2. 判断是否需要重新计算
    need_recalc = (
        force_refresh  # 强制刷新
        or cached is None  # 无缓存
        or cached.get('state') != '1'  # 未完成状态
    )
    
    if not need_recalc and cached:
        logger.info(f"返回缓存的日报告 {date}")
        return _daily_dict_to_response(cached)
    
    # 3. 重新计算各板块数据
    logger.info(f"重新计算日报告 {date}")
    
    sunburst_data = _calc_sunburst_data(
        start_date=date, 
        end_date=date,
        title="今日时间分布",
        total_range_minutes=1440
    )
    todo_data = _calc_todo_stats(start_date=date, end_date=date)
    goal_data = _calc_goal_progress(start_date=date, end_date=date)
    daily_trend_data = _calc_hourly_trend(date)
    
    # 4. 保存到数据库
    # 判断状态：只有当今天的日期晚于报告日期时，才标记为已完成
    today = datetime.now().strftime('%Y-%m-%d')
    state = '1' if today > date else '0'
    
    report_data = {
        'sunburst_data': sunburst_data.model_dump() if sunburst_data else None,
        'todo_data': todo_data.model_dump() if todo_data else None,
        'goal_data': [g.model_dump() for g in goal_data] if goal_data else None,
        'daily_trend_data': daily_trend_data,
        'state': state
    }
    
    daily_report_provider.upsert_daily_report(date, report_data)
    
    # 5. 返回报告数据（保留已有的 ai_summary）
    existing_ai_summary = cached.get('ai_summary') if cached else None
    return DailyReportResponse(
        date=date,
        sunburst_data=sunburst_data,
        todo_data=todo_data,
        goal_data=goal_data,
        daily_trend_data=daily_trend_data,
        ai_summary=existing_ai_summary,
        state=state,
        data_version=1
    )


def get_weekly_report(week_start_date: str, force_refresh: bool) -> WeeklyReportResponse:
    """
    获取周报告
    
    逻辑:
    1. 查询缓存
    2. 判断是否需要重新计算 (force_refresh 或 state != '1' 或无缓存)
    3. 需要时重新计算并保存
    4. 返回报告数据
    
    Args:
        week_start_date: 周开始日期 YYYY-MM-DD（周一）
        force_refresh: 是否强制重新计算
        
    Returns:
        WeeklyReportResponse: 周报告数据
    """
    # 计算周结束日期（周日）
    start_dt = datetime.strptime(week_start_date, '%Y-%m-%d')
    end_dt = start_dt + timedelta(days=6)
    week_end_date = end_dt.strftime('%Y-%m-%d')
    
    # 1. 查询缓存
    cached = weekly_report_provider.get_weekly_report(week_start_date)
    
    # 2. 判断是否需要重新计算
    need_recalc = (
        force_refresh  # 强制刷新
        or cached is None  # 无缓存
        or cached.get('state') != '1'  # 未完成状态
    )
    
    if not need_recalc and cached:
        logger.info(f"返回缓存的周报告 {week_start_date}")
        return _weekly_dict_to_response(cached, week_start_date, week_end_date)
    
    # 3. 重新计算各板块数据
    logger.info(f"重新计算周报告 {week_start_date} ~ {week_end_date}")
    
    sunburst_data = _calc_sunburst_data(
        start_date=week_start_date, 
        end_date=week_end_date,
        title="本周时间分布",
        total_range_minutes=10080  # 7 * 24 * 60
    )
    todo_data = _calc_todo_stats(start_date=week_start_date, end_date=week_end_date)
    goal_data = _calc_goal_progress(start_date=week_start_date, end_date=week_end_date)
    daily_trend_data = _calc_weekly_trend(week_start_date, week_end_date)
    
    # 4. 保存到数据库
    # 判断状态：只有当今天的日期晚于周结束日期时，才标记为已完成
    today = datetime.now().strftime('%Y-%m-%d')
    state = '1' if today > week_end_date else '0'
    
    report_data = {
        'sunburst_data': sunburst_data.model_dump() if sunburst_data else None,
        'todo_data': todo_data.model_dump() if todo_data else None,
        'goal_data': [g.model_dump() for g in goal_data] if goal_data else None,
        'daily_trend_data': daily_trend_data,
        'state': state
    }
    
    weekly_report_provider.upsert_weekly_report(week_start_date, report_data)
    
    # 5. 返回报告数据（保留已有的 ai_summary）
    existing_ai_summary = cached.get('ai_summary') if cached else None
    return WeeklyReportResponse(
        week_start_date=week_start_date,
        week_end_date=week_end_date,
        sunburst_data=sunburst_data,
        todo_data=todo_data,
        goal_data=goal_data,
        daily_trend_data=daily_trend_data,
        ai_summary=existing_ai_summary,
        state=state,
        data_version=1
    )


def get_monthly_report(month: str, force_refresh: bool) -> MonthlyReportResponse:
    """
    获取月报告
    
    逻辑:
    1. 查询缓存
    2. 判断是否需要重新计算 (force_refresh 或 state != '1' 或无缓存)
    3. 需要时重新计算并保存
    4. 返回报告数据
    
    Args:
        month: 月份 YYYY-MM
        force_refresh: 是否强制重新计算
        
    Returns:
        MonthlyReportResponse: 月报告数据
    """
    import calendar
    
    # 解析月份，计算月初和月末日期
    year, mon = map(int, month.split('-'))
    month_start_date = f"{year}-{mon:02d}-01"
    last_day = calendar.monthrange(year, mon)[1]
    month_end_date = f"{year}-{mon:02d}-{last_day:02d}"
    
    # 1. 查询缓存
    cached = monthly_report_provider.get_monthly_report(month_start_date)
    
    # 2. 判断是否需要重新计算
    need_recalc = (
        force_refresh  # 强制刷新
        or cached is None  # 无缓存
        or cached.get('state') != '1'  # 未完成状态
    )
    
    if not need_recalc and cached:
        logger.info(f"返回缓存的月报告 {month}")
        return _monthly_dict_to_response(cached, month_start_date, month_end_date)
    
    # 3. 重新计算各板块数据
    logger.info(f"重新计算月报告 {month_start_date} ~ {month_end_date}")
    
    # 计算月份总分钟数
    total_range_minutes = last_day * 24 * 60
    
    sunburst_data = _calc_sunburst_data(
        start_date=month_start_date, 
        end_date=month_end_date,
        title="本月时间分布",
        total_range_minutes=total_range_minutes
    )
    todo_data = _calc_todo_stats(start_date=month_start_date, end_date=month_end_date)
    goal_data = _calc_goal_progress(start_date=month_start_date, end_date=month_end_date)
    daily_trend_data = _calc_monthly_trend(month_start_date, month_end_date)
    heatmap_data = _calc_heatmap_data(month_start_date, month_end_date)
    
    # 4. 保存到数据库
    # 判断状态：只有当今天的日期晚于月结束日期时，才标记为已完成
    today = datetime.now().strftime('%Y-%m-%d')
    state = '1' if today > month_end_date else '0'
    
    report_data = {
        'sunburst_data': sunburst_data.model_dump() if sunburst_data else None,
        'todo_data': todo_data.model_dump() if todo_data else None,
        'goal_data': [g.model_dump() for g in goal_data] if goal_data else None,
        'daily_trend_data': daily_trend_data,
        'heatmap_data': [h.model_dump() for h in heatmap_data] if heatmap_data else None,
        'state': state
    }
    
    monthly_report_provider.upsert_monthly_report(month_start_date, report_data)
    
    # 5. 返回报告数据（保留已有的 ai_summary）
    existing_ai_summary = cached.get('ai_summary') if cached else None
    return MonthlyReportResponse(
        month_start_date=month_start_date,
        month_end_date=month_end_date,
        sunburst_data=sunburst_data,
        todo_data=todo_data,
        goal_data=goal_data,
        daily_trend_data=daily_trend_data,
        heatmap_data=heatmap_data,
        ai_summary=existing_ai_summary,
        state=state,
        data_version=1
    )


async def get_daily_ai_summary(date: str, options: List[str]) -> dict:
    """
    获取每日 AI 总结（异步版本）
    
    调用 LLM 生成每日活动的智能分析总结，并保存到 daily_report 表
    
    Args:
        date: 日期 YYYY-MM-DD
        options: 总结选项列表
            - behavior_stats: 各时段的主分类和子分类的占比统计
            - longest_activities: 各时段内最长的活动记录
            - goal_time_spent: 各目标花费的时间
            - user_notes: 用户手动添加的时间块备注
            - tasks: 今日重点内容
            - all: 所有选项
        
    Returns:
        dict: 包含 content 和 tokens_usage 的字典
            - content: AI 生成的总结内容
            - tokens_usage: Token 使用量统计
    """
    from lifeprism.llm.llm_classify.function.report_summary import daily_summary
    
    logger.info(f"生成每日 AI 总结 {date}, options={options}")
    result = await daily_summary(date=date, options=options)
    
    # 保存 AI 总结到 daily_report 表
    try:
        daily_report_provider.upsert_daily_report(date, {
            'ai_summary': result['content']
        })
        logger.info(f"已保存 AI 总结到日报告 {date}")
    except Exception as e:
        logger.error(f"保存 AI 总结失败: {e}")
    
    return result


async def get_weekly_ai_summary(week_start_date: str, week_end_date: str, options: List[str]) -> dict:
    """
    获取周 AI 总结（异步版本）
    
    调用 LLM 生成每周活动的智能分析总结，并保存到 weekly_report 表
    
    Args:
        week_start_date: 周开始日期 YYYY-MM-DD（周一）
        week_end_date: 周结束日期 YYYY-MM-DD（周日）
        options: 总结选项列表
            - behavior_stats: 各时段的主分类和子分类的占比统计
            - longest_activities: 各时段内最长的活动记录
            - goal_time_spent: 各目标花费的时间
            - user_notes: 用户手动添加的时间块备注
            - tasks: 本周重点内容
            - all: 所有选项
        
    Returns:
        dict: 包含 content 和 tokens_usage 的字典
            - content: AI 生成的总结内容
            - tokens_usage: Token 使用量统计
    """
    from lifeprism.llm.llm_classify.function.report_summary import multi_days_summary
    
    logger.info(f"生成周 AI 总结 {week_start_date} ~ {week_end_date}, options={options}")
    
    start_time = f"{week_start_date} 00:00:00"
    end_time = f"{week_end_date} 23:59:59"
    
    result = await multi_days_summary(
        start_time=start_time,
        end_time=end_time,
        split_count=7,  # 周报按7天分割
        options=options
    )
    
    # 保存 AI 总结到 weekly_report 表
    try:
        weekly_report_provider.upsert_weekly_report(week_start_date, {
            'ai_summary': result['content']
        })
        logger.info(f"已保存 AI 总结到周报告 {week_start_date}")
    except Exception as e:
        logger.error(f"保存周 AI 总结失败: {e}")
    
    return result


async def get_monthly_ai_summary(month_start_date: str, month_end_date: str, options: List[str]) -> dict:
    """
    获取月 AI 总结（异步版本）
    
    调用 LLM 生成每月活动的智能分析总结，并保存到 monthly_report 表
    
    Args:
        month_start_date: 月开始日期 YYYY-MM-01
        month_end_date: 月结束日期 YYYY-MM-DD（月末）
        options: 总结选项列表
            - behavior_stats: 各时段的主分类和子分类的占比统计
            - longest_activities: 各时段内最长的活动记录
            - goal_time_spent: 各目标花费的时间
            - user_notes: 用户手动添加的时间块备注
            - tasks: 本月重点内容
            - all: 所有选项
        
    Returns:
        dict: 包含 content 和 tokens_usage 的字典
            - content: AI 生成的总结内容
            - tokens_usage: Token 使用量统计
    """
    from lifeprism.llm.llm_classify.function.report_summary import multi_days_summary
    
    logger.info(f"生成月 AI 总结 {month_start_date} ~ {month_end_date}, options={options}")
    
    start_time = f"{month_start_date} 00:00:00"
    end_time = f"{month_end_date} 23:59:59"
    
    # 计算天数用于 split_count
    start_dt = datetime.strptime(month_start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(month_end_date, '%Y-%m-%d')
    days = (end_dt - start_dt).days + 1
    
    # 月报分割为4段（约每周一段）
    split_count = min(4, days)
    
    result = await multi_days_summary(
        start_time=start_time,
        end_time=end_time,
        split_count=split_count,
        options=options
    )
    
    # 保存 AI 总结到 monthly_report 表
    try:
        monthly_report_provider.upsert_monthly_report(month_start_date, {
            'ai_summary': result['content']
        })
        logger.info(f"已保存 AI 总结到月报告 {month_start_date}")
    except Exception as e:
        logger.error(f"保存月 AI 总结失败: {e}")
    
    return result


# ==================== 通用数据计算函数 ====================

def _calc_sunburst_data(
    start_date: str, 
    end_date: str,
    title: str,
    total_range_minutes: int
) -> Optional[TimeOverviewData]:
    """
    计算旭日图数据（三层嵌套结构：Category → SubCategory → App）
    
    统一处理日报和周报的旭日图计算，通过参数区分:
    - 日报: start_date == end_date, title="今日时间分布", total_range_minutes=1440
    - 周报: start_date ~ end_date (7天), title="本周时间分布", total_range_minutes=10080
    """
    try:
        # 加载数据
        start_time = f"{start_date} 00:00:00"
        end_time = f"{end_date} 23:59:59"
        df = server_lw_data_provider.load_user_app_behavior_log(
            start_time=start_time, 
            end_time=end_time
        )
        
        if df is None or df.empty:
            return _build_empty_sunburst(start_date, end_date, title, total_range_minutes)
        
        # 预计算时长（分钟）
        df['start_dt'] = pd.to_datetime(df['start_time'])
        df['end_dt'] = pd.to_datetime(df['end_time'])
        df['duration_minutes'] = (df['end_dt'] - df['start_dt']).dt.total_seconds() / 60
        
        # 获取分类名称映射
        categories_df = server_lw_data_provider.load_categories()
        category_name_map = {}
        if categories_df is not None and not categories_df.empty:
            category_name_map = {str(row['id']): row['name'] for _, row in categories_df.iterrows()}
        
        sub_categories_df = server_lw_data_provider.load_sub_categories()
        sub_category_name_map = {}
        if sub_categories_df is not None and not sub_categories_df.empty:
            sub_category_name_map = {str(row['id']): row['name'] for _, row in sub_categories_df.iterrows()}
        
        # 构建 Level 1 (Category)
        root_data = _build_category_level(df, category_name_map, is_main_category=True)
        
        total_minutes = int(df['duration_minutes'].sum())
        hours = total_minutes // 60
        mins = total_minutes % 60
        
        # 构建 Level 2 & 3 (SubCategory → App)
        details = {}
        categories = df['category_id'].dropna().unique()
        
        for category_id in categories:
            cat_df = df[df['category_id'] == category_id]
            if cat_df.empty:
                continue
            
            category_name = category_name_map.get(str(category_id), "Uncategorized")
            
            # 检测该主分类下是否有子分类
            sub_categories = cat_df['sub_category_id'].dropna().unique()
            
            if len(sub_categories) == 0:
                # 无子分类 → 直接构建 App 层
                app_data = _build_app_level(
                    cat_df,
                    title=f"{category_name} Apps",
                    sub_title=f"Top applications in {category_name}",
                    parent_category_id=str(category_id)
                )
                details[category_name] = app_data
            else:
                # 有子分类 → 正常构建子分类层
                cat_data = _build_category_level(
                    cat_df, 
                    sub_category_name_map, 
                    is_main_category=False,
                    group_field='sub_category_id'
                )
                cat_data_details = {}
                
                # Level 3 (Apps)
                for sub_cat_id in sub_categories:
                    sub_df = cat_df[cat_df['sub_category_id'] == sub_cat_id]
                    if sub_df.empty:
                        continue
                    
                    sub_cat_name = sub_category_name_map.get(str(sub_cat_id), "Uncategorized")
                    
                    app_data = _build_app_level(
                        sub_df,
                        title=f"{sub_cat_name} Apps",
                        sub_title=f"Top applications in {sub_cat_name}",
                        parent_sub_category_id=str(sub_cat_id)
                    )
                    cat_data_details[sub_cat_name] = app_data
                
                cat_data.details = cat_data_details if cat_data_details else None
                details[category_name] = cat_data
        
        return TimeOverviewData(
            title=title,
            sub_title=f"共计 {hours} 小时 {mins} 分钟",
            total_tracked_minutes=total_minutes,
            total_range_minutes=total_range_minutes,
            pie_data=root_data.pie_data,
            bar_keys=root_data.bar_keys,
            bar_data=root_data.bar_data,
            details=details if details else None
        )
        
    except Exception as e:
        logger.error(f"计算旭日图数据失败: {e}")
        return _build_empty_sunburst(start_date, end_date, title, total_range_minutes)


def _calc_todo_stats(start_date: str, end_date: str) -> TodoStatsData:
    """
    计算 Todo 统计数据
    
    统一处理日报和周报:
    - 日报: start_date == end_date, 只计算单天
    - 周报: start_date ~ end_date, 遍历多天聚合
    """
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        days = (end_dt - start_dt).days + 1
        
        total = 0
        completed = 0
        procrastination = 0
        
        for i in range(days):
            current_date = (start_dt + timedelta(days=i)).strftime('%Y-%m-%d')
            todos = todo_provider.get_todos_by_date(current_date, include_cross_day=False)
            
            total += len(todos)
            completed += sum(1 for t in todos if t.get('state') == 'completed')
            
            # 计算拖延：未完成且超过预期日期
            procrastination += sum(1 for t in todos if
                t.get('state') != 'completed' and
                t.get('expected_finished_at') and
                t['expected_finished_at'] < current_date
            )
        
        pending = total - completed
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


def _calc_goal_progress(start_date: str, end_date: str) -> List[GoalProgressData]:
    """
    计算 Goal 进度数据
    
    统一处理日报和周报:
    - 日报: start_date == end_date, 只计算单天
    - 周报: start_date ~ end_date, 遍历多天聚合（去重）
    
    时间投入从 user_app_behavior_log 实时计算
    """
    try:
        # 获取所有活跃目标
        goals = goal_provider.get_active_goals()
        if not goals:
            return []
        
        result = []
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        days = (end_dt - start_dt).days + 1
        
        for goal in goals:
            goal_id = goal['id']
            
            # 收集日期范围内的待办
            goal_todos = []
            existing_ids = set()
            
            for i in range(days):
                current_date = (start_dt + timedelta(days=i)).strftime('%Y-%m-%d')
                all_todos = todo_provider.get_todos_by_date(current_date, include_cross_day=True)
                day_goal_todos = [t for t in all_todos if t.get('link_to_goal_id') == goal_id]
                
                # 避免重复添加（跨天任务可能重复）
                for t in day_goal_todos:
                    if t['id'] not in existing_ids:
                        goal_todos.append(t)
                        existing_ids.add(t['id'])
            
            # 计算时间投入
            time_invested = _calc_goal_time_invested(goal_id, start_date, end_date)
            
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


def _calc_goal_time_invested(goal_id: str, start_date: str, end_date: str) -> int:
    """
    计算目标在日期范围内的时间投入（分钟）
    
    从 user_app_behavior_log 中查询 link_to_goal_id 匹配的记录
    """
    try:
        start_time = f"{start_date} 00:00:00"
        end_time = f"{end_date} 23:59:59"
        
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


# ==================== 趋势数据计算函数（日报和周报不同） ====================

def _calc_hourly_trend(date: str) -> List[Dict[str, Any]]:
    """
    计算24小时趋势数据（日报专用）
    
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
            return _build_empty_hourly_trend()
        
        # 获取分类名称映射
        categories_df = server_lw_data_provider.load_categories()
        category_name_map = {}
        if categories_df is not None and not categories_df.empty:
            category_name_map = {str(row['id']): row['name'] for _, row in categories_df.iterrows()}
        
        # 预处理时间
        df['start_dt'] = pd.to_datetime(df['start_time'])
        df['end_dt'] = pd.to_datetime(df['end_time'])
        
        # 按小时统计各分类时长
        hourly_data = defaultdict(lambda: defaultdict(int))
        
        for _, row in df.iterrows():
            start = row['start_dt']
            end = row['end_dt']
            cat_id = str(row['category_id']) if pd.notna(row['category_id']) else 'unknown'
            cat_name = category_name_map.get(cat_id, 'Uncategorized')
            
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
        return _build_empty_hourly_trend()


def _calc_weekly_trend(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """
    计算每日趋势数据（周报专用）
    
    返回格式: [{'label': '周一', 'work': 120, 'entertainment': 60, ...}, ...]
    """
    try:
        start_time = f"{start_date} 00:00:00"
        end_time = f"{end_date} 23:59:59"
        
        df = server_lw_data_provider.load_user_app_behavior_log(
            start_time=start_time,
            end_time=end_time
        )
        
        if df is None or df.empty:
            return _build_empty_weekly_trend(start_date)
        
        # 获取分类名称映射
        categories_df = server_lw_data_provider.load_categories()
        category_name_map = {}
        if categories_df is not None and not categories_df.empty:
            category_name_map = {str(row['id']): row['name'] for _, row in categories_df.iterrows()}
        
        # 预处理时间
        df['start_dt'] = pd.to_datetime(df['start_time'])
        df['end_dt'] = pd.to_datetime(df['end_time'])
        df['date'] = df['start_dt'].dt.date
        df['duration_minutes'] = (df['end_dt'] - df['start_dt']).dt.total_seconds() / 60
        
        # 按日期和分类聚合
        daily_data = defaultdict(lambda: defaultdict(int))
        
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        for _, row in df.iterrows():
            row_date = row['date']
            cat_id = str(row['category_id']) if pd.notna(row['category_id']) else 'unknown'
            cat_name = category_name_map.get(cat_id, 'Uncategorized')
            minutes = row['duration_minutes']
            
            daily_data[row_date][cat_name] += minutes
        
        # 收集所有出现过的分类名称
        all_categories = set()
        for day_data in daily_data.values():
            all_categories.update(day_data.keys())
        
        # 构建结果 - 7天数据
        weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        result = []
        
        for i in range(7):
            current_date = start_dt + timedelta(days=i)
            data_point = {'label': weekday_names[i], 'date': str(current_date)}
            
            # 为所有分类设置值（没有数据的为 0）
            for cat_name in all_categories:
                data_point[cat_name] = int(daily_data[current_date].get(cat_name, 0))
            
            result.append(data_point)
        
        return result
        
    except Exception as e:
        logger.error(f"计算周趋势数据失败: {e}")
        return _build_empty_weekly_trend(start_date)


def _calc_monthly_trend(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """
    计算月度每日趋势数据（月报专用）
    
    返回格式: [{'label': '1', 'work': 120, 'entertainment': 60, ...}, ...]
    label 为日期的天数（1, 2, 3, ...）
    """
    try:
        start_time = f"{start_date} 00:00:00"
        end_time = f"{end_date} 23:59:59"
        
        df = server_lw_data_provider.load_user_app_behavior_log(
            start_time=start_time,
            end_time=end_time
        )
        
        if df is None or df.empty:
            return _build_empty_monthly_trend(start_date, end_date)
        
        # 获取分类名称映射
        categories_df = server_lw_data_provider.load_categories()
        category_name_map = {}
        if categories_df is not None and not categories_df.empty:
            category_name_map = {str(row['id']): row['name'] for _, row in categories_df.iterrows()}
        
        # 预处理时间
        df['start_dt'] = pd.to_datetime(df['start_time'])
        df['end_dt'] = pd.to_datetime(df['end_time'])
        df['date'] = df['start_dt'].dt.date
        df['duration_minutes'] = (df['end_dt'] - df['start_dt']).dt.total_seconds() / 60
        
        # 按日期和分类聚合
        daily_data = defaultdict(lambda: defaultdict(int))
        
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        for _, row in df.iterrows():
            row_date = row['date']
            cat_id = str(row['category_id']) if pd.notna(row['category_id']) else 'unknown'
            cat_name = category_name_map.get(cat_id, 'Uncategorized')
            minutes = row['duration_minutes']
            
            daily_data[row_date][cat_name] += minutes
        
        # 收集所有出现过的分类名称
        all_categories = set()
        for day_data in daily_data.values():
            all_categories.update(day_data.keys())
        
        # 构建结果 - 整月数据
        result = []
        days = (end_dt - start_dt).days + 1
        
        for i in range(days):
            current_date = start_dt + timedelta(days=i)
            day_of_month = current_date.day
            data_point = {'label': str(day_of_month), 'date': str(current_date)}
            
            # 为所有分类设置值（没有数据的为 0）
            for cat_name in all_categories:
                data_point[cat_name] = int(daily_data[current_date].get(cat_name, 0))
            
            result.append(data_point)
        
        return result
        
    except Exception as e:
        logger.error(f"计算月趋势数据失败: {e}")
        return _build_empty_monthly_trend(start_date, end_date)


def _calc_heatmap_data(start_date: str, end_date: str) -> List[HeatmapDataItem]:
    """
    计算热力图数据（月报专用）
    
    为每一天计算总追踪分钟数和分类分解
    """
    try:
        start_time = f"{start_date} 00:00:00"
        end_time = f"{end_date} 23:59:59"
        
        df = server_lw_data_provider.load_user_app_behavior_log(
            start_time=start_time,
            end_time=end_time
        )
        
        if df is None or df.empty:
            return _build_empty_heatmap(start_date, end_date)
        
        # 获取分类名称映射
        categories_df = server_lw_data_provider.load_categories()
        category_name_map = {}
        if categories_df is not None and not categories_df.empty:
            category_name_map = {str(row['id']): row['name'] for _, row in categories_df.iterrows()}
        
        # 预处理时间
        df['start_dt'] = pd.to_datetime(df['start_time'])
        df['end_dt'] = pd.to_datetime(df['end_time'])
        df['date'] = df['start_dt'].dt.date
        df['duration_minutes'] = (df['end_dt'] - df['start_dt']).dt.total_seconds() / 60
        
        # 按日期和分类聚合（使用 float 累加保持精度）
        daily_totals = defaultdict(float)
        daily_breakdown = defaultdict(lambda: defaultdict(float))
        
        for _, row in df.iterrows():
            row_date = row['date']
            cat_id = str(row['category_id']) if pd.notna(row['category_id']) else 'unknown'
            cat_name = category_name_map.get(cat_id, 'Uncategorized')
            minutes = row['duration_minutes']
            
            daily_totals[row_date] += minutes
            daily_breakdown[row_date][cat_name] += minutes
        
        # 构建结果
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
        days = (end_dt - start_dt).days + 1
        
        result = []
        for i in range(days):
            current_date = start_dt + timedelta(days=i)
            date_str = current_date.strftime('%Y-%m-%d')
            
            # 最终输出时取整
            breakdown = daily_breakdown.get(current_date, {})
            breakdown_int = {k: int(v) for k, v in breakdown.items()} if breakdown else None
            
            result.append(HeatmapDataItem(
                date=date_str,
                total_minutes=int(daily_totals.get(current_date, 0)),
                category_breakdown=breakdown_int
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"计算热力图数据失败: {e}")
        return _build_empty_heatmap(start_date, end_date)


# ==================== 辅助构建函数 ====================

def _build_category_level(
    df: pd.DataFrame, 
    name_map: dict, 
    is_main_category: bool,
    group_field: str = 'category_id'
) -> TimeOverviewData:
    """构建分类级别数据"""
    stats = df.groupby(group_field).agg({
        'duration_minutes': 'sum'
    }).reset_index()
    stats.columns = ['id', 'minutes']
    stats = stats.sort_values('minutes', ascending=False)
    
    total_minutes = int(stats['minutes'].sum())
    
    pie_data = []
    bar_keys = []
    
    for _, row in stats.iterrows():
        cat_id = str(row['id']) if pd.notna(row['id']) else "unknown"
        name = name_map.get(cat_id, "Uncategorized")
        minutes = int(row['minutes'])
        
        if is_main_category:
            item_color = color_manager.get_main_category_color(cat_id)
        else:
            item_color = color_manager.get_sub_category_color(cat_id)
        
        pie_data.append(ChartSegment(
            key=cat_id,
            name=name,
            value=minutes,
            color=item_color,
            title=""
        ))
        
        bar_keys.append(BarConfig(
            key=cat_id,
            label=name,
            color=item_color
        ))
    
    return TimeOverviewData(
        title="",
        sub_title="",
        total_tracked_minutes=total_minutes,
        pie_data=pie_data,
        bar_keys=bar_keys,
        bar_data=None,
        details=None
    )


def _build_app_level(
    df: pd.DataFrame,
    title: str,
    sub_title: str,
    parent_sub_category_id: str = None,
    parent_category_id: str = None
) -> TimeOverviewData:
    """构建应用级别数据（Top 5 + Other）"""
    stats = df.groupby('app')['duration_minutes'].sum().sort_values(ascending=False)
    total_minutes = int(stats.sum())
    
    top_5 = stats.head(5)
    other_value = stats.iloc[5:].sum() if len(stats) > 5 else 0
    
    # 根据传入的参数决定使用主分类或子分类颜色作为基准
    if parent_sub_category_id:
        base_color = color_manager.get_sub_category_color(parent_sub_category_id)
    elif parent_category_id:
        base_color = color_manager.get_main_category_color(parent_category_id)
    else:
        base_color = "#5B8FF9"  # 默认颜色
    
    pie_data = []
    bar_keys = []
    
    for i, (app_name, minutes) in enumerate(top_5.items()):
        # 为每个 App 生成随机浅色
        app_color = get_log_color(base_color)
        
        # 获取该应用的 top 3 titles
        app_df = df[df['app'] == app_name]
        title_stats = app_df.groupby('title')['duration_minutes'].sum().sort_values(ascending=False).head(3)
        top_titles = "-split-".join(title_stats.index.tolist())
        
        pie_data.append(ChartSegment(
            key=app_name,
            name=app_name,
            value=int(minutes),
            color=app_color,
            title=top_titles
        ))
        
        bar_keys.append(BarConfig(
            key=app_name,
            label=app_name,
            color=app_color
        ))
    
    if other_value > 0:
        other_color = "#9CA3AF"
        pie_data.append(ChartSegment(
            key="Other",
            name="Other Apps",
            value=int(other_value),
            color=other_color,
            title=""
        ))
        bar_keys.append(BarConfig(
            key="Other",
            label="Other",
            color=other_color
        ))
    
    return TimeOverviewData(
        title=title,
        sub_title=sub_title,
        total_tracked_minutes=total_minutes,
        pie_data=pie_data,
        bar_keys=bar_keys,
        bar_data=None,
        details=None
    )


# ==================== 空数据构建函数 ====================

def _build_empty_sunburst(
    start_date: str, 
    end_date: str, 
    title: str, 
    total_range_minutes: int
) -> TimeOverviewData:
    """构建空的旭日图数据"""
    if start_date == end_date:
        sub_title = f"暂无 {start_date} 的活动数据"
    else:
        sub_title = f"暂无 {start_date} ~ {end_date} 的活动数据"
    
    return TimeOverviewData(
        title=title,
        sub_title=sub_title,
        total_tracked_minutes=0,
        total_range_minutes=total_range_minutes,
        pie_data=[],
        details=None
    )


def _build_empty_hourly_trend() -> List[Dict[str, Any]]:
    """构建空的24小时趋势数据"""
    return [{'label': str(h)} for h in range(24)]


def _build_empty_weekly_trend(start_date: str = None) -> List[Dict[str, Any]]:
    """构建空的周趋势数据"""
    weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    if start_date:
        from datetime import datetime, timedelta
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        return [{'label': name, 'date': str(start_dt + timedelta(days=i))} for i, name in enumerate(weekday_names)]
    return [{'label': name} for name in weekday_names]


def _build_empty_monthly_trend(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """构建空的月趋势数据"""
    from datetime import datetime, timedelta
    start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
    days = (end_dt - start_dt).days + 1
    return [{'label': str(i + 1), 'date': str(start_dt + timedelta(days=i))} for i in range(days)]


def _build_empty_heatmap(start_date: str, end_date: str) -> List[HeatmapDataItem]:
    """构建空的热力图数据"""
    start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
    days = (end_dt - start_dt).days + 1
    
    result = []
    for i in range(days):
        current_date = start_dt + timedelta(days=i)
        result.append(HeatmapDataItem(
            date=current_date.strftime('%Y-%m-%d'),
            total_minutes=0,
            category_breakdown=None
        ))
    return result


# ==================== 缓存数据转换函数 ====================

def _daily_dict_to_response(data: Dict[str, Any]) -> DailyReportResponse:
    """将数据库记录转换为日报告响应模型"""
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
        ai_summary=data.get('ai_summary'),
        state=data.get('state', '0'),
        data_version=data.get('data_version', 1)
    )


def _weekly_dict_to_response(
    data: Dict[str, Any], 
    week_start_date: str, 
    week_end_date: str
) -> WeeklyReportResponse:
    """将数据库记录转换为周报告响应模型"""
    sunburst_data = None
    if data.get('sunburst_data'):
        sunburst_data = TimeOverviewData(**data['sunburst_data'])
    
    todo_data = None
    if data.get('todo_data'):
        todo_data = TodoStatsData(**data['todo_data'])
    
    goal_data = None
    if data.get('goal_data'):
        goal_data = [GoalProgressData(**g) for g in data['goal_data']]
    
    return WeeklyReportResponse(
        week_start_date=week_start_date,
        week_end_date=week_end_date,
        sunburst_data=sunburst_data,
        todo_data=todo_data,
        goal_data=goal_data,
        daily_trend_data=data.get('daily_trend_data'),
        ai_summary=data.get('ai_summary'),
        state=data.get('state', '0'),
        data_version=data.get('data_version', 1)
    )


def _monthly_dict_to_response(
    data: Dict[str, Any], 
    month_start_date: str, 
    month_end_date: str
) -> MonthlyReportResponse:
    """将数据库记录转换为月报告响应模型"""
    sunburst_data = None
    if data.get('sunburst_data'):
        sunburst_data = TimeOverviewData(**data['sunburst_data'])
    
    todo_data = None
    if data.get('todo_data'):
        todo_data = TodoStatsData(**data['todo_data'])
    
    goal_data = None
    if data.get('goal_data'):
        goal_data = [GoalProgressData(**g) for g in data['goal_data']]
    
    heatmap_data = None
    if data.get('heatmap_data'):
        heatmap_data = [HeatmapDataItem(**h) for h in data['heatmap_data']]
    
    return MonthlyReportResponse(
        month_start_date=month_start_date,
        month_end_date=month_end_date,
        sunburst_data=sunburst_data,
        todo_data=todo_data,
        goal_data=goal_data,
        daily_trend_data=data.get('daily_trend_data'),
        heatmap_data=heatmap_data,
        ai_summary=data.get('ai_summary'),
        state=data.get('state', '0'),
        data_version=data.get('data_version', 1)
    )


def test_compare_weekly_and_monthly_trend():
    """
    测试 _calc_weekly_trend 和 _calc_monthly_trend 计算同一周数据时的结果是否一致
    
    用于调试月视图和周视图数据不一致的问题
    """
    # 使用 2025-12-29 ~ 2026-01-04 这一周进行测试（包含 12-31）
    week_start = '2025-12-29'  # 周一
    week_end = '2026-01-04'    # 周日
    
    print("=" * 60)
    print("测试 _calc_weekly_trend vs _calc_monthly_trend")
    print("=" * 60)
    print(f"测试日期范围: {week_start} ~ {week_end}")
    print()
    
    # 1. 计算周趋势
    print("1. _calc_weekly_trend 结果:")
    weekly_result = _calc_weekly_trend(week_start, week_end)
    
    # 提取周四（12-31）的数据进行重点比较
    weekly_dec_31 = None
    for day in weekly_result:
        print(f"   {day}")
        if day.get('date') == '2025-12-31':
            weekly_dec_31 = day
    
    print()
    
    # 2. 计算月趋势（只取 12 月的最后几天）
    print("2. _calc_monthly_trend 结果 (2025-12-29 ~ 2025-12-31):")
    monthly_result = _calc_monthly_trend('2025-12-29', '2025-12-31')
    
    monthly_dec_31 = None
    for day in monthly_result:
        print(f"   {day}")
        if day.get('label') == '31':
            monthly_dec_31 = day
    
    print()
    
    # 3. 比较 12-31 的数据
    print("3. 重点对比 2025-12-31 的数据:")
    print(f"   周视图 (12-31): {weekly_dec_31}")
    print(f"   月视图 (31):    {monthly_dec_31}")
    
    if weekly_dec_31 and monthly_dec_31:
        print()
        print("4. 分类对比:")
        # 获取所有分类键（排除 label 和 date）
        weekly_cats = {k: v for k, v in weekly_dec_31.items() if k not in ['label', 'date']}
        monthly_cats = {k: v for k, v in monthly_dec_31.items() if k != 'label'}
        
        all_cats = set(weekly_cats.keys()) | set(monthly_cats.keys())
        
        has_diff = False
        for cat in sorted(all_cats):
            w_val = weekly_cats.get(cat, 0)
            m_val = monthly_cats.get(cat, 0)
            diff = w_val - m_val
            status = "✅" if diff == 0 else "❌"
            if diff != 0:
                has_diff = True
            print(f"   {status} {cat}: 周={w_val}分钟, 月={m_val}分钟, 差异={diff}分钟 ({diff/60:.2f}小时)")
        
        if has_diff:
            print()
            print("⚠️ 发现数据差异！需要进一步调查原因。")
        else:
            print()
            print("✅ 数据一致！")
    
    print()
    print("=" * 60)


if __name__ == "__main__":
    test_compare_weekly_and_monthly_trend()
