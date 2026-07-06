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
import re
from datetime import datetime, timedelta
from pathlib import Path

from lifeprism.config import settings
from lifeprism.llm.agent.tools.lifeprismsystem import query_user_activity_summary, query_user_mood
from lifeprism.llm.bus import InboundMessage, bus, MessageType, OutboundMessage,TokenType
from lifeprism.llm.prompts import prompt_loader, Prompts
from lifeprism.llm.session import Session, session_manager, ChatHistoryManager
from lifeprism.llm.utils.md_os import write_date_md, extract_date_logs_from_file, read_md
from lifeprism.utils import get_logger,DEBUG
from lifeprism.llm.exceptions import LLMResponseError
from lifeprism.llm.utils import llm_call_logger
logger = get_logger(__name__)
logger.setLevel(DEBUG)
# 常量定义
DAILY_START_HOUR = "04:00:00"  # 每日开始时间
SESSION_BATCH_SIZE = 10  # 批处理大小
DEFAULT_DATE_OFFSET = 7  # 默认日期偏移量（天）
DEFAULT_DAYS_OFFSET = 3  # 默认处理日期限制（天）


def _normalize_activity_summary_format(content: str) -> str:
    """将 LLM 可能输出的 markdown 标题格式强制替换为序号格式

    部分 LLM 模型会忽略 prompt 中的格式约束，输出 ### 今日概览 / ## 电脑使用总览
    等 markdown 标题，这里统一替换为 prompt 要求的分点序号格式。

    Args:
        content: LLM 原始输出

    Returns:
        str: 规范化后的内容
    """
    replacements = [
        # 纯 markdown 标题：### 今日概览 → 1. 今日概览
        (r'^#{1,3}\s+今日概览\s*$', r'1. 今日概览', re.MULTILINE),
        (r'^#{1,3}\s+电脑使用总览\s*$', r'2. 电脑使用总览', re.MULTILINE),
        (r'^#{1,3}\s+高频使用时段\s*$', r'3. 高频使用时段', re.MULTILINE),
        # 混合格式：### 1. 今日概览（附注）→ 1. 今日概览
        (r'^#{1,3}\s+1\.\s*今日概览.*$', r'1. 今日概览', re.MULTILINE),
        (r'^#{1,3}\s+2\.\s*电脑使用总览.*$', r'2. 电脑使用总览', re.MULTILINE),
        (r'^#{1,3}\s+3\.\s*高频使用时段.*$', r'3. 高频使用时段', re.MULTILINE),
    ]
    for pattern, replacement, flags in replacements:
        new_content = re.sub(pattern, replacement, content, flags=flags)
        if new_content != content:
            logger.debug("[_normalize] 替换了格式: %s", pattern)
            content = new_content
    return content


async def summary_activities(activities: str, start_time: str, end_time: str) -> str:
    """总结活动数据

    Args:
        activities: 活动数据字符串
        start_time: 总结的开始时间，格式为 'YYYY-MM-DD HH:MM:SS'
        end_time: 总结的结束时间，格式为 'YYYY-MM-DD HH:MM:SS'

    Returns:
        str: 活动总结内容
    """
    logger.info("[summary_activities] 开始活动总结, 时间范围: %s ~ %s", start_time, end_time)
    logger.debug("[summary_activities] 输入数据长度: %s 字符", len(activities) if activities else 0)

    # 加载 prompt，注入时间参数
    activity_summary_prompt = prompt_loader.load_prompt(
        Prompts.Schedule.ACTIVITY_SUMMARY,
        start_time=start_time,
        end_time=end_time,
    )
    logger.debug("[summary_activities] 已加载 prompt, 长度: %s 字符", len(activity_summary_prompt) if activity_summary_prompt else 0)

    if activities:
        logger.info("[summary_activities] 发送 LLM 请求进行活动总结")
        msg = InboundMessage(
            type=MessageType.GENERAL_TASK,
            token_type=TokenType.DREAM_TASK,
            content=activities,
            extra={"system_prompt": activity_summary_prompt}
        )
        result = await bus.send(msg)
        llm_call_logger.log_call(msg, result, prompt_module=Prompts.Schedule.ACTIVITY_SUMMARY.module, prompt_name=Prompts.Schedule.ACTIVITY_SUMMARY.name)
        
        if result.response and result.response.content:
            logger.info("[summary_activities] LLM 返回成功, 结果长度: %s 字符", len(result.response.content))
            normalized = _normalize_activity_summary_format(result.response.content)
            return normalized
        else:
            logger.error(
                "[summary_activities] 活动总结 LLM 返回空内容: model=%s, result=%s",
                settings.model, str(result)[:200]
            )
            raise LLMResponseError(
                model=settings.model,
                raw_response=str(result)[:500]
            )
    else:
        logger.info("[summary_activities] 没有活动数据，跳过总结")
        return "无今日活动数据"

