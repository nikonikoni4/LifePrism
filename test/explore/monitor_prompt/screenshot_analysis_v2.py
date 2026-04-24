"""
截图语义分析测试

步骤：
1. 获取高密度时间段（复用时间密度分割）
2. 将高密度时间段以15分钟进行切分
3. 对该15分钟区间的截图为active的screen_captures表数据进行提取,active截图稀释一半，每个时间段只保留1，3，5..单数的截图
4. 组织prompt，进行分析
"""
import sys
import asyncio
import base64
import os
sys.path.insert(0, '.')

from datetime import datetime, timedelta
from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider
from lifeprism.llm.providers.build_llm_client import create_llm_client

# === Prompt ===
SYSTEM_PROMPT = """
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
3. 例子：截图中app所在窗口仅存在一些文字，无法聚焦用户的行为。比如显示cursor中一个脚本内容，但是前后截图该脚本内容无变化或不相关，无法判断用户在该内容做了什么动作，就不要输出行为，不要输出“用户在cursor编辑xx.py”等内容
</语义推断情况3>

## 语义识别步骤
<执行步骤>
1. 首先匹配每张截图用户实际使用的窗口：通过每张截图给出的附加信息app和title进行窗口定位
2. 识别窗口内容，如果识别到用户正在打字，关注窗口输入框打字内容
3. 将不同时间的窗口内容按照时间顺序排序，依据窗口内容变化，结合用户目标，判断用户的行为，具体判断情况见《行为语义推断》章节
4. 将相同语义内容进行合并推理，输出行为总结。
5. 自行审查，判断输出内容是否符合规则和输出契约
</执行步骤>


## 规则

<不要做的事情>
    1. 不要输出用户能力相关的行为和总结，比如“文档内容具有技术深度”，“整体行为体现专注度”
    2. 不要输出“相关”等模糊词语，比如不能出现：“用户正在修改相关bug”，应该为用户正在修复X模块bug。如果结果不清晰宁愿不输出也不要给出模糊信息
    3. 不要给出只从app和title就能判断的语义：比如，app:cursor title: xx.py “使用cursor编辑xx.py”。这种语义太过模糊。
</不要做的事情>
<需要做的事情>
    若所有截图都无法判断行为，直接输出：None
</需要做的事情>

## 输出契约
当有行为判断时：
    输出用户行为和总结两个部分
    比如：
    用户行为：
    1. 用户在查看openai的harness engineering博客
    2. 用户在查看claude的harness engineering博客
    3. 用户在编写harness engineering笔记
    4. 用户在观看《老友记》
    总结：
    用户在观看openai和claude的harness engineering博客，并且编写笔记。随后用户观看《老友记》
无行为判断时，直接输出：None

"""

goal = """
## 用户今日目标

1. 完成《复利效应》的笔记
2. 完成feat_monitor 监控功能开发
3. 修复habit模块bug：习惯界面链条时间计算有问题

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
output_file = r"D:\desktop\软件开发\LifeWatch-AI\.worktrees\feat_monitor\screenshot_analysis_v2_result.txt"
os.makedirs(os.path.dirname(output_file), exist_ok=True)
result_file = open(output_file, "w", encoding="utf-8")
result_file.write(f"截图语义分析结果 v2 (单数截图稀释)\n")
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
    from lifeprism.repository import lw_db_manager
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
async def analyze_chunk(chunk: dict, screenshots: list, original_count: int) -> str | None:
    """调用LLM分析单个chunk的截图语义（只使用单数序号的截图：1、3、5...）"""
    if not screenshots:
        return None

    # 过滤：只保留单数序号的截图（1、3、5... 即 index 0, 2, 4...）
    odd_index_screenshots = screenshots[::2]
    filtered_count = len(odd_index_screenshots)

    llm_client = create_llm_client()

    # 准备图片消息
    content_parts = []
    for sc in odd_index_screenshots:
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

    # user content 必须是多模态列表；切勿 f-string 拼接 content_parts，否则会把整段 base64
    # 当作普通文本 repr 进一条字符串，token 会暴涨并触发 max message tokens。
    user_content: list = []
    if goal:
        user_content.append({"type": "text", "text": goal.strip()})
    user_content.append({
        "type": "text",
        "text": f"时间范围: {chunk['start']} -> {chunk['end']}",
    })
    user_content.extend(content_parts)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
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
        chunk_start = chunk["start"]
        chunk_end = chunk["end"]

        # 查询active截图
        screenshots = get_active_screenshots(chunk_start, chunk_end)
        screenshot_count = len(screenshots)
        total_screenshots += screenshot_count

        # 计算过滤后的数量（单数序号：1、3、5... 即 index 0, 2, 4...）
        filtered_count = len(screenshots[::2])

        print(f"\n[{i}/{len(all_chunks)}] {chunk_start} -> {chunk_end}")
        print(f"    原始截图: {screenshot_count} 张, 单数过滤后: {filtered_count} 张")

        if not screenshots:
            print(f"    无active截图，跳过")
            continue

        # 调用LLM分析（内部会过滤为单数截图）
        print(f"    正在分析...")
        response = await analyze_chunk(chunk, screenshots, filtered_count)

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
            result_file.write(f"原始截图: {screenshot_count} 张, 单数过滤后: {filtered_count} 张\n")
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
    result_file.write(f"总active截图（原始）: {total_screenshots} 张\n")
    result_file.write(f"总active截图（过滤后）: {sum(c // 2 + c % 2 for c in [len(get_active_screenshots(c['start'], c['end'])) for c in all_chunks])} 张\n")
    result_file.write(f"Total Tokens: {total_tokens['total']:,}\n")
    result_file.close()

    print(f"\n{'='*80}")
    print("统计")
    print("="*80)
    print(f"  高密度时间段: {len(high_density_segments)} 个")
    print(f"  15分钟块: {len(all_chunks)} 个")
    print(f"  有active截图的块: {sum(1 for c in all_chunks if get_active_screenshots(c['start'], c['end']))} 个")
    print(f"  实际分析块: {analyzed_chunks} 个")
    filtered_total = sum(c // 2 + c % 2 for c in [len(get_active_screenshots(c['start'], c['end'])) for c in all_chunks])
    print(f"  总active截图（原始）: {total_screenshots} 张")
    print(f"  总active截图（过滤后）: {filtered_total} 张")
    print(f"  Total Tokens: {total_tokens['total']:,}")
    print(f"  结果已保存到: {output_file}")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())