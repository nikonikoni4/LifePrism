from dataclasses import field
import json
from typing import Any

from lifeprism.llm.agent.tools.base import Tool,ERROR
from lifeprism.repository import (
    todo_repository,
    goal_repository,
    behavior_analysis_repository,
    custom_block_repository,
    computer_usage_repository,
    QueryOptions,
    mood_repository
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
class UserActivitySummaryTool(Tool):
    """数据查询工具"""
    def __init__(self):
        pass 

    @property
    def name(self) -> str:
        """函数调用中使用的工具名。"""
        return "query_user_activity_summary"

    @property
    def description(self) -> str:
        """工具功能说明。"""
        
        return """查询lifeprism系统中用户的行为活动数据，包括
        1. computer_usage_stats ： 电脑使用的高频时段和该时段内的分类统计数据。
        2. user_behavior_notes ： 用户对于某段时间的自定义行为备注，是了解用户行为最直接的数据。
        3. ai_behavior_notes ： AI对于某段时间的截图分析，由AI经过截图分析，不一定准确，仅供参考。
        4. todolist ： 用户在这段时间内的任务列表。
        """
        

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

            return query_user_activity_summary(query_option, start_time, end_time)
        except ValueError as e:
            return f"{ERROR}参数错误: {str(e)}"
        except Exception as e:
            return f"{ERROR}查询失败: {str(e)}"
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

def query_user_activity_summary(query_option: set[str],start_time: str,end_time: str) -> str:
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
        raise ValueError(f"{ERROR} Invalid query options: {invalid_options}")

    try:
        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        raise ValueError(f"{ERROR} Invalid time format. Expected 'YYYY-MM-DD HH:MM:SS': {e}")

    if start_dt >= end_dt:
        raise ValueError(f"{ERROR} start_time must be before end_time")

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
        custom_blocks, _ = custom_block_repository.query_custom_blocks(QueryOptions(fields=['id','start_time', 'end_time', 'content']).with_time_range(start_time, end_time))
        if not custom_blocks:
            parts.append("## 用户自定义行为备注 \n 用户自定义行为备注为空")
        else:
            content = "## 用户自定义行为备注\n"
            for i in range(len(custom_blocks)):
                content += f"{i}. 'block_id': {custom_blocks[i]['id']}, {custom_blocks[i]['start_time']}~{custom_blocks[i]['end_time']} : {custom_blocks[i]['content']}\n"
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

class UserComputerLogTool(Tool):
    """用户电脑使用日志工具"""
    def __init__(self):
        pass

    @property
    def name(self) -> str:
        """函数调用中使用的工具名。"""
        return "query_user_activity_log"

    @property
    def description(self) -> str:
        """工具功能说明。"""
        return """查询用户电脑使用的详细日志，返回格式化的活动记录。
        适用场景：需要查看用户在某个时间段内具体使用了哪些应用、窗口标题、使用时长等详细信息。
        """

    @property
    def parameters(self) -> dict[str, Any]:
        """工具参数的 JSON Schema"""
        return {
            "type": "object",
            "properties": {
                "start_time": {
                    "type": "string",
                    "description": "查询开始时间，格式：YYYY-MM-DD HH:MM:SS"
                },
                "end_time": {
                    "type": "string",
                    "description": "查询结束时间，格式：YYYY-MM-DD HH:MM:SS"
                },
                "duration_min": {
                    "type": "integer",
                    "description": "最小持续时长（秒），只返回持续时长大于等于此值的记录，默认45秒",
                    "default": 45
                }
            },
            "required": ["start_time", "end_time"]
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
            start_time = kwargs.get('start_time', '')
            end_time = kwargs.get('end_time', '')
            duration_min = kwargs.get('duration_min', 45)
            if not start_time or not end_time:
                return f"{ERROR}参数错误: start_time 和 end_time 是必填参数"
            if not duration_min:
                duration_min = 45
            return query_user_activity_log(start_time, end_time, duration_min)
        except ValueError as e:
            return f"{ERROR}参数错误: {str(e)}"
        except Exception as e:
            return f"{ERROR}查询失败: {str(e)}"



def _format_duration(seconds: int) -> str:
    """将秒数格式化为可读的时长字符串

    Args:
        seconds: 持续时长（秒）

    Returns:
        str: 格式化后的时长，如 "1小时5分30秒"、"5分30秒"、"30秒"
    """
    if seconds < 60:
        return f"{seconds}秒"

    minutes = seconds // 60
    remaining_seconds = seconds % 60

    if minutes < 60:
        if remaining_seconds > 0:
            return f"{minutes}分{remaining_seconds}秒"
        return f"{minutes}分"

    hours = minutes // 60
    remaining_minutes = minutes % 60

    if remaining_minutes > 0 and remaining_seconds > 0:
        return f"{hours}小时{remaining_minutes}分{remaining_seconds}秒"
    elif remaining_minutes > 0:
        return f"{hours}小时{remaining_minutes}分"
    elif remaining_seconds > 0:
        return f"{hours}小时{remaining_seconds}秒"
    return f"{hours}小时"


def query_user_activity_log(start_time: str, end_time: str, duration_min: int = 45) -> str:
    """查询用户电脑使用的详细日志

    Args:
        start_time: 查询开始时间 YYYY-MM-DD HH:MM:SS
        end_time: 查询结束时间 YYYY-MM-DD HH:MM:SS
        duration_min: 最小持续时长（秒），只返回持续时长大于等于此值的记录，默认45秒

    Returns:
        str: 格式化的活动日志，每行格式为 "start_time ~ end_time app title duration category_name"
    """
    MAX_LEN = 40
    result = f"[日志查询说明] 查询结果屏蔽了持续时间小于{duration_min}秒的记录。\n\n"

    app_log, _ = computer_usage_repository.query_computer_usage_with_names(
        QueryOptions(fields=['start_time', 'end_time', 'app', 'title', 'duration', 'category_id']).with_time_range(start_time, end_time)
    )

    # 时长过滤
    app_log = [log for log in app_log if log.get('duration', 0) >= duration_min]

    if not app_log:
        return f"该时间段内没有持续时长大于等于{duration_min}秒的电脑使用记录。"

    if len(app_log) > MAX_LEN:
        total_log = len(app_log)
        app_log = app_log[:MAX_LEN]
        result += f"注意：当前搜索区间过大，共{total_log}条记录，仅展示前{MAX_LEN}条记录。展示的时间范围为：{app_log[0]['start_time']} ~ {app_log[-1]['end_time']}。\n\n"

    result += "查询结果：\n"
    # 解析输出
    for log in app_log:
        start = log.get('start_time', '')
        end = log.get('end_time', '')
        app = log.get('app', '未知应用')
        title = log.get('title', '无标题')
        duration_sec = log.get('duration', 0)
        category = log.get('category_name', '未分类')

        # 格式化持续时长
        duration_str = _format_duration(duration_sec)

        result += f"{start} ~ {end} {app} {title} {duration_str} {category}\n"

    return result.strip()


def create_or_update_user_behavior_note(
    start_time: str,
    end_time: str,
    content: str,
    block_id: int | None = None
) -> str:
    """创建或更新用户行为备注

    Args:
        start_time: 开始时间 YYYY-MM-DD HH:MM:SS
        end_time: 结束时间 YYYY-MM-DD HH:MM:SS
        content: 备注内容
        block_id: 可选，时间块 ID。如果提供则更新，否则创建

    Returns:
        str: 操作结果描述

    Raises:
        ValueError: 时间格式错误或时间范围无效
    """
    from datetime import datetime

    # 参数校验
    try:
        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        raise ValueError(f"{ERROR} 时间格式错误，期望格式为 'YYYY-MM-DD HH:MM:SS': {e}")

    if start_dt >= end_dt:
        raise ValueError(f"{ERROR} 开始时间必须早于结束时间")

    # 计算 duration（分钟）
    duration = int((end_dt - start_dt).total_seconds() / 60)

    # 硬编码 color
    color = "#bfdbfe"

    # 构建数据
    data = {
        "start_time": start_time,
        "end_time": end_time,
        "content": content,
        "duration": duration,
        "color": color
    }

    try:
        if block_id is not None:
            # 更新模式
            result = custom_block_repository.update_custom_block(block_id, data)
            if result:
                return f"成功更新行为备注 (ID: {block_id})\n时间段: {start_time} ~ {end_time}\n内容: {content}\n时长: {duration} 分钟"
            else:
                return f"更新失败: 未找到 ID 为 {block_id} 的记录"
        else:
            # 创建模式
            result = custom_block_repository.create_custom_block(data)
            if result:
                new_id = result.get('id', '未知')
                return f"成功创建行为备注 (ID: {new_id})\n时间段: {start_time} ~ {end_time}\n内容: {content}\n时长: {duration} 分钟"
            else:
                return "创建失败: 未知错误"
    except Exception as e:
        raise Exception(f"数据库操作失败: {str(e)}")


class UpdateUserBehaviorNoteTool(Tool):
    """创建或更新用户行为备注工具"""
    def __init__(self):
        pass

    @property
    def name(self) -> str:
        """函数调用中使用的工具名。"""
        return "create_or_update_user_behavior_note"

    @property
    def description(self) -> str:
        """工具功能说明。"""
        return """创建或更新用户对某段时间的自定义行为备注。
        适用场景：用户想要记录或修改某个时间段内做了什么事情。
        如果提供 block_id 则更新现有记录，block_id可通过query_user_activity_summary工具获取。
               """

    @property
    def parameters(self) -> dict[str, Any]:
        """工具参数的 JSON Schema"""
        return {
            "type": "object",
            "properties": {
                "start_time": {
                    "type": "string",
                    "description": "开始时间，格式：YYYY-MM-DD HH:MM:SS"
                },
                "end_time": {
                    "type": "string",
                    "description": "结束时间，格式：YYYY-MM-DD HH:MM:SS"
                },
                "content": {
                    "type": "string",
                    "description": "行为备注内容"
                },
                "block_id": {
                    "type": "integer",
                    "description": "可选，时间块 ID。如果提供则更新现有记录，否则创建新记录。 可以通过query_user_activity_summary工具获取。"
                }
            },
            "required": ["start_time", "end_time", "content"]
        }

    async def execute(self, **kwargs: Any) -> Any:
        """
        使用给定参数执行工具

        参数:
            **kwargs: 工具特有参数
                - start_time: 开始时间
                - end_time: 结束时间
                - content: 备注内容
                - block_id: 可选，用于更新

        返回:
            工具执行结果（字符串）
        """
        try:
            start_time = kwargs.get('start_time', '')
            end_time = kwargs.get('end_time', '')
            content = kwargs.get('content', '')
            block_id = kwargs.get('block_id')

            if not start_time or not end_time or not content:
                return f"{ERROR} 参数错误: start_time、end_time 和 content 是必填参数"

            return create_or_update_user_behavior_note(
                start_time=start_time,
                end_time=end_time,
                content=content,
                block_id=block_id
            )
        except ValueError as e:
            return f"{ERROR} 参数错误: {str(e)}"
        except Exception as e:
            return f"{ERROR} 操作失败: {str(e)}"


def _get_mood_type_ids()->list[str]:
    """获取所有可用的心情类型ID"""
    mood_types = mood_repository.get_mood_types()
    return [m['id'] for m in mood_types]

def _get_mood_types()->str:
    """获取所有可用的心情类型,输出id:name对"""
    mood_types = mood_repository.get_mood_types()
    return '\n '.join([f"{m['id']}: {m['name']}" for m in mood_types])

class UserMoodQuryTool(Tool):
    """查询用户心情记录工具"""
    def __init__(self):
        pass

    @property
    def name(self) -> str:
        """函数调用中使用的工具名。"""
        return "query_user_mood"

    @property
    def description(self) -> str:
        """工具功能说明。"""
        return """查询用户在指定时间范围内的心情记录，包括心情评分、内容和影响因素。
        返回格式化的心情记录列表，便于用户查看和分析心情变化趋势。"""

    @property
    def parameters(self) -> dict[str, Any]:
        """工具参数的 JSON Schema"""
        return {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "查询开始日期，格式：YYYY-MM-DD"
                },
                "end_date": {
                    "type": "string",
                    "description": "查询结束日期，格式：YYYY-MM-DD"
                },
                "by_mood_type_id": {
                    "type": ["string", "null"],
                    "description": f"可选，按心情类型ID过滤，可使用的心情ID类型以及心情名称对(id:name): \n {_get_mood_types()}",
                    "enum": _get_mood_type_ids()
                }
            },
            "required": ["start_date", "end_date"]
        }


    async def execute(self, **kwargs: Any) -> Any:
        """
        使用给定参数执行工具

        参数:
            **kwargs: 工具特有参数

        返回:
            格式化的心情记录字符串
        """
        try:
            start_date = kwargs.get('start_date', '')
            end_date = kwargs.get('end_date', '')
            by_mood_type_id = kwargs.get('by_mood_type_id', None)

            return query_user_mood(start_date, end_date, by_mood_type_id)
        except ValueError as e:
            return f"{ERROR}参数错误: {str(e)}"
        except Exception as e:
            return f"{ERROR}查询失败: {str(e)}"

