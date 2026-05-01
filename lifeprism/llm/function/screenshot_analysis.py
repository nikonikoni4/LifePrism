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
import json
from lifeprism.llm.utils.parse_utils import extract_json_from_response
from lifeprism.llm.bus import OutboundMessage, bus, MessageType, InboundMessage
from lifeprism.config import settings
from lifeprism.utils import get_logger,DEBUG
from lifeprism.llm.providers.dataset_providers import llm_dataset_provider
from lifeprism.repository import (
    map_cache_repository,
    raw_behavior_analysis_repository, 
    behavior_analysis_repository,
    category_repository,
    QueryOptions,
    screen_capture_repository,
)
logger = get_logger(__name__)
logger.setLevel(DEBUG)

# logger.setLevel(DEBUG)
# ==================== 常量配置 ====================

ANALYSIS_SYSTEM_PROMPT = """
## task
你需要依据用户的连续行为截图来判断用户在该时间段的行为语义。

## 核心原则

1. **精确度优先**：宁愿不输出结果，也不要输出不确定的、过度推断的用户行为
2. **基于截图内容**：必须严格基于实际截图内容进行分析，不要受输出示例的具体内容影响
3. **独立判断**：每次分析都是独立的，不要套用任何模板或历史案例

## 语义说明

1. 语义必须是具有内容的，而不能仅仅是描述行为：
   - 合理语义：'观看《老友记》电视剧'，编写读书笔记，修改xxbug，实现新功能
   - 不合理语义：在cursor界面编辑xx.py，使用claude code进行编码
2. 良好的语义是能够匹配用户的真实目的，具体查看《行为语义推断》章节
3. 输入的图片是一个时间段的截图，不一定仅仅只代表用户的一个行为，而可能是多个行为

## 行为语义推断

好的行为分析结果需要与用户目的进行匹配，有3种语义判断情况:
### 情况1
1. 触发场景：用户目标存在，且行为与用户目标强相关
2. 行为语义推断：行为语义需要是这个目标的细分语义阐述
3. 例子：用户的目标是阅读《XXX》，与目标窗口对应，那么行为语义就应该是查看《xxx》的<具体>章节

### 情况2
1. 触发场景：用户目标不存在，或行为与用户目标弱相关（需要经过超过2~3次逻辑推理转折才能和用户目标上联系上），不相关
2. 行为语义推断：需要放弃与目标结合判断，专注于具体截图以及截图变化趋势判断行为语义
3. 例子：用户正在使用AI工具查询某些内容，但是这个内容可能与目标没有直接关联，就不能强行绑定用户为了实现什么目标而利用ai工具查询内容

### 情况3
1. 触发场景：在语义推断情况2的基础上，所给出的行为语义判断过于模糊，详情见规则中的不要做的事情，第2和3条
2. 行为语义推断：需要放弃该条行为的输出，遵守核心规则：宁愿不输出结果，也不要输出不确定的，过度推断的用户行为
3. 例子：截图中app所在窗口仅存在一些文字，无法聚焦用户的行为。比如显示cursor中一个脚本内容，但是前后截图该脚本内容无变化或不相关，无法判断用户在该内容做了什么动作，就不要输出行为，不要输出"用户在cursor编辑xx.py"等内容


## 语义识别步骤
<执行步骤>
1. 首先匹配每张截图用户实际使用的窗口：通过每张截图给出的附加信息app和title进行窗口定位
2. 识别窗口内容，如果识别到用户正在打字，关注窗口输入框打字内容
3. 将不同时间的窗口内容按照时间顺序排序，依据窗口内容变化，结合用户目标，判断用户的行为，具体判断情况见《行为语义推断》章节
4. 将相同语义内容进行合并推理
5. 自行审查，判断输出内容是否符合规则和输出契约
</执行步骤>


## 规则

### 不要做的事情
    1. 不要输出用户能力相关的行为和总结，比如"文档内容具有技术深度"，"整体行为体现专注度"
    2. 不要输出"相关"等模糊词语，比如不能出现："用户正在修改相关bug"，应该为用户正在修复X模块bug。如果结果不清晰宁愿不输出也不要给出模糊信息
    3. 不要给出只从app和title就能判断的语义：比如，app:cursor title: xx.py "使用cursor编辑xx.py"。这种语义太过模糊。
    4. 不要在输出中引用截图信息，比如见截图1等，你需要的是说明用户行为
    5. 不要在输出中包含具体的时间



## 输入说明

1. 每张截图对应着一个文本描述，会传入截图时间,截图时使用的app名称以及app的标题，以及这个文本描述对应的图片id（与图片传入顺序对应）
2. **特殊情况**:当传入[无截图]时，意味着这个文本没有图片对应，需要根据文本描述判断行为即可

## 输出契约

**严格输出格式要求**：
- 当能够判断行为时：使用数字编号（1. 2. 3. ...）分点列出，每条行为独立成行
- **只输出行为列表**：严格按照数字编号格式输出，不要有任何其他内容


"""

