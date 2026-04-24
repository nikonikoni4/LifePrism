"""截图语义分析模块

提供截图语义分析功能，通过 LLM 分析用户行为截图，识别用户在特定时间段的行为语义。

主要功能：
1. 获取高密度活动时间段
2. 将时间段切分为固定大小的 chunk
3. 查询每个 chunk 的 active 截图
4. 调用 LLM 分析截图语义
"""
import asyncio
import os
import base64
import mimetypes
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from lifeprism.llm.providers import LLMResponse
from lifeprism.llm.providers.dataset_providers import llm_dataset_provider
from lifeprism.llm.channel.manager import channel_manager
from lifeprism.llm.bus.events import MessageType
from lifeprism.config import settings
from lifeprism.utils import get_logger
from lifeprism.storage import raw_behavior_analysis_store
logger = get_logger(__name__)

# ==================== 常量配置 ====================

ANALYSIS_SYSTEM_PROMPT = """
## task
你需要依据用户的连续行为截图来判断用户在该时间段的行为语义。

## 核心原则

把精确度放在首位，宁愿不输出结果，也不要输出不确定的，过度推断的用户行为。

## 语义说明

1. 语义必须是具有内容的，而不能仅仅是描述行为：
   - 合理语义：'观看《老友记》电视剧'，编写读书笔记，修改xxbug，实现新功能
   - 不合理语义：在cursor界面编辑xx.py，使用claude code进行编码
2. 良好的语义是能够匹配用户的真实目的，具体查看《行为语义推断》章节
3. 输入的图片是一个时间段的截图，不一定仅仅只代表用户的一个行为，而可能是多个行为

## 行为语义推断

好的行为分析结果需要与用户目的进行匹配，有3种语义判断情况:
<语义推断情况1>
1. 触发场景：用户目标存在，且行为与用户目标强相关
2. 行为语义推断：行为语义需要是这个目标的细分语义阐述
3. 例子：用户的目标是阅读《XXX》，与目标窗口对应，那么行为语义就应该是查看《xxx》的<具体>章节
</语义推断情况1>

<语义推断情况2>
1. 触发场景：用户目标不存在，或行为与用户目标弱相关（需要经过超过2~3次逻辑推理转折才能和用户目标上联系上），不相关
2. 行为语义推断：需要放弃与目标结合判断，专注于具体截图以及截图变化趋势判断行为语义
3. 例子：用户正在使用AI工具查询某些内容，但是这个内容可能与目标没有直接关联，就不能强行绑定用户为了实现什么目标而利用ai工具查询内容
</语义推断情况2>

<语义推断情况3>
1. 触发场景：在语义推断情况2的基础上，所给出的行为语义判断过于模糊，详情见规则中的不要做的事情，第2和3条
2. 行为语义推断：需要放弃该条行为的输出，遵守核心规则：宁愿不输出结果，也不要输出不确定的，过度推断的用户行为
3. 例子：截图中app所在窗口仅存在一些文字，无法聚焦用户的行为。比如显示cursor中一个脚本内容，但是前后截图该脚本内容无变化或不相关，无法判断用户在该内容做了什么动作，就不要输出行为，不要输出"用户在cursor编辑xx.py"等内容
</语义推断情况3>

## 语义识别步骤
<执行步骤>
1. 首先匹配每张截图用户实际使用的窗口：通过每张截图给出的附加信息app和title进行窗口定位
2. 识别窗口内容，如果识别到用户正在打字，关注窗口输入框打字内容
3. 将不同时间的窗口内容按照时间顺序排序，依据窗口内容变化，结合用户目标，判断用户的行为，具体判断情况见《行为语义推断》章节
4. 将相同语义内容进行合并推理
5. 自行审查，判断输出内容是否符合规则和输出契约
</执行步骤>


## 规则

<不要做的事情>
    1. 不要输出用户能力相关的行为和总结，比如"文档内容具有技术深度"，"整体行为体现专注度"
    2. 不要输出"相关"等模糊词语，比如不能出现："用户正在修改相关bug"，应该为用户正在修复X模块bug。如果结果不清晰宁愿不输出也不要给出模糊信息
    3. 不要给出只从app和title就能判断的语义：比如，app:cursor title: xx.py "使用cursor编辑xx.py"。这种语义太过模糊。
</不要做的事情>
<需要做的事情>
    若所有截图都无法判断行为，直接输出：None
</需要做的事情>

## 输出契约
直接输出用户行为
例子：
1. 当有行为判断时:
用户在查看openai的harness engineering博客, 用户在查看claude的harness engineering博客, 用户在观看《老友记》
2. 当无行为判断时:
None

"""

