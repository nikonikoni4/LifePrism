"""
分析active截图中第一张和后续截图的占比
"""
import sqlite3
from pathlib import Path
from collections import Counter

# 数据库路径
db_path = Path("localData/dataset/lifewatch_ai.db")

if not db_path.exists():
    print(f"数据库文件不存在: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. 统计总体情况
print("=" * 80)
print("总体统计")
print("=" * 80)

cursor.execute("""
    SELECT capture_reason, COUNT(*) as count
    FROM screen_captures
    GROUP BY capture_reason
    ORDER BY count DESC
""")
total_stats = cursor.fetchall()
for reason, count in total_stats:
    print(f"{reason:12s}: {count:5d}")

print()

# 2. 分析active截图中第一张和后续截图的占比
print("=" * 80)
print("Active截图分析：第一张 vs 后续截图")
print("=" * 80)

# 获取所有active截图，按engaged_segment_id和时间排序
cursor.execute("""
    SELECT
        id,
        captured_at,
        engaged_segment_id,
        window_app,
        window_title
    FROM screen_captures
    WHERE capture_reason = 'active'
    ORDER BY engaged_segment_id, captured_at
""")

active_screenshots = cursor.fetchall()

# 统计每个segment的截图数量
segment_counts = Counter()
first_shot_count = 0
repeat_shot_count = 0

current_segment = None
segment_position = 0

for shot_id, captured_at, segment_id, app, title in active_screenshots:
    if segment_id != current_segment:
        # 新的segment，这是第一张
        current_segment = segment_id
        segment_position = 1
        first_shot_count += 1
        segment_counts[segment_id] = 1
    else:
        # 同一个segment的后续截图
        segment_position += 1
        repeat_shot_count += 1
        segment_counts[segment_id] += 1

total_active = first_shot_count + repeat_shot_count

print(f"总active截图数: {total_active}")
print(f"第一张截图数: {first_shot_count} ({first_shot_count/total_active*100:.1f}%)")
print(f"后续截图数: {repeat_shot_count} ({repeat_shot_count/total_active*100:.1f}%)")
print()

# 3. 分析segment分布
print("=" * 80)
print("Engaged Segment 分布")
print("=" * 80)

print(f"总segment数: {len(segment_counts)}")
print(f"平均每个segment截图数: {total_active/len(segment_counts):.2f}")
print()

# 统计每个segment截图数量的分布
distribution = Counter(segment_counts.values())
print("截图数量分布:")
for count in sorted(distribution.keys()):
    segments = distribution[count]
    print(f"  {count}张截图的segment: {segments}个 ({segments/len(segment_counts)*100:.1f}%)")

print()

# 4. 找出截图最多的segment
print("=" * 80)
print("截图最多的前10个segment")
print("=" * 80)

top_segments = segment_counts.most_common(10)
for segment_id, count in top_segments:
    cursor.execute("""
        SELECT captured_at, window_app, window_title
        FROM screen_captures
        WHERE engaged_segment_id = ?
        ORDER BY captured_at
        LIMIT 1
    """, (segment_id,))
    first_shot = cursor.fetchone()
    if first_shot:
        captured_at, app, title = first_shot
        print(f"{count:2d}张 | {captured_at} | {app:20s} | {title[:40]}")

conn.close()
