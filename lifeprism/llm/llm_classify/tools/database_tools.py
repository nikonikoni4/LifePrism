"""
数据库相关的 LLM 工具
原则：查询功能应该能够解决一个业务问题，而不是分散的让llm查询
"""
from typing import Annotated
from langchain.tools import tool

from lifeprism.llm.llm_classify.providers.llm_lw_data_provider import llm_lw_data_provider
from lifeprism.utils import get_logger,DEBUG
logger = get_logger(__name__,DEBUG)

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


def _format_segment_category_stats(segments_data: list, activities_by_segment: dict = None) -> str:
    """格式化分段统计与分类占比数据（统一输出，包含主要活动记录）
    
    Args:
        segments_data: 包含每个时段的统计和分类信息的列表
        activities_by_segment: 按时段索引组织的活动记录字典 {segment_index: [activities]}
    
    Returns:
        格式化的字符串，每个时段包含时间范围、分类占比和主要活动记录，子分类嵌套在主分类下
    """
    if not segments_data:
        return "  - 暂无数据"
    
    lines = []
    for i, seg in enumerate(segments_data, 1):
        # 时段标题
        lines.append(f"  - 时段{i}（{seg['segment_start']} 至 {seg['segment_end']}）")
        
        # 主分类占比
        categories = seg.get('categories', [])
        sub_categories = seg.get('sub_categories', [])
        
        if categories:
            lines.append("    - 分类占比:")
            
            # 为每个主分类找到对应的子分类
            for cat in categories:
                cat_id = cat['id']
                lines.append(f"      - {cat['name']}: {_format_seconds(cat['duration'])}（{cat['percentage']}%）")
                
                # 找到属于这个主分类的子分类
                if sub_categories and cat_id != 'idle':  # 空闲没有子分类
                    related_subs = [sub for sub in sub_categories if sub.get('category_id') == cat_id]
                    for sub in related_subs:
                        lines.append(f"         - {sub['name']}: {_format_seconds(sub['duration'])}（{sub['percentage']}%）")
        
        # 主要活动记录
        if activities_by_segment and i in activities_by_segment:
            activities = activities_by_segment[i]
            if activities:
                lines.append("    - 主要活动记录:")
                for act in activities:
                    title = act.get('title', '未知')
                    app = act.get('app', '未知')
                    duration = _format_seconds(act.get('duration_seconds', 0))
                    lines.append(f"      - {title}（{app}）: {duration}")
    
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


