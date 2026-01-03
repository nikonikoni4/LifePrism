"""
数据库相关的 LLM 工具
原则：查询功能应该能够解决一个业务问题，而不是分散的让llm查询
"""
from typing import Annotated
from langchain.tools import tool

from lifewatch.llm.llm_classify.providers.llm_lw_data_provider import llm_lw_data_provider


def _format_seconds(seconds: int) -> str:
    """将秒数格式化为可读时间"""
    if seconds < 60:
        return f"{seconds}秒"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}分钟"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes > 0:
            return f"{hours}小时{minutes}分钟"
        return f"{hours}小时"


def _format_stats(stats: list) -> str:
    """格式化分段统计数据"""
    if not stats:
        return "  - 暂无数据"
    
    lines = []
    for i, seg in enumerate(stats, 1):
        lines.append(f"  - 时段{i}（{seg['segment_start']} 至 {seg['segment_end']}）")
        lines.append(f"    - 活跃时间: {_format_seconds(seg['active_seconds'])}（{seg['active_percentage']}%）")
        lines.append(f"    - 空闲时间: {_format_seconds(seg['idle_seconds'])}（{seg['idle_percentage']}%）")
    return "\n".join(lines)


def _format_category_distribution(dist: dict) -> str:
    """格式化分类占比数据"""
    if not dist:
        return "  - 暂无数据"
    
    lines = []
    total_seconds = dist.get("segment_total_seconds", 0)
    lines.append(f"  - 统计时长: {_format_seconds(total_seconds)}")
    
    # 主分类
    categories = dist.get("categories", [])
    if categories:
        lines.append("  - 主分类占比:")
        for cat in categories:
            lines.append(f"    - {cat['name']}: {_format_seconds(cat['duration'])}（{cat['percentage']}%）")
    
    # 子分类
    sub_categories = dist.get("sub_categories", [])
    if sub_categories:
        lines.append("  - 子分类占比:")
        for sub in sub_categories:
            lines.append(f"    - {sub['name']}: {_format_seconds(sub['duration'])}（{sub['percentage']}%）")
    
    return "\n".join(lines)


def _format_longest_activities(activities: list) -> str:
    """格式化最长活动数据"""
    if not activities:
        return "  - 暂无数据"
    
    lines = []
    for act in activities:
        title = act.get('title', '未知')
        app = act.get('app', '未知')
        duration = _format_seconds(act.get('duration_seconds', 0))
        lines.append(f"  - {title}（{app}）: {duration}")
    return "\n".join(lines)


def _format_goal_time_spent(goals: dict) -> str:
    """格式化目标时间花费数据"""
    if not goals:
        return "  - 暂无目标时间记录"
    
    lines = []
    for goal_id, info in goals.items():
        name = info.get('name', '未知目标')
        duration = _format_seconds(info.get('duration_seconds', 0))
        lines.append(f"  - {name}: {duration}")
    return "\n".join(lines)


def _format_user_notes(notes: list) -> str:
    """格式化用户备注数据"""
    if not notes:
        return "  - 暂无用户备注"
    
    lines = []
    for note in notes:
        start = note.get('start_time', '')
        end = note.get('end_time', '')
        content = note.get('content', '')
        duration = note.get('duration_minutes', 0)
        lines.append(f"  - [{start} ~ {end}]（{duration}分钟）: {content}")
    return "\n".join(lines)


def _format_daily_summary(content: str) -> str:
    """格式化每日重点与任务"""
    if not content:
        return "  - 暂无数据"
    # 增加缩进，使输出整齐
    lines = content.strip().split('\n')
    return "\n".join([f"  {line}" for line in lines])


