"""
探索性测试：user_app_behavior_log 的时间密度分割

参数：
- TIME_BUCKET_MINUTES = 10
- MAX_BRIDGE_BUCKETS = 0
- 密度阈值 = 0.6
- 时间段过滤 = 6分钟
"""
import sys
sys.path.insert(0, '.')

from datetime import datetime, timedelta
from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider
from lifeprism.llm.summary_context.aggregators.activity_aggregator import (
    compute_bucket_density,
    _collect_buckets,
    _build_segments,
    _build_segment_item,
)

# === 自定义参数 ===
# 临时覆盖全局变量
import lifeprism.llm.summary_context.aggregators.activity_aggregator as agg_module
agg_module.TIME_BUCKET_MINUTES = 10
agg_module.MAX_BRIDGE_BUCKETS = 0
agg_module.ACTIVE_SEGMENT_DENSITY_THRESHOLD = 0.6
agg_module.ACTIVE_SEGMENT_MIN_DURATION_MINUTES = 6

# 引用时用模块里的常量
TIME_BUCKET_MINUTES = agg_module.TIME_BUCKET_MINUTES
MAX_BRIDGE_BUCKETS = agg_module.MAX_BRIDGE_BUCKETS
DENSITY_THRESHOLD = 0.6
MIN_DURATION_MINUTES = 6


# prompt

## llm 语义分割prompt





# === 查询数据 ===
provider = LWBaseDataProvider()

range_start = "2026-04-19 00:00:00"
range_end = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

print(f"查询范围: {range_start} -> {range_end}")
print(f"参数: TIME_BUCKET_MINUTES={TIME_BUCKET_MINUTES}, MAX_BRIDGE_BUCKETS={MAX_BRIDGE_BUCKETS}, DENSITY_THRESHOLD={DENSITY_THRESHOLD}, MIN_DURATION_MINUTES={MIN_DURATION_MINUTES}")
print()

logs, total = provider.get_activity_logs(start_time=range_start, end_time=range_end)
print(f"查询到 {total} 条记录")
print()

if not logs:
    print("没有数据")
    sys.exit(0)

# === 转换格式以适配现有函数 ===
adapted_logs = []
for log in logs:
    adapted_logs.append({
        "start_time": log["start_time"],
        "end_time": log["end_time"],
        "duration": log.get("duration", 0),
        "app": log.get("app", ""),
        "title": log.get("title", ""),
    })

# === 执行分割 ===
segments = _build_segments(
    logs=adapted_logs,
    range_start=range_start,
    range_end=range_end,
    threshold=DENSITY_THRESHOLD,
    min_duration_minutes=MIN_DURATION_MINUTES,
    segment_type="explor_test",
)

print(f"分割出的段数: {len(segments)}")
print()

# === 查询 app_description 的辅助函数 ===
def get_app_descriptions(apps: set) -> dict:
    """从 category_map_cache 查询 app 的 description"""
    if not apps:
        return {}
    from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider
    prov = LWBaseDataProvider()
    df = prov.load_category_map_cache_V2()
    if df is None:
        return {}
    result = {}
    for app in apps:
        row = df[df['app'] == app]
        if not row.empty:
            desc = row.iloc[0].get('app_description', '')
            result[app] = desc if desc else 'N/A'
        else:
            result[app] = 'N/A'
    return result

# === 查询 screenshot counts 的辅助函数 ===
def get_screenshot_counts(seg_start: str, seg_end: str) -> dict:
    """查询某个时间段内各类型截图的数量"""
    sql = """
    SELECT capture_reason, COUNT(*) as count
    FROM screen_captures
    WHERE captured_at >= ? AND captured_at <= ?
    GROUP BY capture_reason
    """
    from lifeprism.repository import lw_db_manager
    result = {'scheduled': 0, 'enter': 0, 'active': 0}
    with lw_db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, (seg_start, seg_end))
        for row in cursor.fetchall():
            reason = row[0] if row[0] else 'unknown'
            if reason in result:
                result[reason] = row[1]
            else:
                result[reason] = row[1]
    return result

# === 展示结果 ===
print("=" * 80)
print("时间段分割结果")
print("=" * 80)

for i, seg in enumerate(segments, 1):
    seg_start = seg["start"]
    seg_end = seg["end"]
    duration_min = seg["duration_seconds"] // 60

    print(f"\n[段 {i}] {seg_start} -> {seg_end}")
    print(f"  时长: {duration_min} 分钟")

    # 收集该段内的app使用情况
    seg_start_dt = datetime.fromisoformat(seg_start)
    seg_end_dt = datetime.fromisoformat(seg_end)
    seg_apps = {}
    for log in adapted_logs:
        log_start = datetime.fromisoformat(log["start_time"])
        log_end = datetime.fromisoformat(log["end_time"])
        if log_start < seg_end_dt and log_end > seg_start_dt:
            app = log.get("app", "unknown")
            dur = log.get("duration", 0)
            if app not in seg_apps:
                seg_apps[app] = 0
            seg_apps[app] += dur

    # 统计log条数
    log_count = sum(1 for log in adapted_logs
                    if datetime.fromisoformat(log["start_time"]) < seg_end_dt
                    and datetime.fromisoformat(log["end_time"]) > seg_start_dt)
    print(f"  Log条数: {log_count}")

    # 获取app description
    app_descriptions = get_app_descriptions(set(seg_apps.keys()))

    # 按使用时长排序
    sorted_apps = sorted(seg_apps.items(), key=lambda x: x[1], reverse=True)
    print(f"  App使用 (前8):")
    for app, dur in sorted_apps[:8]:
        desc = app_descriptions.get(app, 'N/A')
        print(f"    - {app}: {dur//60}分钟 | {desc}")

    # 截图统计
    screenshot_counts = get_screenshot_counts(seg_start, seg_end)
    total_sc = sum(screenshot_counts.values())
    print(f"  截图数量: scheduled={screenshot_counts['scheduled']}, enter={screenshot_counts['enter']}, active={screenshot_counts['active']} (共{total_sc}张)")

print()
print("=" * 80)
