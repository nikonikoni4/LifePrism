"""定时任务模块

包含以下定时任务（必须严格按照顺序执行）：
1. 每天数据分类
2. 截图分析（在 sync service 中实现）
3. 日记总结（在 diary service 中实现）
4. 活动总结
5. 聊天记录总结
"""
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

from lifeprism.config import settings
from lifeprism.llm.agent.tools.lifeprismsystem import query_user_activity_summary, query_user_mood
from lifeprism.llm.bus import InboundMessage, bus, MessageType, OutboundMessage
from lifeprism.llm.prompts import prompt_loader, Prompts
from lifeprism.llm.session import Session, session_manager, ChatHistoryManager
from lifeprism.llm.utils.md_os import write_date_md, extract_date_logs_from_file, read_md
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import ExternalServiceError

logger = get_logger(__name__)

# 常量定义
DAILY_START_HOUR = "04:00:00"  # 每日开始时间
SESSION_BATCH_SIZE = 10  # 批处理大小
DEFAULT_DATE_OFFSET = 7  # 默认日期偏移量（天）
DEFAULT_DAYS_OFFSET = 3  # 默认处理日期限制（天）


async def summary_activities(activities: str) -> str:
    """总结活动数据

    Args:
        activities: 活动数据字符串

    Returns:
        str: 活动总结内容
    """
    # 加载 prompt
    activity_summary_prompt = prompt_loader.load_prompt(Prompts.Schedule.ACTIVITY_SUMMARY)

    if activities:
        result = await bus.send(
            InboundMessage(
                MessageType.DREAM_TASK,
                extra={"system_prompt": activity_summary_prompt}
            )
        )
        if result.response and result.response.content:
            return result.response.content
        else:
            logger.error(f"活动总结llm返回数据错误,{result}")
            raise ExternalServiceError(f"活动总结llm返回数据错误,{result}")
    else:
        logger.info("没有活动数据，跳过总结")
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
        logger.info("没有心情数据，跳过总结")
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

async def update_memory(date: str, date_offset: int = DEFAULT_DATE_OFFSET) -> None:
    """依据behavior.md更新记忆文档

    Args:
        date: 结束时间 YYYY-MM-DD, 包括这一天
        date_offset: 时间偏移量，用于计算开始时间 date - date_offset
    """
    if date_offset < 0:
        date_offset = 0
        logger.warning("date_offset为负")
    
    # 加载 prompt 并注入参数
    update_memory_prompt = prompt_loader.load_prompt(
        Prompts.Schedule.UPDATE_MEMORY,
        recent_state_path=str((settings.lifeprism_data_path / "user/daily_data/recent_state.md").resolve()),
        user_md_path=str((settings.lifeprism_data_path / "user/user.md").resolve()),
        diary_path_template=str((settings.lifeprism_data_path / "daily/YYYY/MM/YYYY-MM-DD.md").resolve())
    )

    # 获取behavior.md
    end_time = datetime.strptime(date, "%Y-%m-%d")
    start_time = end_time - timedelta(days=date_offset)
    start_date = start_time.strftime("%Y-%m-%d")

    behavior_md = extract_date_logs_from_file(
        settings.lifeprism_data_path / "user/daily_data/behavior.md",
        start_date,
        date
    )
    # 获取当前的recent_state.md
    recent_state_md = read_md(settings.lifeprism_data_path / "user/daily_data/recent_state.md")

    # 构建content
    content = f"""
    你需要帮我更新recent_state.md 文档，如果涉及到user.md相关内容,也需要更新user.md文档。
    ## 近{date_offset}天的behavior.md内容
    {behavior_md}
    ## 之前的recent_state.md内容仅作参考
    {recent_state_md}
    """
    await bus.send(
        InboundMessage(
            MessageType.DREAM_TASK,
            content=content,
            extra={'system_prompt': update_memory_prompt}
        )
    )
    



