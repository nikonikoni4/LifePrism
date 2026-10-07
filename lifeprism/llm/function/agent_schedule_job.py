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
import os
import re
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from lifeprism.config import get_user_timezone, settings
from lifeprism.llm.bus import InboundMessage, MessageType, TokenType, bus
from lifeprism.llm.exceptions import LLMResponseError
from lifeprism.llm.prompts import Prompts, prompt_loader
from lifeprism.llm.runtime_tools.lifeprismsystem import query_user_activity_summary, query_user_mood
from lifeprism.llm.utils import llm_call_logger
from lifeprism.llm.utils.md_os import extract_date_logs_from_file, read_md, write_date_md
from lifeprism.utils import DEBUG, get_logger
from lifeprism.utils.time_utils import (
    build_local_datetime,
    get_local_today,
    local_to_utc_iso,
    utc_to_local_display,
)

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
        (r"^#{1,3}\s+今日概览\s*$", r"1. 今日概览", re.MULTILINE),
        (r"^#{1,3}\s+电脑使用总览\s*$", r"2. 电脑使用总览", re.MULTILINE),
        (r"^#{1,3}\s+高频使用时段\s*$", r"3. 高频使用时段", re.MULTILINE),
        # 混合格式：### 1. 今日概览（附注）→ 1. 今日概览
        (r"^#{1,3}\s+1\.\s*今日概览.*$", r"1. 今日概览", re.MULTILINE),
        (r"^#{1,3}\s+2\.\s*电脑使用总览.*$", r"2. 电脑使用总览", re.MULTILINE),
        (r"^#{1,3}\s+3\.\s*高频使用时段.*$", r"3. 高频使用时段", re.MULTILINE),
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
    logger.debug(
        "[summary_activities] 已加载 prompt, 长度: %s 字符",
        len(activity_summary_prompt) if activity_summary_prompt else 0,
    )

    if activities:
        logger.info("[summary_activities] 发送 LLM 请求进行活动总结")
        msg = InboundMessage(
            type=MessageType.GENERAL_TASK,
            token_type=TokenType.DREAM_TASK,
            content=activities,
            extra={"system_prompt": activity_summary_prompt},
            workflow_id="daily-memory",
        )
        result = await bus.send(msg)
        llm_call_logger.log_call(
            msg,
            result,
            prompt_module=Prompts.Schedule.ACTIVITY_SUMMARY.module,
            prompt_name=Prompts.Schedule.ACTIVITY_SUMMARY.name,
        )

        if result.response and result.response.content:
            logger.info(
                "[summary_activities] LLM 返回成功, 结果长度: %s 字符", len(result.response.content)
            )
            normalized = _normalize_activity_summary_format(result.response.content)
            return normalized
        else:
            logger.error(
                "[summary_activities] 活动总结 LLM 返回空内容: model=%s, result=%s",
                settings.model,
                str(result)[:200],
            )
            raise LLMResponseError(model=settings.model, raw_response=str(result)[:500])
    else:
        logger.info("[summary_activities] 没有活动数据，跳过总结")
        return "无今日活动数据"


