from lifeprism.llm.llm_classify.new_type.provider import DataProvider
from langchain_core.tools import tool
from typing import Optional, List, Dict

# 初始化数据提供者
data_provider = DataProvider()


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
def format_hourly_logs(hourly_logs):
    """
    格式化按小时分段的活动日志
    
    Args:
        hourly_logs: get_logs_by_time 返回的字典数据
    
    Returns:
        str: 格式化后的文本
    """
    if not hourly_logs:
        return "今日暂无活动记录"
    
    output_lines = []
    
    for hour_key in sorted(hourly_logs.keys()):
        hour_data = hourly_logs[hour_key]
        logs = hour_data.get('logs', [])
        category_stats = hour_data.get('category_stats', [])
        
        # 格式化分类统计
        category_parts = []
        for cat in category_stats:
            cat_name = cat.get('name', '未分类')
            duration_min = cat.get('duration', 0) // 60
            category_parts.append(f"{cat_name}({duration_min}m)")
        
        category_str = "，".join(category_parts) if category_parts else "无分类"
        
        # 输出时间段和分类统计
        output_lines.append(f"\n{hour_key}: {category_str}")
        
        # 输出详细日志
        for i, log in enumerate(logs, 1):
            duration_min = log.get('duration', 0) // 60
            app = log.get('app', 'Unknown')
            title = log.get('title', '')
            
            # 格式化输出
            if title:
                output_lines.append(f"  {i}. [{duration_min}分钟] {app} - {title}")
            else:
                output_lines.append(f"  {i}. [{duration_min}分钟] {app}")
    
    return "\n".join(output_lines)
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
    
    Returns:
        行为日志列表，每条记录包含:
        - start_time: 开始时间
        - end_time: 结束时间
        - duration: 持续时间(秒)
        - app: 应用名称
        - title: 窗口标题
        - category_name: 主分类名称
        - sub_category_name: 子分类名称
        - goal_name: 关联的目标名称
    
    示例:
        query_behavior_logs("2026-01-05 00:00:00", "2026-01-05 23:59:59", limit=5)
    """
    return data_provider.query_behavior_logs(
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        order_by=order_by
    )


# @tool
# def query_todos(date: str) -> List[Dict]:
#     """
#     查询指定日期的待办事项（排除任务池中的 inactive 状态）。
    
#     Args:
#         date: 日期，格式 YYYY-MM-DD，例如 "2026-01-05"
    
#     Returns:
#         待办事项列表，每条记录包含:
#         - id: 待办事项ID
#         - content: 待办内容
#         - state: 状态 (active/completed)
#         - goal_name: 关联的目标名称
    
#     示例:
#         query_todos("2026-01-05")
#     """
#     return data_provider.query_todos(date=date)


@tool
def query_goals() -> List[Dict]:
    """
    查询所有目标信息。
    
    Returns:
        目标列表，每条记录包含:
        - id: 目标ID
        - name: 目标名称
        - status: 状态 (active/completed/archived)
    
    示例:
        query_goals()
    """
    return data_provider.query_goals()


@tool
def query_time_paradoxes() -> List[Dict]:
    """
    查询用户的时间悖论测试结果（过去/现在/未来的自我探索）。

    
    Returns:
        时间悖论测试结果列表，每条记录包含:
        - mode: 模式 (past/present/future)
        - mode_name: 模式中文名称 (我曾经是谁/我现在是谁/我要成为什么样的人)
        - ai_abstract: AI总结内容
    """
    return data_provider.query_time_paradoxes()


@tool
def get_logs_by_time(date: str) -> Dict[str, Dict]:
    """
    按时间段（每小时）获取活动日志。
    每个小时内筛选时长大于1分钟的日志，按时长降序排序，最多返回3条。
    同时返回该小时的分类统计信息。
    Args:
        date: 日期，格式 YYYY-MM-DD，例如 "2026-01-05"
    Returns:
        按小时分组的日志数据，格式:
        20:00-21:00: 工作/学习(23m)，其他(1m)
            1. [4分钟] antigravity - lifewatch-ai - antigravity - database.py●
    示例:
        get_logs_by_time("2026-01-05")
    """
    hourly_logs = data_provider.get_logs_by_time(date=date)
    formatted_logs = format_hourly_logs(hourly_logs)
    return formatted_logs


@tool
def get_user_focus_notes(start_time: str, end_time: str) -> List[Dict]:
    """
    获取用户手动添加的时间块备注（非电脑活动记录）。
    Args:
        start_time: 开始时间，格式 YYYY-MM-DD HH:MM:SS
        end_time: 结束时间，格式 YYYY-MM-DD HH:MM:SS
    Returns:
        格式化后的用户备注文本：
          - [2026-01-02T00:10:00 ~ 2026-01-02T02:10:00]（120分钟）: 完成reward界面
    示例:
        get_user_focus_notes("2026-01-05 00:00:00", "2026-01-05 23:59:59")
    """
    custom_block = data_provider.get_user_focus_notes(start_time=start_time, end_time=end_time)
    return _format_user_notes(custom_block)

