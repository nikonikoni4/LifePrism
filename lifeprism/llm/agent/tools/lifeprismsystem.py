from dataclasses import field
from typing import Any

from lifeprism.llm.agent.tools.base import Tool
from lifeprism.repository import (
    todo_repository,
    goal_repository,
    behavior_analysis_repository,
    custom_block_repository,
    computer_usage_repository,
    QueryOptions
)
from lifeprism.llm.utils import build_time_segments
# 数据
## 类型1：用户行为数据
# 1. 电脑使用分类数据 -> user_app_behavior_log  通常不直接使用这个，只是作为小范围的数据精细补充查询
# 2. 电脑使用分类统计数据 -> user_app_behavior_log的统计数据
# 3. 用户行为备注 -> timeline_custom_block 用户对于某个时间所做的事情的自定义备注
# 4. AI行为分析 -> behavior_analysis 对于某段时间的截图分析，由AI经过截图分析，不一定准确
## 类型2：习惯数据
# 1. 当前打算养成的习惯 -> habits，习惯描述
# 2. 习惯统计 -> 习惯的等级，历史进度，当前的打卡情况
# 3. 当前理想的习惯时间链条

## 类型3 目标数据
# 1. 激活的目标，以及目标描述
# 2. todolist查询

## 类型4 心情数据
# 1. 当前的心情 -> mood，心情描述

# 按照参数类似性进行分类
# 1. 输入是时间范围的查询数据 ： 电脑使用分类数据 ；电脑使用分类统计数据 ；用户行为备注 ；AI行为分析

# 问题： 需不需要增加除时间范围以外的筛选条件？ ： 
# 1. 需要 ： 可以精细化筛选，比如心情，只看心情糟糕的（但是心情还没有实际投入使用）。这个目前看来按照筛选条件来用，频率似乎不是很多
# 电脑使用分类数据 按照类别来查询？ 没有必要，这个单独的查询作用都不是很大
# 按照时长？ 这个有一点作用 但是统计数据里面已经有这个了，统计数据给出高密度时间段，以及这个时间段的分类和每个分类最高的app title使用时间
# 决定暂时不使用除时间范围以外的筛选条件，应该就给这个然后看看其效果如果，不行之后在增加其他的
# 先全部写在一个

# 习惯养成暂时先不查询
class LifeprismDataQueryTool(Tool):
    """数据查询工具"""
    def __init__(self):
        pass 

    @property
    def name(self) -> str:
        """函数调用中使用的工具名。"""
        return "lifeprism_data_query"

    @property
    def description(self) -> str:
        """工具功能说明。"""
        return "查询 LifePrism 系统中的数据，包括电脑使用数据，用户自定义行为备注，AI行为备注，目标数据，todolist"

    @property
    def parameters(self) -> dict[str, Any]:
        """工具参数的 JSON Schema"""
        return {
            "type": "object",
            "properties": {
                "query_option": {
                    "type": "array",
                    "description": "查询选项列表",
                    "items": {
                        "type": "string",
                        "enum": ["computer_usage_stats", "user_behavior_notes", "ai_behavior_notes",  "todolist"]# "goals",
                    },
                    "minItems": 1
                },
                "start_time": {
                    "type": "string",
                    "description": "查询开始时间，格式：YYYY-MM-DD HH:MM:SS"
                },
                "end_time": {
                    "type": "string",
                    "description": "查询结束时间，格式：YYYY-MM-DD HH:MM:SS"
                }
            },
            "required": ["query_option", "start_time", "end_time"]
        }

    async def execute(self, **kwargs: Any) -> Any:
        """
        使用给定参数执行工具

        参数:
            **kwargs: 工具特有参数

        返回:
            工具执行结果（字符串或内容块列表）
        """
        try:
            query_option = set(kwargs.get('query_option', []))
            start_time = kwargs.get('start_time', '')
            end_time = kwargs.get('end_time', '')

            return query_data(query_option, start_time, end_time)
        except ValueError as e:
            return f"参数错误: {str(e)}"
        except Exception as e:
            return f"查询失败: {str(e)}"
def _category_stats(logs: list[dict], segment_start_time: str, segment_end_time: str) -> dict:
    """
    计算某段时间内的分类占比（如果某个log的区间在边界，会依据边界截断）

    Args:
        logs: 电脑使用数据（包含start_time, end_time, duration, category_name）
        segment_start_time: 分析开始时间 YYYY-MM-DD HH:MM:SS
        segment_end_time: 分析结束时间 YYYY-MM-DD HH:MM:SS

    Returns:
        dict: {'category_name': percentage, ...}
    """
    from datetime import datetime

    segment_start = datetime.fromisoformat(segment_start_time.replace(' ', 'T'))
    segment_end = datetime.fromisoformat(segment_end_time.replace(' ', 'T'))

    category_durations = {}
    total_duration = 0

    for log in logs:
        log_start = datetime.fromisoformat(log['start_time'].replace(' ', 'T'))
        log_end = datetime.fromisoformat(log['end_time'].replace(' ', 'T'))

        # 截断到边界
        actual_start = max(log_start, segment_start)
        actual_end = min(log_end, segment_end)

        if actual_start >= actual_end:
            continue

        duration = (actual_end - actual_start).total_seconds()
        category = log.get('category_name', '未分类')

        category_durations[category] = category_durations.get(category, 0) + duration
        total_duration += duration

    if total_duration == 0:
        return {}

    return {cat: (dur / total_duration * 100) for cat, dur in category_durations.items()}