def get_mood_data(start_time: str, end_time: str) -> str:
    """获取心情数据

    Args:
        start_time: 开始时间，格式为 'YYYY-MM-DD HH:MM:SS'
        end_time: 结束时间，格式为 'YYYY-MM-DD HH:MM:SS'

    Returns:
        str: 格式化的心情数据字符串
    """
    logger.debug("[get_mood_data] 获取心情数据, 时间范围: %s ~ %s", start_time, end_time)

    # 直接使用时间查询，不再转换为日期
    mood_data = query_user_mood(start_time, end_time)
    logger.debug("[get_mood_data] 获取到心情数据长度: %s 字符", len(mood_data) if mood_data else 0)

    return mood_data

async def summary_moods(mood_data: str) -> str:
    """总结心情数据

    Args:
        mood_data: 心情数据字符串

    Returns:
        str: 心情总结内容
    """
    logger.info("[summary_moods] 开始心情总结")
    logger.debug("[summary_moods] 输入数据长度: %s 字符", len(mood_data) if mood_data else 0)
    
    # 加载 prompt
    mood_summary_prompt = prompt_loader.load_prompt(Prompts.Schedule.MOOD_SUMMARY)
    logger.debug("[summary_moods] 已加载 prompt, 长度: %s 字符", len(mood_summary_prompt) if mood_summary_prompt else 0)

    # 检查是否有心情数据
    if not mood_data or "无心情记录" in mood_data:
        logger.info("[summary_moods] 没有心情数据，跳过总结")
        return "无心情记录"

    # 调用 LLM 进行总结
    logger.info("[summary_moods] 发送 LLM 请求进行心情总结")
    msg = InboundMessage(
        type = MessageType.GENERAL_TASK,
        token_type = TokenType.DREAM_TASK,
        content=f"## 需要总结的心情数据\n{mood_data}",
        extra={"system_prompt": mood_summary_prompt}
    )
    result = await bus.send(msg)
    llm_call_logger.log_call(msg, result, prompt_module=Prompts.Schedule.MOOD_SUMMARY.module, prompt_name=Prompts.Schedule.MOOD_SUMMARY.name)

    # 处理返回结果
    if result.response and result.response.content:
        logger.info("[summary_moods] LLM 返回成功, 结果长度: %s 字符", len(result.response.content))
        return result.response.content
    else:
        logger.error(
            "[summary_moods] 心情总结 LLM 返回空内容: model=%s, result=%s",
            settings.model, str(result)[:200]
        )
        raise LLMResponseError(
            model=settings.model,
            raw_response=str(result)[:500]
        )

