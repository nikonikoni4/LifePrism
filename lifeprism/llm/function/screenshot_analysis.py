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
from lifeprism.llm.exceptions import LLMResponseError, LLMOutputParseError
from lifeprism.llm.utils.parse_utils import extract_json_from_response
from lifeprism.llm.bus import OutboundMessage, bus, MessageType, InboundMessage
from lifeprism.config import settings
from lifeprism.utils import get_logger,DEBUG
from lifeprism.llm.prompts import prompt_loader, Prompts
from lifeprism.repository import (
    map_cache_repository,
    raw_behavior_analysis_repository,
    behavior_analysis_repository,
    category_repository,
    QueryOptions,
    screen_capture_repository,
    LWBaseDataProvider,
)
logger = get_logger(__name__)
# logger.setLevel(DEBUG)

# logger.setLevel(DEBUG)
# ==================== 常量配置 ====================

DENSITY_THRESHOLD = 0.6
MIN_DURATION_MINUTES = 6
MAX_SCREENSHOTS_PER_CHUNK = 9  # Doubao Seed 2.0 Lite 最多支持 9 张图片

# 根据截图频率等级动态设置 chunk 大小（分钟）
# 计算依据：first_active_after_seconds + 12秒segment冷却 = 单张截图周期
# 9张图片 × 单张周期 + 20%余量
CHUNK_MINUTES_BY_LEVEL = {
    1: 12,  # 低频：(60s + 12s) × 9 ≈ 10.8分钟 + 余量
    2: 10,  # 中频：(45s + 12s) × 9 ≈ 8.55分钟 + 余量
    3: 8,   # 高频：(30s + 12s) × 9 ≈ 6.3分钟 + 余量
}

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
        full_path = settings.lifeprism_data_path / file_path
        mime_type, _ = mimetypes.guess_type(str(full_path))
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
        full_path = settings.lifeprism_data_path / path
        if full_path.exists():
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

    # 限制截图数量，直接截断
    if len(screenshots) > MAX_SCREENSHOTS_PER_CHUNK:
        screenshots = screenshots[:MAX_SCREENSHOTS_PER_CHUNK]
        logger.warning(f"截图数量超过 {MAX_SCREENSHOTS_PER_CHUNK}，已截断至 {len(screenshots)} 张")

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
        # 加载截图分析 prompt
        analysis_prompt = prompt_loader.load_prompt(Prompts.Schedule.SCREENSHOT_ANALYSIS)

        msg = InboundMessage(
            content=user_content,
            type=MessageType.GENERAL_TASK,
            extra={'system_prompt' : analysis_prompt}
        )
        llm_result :OutboundMessage = await bus.send(msg)
        response_content = llm_result.response.content

        if response_content:
            # 清理 LLM 响应中的 Markdown 格式
            # cleaned_response = _clean_llm_response(response_content)
            cleaned_response = response_content
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
            logger.error(
                "截图分析 LLM 返回空内容: chunk_start=%s, chunk_end=%s, model=%s",
                chunk['start'], chunk['end'], settings.model
            )
            raise LLMResponseError(
                model=settings.model,
                raw_response="(empty response)"
            )
    except ValueError as e:
        logger.error(f"截图分析参数错误: chunk={chunk}, error={e}")
        raise
    except LLMResponseError:
        raise
    except Exception as e:
        logger.error(
            "截图分析 LLM 调用失败: chunk_start=%s, chunk_end=%s, model=%s, error=%s",
            chunk['start'], chunk['end'], settings.model, e
        )
        raise LLMResponseError(
            model=settings.model,
            raw_response=str(e)[:500],
            cause=e
        ) from e


