"""
LLM语义分割测试：基于时间密度分割的段，进一步做语义细分

1. 从 test_bucket_density.py 获取时间密度分割结果（segments）
2. 对每个段，调用 LLM 进行语义细分
3. 输出更细粒度的语义分割结果
"""
import sys
import asyncio
sys.path.insert(0, '.')

from datetime import datetime
from lifeprism.llm.providers.build_llm_client import create_llm_client
from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider


# === prompt ===
STEP_1_PROMPT = """
## task
你需要依据现有数据（app，app_description，title，duration，start_time，end_time）对时间段进行语义分割。

## 核心原则
**没有把握时，宁愿合并不分割，也不要随意切分导致时间段太细。** 分割的目的是让每段都能回答"用户在这段时间做了什么具体的事"，而不是描述"用了什么工具"。

## 语义判断标准

### ✅ 应该分割的情况
1. **有具体名字的内容切换**：
   - 例：浏览器title从"《老友记》第十季"切换到"GitHub - xxx项目" → 分割
   - 例：浏览器title从"娱乐视频"切换到"论文PDF" → 分割

2. **明显不同类别的app切换**：
   - 例：Cursor(编程) → msedge(看视频) → Cursor(继续编程) → 分割

3. **同一app内但title语义完全不同**：即使app相同，title能明确区分不同活动
   - 例：浏览器从"追剧"切换到"查资料" → 分割

### ❌ 不应该分割的情况
1. **没有具体内容的工具操作**：只描述了工具，并且不能从上下文推断出其动作发生变化
   - 例："在Cursor中编辑xxx.py" → 不分割
   - 例："在终端运行命令" → 不分割
   - 例："浏览器打开了新标签页" → 不分割

2. **短时间碎片切换后很快回归**：在两个app间快速切换（各<5分钟）又回到原app → 视为同一语义


## 输出格式：json格式的list
输出分割后的时间段列表：
```json
[
    {"start_time": "ISO格式", "end_time": "ISO格式"},
    {"start_time": "ISO格式", "end_time": "ISO格式"}
]
```

"""


def get_segment_logs(segments: list, logs: list) -> list:
    """收集每个段内的log数据（含app_description）"""
    from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider

    prov = LWBaseDataProvider()
    df = prov.load_category_map_cache_V2()
    app_desc_map = {}
    if df is not None:
        for _, row in df.iterrows():
            app_desc_map[row['app']] = row.get('app_description', '') or 'N/A'

    result = []
    for seg in segments:
        seg_start = datetime.fromisoformat(seg["start"])
        seg_end = datetime.fromisoformat(seg["end"])
        seg_logs = []
        for log in logs:
            log_start = datetime.fromisoformat(log["start_time"])
            log_end = datetime.fromisoformat(log["end_time"])
            if log_start < seg_end and log_end > seg_start:
                app = log.get("app", "")
                seg_logs.append({
                    "start_time": log["start_time"],
                    "end_time": log["end_time"],
                    "duration": log.get("duration", 0),
                    "app": app,
                    "app_description": app_desc_map.get(app, 'N/A'),
                    "title": log.get("title", "") or "",
                })
        result.append({
            "segment": seg,
            "logs": seg_logs,
        })
    return result


def format_logs_for_llm(seg_logs: list) -> str:
    """将logs格式化为LLM可读的字符串"""
    lines = []
    for log in seg_logs:
        lines.append(
            f"- [{log['start_time']} -> {log['end_time']}] {log['duration']//60}min | "
            f"app: {log['app']} | desc: {log['app_description']} | title: {log['title'][:50]}"
        )
    return "\n".join(lines)


async def call_llm_segment(prompt: str, data: str, range_start: str, range_end: str) -> str:
    """调用LLM进行语义分割"""
    llm_client = create_llm_client()
    messages = [
        {"role": "system", "content": "你是一个专业的用户行为分析助手，擅长从时间线数据中提取语义单元。"},
        {"role": "user", "content": f"{prompt}\n\n## 时间段范围\n{range_start} -> {range_end}\n\n## 数据\n{data}"}
    ]
    response = await llm_client.chat(messages)
    return response


