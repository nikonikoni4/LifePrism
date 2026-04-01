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

def get_monitor_events(db_path, min_duration=30.0):
    if not os.path.exists(db_path):
        print(f"Monitor DB not found at {db_path}")
        return [], None

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT timestamp, duration, app, title FROM window_events WHERE duration >= ? ORDER BY timestamp", (min_duration,))
    rows = cursor.fetchall()
    events = []
    for row in rows:
        events.append({
            'timestamp': row['timestamp'],
            'duration': row['duration'],
            'app': row['app'],
            'title': row['title']
        })

    # 获取最后一条数据的时间作为基准
    cursor.execute("SELECT timestamp FROM window_events ORDER BY id DESC LIMIT 1")
    last_row = cursor.fetchone()
    last_time = last_row['timestamp'] if last_row else None

    conn.close()
    return events, last_time

def compare():
    print("Starting Data Comparison...")

    # 1. Fetch from Windows Monitor
    data_path = Path(settings.lifeprism_data_path)
    monitor_db = str(data_path / "window_activity.db")
    monitor_events, last_time_str = get_monitor_events(monitor_db)

    if not last_time_str:
        print("No events found in monitor database.")
        return

    print(f"Monitor last event time (Local): {last_time_str}")

    # 2. Fetch from ActivityWatch
    try:
        provider = AWBaseDataProvider()

        # 将 monitor 的最后时间转为 datetime 对象 (本地时间)
        # monitor.py 使用 datetime.now().isoformat()
        end_time_local = datetime.fromisoformat(last_time_str)
        # 取最后 15 分钟进行对比
        start_time_local = end_time_local - timedelta(minutes=15)

        print(f"Fetching AW data from {start_time_local} to {end_time_local} (Local Time)")

        # AWBaseDataProvider.get_window_events 内部会将本地时间转为 UTC 进行查询
        aw_raw_events = provider.get_window_events(start_time=start_time_local, end_time=end_time_local)

        aw_events = []
        for e in aw_raw_events:
            if e['duration'] >= 30.0:
                # 解析 AW 的 UTC 时间戳并转为本地时间显示
                dt_utc = provider._parse_timestamp(e['timestamp'])
                dt_local = provider._utc_to_local(dt_utc)

                aw_events.append({
                    'timestamp': dt_local.strftime("%Y-%m-%dT%H:%M:%S"),
                    'duration': e['duration'],
                    'app': e['data'].get('app', 'unknown'),
                    'title': e['data'].get('title', 'unknown')
                })
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
