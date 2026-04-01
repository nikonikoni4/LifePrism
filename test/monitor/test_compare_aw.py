import sqlite3
import json
import time
import os
from datetime import datetime, timedelta, timezone
import pytz
from pathlib import Path

# Ensure we can import from lifeprism
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from lifeprism.storage.base_providers.aw_base_data_provider import AWBaseDataProvider
from lifeprism.config.settings_manager import settings
from lifeprism.config import LOCAL_TIMEZONE

def get_monitor_events(db_path, minutes=10):
    if not os.path.exists(db_path):
        print(f"Monitor DB not found at {db_path}")
        return [], None

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 获取最后一条数据的时间作为基准
    cursor.execute("SELECT timestamp FROM window_events ORDER BY id DESC LIMIT 1")
    last_row = cursor.fetchone()
    last_time_str = last_row['timestamp'] if last_row else None

    if not last_time_str:
        conn.close()
        return [], None

    # 计算起始时间 (Local Time)
    last_time_dt = datetime.fromisoformat(last_time_str)
    start_time_dt = last_time_dt - timedelta(minutes=minutes)
    start_time_str = start_time_dt.isoformat()

    # 查询最后 N 分钟的所有数据
    cursor.execute("""
        SELECT timestamp, duration, app, title
        FROM window_events
        WHERE timestamp >= ?
        ORDER BY timestamp
    """, (start_time_str,))

    rows = cursor.fetchall()
    events = []
    for row in rows:
        events.append({
            'timestamp': row['timestamp'],
            'duration': row['duration'],
            'app': row['app'],
            'title': row['title']
        })

    conn.close()
    return events, last_time_str

def compare():
    print("Starting Data Comparison...")

    # 1. Fetch from Windows Monitor
    data_path = Path(settings.lifeprism_data_path)
    monitor_db = str(data_path / "window_activity.db")
    minutes = 10
    monitor_events, last_time_str = get_monitor_events(monitor_db, minutes=minutes)

    if not last_time_str:
        print("No events found in monitor database.")
        return

    # 确保 monitor_events 是按时间正序排列的
    monitor_events.sort(key=lambda x: x['timestamp'])

    print(f"Monitor last event time (Local): {last_time_str}")
    print(f"Fetching Monitor data for the last {minutes} minutes.")

    # 2. Fetch from ActivityWatch
    try:
        provider = AWBaseDataProvider()

        # 将 monitor 的最后时间转为 datetime 对象 (本地时间)
        end_time_local = datetime.fromisoformat(last_time_str)
        # 取最后 10 分钟进行对比
        start_time_local = end_time_local - timedelta(minutes=minutes)

        print(f"Fetching AW data from {start_time_local} to {end_time_local} (Local Time)")

        # 将本地时间显式转为 UTC 字符串，因为 provider 期望 ISO 格式且内部处理逻辑可能比较复杂
        # 或者直接传带时区的本地时间
        start_time_utc = provider._local_to_utc(start_time_local)
        end_time_utc = provider._local_to_utc(end_time_local)

        # 绕过 get_window_events 内部对 start_time/end_time 的复杂判定，直接使用 UTC 字符串
        # 注意：provider.get_window_events 内部会根据参数类型处理
        aw_raw_events = provider.get_window_events(start_time=start_time_utc.isoformat(), end_time=end_time_utc.isoformat())

        aw_events = []
        for e in aw_raw_events:
            if e['duration'] >= 30.0:
                dt_utc = provider._parse_timestamp(e['timestamp'])
                dt_local = provider._utc_to_local(dt_utc)

                aw_events.append({
                    'timestamp': dt_local.strftime("%Y-%m-%dT%H:%M:%S"),
                    'duration': e['duration'],
                    'app': e['data'].get('app', 'unknown'),
                    'title': e['data'].get('title', 'unknown')
                })
        # 3. 排序：将 AW 结果按时间正序排列
        aw_events.sort(key=lambda x: x['timestamp'])
    except Exception as e:
        print(f"Error fetching AW data: {e}")
        aw_events = []

    print(f"\n--- Windows Monitor Events (>= 30s) [Count: {len(monitor_events)}] ---")
    for e in monitor_events:
        # 统一格式化显示
        dt = datetime.fromisoformat(e['timestamp'])
        print(f"[{dt.strftime('%Y-%m-%dT%H:%M:%S')}] {e['duration']:.1f}s | {e['app']} | {e['title'][:50]}")

    print(f"\n--- ActivityWatch Events (>= 30s) [Count: {len(aw_events)}] ---")
    for e in aw_events:
        print(f"[{e['timestamp']}] {e['duration']:.1f}s | {e['app']} | {e['title'][:50]}")

if __name__ == "__main__":
    compare()
