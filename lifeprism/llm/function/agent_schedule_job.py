# 在这里编写定时任务的函数和时间间隔任务函数
# 任务包括：
# 定时任务，必须严格按照顺序执行：1）每天数据分类 2）截图分析(sync service中实现)，3）日记总结（在diary service中实现） ,
# 4）活动总结, 聊天记录总结，
# 定时任务的实现需要修改的其他地方：1. 前端不在自动发出更新请求，而是定时更新 2.
from ast import In
from datetime import datetime, timedelta
from pathlib import Path

from jinja2 import ext
import lifeprism
from lifeprism.llm.session import session_manager, Session
from lifeprism.utils import get_logger
from lifeprism.llm.agent.tools.lifeprismsystem import query_user_activity_summary,query_user_mood
import json
from lifeprism.llm.session import Session, session_manager,ChatHistoryManager
from lifeprism.llm.bus import InboundMessage, bus,MessageType,OutboundMessage
from lifeprism.config import settings
import asyncio
from lifeprism.utils.exceptions import ExternalServiceError
from lifeprism.llm.utils.md_os import write_date_md,extract_date_logs_from_file,read_md
from lifeprism.llm.prompts import prompt_loader, Prompts

logger = get_logger(__name__)


async def summary_activities(activities : str)->str:
    # 加载 prompt
    activity_summary_prompt = prompt_loader.load_prompt(Prompts.Schedule.ACTIVITY_SUMMARY)

    if activities:
        result = await bus.send(
            InboundMessage(
                MessageType.DREAM_TASK,
                extra = {"system_prompt": activity_summary_prompt}
            )
        )
        if result.response and result.response.content:
            return result.response.content
        else:
            logger.error(f"活动总结llm返回数据错误,{result}")
            raise ExternalServiceError(f"活动总结llm返回数据错误,{result}")
    else:
        logger.warning("没有总结数据")
        return "无今日活动数据"

def get_mood_data(start_time: str, end_time: str) -> str:
    """获取心情数据

    Args:
        start_time: 开始时间，格式为 'YYYY-MM-DD HH:MM:SS'
        end_time: 结束时间，格式为 'YYYY-MM-DD HH:MM:SS'

    Returns:
        str: 格式化的心情数据字符串
    """
    # 将时间格式从 'YYYY-MM-DD HH:MM:SS' 转换为 'YYYY-MM-DD'
    start_date = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
    end_date = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')

    # 调用 query_user_mood 获取心情数据
    mood_data = query_user_mood(start_date, end_date)

    return mood_data

async def summary_moods(mood_data: str) -> str:
    """总结心情数据

    Args:
        mood_data: 心情数据字符串

    Returns:
        str: 心情总结内容
    """
    # 加载 prompt
    mood_summary_prompt = prompt_loader.load_prompt(Prompts.Schedule.MOOD_SUMMARY)

    # 检查是否有心情数据
    if not mood_data or "无心情记录" in mood_data:
        logger.warning("没有心情数据")
        return "无心情记录"

    # 调用 LLM 进行总结
    result = await bus.send(
        InboundMessage(
            MessageType.DREAM_TASK,
            content=f"## 需要总结的心情数据\n{mood_data}",
            extra={"system_prompt": mood_summary_prompt}
        )
    )

    # 处理返回结果
    if result.response and result.response.content:
        return result.response.content
    else:
        logger.error(f"心情总结 LLM 返回数据错误: {result}")
        raise ExternalServiceError(f"心情总结 LLM 返回数据错误: {result}")

