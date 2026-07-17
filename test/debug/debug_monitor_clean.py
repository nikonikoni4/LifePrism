import os
import sys
from datetime import datetime, timedelta

import pandas as pd

# 添加项目根目录到路径
project_root = os.path.abspath(os.curdir)
sys.path.insert(0, project_root)

from lifeprism.config.settings_manager import settings
from lifeprism.processors.data_clean import clean_activitywatch_data
from lifeprism.repository import lw_db_manager


def setup_debug_data():
    """在 window_events 表中创建一些模拟数据"""
    print("正在创建模拟数据...")
    now = datetime.now()
    events = [
        ("2026-04-02T10:00:00", 60, "chrome", "GitHub - Anthropic"),
        ("2026-04-02T10:01:00", 30, "code", "data_clean.py - LifeWatch-AI"),
        ("2026-04-02T10:01:30", 120, "chrome", "Google Search"),
    ]

    with lw_db_manager.get_connection() as conn:
        cursor = conn.cursor()
        # 确保表存在 (虽然应该已经存在)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS window_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                duration REAL NOT NULL,
                app TEXT NOT NULL,
                title TEXT NOT NULL
            )
        """)
        for ts, dur, app, title in events:
            cursor.execute(
                "INSERT INTO window_events (timestamp, duration, app, title) VALUES (?, ?, ?, ?)",
                (ts, dur, app, title),
            )
        conn.commit()
    print("模拟数据创建完成。")


def test_clean():
    # 强制设置 monitor_type
    settings.set("monitor_type", "lifeprism")
    print(f"当前 Monitor Type: {settings.monitor_type}")

    start_time = datetime(2026, 4, 2, 0, 0, 0)
    end_time = datetime(2026, 4, 2, 23, 59, 59)

    # 模拟空的分类缓存
    df_cache = pd.DataFrame(
        columns=["app", "title", "category_id", "sub_category_id", "state", "is_multipurpose_app"]
    )

    print("运行 clean_activitywatch_data...")
    df_result, state = clean_activitywatch_data(start_time, end_time, df_cache)

    print(f"清洗结果: {len(df_result)} 条处理后的事件")
    for _, row in df_result.iterrows():
        print(f"  - [{row['start_time']}] {row['app']} | {row['duration']}s | {row['title']}")

    print(f"待分类项: {len(state.log_items)} 个")


if __name__ == "__main__":
    try:
        setup_debug_data()
        test_clean()
    except Exception as e:
        import traceback

        traceback.print_exc()