async def main():
    # === 从 test_bucket_density 获取segments ===
    # 复用 test_bucket_density 的参数和数据
    import lifeprism.llm.summary_context.aggregators.activity_aggregator as agg_module
    agg_module.TIME_BUCKET_MINUTES = 10
    agg_module.MAX_BRIDGE_BUCKETS = 0
    agg_module.ACTIVE_SEGMENT_DENSITY_THRESHOLD = 0.6
    agg_module.ACTIVE_SEGMENT_MIN_DURATION_MINUTES = 6

    DENSITY_THRESHOLD = 0.6
    MIN_DURATION_MINUTES = 6

    provider = LWBaseDataProvider()
    range_start = "2026-04-19 00:00:00"
    range_end = "2026-04-20 18:08:46"  # 用上次测试的时间

    logs, total = provider.get_activity_logs(start_time=range_start, end_time=range_end)
    print(f"获取到 {total} 条记录")

    adapted_logs = []
    for log in logs:
        adapted_logs.append({
            "start_time": log["start_time"],
            "end_time": log["end_time"],
            "duration": log.get("duration", 0),
            "app": log.get("app", ""),
            "title": log.get("title", ""),
        })

    from lifeprism.llm.summary_context.aggregators.activity_aggregator import _build_segments
    segments = _build_segments(
        logs=adapted_logs,
        range_start=range_start,
        range_end=range_end,
        threshold=DENSITY_THRESHOLD,
        min_duration_minutes=MIN_DURATION_MINUTES,
        segment_type="explor_test",
    )
    print(f"时间密度分割出 {len(segments)} 个段")

    # === 获取每个段的详细数据 ===
    segments_with_logs = get_segment_logs(segments, adapted_logs)

    # === 对每个段调用LLM进行语义细分 ===
    print("\n" + "=" * 80)
    print("LLM 语义分割结果")
    print("=" * 80)

    total_tokens = {"prompt": 0, "completion": 0, "total": 0}

    for i, swl in enumerate(segments_with_logs, 1):
        seg = swl["segment"]
        seg_logs = swl["logs"]
        seg_start = seg["start"]
        seg_end = seg["end"]
        duration_min = seg["duration_seconds"] // 60

        if not seg_logs:
            print(f"\n[段 {i}] {seg_start} -> {seg_end} ({duration_min}min) - 无log数据")
            continue

        print(f"\n[段 {i}] {seg_start} -> {seg_end} ({duration_min}min)")
        print(f"  原始log条数: {len(seg_logs)}")

        # 格式化数据给LLM
        data_str = format_logs_for_llm(seg_logs)

        # 调用LLM
        try:
            response = await call_llm_segment(STEP_1_PROMPT, data_str, seg_start, seg_end)
            print(f"  LLM响应:\n{response}")
            if hasattr(response, 'usage') and response.usage:
                total_tokens["prompt"] += response.usage.get('prompt_tokens', 0)
                total_tokens["completion"] += response.usage.get('completion_tokens', 0)
                total_tokens["total"] += response.usage.get('total_tokens', 0)
        except Exception as e:
            print(f"  LLM调用失败: {e}")

    print("\n" + "=" * 80)
    print("Tokens 消耗统计")
    print("=" * 80)
    print(f"  Prompt Tokens:     {total_tokens['prompt']:,}")
    print(f"  Completion Tokens: {total_tokens['completion']:,}")
    print(f"  Total Tokens:      {total_tokens['total']:,}")
    print(f"  段数: {len(segments_with_logs)}")
    avg = total_tokens['total'] // len(segments_with_logs) if segments_with_logs else 0
    print(f"  平均每段: {avg:,} tokens")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