DENSITY_THRESHOLD = 0.6
MIN_DURATION_MINUTES = 6
CHUNK_MINUTES = 15

# ==================== 辅助函数 ====================

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
    return screen_capture_repository.query_screenshots(
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

def _get_screenshot_category_info(app: str, title: str) -> Dict[str, Any]:
    """获取截图的分类信息（一次查询获取所有需要的信息）

    Args:
        app: 应用名称
        title: 窗口标题

    Returns:
        Dict[str, Any]: 包含以下字段的字典
            - category_id: 分类 ID（可能为 None）
            - category_name: 分类名称（仅在被忽略时查询）
            - app_description: 应用描述
            - is_ignored: 是否应该被忽略
    """
    try:
        # 1. 判断是否为多用途应用
        is_multi = settings.is_multi_purpose_app(app)

        # 2. 一次查询获取 category_id 和 app_description
        category_id = None
        app_description = ""

        if is_multi:
            # 从 multi_purpose_map_cache 查找
            result, _ = map_cache_repository.query_multi_purpose_map_cache(
                QueryOptions(filters={"app": app, "title": title}, fields=["category_id", "app_description"])
            )
            if result:
                category_id = result[0].get("category_id")
                app_description = result[0].get("app_description", "")
        else:
            # 从 single_purpose_map_cache 查找
            result, _ = map_cache_repository.query_single_purpose_map_cache(
                QueryOptions(filters={"app": app}, fields=["category_id", "app_description"])
            )
            if result:
                category_id = result[0].get("category_id")
                app_description = result[0].get("app_description", "")

        # 3. 判断是否应该被忽略
        ignore_categories_id = settings.get("screen_analysis_ignore", [])
        is_ignored = category_id in ignore_categories_id if category_id else False

        # 4. 只在被忽略时才查询分类名称（延迟查询优化）
        category_name = None
        if is_ignored and category_id:
            category_info = category_repository.get_category_by_id(category_id)
            if category_info:
                category_name = category_info.get("name", "未分类")
            else:
                category_name = "未分类"

        return {
            "category_id": category_id,
            "category_name": category_name,  # 可能为 None（不被忽略时）
            "app_description": app_description,
            "is_ignored": is_ignored
        }

    except Exception as e:
        logger.warning(f"获取截图分类信息失败 (app={app}, title={title}): {e}")
        return {
            "category_id": None,
            "category_name": None,
            "app_description": "",
            "is_ignored": False
        }




def _is_image_screenshot(image_path_list: list[str]) -> bool:
    """判断是否为无图片截图

    Args:
        screenshots: 截图列表

    Returns:
        bool: True 表示有图片截图，False 表示无图片截图
    """
    # 转化为path，并判断是否存在图片
    for path in image_path_list:
        full_path = os.path.join(settings.lifeprism_data_path, path)
        if os.path.exists(full_path):
            # 图片存在，返回True
            return True
    # 所有图片都不存在，返回False
    return False
def _clean_llm_response(response: str) -> str:
    """清理 LLM 响应中的 Markdown 格式和多余内容

    Args:
        response: LLM 原始响应

    Returns:
        str: 清理后的纯文本响应
    """
    if not response or response.strip() == "None":
        return response

    lines = response.split('\n')
    cleaned_lines = []

    for line in lines:
        line = line.strip()

        # 跳过空行
        if not line:
            continue

        # 跳过 Markdown 标题行（以 # 开头）
        if line.startswith('#'):
            continue

        # 跳过分隔线
        if line.startswith('---') or line.startswith('==='):
            continue

        # 跳过表格行（包含 | 符号）
        if '|' in line and line.count('|') >= 2:
            continue

        # 跳过代码块标记
        if line.startswith('```'):
            continue

        # 移除加粗标记 **text**
        line = line.replace('**', '')

        # 移除斜体标记 *text*
        line = line.replace('*', '')

        # 移除代码标记 `code`
        line = line.replace('`', '')

        # 只保留以数字开头的行（行为列表）
        if line and line[0].isdigit() and '. ' in line:
            cleaned_lines.append(line)

    # 如果清理后没有有效行，返回 None
    if not cleaned_lines:
        return "None"

    return '\n'.join(cleaned_lines)


# ==================== 核心函数 ====================

async def analyze_chunk_screenshots(
    chunk: Dict[str, str],
    screenshots: List[Dict[str, Any]],
    todolist: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """分析单个 chunk 的截图语义

    Args:
        chunk: 时间段字典，包含 start 和 end
        screenshots: 截图列表
        todolist: 用户今日目标文本（可选）

    Returns:
        Optional[Dict[str, Any]]: LLM 分析结果，失败返回 None
    """
    if not screenshots:
        return None
    if not _is_image_screenshot([sc["file_path"] for sc in screenshots]):
        # 所有截图都不存在，返回None
        return None
    # 准备图片消息
    content_parts = []
    img_idx = 1
    first_app_screenshots = set()  # 记录已出现的 app

    for sc in screenshots:
        app = sc.get("window_app", "")
        title = sc.get("window_title", "")[:50]
        captured_at = sc.get("captured_at", "")

        # 一次查询获取所有分类信息（包括是否忽略）
        category_info = _get_screenshot_category_info(app, title)

        # 判断是否忽略该截图
        if category_info["is_ignored"]:
            # 判断是否是该 app 的第一张截图
            is_first_screenshot = app not in first_app_screenshots
            is_first_screenshot = False # 暂时不保留第一张截图
            if is_first_screenshot:
                # 第一张截图：保留图片
                first_app_screenshots.add(app)
                b64 = encode_image_to_base64(sc["file_path"])
                if b64:
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": b64}
                    })
                    content_parts.append({
                        "type": "text",
                        "text": f"[{img_idx}] | timestamp: {captured_at} app: {app} | title: {title}"
                    })
                    logger.debug(f"[{img_idx}] | timestamp: {captured_at} app: {app} | title: {title} (首张截图，保留)")
                    img_idx += 1
            else:
                # 非第一张截图：用文字替换
                logger.debug(f"截图 {sc['file_path']} 被忽略，app: {app}")
                category_name = category_info['category_name'] or "未分类"
                content_parts.append({
                    "type": "text",
                    "text": f"[无截图] timestamp: {captured_at} | app: {app} | title: {title} | category: {category_name} | description: {category_info['app_description']}"
                })
                logger.debug(f"[无截图] timestamp: {captured_at} | app: {app} | title: {title} | category: {category_name} | description: {category_info['app_description']}")
            continue

        # 不忽略，正常处理图片
        first_app_screenshots.add(app)  # 记录该 app 已出现
        b64 = encode_image_to_base64(sc["file_path"])
        if b64:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": b64}
            })
            content_parts.append({
                "type": "text",
                "text": f"[{img_idx}] | timestamp: {captured_at} app: {app} | title: {title}"
            })
            logger.debug(f"[{img_idx}] | timestamp: {captured_at} app: {app} | title: {title}")
            img_idx += 1

    # 构建 user content
    user_content: List[Dict[str, str]] = []
    if todolist:
        user_content.append({"type": "text", "text": todolist})

    user_content.extend(content_parts)


    try:
        msg = InboundMessage(
            content=user_content,
            type=MessageType.GENERAL_TASK,
            extra={'system_prompt' : ANALYSIS_SYSTEM_PROMPT}
        )
        response :OutboundMessage = await bus.send(msg)
        response = response.response.content

        if response:
            # 清理 LLM 响应中的 Markdown 格式
            cleaned_response = _clean_llm_response(response)

            # 写入数据库前，将 ISO 格式（带 T）转换为数据库格式（空格分隔）
            start_time_db = chunk['start'].replace('T', ' ')
            end_time_db = chunk['end'].replace('T', ' ')

            data = {
                'start_time' : start_time_db,
                'end_time' : end_time_db,
                'screen_count' : len(screenshots),
                'behavior' : f"{start_time_db} ~ {end_time_db}\n behavior: {cleaned_response} \n"
            }

            raw_behavior_analysis_repository.create_raw_behavior(data)
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
            - screen_count: 截图数量
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
    logger.info(f"获取到 {len(high_density_segments)} 个高密度时间段, {high_density_segments}")

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
        screen_count = len(screenshots)

        logger.info(
            f"[{i}/{len(all_chunks)}] {chunk_start} -> {chunk_end}, "
            f"截图数量: {screen_count}"
        )

        if not screenshots:
            continue

        pending_chunks.append({
            "chunk": chunk,
            "screen_count": screen_count,
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


async def _behavior_summary(start_time:str,end_time:str,screen_count:int,behavior : str,todolist:str)->dict[str,Any]:
    """
    对输入的行为内容进行总结
    args ：
        start_time : 开始时间（YYYY-MM-DD HH:MM:SS 格式）
        end_time : 结束时间（YYYY-MM-DD HH:MM:SS 格式）
        screen_count : 截图数量
        todolist : 用户今日目标文本（可选）
        behavior : 输入的行为
    return :
        行为总结json字符串
        包含字段：
        - behavior_summary : 行为总结，不超过150字
        - title : 行为标题，对于行为的极致压缩，不超过30个字（一个英文单词算一个字符）
    """
    if not behavior:
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
    3. 输出中不要直接包含“用户”等主语
    4. 不要使用“完成了”等字眼，只描述做了什么内容，而不是完成了什么
    5. 不要在总结中出现具体时间，输入的时间只作为动作顺序参考，不作为总结的内容
    6. 不要编造用户行为，需要基于实际输入的行为内容进行总结。


    ## 输出契约

    **输出格式**：JSON 对象，包含以下字段
    - behavior_summary : 行为总结，不超过150字
    - title : 行为标题，对于行为的极致压缩，不超过30个字（一个英文单词算一个字符）

    一下的示例仅供参考，真实内容需要依据输入的行为内容进行总结。
    **正确的输出示例**：
    {
        "behavior_summary" : "阅读 FastAPI 官方文档的异步编程章节，在 api_service.py 中重构用户认证接口，将同步调用改为异步实现",
        "title" : "重构用户认证接口为异步实现"
    }

    **错误的输出示例**（不要这样输出）：
    {
        "behavior_summary" : "完成了相关功能的开发工作",  // 过于笼统，缺少具体内容
        "title" : "开发工作"  // 没有说明具体做了什么
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
        {behavior}
        """
    )
    user_prompt = "\n".join(user_prompt_parts)
    

    try:
        msg = InboundMessage(
            content=user_prompt,
            type=MessageType.GENERAL_TASK,
            extra={"system_prompt": SUMMARY_SYSTEM_PROMPT},
        )
        response :OutboundMessage = await bus.send(msg)
        response = response.response.content
        if response:
            # 解析json字符串
           
            response = extract_json_from_response(response)
            data : dict = json.loads(response)
            if "behavior_summary" in data and "title" in data:
                # 写入数据库前，将 ISO 格式（带 T）转换为数据库格式（空格分隔）
                start_time_db = start_time.replace('T', ' ') if 'T' in start_time else start_time
                end_time_db = end_time.replace('T', ' ') if 'T' in end_time else end_time

                # 存入数据库 start_time, end_time, behavior, behavior_summary, title, screen_count
                data["screen_count"] = screen_count
                data["behavior"] = behavior
                data["start_time"] = start_time_db
                data["end_time"] = end_time_db
                behavior_analysis_repository.create_behavior(
                    data=data,
                )
                return data
            else:
                raise ValueError(f"截图分析行为总结-llm输出字段错误:{data.keys()}")
            
        else:
            raise ValueError("截图分析行为总结-llm输出为空")
       
    except json.JSONDecodeError:
        logger.error(f"截图分析行为总结-json解析失败: {response}")
        return None

def merage_results_list(analysis_results_list : list[dict[str,Any]])->list[dict[str,Any]]:
    """ 对相邻的结果进行合并"""
    if not analysis_results_list:
        return []

    merged_results = []
    for i in range(len(analysis_results_list)):
        if i == 0 or analysis_results_list[i]['start_time'] != merged_results[-1]['end_time']:
            merged_results.append(analysis_results_list[i])
        else:
            merged_results[-1]['screen_count'] += analysis_results_list[i]['screen_count']
            merged_results[-1]['behavior'] += analysis_results_list[i]['behavior']
            merged_results[-1]['end_time'] = analysis_results_list[i]['end_time']
    return merged_results
async def screenshot_behavior_summary( analysis_results_list : list[dict[str,Any]], todolist: str = "")->list[dict[str,str]]:
    """
    对单个chuck分析进行合并总结
    args:
        analysis_start_time: 分析开始时间，格式为YYYY-MM-DD HH:MM:SS
        analysis_end_time: 分析结束时间，格式为YYYY-MM-DD HH:MM:SS
        analysis_results_list: 分析结果列表，每个元素为一个字典，包含字段:
        - start_time: 开始时间，格式为YYYY-MM-DD HH:MM:SS
        - end_time: 结束时间，格式为YYYY-MM-DD HH:MM:SS
        - screen_count: 截图数量
        - behavior: 行为描述
        todolist: 用户目标
        
    return:
        合并后的分析结果列表，每个元素为一个字典，包含字段:
        - start_time: 开始时间，格式为YYYY-MM-DD HH:MM:SS
        - end_time: 结束时间，格式为YYYY-MM-DD HH:MM:SS
        - screen_count: 截图数量
        - behavior: 行为描述
        - behavior_summary: 行为总结
        - title: 行为标题
    """

    # 合并连续的时间段
    merged_results = merage_results_list(analysis_results_list)
    # 进行总结
    task_list = []
    for result in merged_results:
        task_list.append(
            _behavior_summary(
                start_time=result['start_time'],
                end_time=result['end_time'],
                behavior=result['behavior'],
                screen_count=result['screen_count'],
                todolist=todolist,
            )
        )
    summary_results = await asyncio.gather(*task_list)
    # 过滤掉None值
    summary_results = [result for result in summary_results if result is not None]
    return summary_results



if __name__ == "__main__":
    # from lifeprism.llm.agent.loop import agent_loop
    # import asyncio
    # todolist = ""
    # async def main():
    #     loop_task = asyncio.create_task(agent_loop.loop())
    #     # logger.info("[STARTUP] AgentLoop started") # logger is not imported in this file
    #     response = await screenshot_analysis("2026-04-20 02:45:00","2026-04-20 03:00:00",todolist)
    #     print(response)
    #     loop_task.cancel() # Cancel the loop task when done to exit cleanly
        
    # asyncio.run(main())
    raw_results,_ = raw_behavior_analysis_repository.query_raw_behaviors(QueryOptions(time_range=("2026-04-28 12:00:05","2026-04-28 17:05:00")))
    merged_results = merage_results_list(raw_results)
    for result in raw_results:
        print(f"{result['start_time']}~{result['end_time']}")
        
    
    for result in merged_results:
        print("="*20)
        print(f"{result['start_time']}~{result['end_time']}")

        print("="*20)


    print('2026-04-28 12:15:05' == '2026-04-28 12:15:05')