def get_mood_data(start_time: str, end_time: str) -> str:
    """获取心情数据

    Args:
        start_time: 开始时间，格式为 'YYYY-MM-DD HH:MM:SS'（本地时区）
        end_time: 结束时间，格式为 'YYYY-MM-DD HH:MM:SS'（本地时区）

    Returns:
        str: 格式化的心情数据字符串
    """
    logger.debug("[get_mood_data] 获取心情数据, 时间范围: %s ~ %s", start_time, end_time)

    # 工具函数接收 UTC ISO，本地时间就地转换
    mood_data = query_user_mood(local_to_utc_iso(start_time), local_to_utc_iso(end_time))
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
    logger.debug(
        "[summary_moods] 已加载 prompt, 长度: %s 字符",
        len(mood_summary_prompt) if mood_summary_prompt else 0,
    )

    # 检查是否有心情数据
    if not mood_data or "无心情记录" in mood_data:
        logger.info("[summary_moods] 没有心情数据，跳过总结")
        return "无心情记录"

    # 调用 LLM 进行总结
    logger.info("[summary_moods] 发送 LLM 请求进行心情总结")
    msg = InboundMessage(
        type=MessageType.GENERAL_TASK,
        token_type=TokenType.DREAM_TASK,
        content=f"## 需要总结的心情数据\n{mood_data}",
        extra={"system_prompt": mood_summary_prompt},
        workflow_id="daily-memory",
    )
    result = await bus.send(msg)
    llm_call_logger.log_call(
        msg,
        result,
        prompt_module=Prompts.Schedule.MOOD_SUMMARY.module,
        prompt_name=Prompts.Schedule.MOOD_SUMMARY.name,
    )

    # 处理返回结果
    if result.response and result.response.content:
        logger.info("[summary_moods] LLM 返回成功, 结果长度: %s 字符", len(result.response.content))
        return result.response.content
    else:
        logger.error(
            "[summary_moods] 心情总结 LLM 返回空内容: model=%s, result=%s",
            settings.model,
            str(result)[:200],
        )
        raise LLMResponseError(model=settings.model, raw_response=str(result)[:500])


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
        recent_state_path=str(
            (settings.lifeprism_data_path / "user/daily_data/recent_state.md").resolve()
        ),
        upper_limit=1000,
    )
    logger.debug(
        "[update_memory] 已加载 prompt, 长度: %s 字符",
        len(update_memory_prompt) if update_memory_prompt else 0,
    )

    # 获取behavior.md
    end_time = datetime.strptime(date, "%Y-%m-%d")
    start_time = end_time - timedelta(days=date_offset)
    start_date = start_time.strftime("%Y-%m-%d")
    logger.debug("[update_memory] 提取 behavior.md 时间范围: %s ~ %s", start_date, date)

    behavior_md = extract_date_logs_from_file(
        settings.lifeprism_data_path / "user/daily_data/behavior.md", start_date, date
    )
    logger.debug(
        "[update_memory] behavior.md 内容长度: %s 字符", len(behavior_md) if behavior_md else 0
    )

    # 获取当前的recent_state.md
    recent_state_md = read_md(settings.lifeprism_data_path / "user/daily_data/recent_state.md")
    logger.debug(
        "[update_memory] recent_state.md 内容长度: %s 字符",
        len(recent_state_md) if recent_state_md else 0,
    )

    # 工具函数接收 UTC ISO，硬编码本地时间后就地转换
    computer_overview = query_user_activity_summary(
        set(["computer_overview"]),
        local_to_utc_iso(build_local_datetime(start_date, DAILY_START_HOUR)),
        local_to_utc_iso(build_local_datetime(date, DAILY_START_HOUR)),
    )
    logger.debug(
        "[update_memory] 电脑使用总览数据长度: %s 字符",
        len(computer_overview) if computer_overview else 0,
    )

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
        type=MessageType.DREAM_TASK,  # 这里需要工具，因为他需要变更user和state，其他的四个子任务不需要工具调用
        token_type=TokenType.DREAM_TASK,
        content=content,
        extra={"system_prompt": update_memory_prompt},
        workflow_id="daily-memory",
    )
    result = await bus.send(msg)
    llm_call_logger.log_call(
        msg,
        result,
        prompt_module=Prompts.Schedule.UPDATE_MEMORY.module,
        prompt_name=Prompts.Schedule.UPDATE_MEMORY.name,
    )
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
    next_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    start_time = build_local_datetime(date, DAILY_START_HOUR)
    end_time = build_local_datetime(next_date, DAILY_START_HOUR)
    logger.debug("[dreaming] 时间范围: %s ~ %s", start_time, end_time)

    # 阶段1: 获取用户活动数据并总结
    logger.info("[dreaming] 阶段1: 获取用户活动数据")
    activity_types = set(["high_usage_segments", "user_behavior_notes", "ai_behavior_notes"])
    logger.debug("[dreaming] 查询活动类型: %s", activity_types)

    # 工具函数接收 UTC ISO，本地时间就地转换（start_time/end_time 本身保持本地格式用于 prompt 注入）
    activities = query_user_activity_summary(
        activity_types,
        local_to_utc_iso(start_time),
        local_to_utc_iso(end_time),
    )
    logger.debug("[dreaming] 获取到活动数据长度: %s 字符", len(activities) if activities else 0)
    if activities:
        logger.debug("[dreaming] 活动数据前200字符: %s", activities[:200])

    logger.info("[dreaming] 阶段1: 总结活动数据")
    activities_summary_content = await summary_activities(activities, start_time, end_time)
    logger.debug(
        "[dreaming] 活动总结结果长度: %s 字符",
        len(activities_summary_content) if activities_summary_content else 0,
    )
    logger.debug(
        "[dreaming] 活动总结结果前200字符: %s",
        activities_summary_content[:200] if activities_summary_content else "无",
    )

    # 阶段2: 获取心情数据并总结
    logger.info("[dreaming] 阶段2: 获取心情数据")
    mood_data = get_mood_data(start_time, end_time)
    logger.debug("[dreaming] 获取到心情数据长度: %s 字符", len(mood_data) if mood_data else 0)
    if mood_data:
        logger.debug("[dreaming] 心情数据前200字符: %s", mood_data[:200])

    logger.info("[dreaming] 阶段2: 总结心情数据")
    mood_summary_content = await summary_moods(mood_data)
    logger.debug(
        "[dreaming] 心情总结结果长度: %s 字符",
        len(mood_summary_content) if mood_summary_content else 0,
    )
    logger.debug(
        "[dreaming] 心情总结结果前200字符: %s",
        mood_summary_content[:200] if mood_summary_content else "无",
    )

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