DENSITY_THRESHOLD = 0.6
MIN_DURATION_MINUTES = 6
CHUNK_MINUTES = 15

# ==================== 辅助函数 ====================

def get_todolist(start_date: str, end_date: str) -> Optional[str]:
    """获取指定日期范围的 TodoList 并格式化为结构化文本

    Args:
        start_date: 开始日期（YYYY-MM-DD 格式）
        end_date: 结束日期（YYYY-MM-DD 格式）

    Returns:
        Optional[str]: 格式化的目标文本，如果没有任务则返回 None

    Example:
        >>> text = get_todolist("2026-04-21", "2026-04-21")
        >>> print(text)
        ## 目标：
        1. 完成《复利效应》的笔记
        2. 完成 feat_monitor 监控功能开发
        3. 修复 habit 模块 bug：习惯界面链条时间计算有问题
    """
    try:
        todos = llm_dataset_provider.query_todos(
            start_date=start_date,
            end_date=end_date,
            include_cross_day=True
        )

        active_todos = [
            todo for todo in todos
            if todo.get("state") in ("active", "scheduled")
        ]

        if not active_todos:
            return None

        # 判断是否跨天
        is_single_day = (start_date == end_date)
        header = "## 今日目标：" if is_single_day else f"## 目标（{start_date} ~ {end_date}）："

        lines = [header, ""]
        for i, todo in enumerate(active_todos, 1):
            content = todo.get("content", "").strip()
            if content:
                lines.append(f"{i}. {content}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"获取 TodoList 失败: {e}", exc_info=True)
        return None


def split_segment_into_chunks(segment: Dict[str, str], chunk_minutes: int) -> List[Dict[str, str]]:
    """将一个时间段切分为固定大小的 chunk

    Args:
        segment: 时间段字典，包含 start 和 end 键
        chunk_minutes: 每个 chunk 的分钟数

    Returns:
        List[Dict[str, str]]: chunk 列表，每项包含 start 和 end
    """
    start_dt = datetime.fromisoformat(segment["start"])
    end_dt = datetime.fromisoformat(segment["end"])
    chunk_delta = timedelta(minutes=chunk_minutes)

    chunks = []
    cursor = start_dt

    while cursor < end_dt:
        chunk_end = min(cursor + chunk_delta, end_dt)
        chunks.append({
            "start": cursor.isoformat(),
            "end": chunk_end.isoformat(),
        })
        cursor = chunk_end

    return chunks


def get_active_screenshots(seg_start: str, seg_end: str) -> List[Dict[str, Any]]:
    """获取指定时间范围内的 active 截图

    Args:
        seg_start: 开始时间（ISO 格式）
        seg_end: 结束时间（ISO 格式）

    Returns:
        List[Dict[str, Any]]: 截图列表
    """
    return llm_dataset_provider.query_screenshots(
        start_time=seg_start,
        end_time=seg_end,
        capture_reason='active'
    )


def encode_image_to_base64(file_path: str) -> Optional[str]:
    """将图片编码为 base64 data URL

    Args:
        file_path: 图片相对路径（相对于 lifeprism_data_path）

    Returns:
        Optional[str]: base64 data URL，失败返回 None
    """
    try:
        full_path = os.path.join(settings.lifeprism_data_path, file_path)
        mime_type, _ = mimetypes.guess_type(full_path)
        mime_type = mime_type or "image/png"

        with open(full_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")

        return f"data:{mime_type};base64,{b64_data}"
    except Exception as e:
        logger.warning(f"读取图片失败 {file_path}: {e}")
        return None


# ==================== 核心函数 ====================

async def analyze_chunk_screenshots(
    chunk: Dict[str, str],
    screenshots: List[Dict[str, Any]],
    todolist: Optional[str] = None
) -> Optional[RawBehaviorAnalysisItem]:
    """分析单个 chunk 的截图语义

    Args:
        chunk: 时间段字典，包含 start 和 end
        screenshots: 截图列表
        todolist: 用户今日目标文本（可选）

    Returns:
        Optional[RawBehaviorAnalysisItem]: LLM 分析结果，失败返回 None
    """
    if not screenshots:
        return None

    # 准备图片消息
    content_parts = []
    for sc in screenshots:
        app = sc.get("window_app", "")
        title = sc.get("window_title", "")[:50]
        captured_at = sc.get("captured_at", "")

        b64 = encode_image_to_base64(sc["file_path"])
        if b64:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": b64}
            })
            content_parts.append({
                "type": "text",
                "text": f"[{captured_at}] app: {app} | title: {title}"
            })

    if not any(p.get("type") == "image_url" for p in content_parts):
        return None

    # 构建 user content
    user_content: List[Dict[str, str]] = []
    if todolist:
        user_content.append({"type": "text", "text": todolist.strip()})
    user_content.append({
        "type": "text",
        "text": f"时间范围: {chunk['start']} -> {chunk['end']}",
    })
    user_content.extend(content_parts)


    try:
        response :str= await channel_manager.send(
            content = user_content,
            type = MessageType.GENERAL_TASK,
            extra = {'ANALYSIS_SYSTEM_PROMPT' : ANALYSIS_SYSTEM_PROMPT })

        if response:
            data = {
                'start_time' : chunk['start'],
                'end_time' : chunk['end'],
                'screenshot_count' : len(screenshots),
                'behavior' : f"{chunk['start']} ~ {chunk['end']}\n behavior: {response} \n"
            }
            
            raw_behavior_analysis_store.create_raw_behavior(data)
            return data 
        else:
            return None
    except Exception as e:
        logger.error(f"LLM 调用失败: {e}", exc_info=True)
        return None


