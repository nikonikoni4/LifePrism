"""
截图语义分析测试

步骤：
1. 获取高密度时间段（复用时间密度分割）
2. 将高密度时间段以15分钟进行切分
3. 对该15分钟区间的截图为active的screen_captures表数据进行提取
4. 组织prompt，进行分析
"""
import sys
import asyncio
import base64
import os
sys.path.insert(0, '.')

from datetime import datetime, timedelta
from lifeprism.storage.base_providers.lw_base_data_provider import LWBaseDataProvider
from lifeprism.llm.providers.build_llm_client import create_llm_client

# === Prompt ===
SYSTEM_PROMPT = """
## task
你需要依据用户的连续行为截图来判断用户在该时间段的行为语义。

## 语义说明

1. 语义必须是具有内容的，而不能仅仅是描述行为：
   - 合理语义：'观看《老友记》电视剧'，编写读书笔记，修改xxbug，实现新功能
   - 不合理语义：在cursor界面编辑xx.py，使用claude code进行编码
2. 良好的语义是能够匹配用户的真实目的，需要结合用户实际目的进行合理推断。
3. 输入的图片不一定仅仅只代表用户的一个行为，而可能是多个行为。

## 语义识别步骤

1. 首先匹配每张截图用户实际使用的窗口：通过每张截图给出的附加信息app和title进行窗口定位
2. 识别窗口内容，如果识别到用户正在打字，关注打字内容，并且说明这种图片与下一张图片的联系很强
3. 将不同时间的窗口内容按照时间顺序排序，依据窗口内容变化，判断用户的行为
4. 进行总结，将语义相近的行为进行合并

## 不确定说明

当缺乏信息，或者信息太多，你无法判断用户的行为时，直接回复：无法推断用户行为

## 输出契约

输出用户行为和总结两个部分
比如：
用户行为：
1. 用户在查看openai的harness engineering博客
2. 用户在查看claude的harness engineering博客
3. 用户在编写harness engineering笔记
4. 用户在观看《老友记》
总结：
1. 用户在观看openai和claude的harness engineering博客，并且编写笔记
2. 用户在编写笔记之后观看《老友记》

"""

# === 参数 ===
import lifeprism.llm.summary_context.aggregators.activity_aggregator as agg_module
agg_module.TIME_BUCKET_MINUTES = 10
agg_module.MAX_BRIDGE_BUCKETS = 0
agg_module.ACTIVE_SEGMENT_DENSITY_THRESHOLD = 0.6
agg_module.ACTIVE_SEGMENT_MIN_DURATION_MINUTES = 6

DENSITY_THRESHOLD = 0.6
MIN_DURATION_MINUTES = 6
CHUNK_MINUTES = 15

# === 数据查询 ===
provider = LWBaseDataProvider()
range_start = "2026-04-19 00:00:00"
range_end = "2026-04-20 18:08:46"

print(f"查询范围: {range_start} -> {range_end}")
print(f"参数: 密度阈值={DENSITY_THRESHOLD}, 时间段最小={MIN_DURATION_MINUTES}min, 切分={CHUNK_MINUTES}min")

logs, total = provider.get_activity_logs(start_time=range_start, end_time=range_end)
print(f"查询到 {total} 条行为记录")
print()

adapted_logs = []
for log in logs:
    adapted_logs.append({
        "start_time": log["start_time"],
        "end_time": log["end_time"],
        "duration": log.get("duration", 0),
        "app": log.get("app", ""),
        "title": log.get("title", ""),
    })

# === Step 1: 获取高密度时间段 ===
from lifeprism.llm.summary_context.aggregators.activity_aggregator import _build_segments
high_density_segments = _build_segments(
    logs=adapted_logs,
    range_start=range_start,
    range_end=range_end,
    threshold=DENSITY_THRESHOLD,
    min_duration_minutes=MIN_DURATION_MINUTES,
    segment_type="active",
)
print(f"Step 1: 获取到 {len(high_density_segments)} 个高密度时间段")

# === Step 2: 将高密度时间段以15分钟切分 ===
def split_segment_into_chunks(segment: dict, chunk_minutes: int) -> list:
    """将一个时间段切分为固定大小的chunk"""
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

all_chunks = []
for seg in high_density_segments:
    chunks = split_segment_into_chunks(seg, CHUNK_MINUTES)
    all_chunks.extend(chunks)

print(f"Step 2: 切分为 {len(all_chunks)} 个 {CHUNK_MINUTES} 分钟块")

# === 保存结果到文件 ===
output_file = r"D:\desktop\软件开发\LifeWatch-AI\.worktrees\feat_monitor\screenshot_analysis_result.txt"
os.makedirs(os.path.dirname(output_file), exist_ok=True)
result_file = open(output_file, "a", encoding="utf-8")
result_file.write(f"截图语义分析结果\n")
result_file.write(f"="*80 + "\n")