async def update_memory(date:str,date_offset = 7)->None:
    """
    依据behavior.md更新记忆文档
    args :
        date : 结束时间 YYYY-MM-DD, 包括这一天
        date_offset ： 时间偏移量，用于计算开始时间 date - date_offset
    """
    if date_offset<0:
        date_offset = 0
        logger.warning("date_offset为负")

    # 加载 prompt 并注入参数
    update_memory_prompt = prompt_loader.load_prompt(
        Prompts.Schedule.UPDATE_MEMORY,
        recent_state_path=str(settings.lifeprism_data_path / "user/daily_data/recent_state.md"),
        user_md_path=str(settings.lifeprism_data_path / "user/user.md"),
        diary_path_template=str(settings.lifeprism_data_path / "dialy/YYYY/MM/YYYY-MM-DD.md")
    )

    # 获取behavior.md
    end_time = datetime.strptime(date,"%Y-%m-%d")
    start_time = end_time - timedelta(days = date_offset)
    start_date = start_time.strftime("%Y-%m-%d")

    behavior_md = extract_date_logs_from_file(settings.lifeprism_data_path / "user/daily_data/behavior.md",start_date,date)
    # 获取当前的recent_state.md
    recent_state_md = read_md(settings.lifeprism_data_path / "user/daily_data/recent_state.md")

    # 构建content
    content = f"""
    你需要帮我更新recent_state.md 文档，如果涉及到user.md相关内容,也需要更新user.md文档。
    ## 近7天的behavior.md内容
    {behavior_md}
    ## 之前的recent_state.md内容仅作参考
    {recent_state_md}
    """
    await bus.send(
        InboundMessage(
            MessageType.DREAM_TASK,
            content=content,
            extra = {'system_prompt': update_memory_prompt}
        )
    )
    