def query_user_mood(start_date:str,end_date:str,by_mood_type_id:str|None=None)->list[dict[str,Any]]:
    """
    查询用户在指定时间范围内的心情记录。
    args:
        start_date: 开始时间，格式：YYYY-MM-DD
        end_date: 结束时间，格式：YYYY-MM-DD
        by_mood_type_id: 可选，心情类型ID，按心情类型查询
    return:
        心情记录列表
    """
    mood_entries:list[dict]= mood_repository.get_mood_entries(start_date=start_date,end_date=end_date)
    result = []
    if by_mood_type_id:
        for mood_entry in mood_entries:
            if mood_entry['mood_type_id'] == by_mood_type_id:
                result.append(mood_entry)
    else:
        result = mood_entries
    if not result:
        return f"{start_date}~{end_date}  无{by_mood_type_id}对应心情记录" if by_mood_type_id else f"{start_date}~{end_date}  无心情记录"
    formatted_result = []
    for idx, entry in enumerate(result, 1):
        factors_raw = entry.get('factors', '')
        if factors_raw:
            try:
                factors_list = json.loads(factors_raw) if isinstance(factors_raw, str) else factors_raw
                factors_str = ', '.join(factors_list) if isinstance(factors_list, list) else str(factors_list)
            except (json.JSONDecodeError, TypeError):
                factors_str = str(factors_raw)
        else:
            factors_str = ''
        formatted_result.append(
            f"{idx}. {entry.get('created_at', 'N/A')} 心情: {entry.get('score', 'N/A')}分\n"
            f"   内容：{entry.get('content', '无') or '无'}\n"
            f"   影响因素: {factors_str if factors_str else '无'}"
        )
    return '\n\n'.join(formatted_result)