def query_data(query_option: set[str],start_time: str,end_time: str) -> str:
    """查询 LifePrism 系统中的数据
    args :
        query_option: list
            查询选项:
                computer_usage_stats,
                user_behavior_notes,
                ai_behavior_notes,
                # goals,
                todolist

        start_time: 查询开始时间 YYYY-MM-DD HH:MM:SS
        end_time: 查询结束时间 YYYY-MM-DD HH:MM:SS
    return
        str 返回格式化数据
    """
    # 参数校验
    from datetime import datetime

    allowed_options = {"computer_usage", "computer_usage_stats", "user_behavior_notes", "ai_behavior_notes", "todolist"} # , "goals"
    invalid_options = set(query_option) - allowed_options
    if invalid_options:
        raise ValueError(f"Invalid query options: {invalid_options}")

    try:
        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        raise ValueError(f"Invalid time format. Expected 'YYYY-MM-DD HH:MM:SS': {e}")

    if start_dt >= end_dt:
        raise ValueError("start_time must be before end_time")

    parts = []

    
    if 'computer_usage_stats' in query_option:
        app_log, _ = computer_usage_repository.query_computer_usage_with_names(
            QueryOptions(fields=['start_time', 'end_time', 'app', 'title', 'duration', 'category_id', 'sub_category_id']).with_time_range(start_time, end_time)
        )
        if not app_log:
            parts.append("## 电脑使用统计 \n 该时间段没有电脑使用记录")
        else:
            # 计算高密度时间段
            usage_time_segments: list[dict] = build_time_segments(app_log, start_time, end_time, 0.6, 6)

            content = "## 电脑使用统计\n"
            for idx, segment in enumerate(usage_time_segments, 1):
                # 计算每个时间段内的分类占比
                category_stats = _category_stats(app_log, segment['start'], segment['end'])

                content += f"### 时间段 {idx}: {segment['start']} ~ {segment['end']}\n"
                content += f"持续时长: {segment['duration_seconds'] // 60} 分钟\n"
                content += "分类占比:\n"
                for category, percentage in sorted(category_stats.items(), key=lambda x: x[1], reverse=True):
                    content += f"  - {category}: {percentage:.1f}%\n"

            parts.append(content)
    if 'user_behavior_notes' in query_option:
        custom_blocks, _ = custom_block_repository.query_custom_blocks(QueryOptions(fields=['start_time', 'end_time', 'content']).with_time_range(start_time, end_time))
        if not custom_blocks:
            parts.append("## 用户自定义行为备注 \n 用户自定义行为备注为空")
        else:
            content = "## 用户自定义行为备注\n"
            for i in range(len(custom_blocks)):
                content += f"{i}. {custom_blocks[i]['start_time']}~{custom_blocks[i]['end_time']} : {custom_blocks[i]['content']}\n"
            parts.append(content)
    if 'ai_behavior_notes' in query_option:
        behaviors, _ = behavior_analysis_repository.query_behaviors(QueryOptions(fields=['start_time', 'end_time', 'behavior_summary']).with_time_range(start_time, end_time))
        if not behaviors:
            parts.append("## AI分析行为备注 \n AI分析行为备注为空")
        else:
            content = "## AI分析行为备注\n"
            for i in range(len(behaviors)):
                content += f"{i}. {behaviors[i]['start_time']}~{behaviors[i]['end_time']} : {behaviors[i]['behavior_summary']}\n"
            parts.append(content)
    # if 'goals' in query_option:
    #     goals,_= goal_repository.query_goals(QueryOptions(fields=['name','content'],filters={'status':'active'}))
    #     if not goals :
    #         parts.append("## 用户目标 \n 用户目标为空")
    #     else:
    #         content = "## 用户目标\n"
            
    #         for i in range(len(goals)):
    #             description = ""
    #             if goals[i]['content']:
    #                 description = f"描述：{goals[i]['content']}"
    #             content += f"{i}. {goals[i]['name']},{description}\n"
    #         parts.append(content)
    if 'todolist' in query_option:
        todolists, _ = todo_repository.query_todos(QueryOptions(fields=['content', 'date']).with_date_range(start_time[:10], end_time[:10]))
        if not todolists:
            parts.append("## 用户待办事项 \n 用户待办事项为空")
        else:
            from collections import defaultdict
            by_date = defaultdict(list)
            for todo in todolists:
                by_date[todo['date']].append(todo['content'])
            content = "## 用户待办事项\n"
            for date in sorted(by_date.keys()):
                content += f"### {date}\n"
                for idx, item in enumerate(by_date[date], 1):
                    content += f"{idx}. {item}\n"
            parts.append(content)
    return "\n".join(parts)


if __name__ == "__main__":
    print(query_data(['computer_usage_stats'],"2026-04-28 00:00:00","2026-04-29 00:00:00"))