# 1. 定时总结日记，更新behavior.md 和 recent_status.md
async def dreaming(date: str) -> None:
    """更新用户记忆

    从数据库中获取用户最近的聊天记录，查看最近一天的心情变化和日记内容，
    总结为behavior.md 和 recent_status.md 或其他记忆文件

    Args:
        date: 要总结的日期，格式为 '%Y-%m-%d'
              总结时间说明 date 04:00:00 ~ date + 1 04:00:00
    """
    # 获取用户活动, 总结用户活动
    next_date = (datetime.strptime(date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
    start_time = f"{date} {DAILY_START_HOUR}"
    end_time = f"{next_date} {DAILY_START_HOUR}"
    activities = query_user_activity_summary(
        set(["computer_usage_stats", "user_behavior_notes", "ai_behavior_notes"]),
        start_time,
        end_time
    )
    activities_summary_content = await summary_activities(activities)

    # 获取心情数据，并总结
    mood_data = get_mood_data(start_time, end_time)
    mood_summary_content = await summary_moods(mood_data)

    # 将内容写入behavior.md
    path = settings.lifeprism_data_path / "user/daily_data/behavior.md"
    write_date_md(path, date, activities_summary_content, "行为总结")
    write_date_md(path, date, mood_summary_content, "心情总结")

    # 总结内容到recent_state.md和user.md
    await update_memory(date)

 




# 2. 时间间隔任务：

async def extract_from_chat_messages(session: Session) -> str | None:
    """从历史消息中提取有效信息

    Args:
        session: Session 对象

    Returns:
        str | None: 提取的内容，如果没有可提取内容则返回 None
    """
    # 加载 prompt
    extract_chat_prompt = prompt_loader.load_prompt(Prompts.Schedule.EXTRACT_CHAT)

    # 将message[获取所有消息记录中长度不等于last_processed_loc的消息:]转化为str
    message = session.messages[session.last_processed_loc:]
    if message:
        summary_raw_content = json.dumps(message)
        result: OutboundMessage = await bus.send(InboundMessage(
            type=MessageType.DREAM_TASK,
            content=f"## 需要总结的内容 \n {summary_raw_content}",
            extra={"system_prompt": extract_chat_prompt}
        ))
        session.last_processed_loc = len(session.messages)
        session_manager.save_session(session)

        if result.response and result.response.content and result.response.content != "无可提取内容":
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

async def process_session_message(days_offset: int = DEFAULT_DAYS_OFFSET) -> None:
    """将当前的session中没有提取的会话进行提取，将结果放入chat_history.json中

    每隔2h执行一次

    Args:
        days_offset: 处理日期限制，旧session不在处理
    """
    # 1. 加载session meta,获取需要处理的消息
    _session_to_process = []
    session_list = session_manager.show_session_list()
    for session_id in session_list:
        meta_data = session_manager.get_session_metadata(session_id)
        if meta_data.get("message_len", None):
            message_len = meta_data["message_len"]
            last_processed_loc = meta_data.get("last_processed_loc", 0)
            update_at = datetime.fromisoformat(meta_data.get("update_at", datetime.now().isoformat()))
            # 判断是否有未处理消息 且 update_at > 今天 - days_offset
            if message_len > last_processed_loc and update_at > datetime.now() - timedelta(days=days_offset):
                _session_to_process.append(session_id)
    # 处理消息（分组处理，每组最多10个）
    history_manager = ChatHistoryManager()
    if _session_to_process:
        all_results = []

        try:
            # 分组处理
            for i in range(0, len(_session_to_process), SESSION_BATCH_SIZE):
                batch = _session_to_process[i:i + SESSION_BATCH_SIZE]
                # 先加载 session 对象
                sessions = [session_manager._load_session(sid) for sid in batch]
                batch_results = await asyncio.gather(
                    *[extract_from_chat_messages(session) for session in sessions]
                )
                all_results.extend([r for r in batch_results if r is not None])
        finally:
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
    update_memory_prompt = prompt_loader.load_prompt(
        Prompts.Schedule.UPDATE_MEMORY,
        recent_state_path=str(settings.lifeprism_data_path / "user/daily_data/recent_state.md"),
        user_md_path=str(settings.lifeprism_data_path / "user/user.md"),
        diary_path_template=str(settings.lifeprism_data_path / "daily/YYYY/MM/YYYY-MM-DD.md")
    )
    print(update_memory_prompt)