async def screenshot_analysis(
    start_time: str,
    end_time: str,
    todolist: str,
    density_threshold: float = DENSITY_THRESHOLD,
    min_duration_minutes: int = MIN_DURATION_MINUTES,
    frequency_level: int = 2
) -> List[Dict[str, Any]]:
    """分析指定时间段的截图语义

    步骤：
    1. 获取高密度时间段（复用时间密度分割）
    2. 根据频率等级动态设置chunk大小并切分时间段
    3. 对每个 chunk 查询 active 截图
    4. 调用 LLM 分析截图语义

    Args:
        start_time: 开始时间（YYYY-MM-DD HH:MM:SS 格式）
        end_time: 结束时间（YYYY-MM-DD HH:MM:SS 格式）
        todolist: 用户目标列表文本
        density_threshold: 密度阈值（默认 0.6）
        min_duration_minutes: 最小时长（默认 6 分钟）
        frequency_level: 截图频率等级（1=低频 2=中频 3=高频，默认2）

    Returns:
        List[Dict[str, Any]]: 分析结果列表，每项包含：
            - start_time: 开始时间（YYYY-MM-DD HH:MM:SS 格式）
            - end_time: 结束时间（YYYY-MM-DD HH:MM:SS 格式）
            - screen_count: 截图数量
            - behavior: 分析结果
    """
    # 根据频率等级获取chunk大小
    chunk_minutes = CHUNK_MINUTES_BY_LEVEL.get(frequency_level, 10)
    logger.info(f"开始截图语义分析: {start_time} -> {end_time}, 频率等级={frequency_level}, chunk大小={chunk_minutes}分钟")

    # Step 1: 查询活动日志
    provider = LWBaseDataProvider()
    logs, total = provider.get_activity_logs(start_time=start_time, end_time=end_time)
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
    
    # 加载行为总结 prompt
    summary_prompt = prompt_loader.load_prompt(Prompts.Schedule.SCREEN_BEHAVIOR_SUMMARY)
    
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
            extra={"system_prompt": summary_prompt},
        )
        llm_result :OutboundMessage = await bus.send(msg)
        response_content = llm_result.response.content
        if response_content:
            # 解析json字符串

            extracted = extract_json_from_response(response_content)
            data : dict = json.loads(extracted)
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
                logger.error(
                    "截图分析行为总结 LLM 输出解析失败: 期望字段 behavior_summary+title, 实际字段=%s, 原始输出片段=%s",
                    list(data.keys()), response_content[:500]
                )
                raise LLMOutputParseError(
                    expected_fields=["behavior_summary", "title"],
                    actual_keys=list(data.keys()),
                    raw_output=response_content[:500]
                )

        else:
            logger.error(
                "截图分析行为总结 LLM 返回空内容: start_time=%s, end_time=%s, model=%s",
                start_time, end_time, settings.model
            )
            raise LLMResponseError(
                model=settings.model,
                raw_response="(empty response)"
            )

    except json.JSONDecodeError as e:
        logger.error(
            "截图分析行为总结 JSON 解析失败: start_time=%s, end_time=%s, 原始输出片段=%s",
            start_time, end_time, response_content[:500] if 'response_content' in dir() else "(unknown)"
        )
        raise LLMOutputParseError(
            expected_fields=["behavior_summary", "title"],
            actual_keys=[],
            raw_output=response_content[:500] if 'response_content' in dir() else "(unknown)"
        ) from e
    except (LLMResponseError, LLMOutputParseError):
        raise

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
    import asyncio

    async def test_single_chunk():
        from lifeprism.llm.agent.loop import agent_loop
        loop_task = asyncio.create_task(agent_loop.loop())

        """测试单个 chunk 的 LLM 分析，验证 _clean_llm_response 过滤问题"""
        # 使用日志中有截图但 behavior=None 的时间段
        chunk = {
            "start": "2026-05-24T00:15:25",
            "end": "2026-05-24T00:25:25"
        }

        # 获取该时间段的截图
        screenshots = get_active_screenshots(chunk["start"], chunk["end"])
        print(f"截图数量: {len(screenshots)}")
        for sc in screenshots:
            print(f"  - {sc['captured_at']} | {sc['window_app']} | {sc.get('window_title', '')[:50]}")

        if not screenshots:
            print("无截图，退出")
            return

        # 调用 LLM 分析
        result = await analyze_chunk_screenshots(chunk, screenshots, todolist="")

        # 打印结果
        print("\n" + "="*50)
        if result:
            print(f"behavior 字段:\n{result['behavior']}")
        else:
            print("结果为 None")

    asyncio.run(test_single_chunk())


    print('2026-04-28 12:15:05' == '2026-04-28 12:15:05')