async def extract_from_chat_messages(messages: list[dict]) -> str | None:
    """提取已结束轮次的聊天投影，不消费旧 Session 或内部工具轨迹。"""
    if not messages:
        return None
    prompt = prompt_loader.load_prompt(Prompts.Schedule.EXTRACT_CHAT)
    display_messages = [
        {**message, "timestamp": utc_to_local_display(message["timestamp"])} for message in messages
    ]
    msg = InboundMessage(
        type=MessageType.GENERAL_TASK,
        token_type=TokenType.DREAM_TASK,
        workflow_id="chat-extraction",
        content=f"时区：{get_user_timezone()}\n## 需要总结的内容\n"
        + json.dumps(display_messages, ensure_ascii=False),
        extra={"system_prompt": prompt},
    )
    result = await bus.send(msg)
    if result.error:
        raise RuntimeError(result.error)
    if not result.response or not result.response.content or not result.response.content.strip():
        raise LLMResponseError("聊天信息提取返回空响应")
    llm_call_logger.log_call(
        msg,
        result,
        prompt_module=Prompts.Schedule.EXTRACT_CHAT.module,
        prompt_name=Prompts.Schedule.EXTRACT_CHAT.name,
    )
    content = result.response.content.strip()
    return None if content == "无可提取内容" else content


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
    """提取近期统一聊天目录的新轮次，保存历史后推进 meta.extra 游标。"""
    from lifeprism.llm.runtime import agent_runtime
    from lifeprism.llm.session import ChatHistoryManager

    if type(days_offset) is not int or days_offset < 0:
        raise ValueError("days_offset 必须为非负整数")
    # 同一进程的调度/手动调用互斥，避免多个历史管理器互相覆盖。
    if _session_processing_lock.locked():
        logger.info("[process_session_message] 已有任务执行，跳过本次")
        return
    async with _session_processing_lock:
        path = settings.lifeprism_data_path / "user/daily_data/chat_history.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        history_manager = ChatHistoryManager(path)

        def save_history(last_processed_time: datetime | None = None) -> None:
            """原子替换历史，写入失败时保留上一次完整文件。"""
            temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
            history_manager.path = temporary
            try:
                history_manager.save_history(last_processed_time)
                os.replace(temporary, path)
            finally:
                history_manager.path = path
                temporary.unlink(missing_ok=True)

        manager = agent_runtime.chat_sessions
        cutoff = datetime.now(UTC) - timedelta(days=days_offset)

        async def process_one(sid: str) -> None:
            """保存每个窗口；已持久化的历史允许游标提交失败后安全重试。"""

            async def save_window(messages: list[dict], start: int, end: int) -> None:
                covered = max(
                    (
                        item.get("end_turn", 0)
                        for item in history_manager.histories
                        if item.get("session_id") == sid
                    ),
                    default=0,
                )
                if covered >= end:
                    return
                if covered >= start:
                    messages = [message for message in messages if message["turn"] > covered]
                    start = covered + 1
                content = await extract_from_chat_messages(messages)
                history_manager.histories.append(
                    {
                        "timestamp": datetime.now(UTC).isoformat(),
                        "content": content or "",
                        "session_id": sid,
                        "start_turn": start,
                        "end_turn": end,
                    }
                )
                save_history()

            try:
                loaded = manager._read(sid)
                if loaded is None:
                    return
                meta, records = loaded
                # 业务游标不修改更新时间；日期筛选以对话记录时间为准。
                timestamp = records[-1]["timestamp"] if records else meta["updated_at"]
                updated = datetime.fromisoformat(timestamp)
                if updated.tzinfo is None:
                    raise ValueError("原生 Session 时间必须包含时区")
                if updated >= cutoff:
                    await manager.process_pending(sid, save_window)
            except Exception:
                logger.exception("[process_session_message] 会话提取失败: %s", sid)

        ids = [p.stem for p in agent_runtime.chat_session_folder.glob("*.jsonl")]
        for offset in range(0, len(ids), SESSION_BATCH_SIZE):
            await asyncio.gather(
                *(process_one(sid) for sid in ids[offset : offset + SESSION_BATCH_SIZE])
            )
        history = history_manager.get_histories_to_dream()
        date = get_local_today().isoformat()
        for item in history or []:
            item["behavior_date"] = date
        # 重建当天完整章节，避免第二次提取覆盖第一次，也让写入失败可重试。
        content = format_chat_history(
            [item for item in history_manager.histories if item.get("behavior_date") == date]
        )
        if history and content:
            write_date_md(
                settings.lifeprism_data_path / "user/daily_data/behavior.md",
                date,
                content,
                "聊天记录总结",
                mode="overwrite",
            )
        if history:
            save_history(datetime.now(UTC))


_session_processing_lock = asyncio.Lock()


if __name__ == "__main__":
    from datetime import timedelta

    from lifeprism.llm.runtime.worker import agent_loop

    async def main():
        loop_task = asyncio.create_task(agent_loop.loop())
        try:
            # mood_data = get_mood_data("2026-06-30 00:00:00", "2026-07-01 00:00:00")
            # await summary_moods(mood_data)
            await dreaming("2026-06-30")
        finally:
            loop_task.cancel()

    asyncio.run(main())