class UserMoodCreateTool(Tool):
    """创建用户心情记录工具"""
    def __init__(self):
        pass

    @property
    def name(self) -> str:
        """函数调用中使用的工具名。"""
        return "create_user_mood"

    @property
    def description(self) -> str:
        """工具功能说明。"""
        return """创建用户心情记录，包括心情评分、内容和影响因素。
        返回创建的记录ID，便于用户查看和管理心情记录。"""

    @property
    def parameters(self) -> dict[str, Any]:
        """工具参数的 JSON Schema"""
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "心情记录内容，描述当前的心情感受"
                },
                "mood_type_id": {
                    "type": "string",
                    "description": f"可选，按心情类型ID过滤，可使用的心情ID类型以及心情名称对(id:name): \n {_get_mood_types()}",
                    "enum": _get_mood_type_ids()
                },
                "factors": {
                    "type": "array",
                    "description": "可选，可多选，影响心情的因素列表",
                    "items": {
                        "type": "string",
                        "enum": self._get_factors()
                        }
                }
            },
            "required": ["content", "mood_type_id"]
        }

    @staticmethod
    def _get_factors()->list[str]:
        """获取所有可用的影响因素，返回逗号分隔的字符串"""
        impacts = mood_repository.get_mood_impacts()
        return [imp['name'] for imp in impacts]

    async def execute(self, **kwargs: Any) -> Any:
        """
        使用给定参数执行工具

        参数:
            **kwargs: 工具特有参数

        返回:
            创建结果消息
        """
        try:
            content = kwargs.get('content', '')
            mood_type_id = kwargs.get('mood_type_id', '')
            factors = kwargs.get('factors', None)
            if not mood_type_id:
                return f"{ERROR}请输入心情类型ID"

            # 使用mood_type_id查询score
            mood_type = mood_repository.get_mood_type_by_id(mood_type_id)
            if not mood_type:
                return f"{ERROR}心情类型ID {mood_type_id} 不存在"
            score = mood_type.get('score', 50)

            return create_user_mood(content, score, mood_type_id, factors)
        except ValueError as e:
            return f"{ERROR}参数错误: {str(e)}"
        except Exception as e:
            return f"{ERROR}创建失败: {str(e)}"


def create_user_mood(content:str,score:int,mood_type_id:str,factors_raw:list[str]|None=None)->str:
    """
    创建用户心情记录。
    args:
        content: 心情记录内容
        score: 心情评分
        mood_type_id: 心情类型ID
        factors_raw: 可选，影响因素，格式：JSON字符串
    return:
        新创建的 ID
    """
    data = {
        'content': content,
        'score': score,
        'mood_type_id': mood_type_id,
        'factors': factors_raw
    }
    if factors_raw:
        data['factors'] = json.dumps(factors_raw)
    mood_id = mood_repository.create_mood_entry(data)
    return  f"创建心情记录成功，ID: {mood_id}"

if __name__ == "__main__":
    print(query_user_activity_summary(['computer_usage_stats'],"2026-04-28 00:00:00","2026-04-29 00:00:00"))
    print(query_user_activity_log("2026-04-28 00:00:00","2026-04-29 00:00:00"))
    print(create_or_update_user_behavior_note("2026-04-28 00:00:00","2026-04-29 00:00:00","用户在电脑上工作111",129))
    print(query_user_mood("2026-05-03","2026-05-04"))
    print(UserMoodCreateTool().parameters)