async def update_memory(date: str, date_offset: int = DEFAULT_DATE_OFFSET) -> None:
    """依据behavior.md更新记忆文档

    Args:
        date: 结束时间 YYYY-MM-DD, 包括这一天
        date_offset: 时间偏移量，用于计算开始时间 date - date_offset
    """
    logger.info("[update_memory] 开始更新记忆文档, 日期: %s, 偏移量: %s", date, date_offset)
    
    if date_offset < 0:
        date_offset = 0
        logger.warning("[update_memory] date_offset为负，已重置为0")
    
    # 加载 prompt 并注入参数
    update_memory_prompt = prompt_loader.load_prompt(
        Prompts.Schedule.UPDATE_MEMORY,
        recent_state_path=str((settings.lifeprism_data_path / "user/daily_data/recent_state.md").resolve()),
        upper_limit = 1000,
    )
    logger.debug("[update_memory] 已加载 prompt, 长度: %s 字符", len(update_memory_prompt) if update_memory_prompt else 0)

    # 获取behavior.md
    end_time = datetime.strptime(date, "%Y-%m-%d")
    start_time = end_time - timedelta(days=date_offset)
    start_date = start_time.strftime("%Y-%m-%d")
    logger.debug("[update_memory] 提取 behavior.md 时间范围: %s ~ %s", start_date, date)

    behavior_md = extract_date_logs_from_file(
        settings.lifeprism_data_path / "user/daily_data/behavior.md",
        start_date,
        date
    )
    logger.debug("[update_memory] behavior.md 内容长度: %s 字符", len(behavior_md) if behavior_md else 0)
    
    # 获取当前的recent_state.md
    recent_state_md = read_md(settings.lifeprism_data_path / "user/daily_data/recent_state.md")
    logger.debug("[update_memory] recent_state.md 内容长度: %s 字符", len(recent_state_md) if recent_state_md else 0)
    
    computer_overview = query_user_activity_summary(
        set(["computer_overview"]),
        f"{start_date} {DAILY_START_HOUR}",
        f"{date} {DAILY_START_HOUR}"
    )
    logger.debug("[update_memory] 电脑使用总览数据长度: %s 字符", len(computer_overview) if computer_overview else 0)
    
    # 构建content
    content = f"""
    你需要帮我更新recent_state.md 文档，如果涉及到user.md相关内容,也需要更新user.md文档。
    ## 近{date_offset}天的behavior.md内容
    <behavior_md content>
    {behavior_md}
    </behavior_md content>
    ## 近{date_offset}天的电脑使用总览
    {computer_overview}
    ## 之前的recent_state.md内容仅作参考
    {recent_state_md}
    """
    logger.debug("[update_memory] 构建的 LLM 请求内容长度: %s 字符", len(content))
    
    logger.info("[update_memory] 发送 LLM 请求更新记忆文档")
    msg = InboundMessage(
        type = MessageType.DREAM_TASK, # 这里需要工具，因为他需要变更user和state，其他的四个子任务不需要工具调用
        token_type = TokenType.DREAM_TASK,
        content=content,
        extra={'system_prompt': update_memory_prompt}
    )
    result = await bus.send(msg)
    llm_call_logger.log_call(msg, result, prompt_module=Prompts.Schedule.UPDATE_MEMORY.module, prompt_name=Prompts.Schedule.UPDATE_MEMORY.name)
    logger.info("[update_memory] 记忆文档更新完成")
    