async def screenshot_analysis(
    start_time: str,
    end_time: str,
    todolist: str,
    density_threshold: float = DENSITY_THRESHOLD,
    min_duration_minutes: int = MIN_DURATION_MINUTES,
    chunk_minutes: int = CHUNK_MINUTES
) -> List[Dict[str, Any]]:
    """分析指定时间段的截图语义

    步骤：
    1. 获取高密度时间段（复用时间密度分割）
    2. 将高密度时间段以指定分钟数进行切分
    3. 对每个 chunk 查询 active 截图
    4. 调用 LLM 分析截图语义

    Args:
        start_time: 开始时间（YYYY-MM-DD HH:MM:SS 格式）
        end_time: 结束时间（YYYY-MM-DD HH:MM:SS 格式）
        todolist: 用户目标列表文本
        density_threshold: 密度阈值（默认 0.6）
        min_duration_minutes: 最小时长（默认 6 分钟）
        chunk_minutes: chunk 大小（默认 15 分钟）

    Returns:
        List[Dict[str, Any]]: 分析结果列表，每项包含：
            - start_time: 开始时间（YYYY-MM-DD HH:MM:SS 格式）
            - end_time: 结束时间（YYYY-MM-DD HH:MM:SS 格式）
            - screenshot_count: 截图数量
            - behavior: 分析结果
    """
    logger.info(f"开始截图语义分析: {start_time} -> {end_time}")

    # Step 1: 查询活动日志
    logs, total = llm_dataset_provider.get_activity_logs(start_time=start_time, end_time=end_time)
    logger.info(f"查询到 {total} 条行为记录")

    adapted_logs = []
    for log in logs:
        adapted_logs.append({
            "start_time": log["start_time"],
            "end_time": log["end_time"],
            "duration": log.get("duration", 0),
            "app": log.get("app", ""),
            "title": log.get("title", ""),
        })

    # Step 2: 获取高密度时间段
    from lifeprism.llm.utils.density_utils import build_time_segments
    high_density_segments = build_time_segments(
        logs=adapted_logs,
        range_start=start_time,
        range_end=end_time,
        threshold=density_threshold,
        min_duration_minutes=min_duration_minutes,
        segment_type="active",
        bucket_minutes=10,  # 与原来的 TIME_BUCKET_MINUTES 保持一致
        max_bridge_buckets=1,  # 与原来的 MAX_BRIDGE_BUCKETS 保持一致
    )
    logger.info(f"获取到 {len(high_density_segments)} 个高密度时间段")

    # Step 3: 切分为 chunk
    all_chunks = []
    for seg in high_density_segments:
        chunks = split_segment_into_chunks(seg, chunk_minutes)
        all_chunks.extend(chunks)
    logger.info(f"切分为 {len(all_chunks)} 个 {chunk_minutes} 分钟块")

    # Step 4: 分析每个 chunk
    results = []
    pending_chunks: List[Dict[str, Any]] = []
    analysis_tasks = []
    for i, chunk in enumerate(all_chunks, 1):
        chunk_start = chunk["start"]
        chunk_end = chunk["end"]

        screenshots = get_active_screenshots(chunk_start, chunk_end)
        screenshot_count = len(screenshots)

        logger.debug(
            f"[{i}/{len(all_chunks)}] {chunk_start} -> {chunk_end}, "
            f"截图数量: {screenshot_count}"
        )

        if not screenshots:
            continue

        pending_chunks.append({
            "chunk": chunk,
            "screenshot_count": screenshot_count,
        })
        analysis_tasks.append(
            analyze_chunk_screenshots(chunk, screenshots, todolist)
        )

    if analysis_tasks:
        analysis_results = await asyncio.gather(*analysis_tasks)
        for analysis_result in analysis_results:
            if analysis_result:
                results.append(analysis_result)

    logger.info(f"截图语义分析完成，共分析 {len(results)} 个 chunk")
    return results