# 1. 定时总结日记，更新behavior.md 和 recent_status.md
async def dreaming(date: str):
    """更新用户记忆
    从数据库中获取用户最近的聊天记录，查看最近一天的心情变化和日记内容，总结为behavior.md 和 recent_status.md 或其他记忆文件
    
    Args:
        date (str): 要总结的日期，格式为 '%Y-%m-%d'
        总结时间说明 date 04:00:00 ~ date + 1 04:00:00
    """
    # 获取用户活动, 总结用户活动
    next_date = (datetime.strptime(date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
    start_time = date + " 04:00:00"
    end_time = next_date + " 04:00:00"
    activities = query_user_activity_summary(set(["computer_usage_stats", "user_behavior_notes", "ai_behavior_notes"]),start_time,end_time)
    activities_summary_content = summary_activities(activities)
    
    # 获取心情数据，并总结
    mood_data = get_mood_data(start_time, end_time)
    mood_summary_content = await summary_moods(mood_data)

    # 将内容写入behavior.md
    path = settings.lifeprism_data_path / "user/daily_data/behavior.md"
    date = datetime.now().strftime('%Y-%m-%d')
    # 日记总结是单独的函数，在该函数调用之前执行
    # 聊天总结是在间隔2h定时任务process_session_message时添加
    write_date_md(path,date,activities_summary_content,"行为总结")
    write_date_md(path,date,mood_summary_content,"心情总结")
    

    # 总结内容到recent_state.md和user.md
    update_memory(date)

 




# 2. 时间间隔任务：

async def extract_from_chat_messages(session:Session)->str|None:
    """从历史消息中提取有效信息"""
    # 加载 prompt
    extract_chat_prompt = prompt_loader.load_prompt(Prompts.Schedule.EXTRACT_CHAT)

    # 将message[获取所有消息记录中长度不等于last_processed_loc的消息:]转化为str
    message = session.messages[session.last_processed_loc:]
    if message:
        summary_raw_content = json.dumps(message)
        result:OutboundMessage= await bus.send(InboundMessage(
            type = MessageType.DREAM_TASK,
            content = f"## 需要总结的内容 \n {summary_raw_content}",
            extra={"system_prompt": extract_chat_prompt}
        ))
        session.last_processed_loc = len(session.messages)
        session_manager.save_session(session)

        if result.response and result.response.content and result.response.content  != "无可提取内容" :
            return result.response.content
    return None

def format_chat_history(history: list[dict]) -> str:
    """
    格式化聊天历史记录为 Markdown 格式

    Args:
        history: 聊天历史记录列表，每项包含 content 字段

    Returns:
        str: 格式化后的 Markdown 字符串，如果没有有效内容则返回空字符串

    Example:
        >>> history = [
        ...     {"timestamp": "2026-05-12T14:30:45", "content": "讨论了异步编程"},
        ...     {"timestamp": "2026-05-12T15:45:30", "content": "设计数据库方案"}
        ... ]
        >>> print(format_chat_history(history))
        1. 讨论了异步编程

        2. 设计数据库方案
    """
    if not history:
        return ""

    formatted_history = []
    index = 1
    for item in history:
        content = item.get("content", "")
        if content:
            formatted_history.append(f"{index}. {content}")
            index += 1

    return "\n\n".join(formatted_history) if formatted_history else ""

async def process_session_message(days_offset :int = 3):
    """
    将当前的session中没有提取的会话进行提取，将结果放入chat_history.json中
    每隔2h执行一次
    args :
        days_offset : 处理日期限制，旧session不在处理

    """
    # 1. 加载session meta,获取需要处理的消息
    _session_to_process = []
    session_list = session_manager.show_session_list()
    for session_id in session_list:
        meta_data = session_manager.get_session_metadata(session_id)
        if meta_data.get("message_len",None):
            message_len = meta_data["message_len"]
            last_processed_loc = meta_data.get("last_processed_loc",0)
            update_at = datetime.fromisoformat(meta_data.get("update_at", datetime.now().isoformat()))
            # 判断是否有未处理消息 且 update_at > 今天 - days_offset
            if message_len > last_processed_loc and update_at > datetime.now() - timedelta(days=days_offset):
                _session_to_process.append(session_id)
    # 处理消息（分组处理，每组最多10个）
    history_manager = ChatHistoryManager()
    if _session_to_process:
        BATCH_SIZE = 10
        all_results = []

        # 分组处理
        for i in range(0, len(_session_to_process), BATCH_SIZE):
            batch = _session_to_process[i:i + BATCH_SIZE]
            batch_results = await asyncio.gather(
                *[extract_from_chat_messages(session_id) for session_id in batch]
            )
            all_results.extend([r for r in batch_results if r is not None])

        # 删除加载的session_id
        for session_id in _session_to_process:
            session_manager.remove_from_cache(session_id)

        # 创建history

        for content in all_results:
            history_manager.add_content(content)
        history_manager.save_history()
    # 将chat_history 更新到behavior
    history = history_manager.get_histories_to_dream()
    if history:
        history_content = format_chat_history(history)
        if history_content:
            write_date_md(
                settings.lifeprism_data_path / "user/daily_data/behavior.md",
                datetime.now().strftime('%Y-%m-%d'),
                history_content,
                "聊天记录总结"
            )
            # 更新 last_processed_time
            history_manager.save_history(datetime.now())

if __name__ == "__main__":
    # 测试 format_chat_history 函数
    print("=== 测试 format_chat_history ===\n")

    # 测试用例1：正常数据
    test_history_1 = [
        {"timestamp": "2026-05-12T14:30:45", "content": "用户询问了关于 Python 异步编程的问题"},
        {"timestamp": "2026-05-12T15:45:30", "content": "讨论了数据库设计方案"},
        {"timestamp": "2026-05-12T16:20:15", "content": "用户分享了今天的工作进展"}
    ]
    result_1 = format_chat_history(test_history_1)
    print("测试用例1 - 正常数据:")
    print(result_1)
    print("\n" + "="*50 + "\n")

    # 测试用例2：空列表
    test_history_2 = []
    result_2 = format_chat_history(test_history_2)
    print("测试用例2 - 空列表:")
    print(f"结果: '{result_2}' (应该为空字符串)")
    print("\n" + "="*50 + "\n")

    # 测试用例3：包含缺失字段的数据
    test_history_3 = [
        {"timestamp": "2026-05-12T14:30:45", "content": "有效内容"},
        {"timestamp": "2026-05-12T15:45:30"},  # 缺少 content
        {"content": "缺少时间戳的内容（但仍然有效）"},  # 缺少 timestamp
        {"timestamp": "2026-05-12T16:20:15", "content": "另一条有效内容"}
    ]
    result_3 = format_chat_history(test_history_3)
    print("测试用例3 - 包含缺失字段:")
    print(result_3)
    print("\n" + "="*50 + "\n")

    # 测试用例4：只有 content 字段
    test_history_4 = [
        {"content": "第一条内容"},
        {"content": "第二条内容"},
        {"content": "第三条内容"}
    ]
    result_4 = format_chat_history(test_history_4)
    print("测试用例4 - 只有 content 字段:")
    print(result_4)
    print("\n" + "="*50 + "\n")

    print("所有测试完成！")