# === Step 3: 查询每个chunk的active截图 ===
def get_active_screenshots(seg_start: str, seg_end: str) -> list:
    """获取指定时间范围内的active截图"""
    sql = """
    SELECT id, captured_at, file_path, window_app, window_title, capture_reason
    FROM screen_captures
    WHERE captured_at >= ? AND captured_at <= ? AND capture_reason = 'active'
    ORDER BY captured_at ASC
    """
    from lifeprism.storage import lw_db_manager
    results = []
    with lw_db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, (seg_start, seg_end))
        rows = cursor.fetchall()
        for row in rows:
            results.append({
                "id": row[0],
                "captured_at": row[1],
                "file_path": row[2],
                "window_app": row[3],
                "window_title": row[4],
                "capture_reason": row[5],
            })
    return results

def get_data_dir() -> str:
    """获取lifeprism_data_path"""
    from lifeprism.config import settings
    return settings.lifeprism_data_path

def encode_image_to_base64(file_path: str) -> str | None:
    """将图片编码为base64 data URL"""
    try:
        import mimetypes
        full_path = os.path.join(get_data_dir(), file_path)
        mime_type, _ = mimetypes.guess_type(full_path)
        mime_type = mime_type or "image/png"

        with open(full_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")

        return f"data:{mime_type};base64,{b64_data}"
    except Exception as e:
        print(f"      读取图片失败 {file_path}: {e}")
        return None

# === Step 4: 调用LLM分析 ===
async def analyze_chunk(chunk: dict, screenshots: list) -> str | None:
    """调用LLM分析单个chunk的截图语义"""
    if not screenshots:
        return None

    llm_client = create_llm_client()

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
                "image_url": {
                    "url": b64
                }
            })
            content_parts.append({
                "type": "text",
                "text": f"[{captured_at}] app: {app} | title: {title}"
            })

    if not any(p.get("type") == "image_url" for p in content_parts):
        return None

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": [{"type": "text", "text": f"时间范围: {chunk['start']} -> {chunk['end']}"}] + content_parts}
    ]

    try:
        response = await llm_client.chat(messages)
        return response
    except Exception as e:
        print(f"      LLM调用失败: {e}")
        return None

async def main():
    print(f"\n{'='*80}")
    print("Step 3 & 4: 查询active截图并分析")
    print("="*80)

    total_screenshots = 0
    total_tokens = {"prompt": 0, "completion": 0, "total": 0}
    analyzed_chunks = 0

    for i, chunk in enumerate(all_chunks, 1):
        if i ==4 :
            
            chunk_start = chunk["start"]
            chunk_end = chunk["end"]

            # 查询active截图
            screenshots = get_active_screenshots(chunk_start, chunk_end)
            screenshot_count = len(screenshots)
            total_screenshots += screenshot_count

            print(f"\n[{i}/{len(all_chunks)}] {chunk_start} -> {chunk_end}")
            print(f"    Active截图: {screenshot_count} 张")

            if not screenshots:
                print(f"    无active截图，跳过")
                continue

            # 调用LLM分析
            print(f"    正在分析...")
            response = await analyze_chunk(chunk, screenshots)

            if response:
                analyzed_chunks += 1
                if hasattr(response, 'usage') and response.usage:
                    total_tokens["prompt"] += response.usage.get('prompt_tokens', 0)
                    total_tokens["completion"] += response.usage.get('completion_tokens', 0)
                    total_tokens["total"] += response.usage.get('total_tokens', 0)

                content = response.content if hasattr(response, 'content') else str(response)
                print(f"    分析结果:\n{content}")

                # 写入文件
                result_file.write(f"\n[{i}/{len(all_chunks)}] {chunk_start} -> {chunk_end}\n")
                result_file.write(f"Active截图: {screenshot_count} 张\n")
                result_file.write(f"分析结果:\n{content}\n")
                result_file.write("-"*80 + "\n")
            else:
                print(f"    分析失败或无结果")

    # === 统计 ===
    result_file.write("\n" + "="*80 + "\n")
    result_file.write("统计\n")
    result_file.write("="*80 + "\n")
    result_file.write(f"高密度时间段: {len(high_density_segments)} 个\n")
    result_file.write(f"15分钟块: {len(all_chunks)} 个\n")
    result_file.write(f"有active截图的块: {sum(1 for c in all_chunks if get_active_screenshots(c['start'], c['end']))} 个\n")
    result_file.write(f"实际分析块: {analyzed_chunks} 个\n")
    result_file.write(f"总active截图: {total_screenshots} 张\n")
    result_file.write(f"Total Tokens: {total_tokens['total']:,}\n")
    result_file.close()

    print(f"\n{'='*80}")
    print("统计")
    print("="*80)
    print(f"  高密度时间段: {len(high_density_segments)} 个")
    print(f"  15分钟块: {len(all_chunks)} 个")
    print(f"  有active截图的块: {sum(1 for c in all_chunks if get_active_screenshots(c['start'], c['end']))} 个")
    print(f"  实际分析块: {analyzed_chunks} 个")
    print(f"  总active截图: {total_screenshots} 张")
    print(f"  Total Tokens: {total_tokens['total']:,}")
    print(f"  结果已保存到: {output_file}")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())