async def behavior_summary(bahaviors : str,todolist:str)->str:
    """
    对输入的行为内容进行总结
    args ：
        todolist : 用户今日目标文本（可选）
        bahaviors : 输入的行为
    return :
        行为总结json字符串
        包含字段：
        - behavior_summary : 行为总结，不超过150字
        - title : 行为标题，对于行为的极致压缩，不超过30个字（一个英文单词算一个字符）
    """
    if not bahaviors:
        raise ValueError("输入行为为空")
    SUMMARY_SYSTEM_PROMPT = """
    ## task 
    你需要对输入的用户行为进行总结

    ## 需要做的事情
    1. 输入内容如果包含相似、重复的内容需要合理合并
    2. 输入的内容如果包含逻辑关系，可以进行合理推理，比如用户先编写xx计划，然后执行xx计划等
    3. 如果所做的事情与用户的目标相关，需要结合目标进行说明。但不能直接说在进行xx目标，而是要结合具体行为和目标关系说明

    ## 不要做的事情
    1. 不要简单重复输入内容中已经有点内容
    2. 输出不要超过200字
    3. 输出中不要直接包含“用户”等主语
    4. 不要使用“完成了”等字眼，因为仅凭输入是无法判断是否完成了某项工作（即使输入的行为包含“完成”类似的语义也不能在总结中输出“完成”），只描述做了什么内容，而不是完成了什么
    
    ## 输入说明
    输入行为的顺序就是真实动作的时间顺序

    ## 输出契约
    输出json数据,包含字段:
    - behavior_summary : 行为总结，不超过150字
    - title : 行为标题，对于行为的极致压缩，不超过30个字（一个英文单词算一个字符）
    输出示例：
    {
        "behavior_summary" : "完成了habit模块习惯界面链条时间计算bug的全流程修复开发工作，期间穿插查看AI对 心理学概念的解析，并在思源笔记中编写整理《复利效应》的相关读书笔记",
        "title" : ”进行habit习惯链条bug修复与复利效应笔记编写“
    }
    
    """
    user_prompt_parts = []
    if todolist :
        user_prompt_parts.append(
            f"""
            ## 用户目标
            {todolist}
            """
        )
    user_prompt_parts.append(
        f"""
        ## 用户行为
        {bahaviors}
        """
    )
    user_prompt = "\n".join(user_prompt_parts)
    

    try:
        response = await channel_manager.send(
            content=user_prompt,
            type=MessageType.GENERAL_TASK,
            extra={"system_prompt": SUMMARY_SYSTEM_PROMPT},
        )
        return response if response else ""
    except Exception as e:
        logger.error(f"行为总结调用失败: {e}", exc_info=True)
        return ""
if __name__ == "__main__":
    from lifeprism.llm.agent.loop import agent_loop
    import asyncio
    
    async def main():
        loop_task = asyncio.create_task(agent_loop.loop())
        # logger.info("[STARTUP] AgentLoop started") # logger is not imported in this file
        response = await screenshot_analysis("2026-04-19 11:00:00","2026-04-19 11:15:00")
        print(response)
        loop_task.cancel() # Cancel the loop task when done to exit cleanly
        
    asyncio.run(main())