# 1. 定时总结日记，更新behavior.md 和 recent_status.md
async def dreaming(date: str) -> None:
    """更新用户记忆

    从数据库中获取用户最近的聊天记录，查看最近一天的心情变化和日记内容，
    总结为behavior.md 和 recent_status.md 或其他记忆文件

    Args:
        date: 要总结的日期，格式为 '%Y-%m-%d'
              总结时间说明 date 04:00:00 ~ date + 1 04:00:00
    """
    logger.info("[dreaming] 开始执行 dreaming 任务, 目标日期: %s", date)
    
    # 计算时间范围
    next_date = (datetime.strptime(date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
    start_time = f"{date} {DAILY_START_HOUR}"
    end_time = f"{next_date} {DAILY_START_HOUR}"
    logger.debug("[dreaming] 时间范围: %s ~ %s", start_time, end_time)

    # 阶段1: 获取用户活动数据并总结
    logger.info("[dreaming] 阶段1: 获取用户活动数据")
    activity_types = set(["high_usage_segments", "user_behavior_notes", "ai_behavior_notes"])
    logger.debug("[dreaming] 查询活动类型: %s", activity_types)
    
    activities = query_user_activity_summary(
        activity_types,
        start_time,
        end_time
    )
    logger.debug("[dreaming] 获取到活动数据长度: %s 字符", len(activities) if activities else 0)
    if activities:
        logger.debug("[dreaming] 活动数据前200字符: %s", activities[:200])
    
    logger.info("[dreaming] 阶段1: 总结活动数据")
    activities_summary_content = await summary_activities(activities, start_time, end_time)
    logger.debug("[dreaming] 活动总结结果长度: %s 字符", len(activities_summary_content) if activities_summary_content else 0)
    logger.debug("[dreaming] 活动总结结果前200字符: %s", activities_summary_content[:200] if activities_summary_content else '无')

    # 阶段2: 获取心情数据并总结
    logger.info("[dreaming] 阶段2: 获取心情数据")
    mood_data = get_mood_data(start_time, end_time)
    logger.debug("[dreaming] 获取到心情数据长度: %s 字符", len(mood_data) if mood_data else 0)
    if mood_data:
        logger.debug("[dreaming] 心情数据前200字符: %s", mood_data[:200])
    
    logger.info("[dreaming] 阶段2: 总结心情数据")
    mood_summary_content = await summary_moods(mood_data)
    logger.debug("[dreaming] 心情总结结果长度: %s 字符", len(mood_summary_content) if mood_summary_content else 0)
    logger.debug("[dreaming] 心情总结结果前200字符: %s", mood_summary_content[:200] if mood_summary_content else '无')

    # 阶段3: 将内容写入behavior.md
    logger.info("[dreaming] 阶段3: 写入 behavior.md")
    path = settings.lifeprism_data_path / "user/daily_data/behavior.md"
    logger.debug("[dreaming] behavior.md 路径: %s", path)
    
    write_date_md(path, date, activities_summary_content, "行为总结")
    logger.debug("[dreaming] 已写入行为总结到 behavior.md")
    
    write_date_md(path, date, mood_summary_content, "心情总结")
    logger.debug("[dreaming] 已写入心情总结到 behavior.md")

    # 阶段4: 总结内容到recent_state.md和user.md
    logger.info("[dreaming] 阶段4: 更新记忆文档 (recent_state.md 和 user.md)")
    await update_memory(date)
    
    logger.info("[dreaming] dreaming 任务完成, 目标日期: %s", date)


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
        summary_raw_content = json.dumps(message, ensure_ascii=False)
        msg = InboundMessage(
            type=MessageType.GENERAL_TASK,
            token_type=MessageType.DREAM_TASK,
            content=f"## 需要总结的内容 \n {summary_raw_content}",
            extra={"system_prompt": extract_chat_prompt}
        )
        logger.info("[process_session_message] 发送 LLM 请求提取聊天消息")
        result: OutboundMessage = await bus.send(msg)
        llm_call_logger.log_call(msg, result, prompt_module=Prompts.Schedule.EXTRACT_CHAT.module, prompt_name=Prompts.Schedule.EXTRACT_CHAT.name)
        
        session.last_processed_loc = len(session.messages)
        session_manager.save_session(session)

        if result.response and result.response.content and result.response.content != "无可提取内容":
            return result.response.content
    return None

def format_chat_history(history: list[dict]) -> str:
    """
    格式化聊天历史记录为 Markdown 格式

    每条 history 是 LLM 对一次对话的提取结果，内部已有 `一、` `二、` 层级结构。
    多条记录之间用空行分隔，不再添加序号前缀（避免与内容自身编号冲突）。

    Args:
        history: 聊天历史记录列表，每项包含 content 字段

    Returns:
        str: 格式化后的 Markdown 字符串，如果没有有效内容则返回空字符串
    """
    if not history:
        return ""

    formatted_history = []
    for item in history:
        content = item.get("content", "")
        if content:
            formatted_history.append(content)

    return "\n\n".join(formatted_history) if formatted_history else ""

async def process_session_message(days_offset: int = DEFAULT_DAYS_OFFSET) -> None:
    """将当前的session中没有提取的会话进行提取，将结果放入chat_history.json中

    每隔2h执行一次

    Args:
        days_offset: 处理日期限制，旧session不在处理
    """
    logger.info("[process_session_message] 开始处理会话消息, days_offset=%s", days_offset)
    
    # 1. 加载session meta,获取需要处理的消息
    _session_to_process = []
    session_list = session_manager.show_session_list()
    logger.debug("[process_session_message] 获取到 %s 个 session", len(session_list))
    
    for session_id in session_list:
        meta_data = session_manager.get_session_metadata(session_id)
        logger.debug("[process_session_message] 检查 session: %s, meta_data keys: %s", session_id, list(meta_data.keys()) if meta_data else 'None')
        
        if meta_data.get("message_len", None):
            message_len = meta_data["message_len"]
            last_processed_loc = meta_data.get("last_processed_loc", 0)
            update_at = datetime.fromisoformat(meta_data.get("update_at", datetime.now().isoformat()))
            logger.debug("[process_session_message] session %s: message_len=%s, last_processed_loc=%s, update_at=%s", session_id, message_len, last_processed_loc, update_at)
            
            # 判断是否有未处理消息 且 update_at > 今天 - days_offset
            if message_len > last_processed_loc and update_at > datetime.now() - timedelta(days=days_offset):
                _session_to_process.append(session_id)
                logger.debug("[process_session_message] session %s 需要处理 (有 %s 条新消息)", session_id, message_len - last_processed_loc)
            else:
                logger.debug("[process_session_message] session %s 跳过: message_len(%s) <= last_processed_loc(%s) 或 update_at(%s) 过期", session_id, message_len, last_processed_loc, update_at)
        else:
            logger.debug("[process_session_message] session %s 跳过: 无 message_len", session_id)
    
    logger.debug("[process_session_message] 共 %s 个 session 需要处理: %s", len(_session_to_process), _session_to_process)
    
    # 处理消息（分组处理，每组最多10个）
    history_manager = ChatHistoryManager()
    if _session_to_process:
        all_results = []  # 存储 (session_id, content) 元组

        try:
            # 分组处理
            total_batches = (len(_session_to_process) + SESSION_BATCH_SIZE - 1) // SESSION_BATCH_SIZE
            logger.debug("[process_session_message] 开始分组处理, 每组 %s 个, 共 %s 组", SESSION_BATCH_SIZE, total_batches)

            for i in range(0, len(_session_to_process), SESSION_BATCH_SIZE):
                batch = _session_to_process[i:i + SESSION_BATCH_SIZE]
                batch_num = i // SESSION_BATCH_SIZE + 1
                logger.debug("[process_session_message] 处理第 %s/%s 组: %s", batch_num, total_batches, batch)

                # 先加载 session 对象
                sessions = [session_manager._load_session(sid) for sid in batch]
                logger.debug("[process_session_message] 第 %s 组 session 加载完成", batch_num)

                batch_results = await asyncio.gather(
                    *[extract_from_chat_messages(session) for session in sessions]
                )

                # 保持 session_id 和结果的对应关系
                for session, result in zip(sessions, batch_results):
                    if result is not None:
                        all_results.append((session.id, result))

                valid_count = len([r for r in batch_results if r is not None])
                logger.debug("[process_session_message] 第 %s 组处理完成, 获取 %s/%s 个有效结果", batch_num, valid_count, len(batch_results))

        finally:
            # 删除加载的session_id
            logger.debug("[process_session_message] 清理 session 缓存, 共 %s 个", len(_session_to_process))
            for session_id in _session_to_process:
                session_manager.remove_from_cache(session_id)
            logger.debug("[process_session_message] session 缓存清理完成")

        # 创建history
        logger.info("[process_session_message] 开始保存历史记录, 共 %s 条结果", len(all_results))
        for session_id, content in all_results:
            history_manager.add_content(content, session_id=session_id)
        history_manager.save_history()
        logger.debug("[process_session_message] 历史记录保存完成")
    else:
        logger.debug("[process_session_message] 没有需要处理的 session")

    # 将chat_history 更新到behavior
    logger.info("[process_session_message] 开始更新 behavior")
    history = history_manager.get_histories_to_dream()
    if history:
        logger.debug("[process_session_message] 获取到 %s 条历史记录用于更新 behavior", len(history))
        history_content = format_chat_history(history)
        if history_content:
            logger.debug("[process_session_message] 格式化后 history_content 长度: %s 字符", len(history_content))
            write_date_md(
                settings.lifeprism_data_path / "user/daily_data/behavior.md",
                datetime.now().strftime('%Y-%m-%d'),
                history_content,
                "聊天记录总结"
            )
            # 更新 last_processed_time
            history_manager.save_history(datetime.now())
            logger.info("[process_session_message] behavior 更新完成")
        else:
            logger.debug("[process_session_message] history_content 为空, 跳过更新")
    else:
        logger.debug("[process_session_message] 没有历史记录需要更新 behavior")
    
    logger.info("[process_session_message] 会话消息处理完成")

if __name__ == "__main__":
    from datetime import timedelta
    from lifeprism.llm.agent.loop import agent_loop

    async def main():
        loop_task = asyncio.create_task(agent_loop.loop())
        try:
            # mood_data = get_mood_data("2026-06-30 00:00:00", "2026-07-01 00:00:00")
            # await summary_moods(mood_data)
            await dreaming("2026-06-30")
        finally:
            loop_task.cancel()

    asyncio.run(main())
    