@tool
def get_daily_stats(
    start_time: Annotated[str, "开始时间 YYYY-MM-DD HH:MM:SS"],
    end_time: Annotated[str, "结束时间 YYYY-MM-DD HH:MM:SS"],
    split_count: Annotated[int, "切分时间段,把时间分成n个时间段,以获得更加详细的行为统计,长时段split_count应该更大,短时段split_count应该更小"],
    options: Annotated[list, "可选参数,stats,category_distribution,longest_activities,goal_time_spent,user_notes,tasks,all"] = None
) -> str:
    """
    获取时间段小于24h的用户行为统计摘要数据，也可作为数据查询接口
    
    返回指定时间段内的完整统计（格式化文本）：
    - stats: 各时段的活跃/空闲统计
    - category_distribution: 主分类和子分类的占比
    - longest_activities: 各时段内最长的活动记录
    - goal_time_spent: 各目标花费的时间
    - user_notes: 用户手动添加的时间块备注
    - today_focus: 今日重点内容
    """
    try:
        # 解析 options，默认返回全部
        if options is None or "all" in options:
            fetch_all = True
            fetch_options = set()
        else:
            fetch_all = False
            fetch_options = set(options)
        
        prompt_parts = []
        prompt_parts.append(f"用户行为统计（{start_time} 至 {end_time}）\n")
        
        section_num = 1
        
        # 1. 分段统计
        if fetch_all or "stats" in fetch_options:
            stats = llm_lw_data_provider.get_stats_by_time_segments(
                start_time=start_time,
                end_time=end_time,
                segment_count=split_count
            )
            prompt_parts.append(f"{section_num}. 分段活跃统计")
            prompt_parts.append(_format_stats(stats))
            section_num += 1
        
        # 2. 分类占比
        if fetch_all or "category_distribution" in fetch_options:
            distribution = llm_lw_data_provider.get_category_distribution(
                start_time=start_time,
                end_time=end_time
            )
            prompt_parts.append(f"\n{section_num}. 分类时间占比")
            prompt_parts.append(_format_category_distribution(distribution))
            section_num += 1
        
        # 3. 最长活动
        if fetch_all or "longest_activities" in fetch_options:
            activities = llm_lw_data_provider.get_longest_activities(
                start_time=start_time,
                end_time=end_time,
                segment_count=split_count,
                top_percentage=0.1,
                max_count=5
            )
            prompt_parts.append(f"\n{section_num}. 主要活动记录")
            prompt_parts.append(_format_longest_activities(activities))
            section_num += 1
        
        # 4. 目标花费时间和趋势
        if fetch_all or "goal_time_spent" in fetch_options:
            goal_time = llm_lw_data_provider.get_goal_time_spent(
                start_time=start_time,
                end_time=end_time
            )
            prompt_parts.append(f"\n{section_num}. 目标时间投入")
            prompt_parts.append(_format_goal_time_spent(goal_time))
            section_num += 1
        
        # 5. 用户备注
        if fetch_all or "user_notes" in fetch_options:
            notes = llm_lw_data_provider.get_user_focus_notes(
                start_time=start_time,
                end_time=end_time
            )
            prompt_parts.append(f"\n{section_num}. 用户备注")
            prompt_parts.append(_format_user_notes(notes))
            section_num += 1
        
        # 6. 今日重点与任务
        if fetch_all or "tasks" in fetch_options:
            daily_summary = llm_lw_data_provider.get_focus_and_todos(start_time=start_time, end_time=end_time)
            prompt_parts.append(f"\n{section_num}. 今日重点与任务")
            prompt_parts.append(_format_daily_summary(daily_summary))

        return "\n".join(prompt_parts)
        
    except Exception as e:
        return f"获取用户行为统计失败: {str(e)}"

@tool
def get_multi_days_stats(
    start_time: Annotated[str, "开始时间 YYYY-MM-DD HH:MM:SS"],
    end_time: Annotated[str, "结束时间 YYYY-MM-DD HH:MM:SS"],
    options: Annotated[list, "可选参数,goal_trend,tasks,category_trend,user_notes,all"] = None
) -> str:
    """
    获取多天用户行为统计摘要数据，也可作为数据查询接口
    """
    try:
        # 解析 options，默认返回全部
        if options is None or "all" in options:
            fetch_all = True
            fetch_options = set()
        else:
            fetch_all = False
            fetch_options = set(options)
        
        prompt_parts = []
        prompt_parts.append(f"用户行为统计（{start_time} 至 {end_time}）\n")
        
        section_num = 1
        
        # 1. 目标花费时间
        if fetch_all or "goal_trend" in fetch_options:
            goal_trend = llm_lw_data_provider.get_daily_goal_trend(start_time, end_time)
            prompt_parts.append(f"\n{section_num}. 在goal上花费的时间")
            prompt_parts.append(goal_trend)
            section_num += 1
        

        # 2. 每日重点与任务
        if fetch_all or "tasks" in fetch_options:
            summary = llm_lw_data_provider.get_focus_and_todos(start_time, end_time)
            prompt_parts.append(f"\n{section_num}. 每日重点与任务")
            prompt_parts.append(summary)
            section_num += 1
        
        # 3. 分类占比
        if fetch_all or "category_trend" in fetch_options:
            category_trend = llm_lw_data_provider.get_daily_category_trend(start_time, end_time)
            prompt_parts.append(f"\n{section_num}. 分类占比")
            prompt_parts.append(category_trend)
            section_num += 1
        
        # 4. 用户备注
        if fetch_all or "user_notes" in fetch_options:
            notes = llm_lw_data_provider.get_user_focus_notes(start_time, end_time)
            prompt_parts.append(f"\n{section_num}. 用户备注")
            prompt_parts.append(_format_user_notes(notes))
            section_num += 1
        
        return "\n".join(prompt_parts)
        
    except Exception as e:
        return f"获取用户行为统计失败: {str(e)}"

if __name__ == "__main__":
    result = get_multi_days_stats.invoke(
        input = {
            "start_time": "2025-12-25 00:00:00",
            "end_time": "2025-12-30 23:59:59",
            "split_count": 2,
            "options": ["all"]
        }
    )
    print(result)