# 修改此处的option时需要同步修改
# lifeprism\llm\custom_prompt\chatbot_prompt\summary_prompt.py 中的
# daily_summary_template
@tool
def get_daily_stats(
    start_time: Annotated[str, "开始时间 YYYY-MM-DD HH:MM:SS"],
    end_time: Annotated[str, "结束时间 YYYY-MM-DD HH:MM:SS"],
    split_count: Annotated[int, "切分时间段,把时间分成n个时间段,以获得更加详细的行为统计,长时段split_count应该更大,短时段split_count应该更小"],
    options: Annotated[list, "可选参数,pc_active_time,behavior_stats,goal_time_spent,user_notes,tasks,all"] = None
) -> str:
    """
    获取时间段小于24h的用户行为统计摘要数据，也可作为数据查询接口
    
    返回指定时间段内的完整统计（格式化文本）：
    - pc_active_time: 各时段内电脑使用时间占比
    - behavior_stats: 行为数据统计：各时段的主分类和子分类的占比统计+主要活动记录
    - goal_time_spent: 各目标花费的时间
    - user_notes: 用户手动添加的时间块备注
    - tasks: 今日重点内容
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
        # 1. 电脑使用时间
        if fetch_all or "pc_active_time" in fetch_options:
            pc_active_time = llm_lw_data_provider.get_pc_active_time(
                start_time=start_time,
                end_time=end_time,
            )
            if pc_active_time:
                prompt_parts.append(f"{section_num}. 电脑使用时间占比")
                prompt_parts.append(pc_active_time)
                section_num += 1

        # 2. 分段统计与分类占比（包含主要活动记录）
        if fetch_all or "behavior_stats" in fetch_options or "longest_activities" in fetch_options:
            # 获取分段统计数据
            segments_data = llm_lw_data_provider.get_segment_category_stats(
                start_time=start_time,
                end_time=end_time,
                segment_count=split_count
            )
            
            # 获取主要活动记录
            activities = llm_lw_data_provider.get_longest_activities(
                start_time=start_time,
                end_time=end_time,
                segment_count=split_count,
                top_percentage=0.1,
                max_count=5
            )
            
            # 将活动记录按时段索引组织
            activities_by_segment = {}
            if activities:
                for act in activities:
                    segment_index = act.get('segment_index', 1)
                    if segment_index not in activities_by_segment:
                        activities_by_segment[segment_index] = []
                    activities_by_segment[segment_index].append(act)
            
            if segments_data and activities_by_segment:
                prompt_parts.append(f"{section_num}. 分段活跃统计与分类占比")
                prompt_parts.append(_format_segment_category_stats(segments_data, activities_by_segment))
                section_num += 1
        
        # 3. 目标花费时间和趋势
        if fetch_all or "goal_time_spent" in fetch_options:
            goal_time = llm_lw_data_provider.get_goal_time_spent(
                start_time=start_time,
                end_time=end_time
            )
            if goal_time:
                prompt_parts.append(f"\n{section_num}. 目标时间投入")
                prompt_parts.append(_format_goal_time_spent(goal_time))
                section_num += 1
        
        # 4. 用户备注
        if fetch_all or "user_notes" in fetch_options:
            notes = llm_lw_data_provider.get_user_focus_notes(
                start_time=start_time,
                end_time=end_time
            )
            if notes:
                prompt_parts.append(f"\n{section_num}. 用户备注")
                prompt_parts.append(_format_user_notes(notes))
                section_num += 1
        
        # 5. 今日重点与任务
        if fetch_all or "tasks" in fetch_options:
            date = start_time.split(" ")[0]
            daily_todo_and_focus = llm_lw_data_provider.get_focus_and_todos(date=date)
            if daily_todo_and_focus:
                prompt_parts.append(f"\n{section_num}. 今日重点与任务")
                prompt_parts.append(_format_daily_summary(daily_todo_and_focus))
                section_num += 1

        return "\n".join(prompt_parts)
        
    except Exception as e:
        return f"获取用户行为统计失败: {str(e)}"
# 修改此处的option时需要同步修改
# lifeprism\llm\custom_prompt\chatbot_prompt\summary_prompt.py 中的
# multi_days_summary_template
@tool
def get_multi_days_stats(
    start_time: Annotated[str, "开始时间 YYYY-MM-DD HH:MM:SS"],
    end_time: Annotated[str, "结束时间 YYYY-MM-DD HH:MM:SS"],
    options: Annotated[list, "可选参数,goal_trend,tasks,category_trend,user_notes,usage_schedule,all"] = None
) -> str:
    """
    获取多天用户行为统计摘要数据，也可作为数据查询接口
    options: 可选参数列表
     - behavior_stats: 用户行为统计
     - goal_trend: 目标时间投入趋势
     - tasks: 每日重点与任务
     - category_trend: 不同分类投入时间趋势
     - user_notes: 用户备注
     - usage_schedule: 电脑使用时间分析（作息推断）
     - all: 返回全部
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
        if fetch_all or "behavior_stats" in fetch_options:
            behavior_stats = llm_lw_data_provider.get_segment_category_stats(start_time, end_time, segment_count=1,idle = False)
            prompt_parts.append(f"\n{section_num}. 用户行为统计")
            prompt_parts.append(_format_segment_category_stats(behavior_stats))
            logger.debug(f"behavior_stats: {len(prompt_parts[-1])}")
            section_num += 1

        # 1. 目标花费时间
        if fetch_all or "goal_trend" in fetch_options:
            goal_trend = llm_lw_data_provider.get_daily_goal_trend(start_time, end_time)
            prompt_parts.append(f"\n{section_num}. 在goal上花费的时间")
            prompt_parts.append(goal_trend if goal_trend else "  - 暂无数据")
            logger.debug(f"goal_trend: {len(prompt_parts[-1])}")
            section_num += 1
        

        # 2. 每日重点与任务
        if fetch_all or "tasks" in fetch_options:
            summary = llm_lw_data_provider.get_focus_and_todos(start_time=start_time, end_time=end_time)
            prompt_parts.append(f"\n{section_num}. 每日重点与任务")
            prompt_parts.append(summary if summary else "  - 暂无数据")
            logger.debug(f"summary: {len(prompt_parts[-1])}")
            section_num += 1
        
        # 3. 分类投入时间趋势
        if fetch_all or "category_trend" in fetch_options:
            category_trend = llm_lw_data_provider.get_daily_category_trend(start_time, end_time)
            prompt_parts.append(f"\n{section_num}. 分类占比")
            prompt_parts.append(category_trend if category_trend else "  - 暂无数据")
            logger.debug(f"category_trend: {len(prompt_parts[-1])}")
            section_num += 1
        
        # 4. 用户备注
        if fetch_all or "user_notes" in fetch_options:
            notes = llm_lw_data_provider.get_user_focus_notes(start_time, end_time)
            prompt_parts.append(f"\n{section_num}. 用户备注")
            prompt_parts.append(_format_user_notes(notes))
            logger.debug(f"notes: {len(prompt_parts[-1])}")
            section_num += 1
        
        # 5. 电脑使用时间分析（作息推断）
        if fetch_all or "usage_schedule" in fetch_options:
            # 从时间字符串中提取日期部分
            start_date = start_time.split()[0]  # YYYY-MM-DD
            end_date = end_time.split()[0]  # YYYY-MM-DD
            usage_schedule = llm_lw_data_provider.get_computer_usage_schedule(start_date, end_date)
            prompt_parts.append(f"\n{section_num}. 电脑使用时间分析（作息推断）")
            if usage_schedule:
                # 增加缩进，使输出整齐
                lines = usage_schedule.strip().split('\n')
                formatted_schedule = "\n".join([f"  {line}" for line in lines])
                prompt_parts.append(formatted_schedule)
                logger.debug(f"usage_schedule: {len(prompt_parts[-1])}")
            else:
                prompt_parts.append("  - 暂无数据")
            section_num += 1
        
        return "\n".join(prompt_parts)
        
    except Exception as e:
        return f"获取用户行为统计失败: {str(e)}"

if __name__ == "__main__":
    result = get_daily_stats.invoke(
        input = {
            "start_time": "2025-12-30 00:00:00",
            "end_time": "2025-12-30 23:59:59",
            "split_count": 2,
            "options": ["all"]
        }
    )
    print(result)
    result = get_multi_days_stats.invoke(
        input = {
            "start_time": "2025-11-01 00:00:00",
            "end_time": "2025-12-01 00:00:00",
            "options": ["all"]
        }
    )
    print(result)
    summary = llm_lw_data_provider.get_focus_and_todos(start_time="2025-11-01 00:00:00", end_time="2025-12-01 00:00:00")
    print(summary)
