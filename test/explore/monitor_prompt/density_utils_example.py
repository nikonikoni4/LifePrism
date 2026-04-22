"""数据密度计算工具函数使用示例

演示如何使用 lifeprism.llm.utils 中的数据密度计算和时间段识别功能。
"""
from lifeprism.llm.utils import compute_bucket_density, build_time_segments


def example_compute_density():
    """示例：计算时间桶密度"""
    print("=" * 60)
    print("示例 1: 计算时间桶密度")
    print("=" * 60)

    # 准备测试数据
    logs = [
        {
            "start_time": "2026-04-19 09:00:00",
            "end_time": "2026-04-19 09:05:00",
            "duration": 300
        },
        {
            "start_time": "2026-04-19 09:07:00",
            "end_time": "2026-04-19 09:10:00",
            "duration": 180
        }
    ]

    # 计算 9:00-9:10 时间桶的密度
    density = compute_bucket_density(
        bucket_start="2026-04-19 09:00:00",
        bucket_end="2026-04-19 09:10:00",
        logs=logs
    )

    print(f"时间范围: 2026-04-19 09:00:00 -> 2026-04-19 09:10:00")
    print(f"活动记录: 5分钟 + 3分钟 = 8分钟")
    print(f"密度: {density:.2f} (8分钟 / 10分钟)")
    print()


def example_build_segments():
    """示例：识别高密度时间段"""
    print("=" * 60)
    print("示例 2: 识别高密度时间段")
    print("=" * 60)

    # 准备测试数据：模拟一天的活动记录
    logs = [
        # 上午工作时段
        {"start_time": "2026-04-19 09:00:00", "end_time": "2026-04-19 09:30:00", "duration": 1800},
        {"start_time": "2026-04-19 09:30:00", "end_time": "2026-04-19 10:00:00", "duration": 1800},
        {"start_time": "2026-04-19 10:00:00", "end_time": "2026-04-19 10:30:00", "duration": 1800},
        # 午休（低密度）
        {"start_time": "2026-04-19 12:00:00", "end_time": "2026-04-19 12:05:00", "duration": 300},
        # 下午工作时段
        {"start_time": "2026-04-19 14:00:00", "end_time": "2026-04-19 14:30:00", "duration": 1800},
        {"start_time": "2026-04-19 14:30:00", "end_time": "2026-04-19 15:00:00", "duration": 1800},
    ]

    # 识别高密度时间段
    segments = build_time_segments(
        logs=logs,
        range_start="2026-04-19 00:00:00",
        range_end="2026-04-19 23:59:59",
        threshold=0.6,  # 密度阈值 60%
        min_duration_minutes=6,  # 最小时长 6 分钟
        bucket_minutes=10,  # 时间桶大小 10 分钟
        max_bridge_buckets=0  # 不允许桥接
    )

    print(f"参数配置:")
    print(f"  - 密度阈值: 0.6 (60%)")
    print(f"  - 最小时长: 6 分钟")
    print(f"  - 时间桶大小: 10 分钟")
    print(f"  - 最大桥接桶数: 0")
    print()
    print(f"识别到 {len(segments)} 个高密度时间段:")
    print()

    for i, seg in enumerate(segments, 1):
        duration_min = seg["duration_seconds"] // 60
        print(f"时间段 {i}:")
        print(f"  开始: {seg['start']}")
        print(f"  结束: {seg['end']}")
        print(f"  时长: {duration_min} 分钟")
        print(f"  类型: {seg['segment_type']}")
        print()


def example_screenshot_analysis_scenario():
    """示例：截图分析场景（模拟 screenshot_analysis_v2.py 的使用）"""
    print("=" * 60)
    print("示例 3: 截图分析场景")
    print("=" * 60)

    # 模拟真实的活动日志
    logs = [
        {"start_time": "2026-04-19 09:00:00", "end_time": "2026-04-19 09:15:00", "duration": 900, "app": "Chrome", "title": "Google"},
        {"start_time": "2026-04-19 09:15:00", "end_time": "2026-04-19 09:30:00", "duration": 900, "app": "VSCode", "title": "main.py"},
        {"start_time": "2026-04-19 09:35:00", "end_time": "2026-04-19 09:45:00", "duration": 600, "app": "Chrome", "title": "GitHub"},
        {"start_time": "2026-04-19 14:00:00", "end_time": "2026-04-19 14:30:00", "duration": 1800, "app": "Cursor", "title": "test.py"},
    ]

    # Step 1: 获取高密度时间段
    high_density_segments = build_time_segments(
        logs=logs,
        range_start="2026-04-19 00:00:00",
        range_end="2026-04-19 23:59:59",
        threshold=0.6,
        min_duration_minutes=6,
        bucket_minutes=10,
        max_bridge_buckets=0
    )

    print(f"Step 1: 识别到 {len(high_density_segments)} 个高密度时间段")
    print()

    # Step 2: 将高密度时间段切分为 15 分钟块（用于截图分析）
    from datetime import datetime, timedelta

    def split_segment_into_chunks(segment: dict, chunk_minutes: int) -> list:
        """将时间段切分为固定大小的块"""
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
        chunks = split_segment_into_chunks(seg, chunk_minutes=15)
        all_chunks.extend(chunks)

    print(f"Step 2: 切分为 {len(all_chunks)} 个 15 分钟块")
    print()
    print("切分结果:")
    for i, chunk in enumerate(all_chunks, 1):
        print(f"  块 {i}: {chunk['start']} -> {chunk['end']}")
    print()
    print("接下来可以对每个 15 分钟块查询截图并进行语义分析")


if __name__ == "__main__":
    example_compute_density()
    example_build_segments()
    example_screenshot_analysis_scenario()
