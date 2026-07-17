import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytz

# 添加项目根目录到 sys.path 以便导入 lifeprism 模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from lifeprism.config.settings_manager import settings
from lifeprism.repository.base_providers.aw_base_data_provider import AWBaseDataProvider


def get_window_activity_data(db_path, minutes=10, min_duration=30.0):
    """1. 获取 window_activity.db 数据"""
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件不存在 {db_path}")
        return [], None, None

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1.1 获取最后一条数据的时间作为结束时间
    cursor.execute("SELECT timestamp FROM window_events ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    if not row:
        conn.close()
        return [], None, None

    end_time_str = row["timestamp"]
    end_time_dt = datetime.fromisoformat(end_time_str)
    # 2. 构建开始时间
    start_time_dt = end_time_dt - timedelta(minutes=minutes)
    start_time_str = start_time_dt.isoformat()

    # 3. 获取时长 > 30s 的数据
    cursor.execute(
        """
        SELECT timestamp, duration, app, title
        FROM window_events
        WHERE timestamp >= ? AND timestamp <= ? AND duration >= ?
        ORDER BY timestamp ASC
    """,
        (start_time_str, end_time_str, min_duration),
    )

    rows = cursor.fetchall()
    events = []
    for r in rows:
        events.append(
            {
                "timestamp": r["timestamp"],
                "duration": r["duration"],
                "app": r["app"],
                "title": r["title"],
            }
        )

    conn.close()
    return events, start_time_dt, end_time_dt


def run_test():
    print("=== 开始对比测试 ===")

    # 获取路径
    data_path = settings.lifeprism_data_path
    monitor_db = str(data_path / "window_activity.db")

    # 1-3. 处理本地监控数据
    monitor_events, start_dt, end_dt = get_window_activity_data(monitor_db, minutes=10)
    if not start_dt:
        print("本地数据库中没有数据")
        return

    print(f"测试窗口 (本地): {start_dt.isoformat()} 至 {end_dt.isoformat()}")

    # 4. 将时间转化为标准 UTC (假设本地是上海时区)
    # AWBaseDataProvider 内部的 _local_to_utc 会处理这个转换
    provider = AWBaseDataProvider()
    start_utc = provider._local_to_utc(start_dt)
    end_utc = provider._local_to_utc(end_dt)

    print(f"测试窗口 (UTC):  {start_utc.isoformat()} 至 {end_utc.isoformat()}")

    # 5. 从 AW 数据库获取数据
    # 为确保时间对齐，我们直接构造 UTC 时间进行查询，绕过 provider 内部可能的时区偏差
    # 假设本地是 UTC+8 (上海)
    tz_sh = pytz.timezone("Asia/Shanghai")
    start_dt_aware = tz_sh.localize(start_dt)
    end_dt_aware = tz_sh.localize(end_dt)

    start_utc = start_dt_aware.astimezone(pytz.UTC)
    end_utc = end_dt_aware.astimezone(pytz.UTC)

    # 调用 get_window_events，注意：如果传入的是带时区的 datetime，provider 内部应该能处理
    # 但为了保险，我们直接传入 UTC datetime
    aw_raw_events = provider.get_window_events(start_time=start_utc, end_time=end_utc)

    # 过滤时长 > 30s 并转换显示时区
    aw_events = []
    for e in aw_raw_events:
        if e["duration"] >= 30.0:
            dt_utc = provider._parse_timestamp(e["timestamp"])
            dt_local = provider._utc_to_local(dt_utc)
            aw_events.append(
                {
                    "timestamp": dt_local.isoformat(),
                    "duration": e["duration"],
                    "app": e["data"].get("app", "unknown"),
                    "title": e["data"].get("title", "unknown"),
                }
            )

    # 排序
    aw_events.sort(key=lambda x: x["timestamp"])

    # 6. 打印对比数据
    print(f"\n--- Windows Monitor 记录 (时长 >= 30s) [数量: {len(monitor_events)}] ---")
    for e in monitor_events:
        print(f"[{e['timestamp']}] {e['duration']:>6.1f}s | {e['app']:<20} | {e['title'][:60]}")

    print(f"\n--- ActivityWatch 记录 (时长 >= 30s) [数量: {len(aw_events)}] ---")
    for e in aw_events:
        print(f"[{e['timestamp']}] {e['duration']:>6.1f}s | {e['app']:<20} | {e['title'][:60]}")


if __name__ == "__main__":
    run_test()
