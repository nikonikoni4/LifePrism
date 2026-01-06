"""
数据库相关的 LLM 工具
原则：查询功能应该能够解决一个业务问题，而不是分散的让llm查询
"""
from typing import Annotated,Optional,List,Dict
from langchain.tools import tool
from lifeprism.llm.llm_classify.providers.llm_lw_data_provider import llm_lw_data_provider
from lifeprism.llm.llm_classify.utils.data_base_format import(
     _format_seconds,
     _format_segment_category_stats,
     _format_longest_activities,
     _format_goal_time_spent,
     _format_user_notes,
     _format_daily_summary,
     format_behavior_logs_lines
)
from lifeprism.utils import get_logger,DEBUG
logger = get_logger(__name__,DEBUG)

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


# ================================================
# 新工具
# ================================================

@tool
def query_behavior_logs(
    start_time: str,
    end_time: str,
    limit: Optional[int] = 10,
    order_by: str = "duration DESC"
) -> List[Dict]:
    """
    查询用户行为日志，获取指定时间范围内的应用使用记录。当需要仔细了解某个时间段的活动时，可以使用此工具。
    注意：一条电脑行为通常较短，一个小时内可能会产生大量数据，谨慎选择感兴趣的时间段调用分析。
    Args:
        start_time: 开始时间，格式 YYYY-MM-DD HH:MM:SS
        end_time: 结束时间，格式 YYYY-MM-DD HH:MM:SS
        limit: 返回记录数限制，默认10条，最大20条
        order_by: 排序方式，默认按时长降序 "duration DESC"
    返回示例:
        22:27 ~ 22:28 (1m) antigravity - lifewatch-ai - antigravity - llm_lw_data_provider.py [工作/学习/编程] {完成lifewatch项目}
    """
    return format_behavior_logs_lines(llm_lw_data_provider.query_behavior_logs(
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        order_by=order_by
    ))



@tool
def query_goals() -> List[Dict]:
    """
    查询用户设置的目标。
    Returns:
        目标列表
    """
    return llm_lw_data_provider.query_goals()


@tool
def query_psychological_assessment() -> List[Dict]:
    """
    查询用户的心理测评数据（过去/现在/未来的自我探索）。
    
    Returns:
        心理测评结果列表，每条记录包含:
        - mode: 模式 (past/present/future)
        - mode_name: 模式中文名称 (我曾经是谁/我现在是谁/我要成为什么样的人)
        - ai_abstract: AI总结内容
    """ 
    return llm_lw_data_provider.query_time_paradoxes()






if __name__ == "__main__":
    # result = get_daily_stats.invoke(
    #     input = {
    #         "start_time": "2025-12-30 00:00:00",
    #         "end_time": "2025-12-30 23:59:59",
    #         "split_count": 2,
    #         "options": ["all"]
    #     }
    # )
    # print(result)
    # result = get_multi_days_stats.invoke(
    #     input = {
    #         "start_time": "2025-11-01 00:00:00",
    #         "end_time": "2025-12-01 00:00:00",
    #         "options": ["all"]
    #     }
    # )
    # print(result)
    # summary = llm_lw_data_provider.get_focus_and_todos(start_time="2025-11-01 00:00:00", end_time="2025-12-01 00:00:00")
    # print(summary)

    print(query_behavior_logs.invoke(
        input = {
            "start_time": "2026-01-05 00:00:00",
            "end_time": "2026-01-05 23:59:59",
            "limit": 5
        }
    ))
