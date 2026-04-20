"""
机械分割测试：直接按固定时间间隔（10分钟）切分，不调用LLM

作为LLM语义分割的baseline对比
"""
import sys
sys.path.insert(0, '.')

from datetime import datetime, timedelta
from lifeprism.storage.base_providers.lw_base_data_provider import LWBaseDataProvider

# === 参数 ===
CHUNK_MINUTES = 15

# === 查询数据 ===
provider = LWBaseDataProvider()
range_start = "2026-04-19 00:00:00"
range_end = "2026-04-20 18:08:46"

print(f"查询范围: {range_start} -> {range_end}")
print(f"切分间隔: {CHUNK_MINUTES} 分钟")
print()

logs, total = provider.get_activity_logs(start_time=range_start, end_time=range_end)
print(f"查询到 {total} 条记录")

if not logs:
    print("没有数据")
    sys.exit(0)

adapted_logs = []
for log in logs:
    adapted_logs.append({
        "start_time": log["start_time"],
        "end_time": log["end_time"],
        "duration": log.get("duration", 0),
        "app": log.get("app", ""),
        "title": log.get("title", ""),
    })

# === 机械切分 ===
def mechanical_split(logs: list, range_start: str, range_end: str, chunk_minutes: int) -> list:
    """直接按固定时间间隔切分"""
    start_dt = datetime.fromisoformat(range_start)
    end_dt = datetime.fromisoformat(range_end)
    chunk_delta = timedelta(minutes=chunk_minutes)

    chunks = []
    cursor = start_dt

    while cursor < end_dt:
        chunk_end = min(cursor + chunk_delta, end_dt)

        # 收集该时间段内的logs
        chunk_logs = []
        for log in logs:
            log_start = datetime.fromisoformat(log["start_time"])
            log_end = datetime.fromisoformat(log["end_time"])
            if log_start < chunk_end and log_end > cursor:
                chunk_logs.append(log)

        chunks.append({
            "start": cursor.isoformat(),
            "end": chunk_end.isoformat(),
            "logs": chunk_logs,
        })

        cursor = chunk_end

    return chunks


# === 查询 app_description ===
def get_app_descriptions(apps: set) -> dict:
    if not apps:
        return {}
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


# === 查询 screenshot counts ===
def get_screenshot_counts(seg_start: str, seg_end: str) -> dict:
    sql = """
    SELECT capture_reason, COUNT(*) as count
    FROM screen_captures
    WHERE captured_at >= ? AND captured_at <= ?
    GROUP BY capture_reason
    """
    from lifeprism.storage import lw_db_manager
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


# === 执行切分并展示 ===
chunks = mechanical_split(adapted_logs, range_start, range_end, CHUNK_MINUTES)

# 过滤掉没有log的时间段
chunks = [c for c in chunks if c["logs"]]

print(f"\n机械切分出 {len(chunks)} 个有效时间段（忽略无活动时段）")
print()

print("=" * 80)
print(f"时间段列表 (每段 {CHUNK_MINUTES} 分钟)")
print("=" * 80)

for i, chunk in enumerate(chunks, 1):
    seg_start = chunk["start"]
    seg_end = chunk["end"]
    seg_logs = chunk["logs"]

    duration_sec = (datetime.fromisoformat(seg_end) - datetime.fromisoformat(seg_start)).total_seconds()
    duration_min = int(duration_sec / 60)

    print(f"\n[{i}] {seg_start} -> {seg_end} ({duration_min}min)")
    print(f"  Log条数: {len(seg_logs)}")

    # 统计app使用
    seg_apps = {}
    for log in seg_logs:
        app = log.get("app", "")
        dur = log.get("duration", 0)
        if app not in seg_apps:
            seg_apps[app] = 0
        seg_apps[app] += dur

    app_descriptions = get_app_descriptions(set(seg_apps.keys()))
    sorted_apps = sorted(seg_apps.items(), key=lambda x: x[1], reverse=True)

    print(f"  App使用 (前5):")
    for app, dur in sorted_apps[:5]:
        desc = app_descriptions.get(app, 'N/A')
        print(f"    - {app}: {dur//60}分钟 | {desc}")

    # 截图统计
    screenshot_counts = get_screenshot_counts(seg_start, seg_end)
    total_sc = sum(screenshot_counts.values())
    print(f"  截图: scheduled={screenshot_counts['scheduled']}, enter={screenshot_counts['enter']}, active={screenshot_counts['active']} (共{total_sc}张)")

print()
print("=" * 80)
print(f"总计: {len(chunks)} 个时间段（忽略无活动时段）")
