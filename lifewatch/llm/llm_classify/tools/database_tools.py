"""
数据库相关的 LLM 工具
原则：查询功能应该能够解决一个业务问题，而不是分散的让llm查询
"""
from typing import Annotated
from langchain.tools import tool

from lifewatch.llm.llm_classify.providers.llm_lw_data_provider import llm_lw_data_provider


@tool
def get_user_behavior_stats(
    start_time: Annotated[str, "开始时间 YYYY-MM-DD HH:MM:SS"],
    end_time: Annotated[str, "结束时间 YYYY-MM-DD HH:MM:SS"],
    split_count: Annotated[int, "切分时间段,把时间分成n个时间段,以获得更加详细的行为统计,长时段split_count应该更大,短时段split_count应该更小"],
    goal_id: Annotated[str, "目标ID,可选,不传则返回所有目标"] = None,
    options: Annotated[list, "可选参数,stats,category_distribution,longest_activities,goal_time_spent,user_notes,all"] = None
) -> dict:
    """
    获取时间段小于24h的用户行为统计摘要数据
    
    返回指定时间段内的完整统计：
    - stats: 各时段的活跃/空闲统计
    - category_distribution: 主分类和子分类的占比
    - longest_activities: 各时段内最长的活动记录
    - goal_time_spent: 各目标花费的时间
    - user_notes: 用户的日/周焦点备注
    """
    try:
        # 解析 options，默认返回全部
        if options is None or "all" in options:
            fetch_all = True
            fetch_options = set()
        else:
            fetch_all = False
            fetch_options = set(options)
        
        data = {}
        
        # 1. 分段统计
        if fetch_all or "stats" in fetch_options:
            data["stats"] = llm_lw_data_provider.get_stats_by_time_segments(
                start_time=start_time,
                end_time=end_time,
                segment_count=split_count
            )
        
        # 2. 分类占比
        if fetch_all or "category_distribution" in fetch_options:
            data["category_distribution"] = llm_lw_data_provider.get_category_distribution(
                start_time=start_time,
                end_time=end_time
            )
        
        # 3. 最长活动
        if fetch_all or "longest_activities" in fetch_options:
            data["longest_activities"] = llm_lw_data_provider.get_longest_activities(
                start_time=start_time,
                end_time=end_time,
                segment_count=split_count,
                top_percentage=0.1,
                max_count=5
            )
        
        # 4. 目标花费时间
        if fetch_all or "goal_time_spent" in fetch_options:
            data["goal_time_spent"] = llm_lw_data_provider.get_goal_time_spent(
                start_time=start_time,
                end_time=end_time,
                goal_id=goal_id
            )
        
        # 5. 用户备注
        if fetch_all or "user_notes" in fetch_options:
            data["user_notes"] = llm_lw_data_provider.get_user_focus_notes(
                start_time=start_time,
                end_time=end_time
            )
        
        return {
            "success": True,
            "data": data
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
