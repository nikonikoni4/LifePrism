"""数据密度计算和时间段识别工具函数

提供活动密度计算、高密度时间段识别等功能，用于分析用户活动模式。
"""
from __future__ import annotations

from datetime import datetime, timedelta


def _to_dt(value: str) -> datetime:
    """将 ISO 格式字符串转换为 datetime 对象

    Args:
        value: ISO 格式时间字符串

    Returns:
        datetime: datetime 对象
    """
    return datetime.fromisoformat(value)


def compute_bucket_density(bucket_start: str, bucket_end: str, logs: list[dict]) -> float:
    """计算时间桶内的活动密度

    密度 = 时间桶内有活动记录覆盖的秒数 / 时间桶总秒数。
    用于判断某个时间段内用户是否活跃。

    Args:
        bucket_start: 时间桶开始时间（ISO 格式）
        bucket_end: 时间桶结束时间（ISO 格式）
        logs: 活动日志列表，每项包含 start_time, end_time, duration

    Returns:
        float: 密度值，范围 [0.0, 1.0]
    """
    start_dt = _to_dt(bucket_start)
    end_dt = _to_dt(bucket_end)
    bucket_seconds = int((end_dt - start_dt).total_seconds())
    if bucket_seconds <= 0:
        return 0.0

    overlap_seconds = 0
    for row in logs:
        row_start = _to_dt(row["start_time"])
        row_end = _to_dt(row["end_time"])
        start_overlap = max(start_dt, row_start)
        end_overlap = min(end_dt, row_end)
        if end_overlap > start_overlap:
            overlap_seconds += int((end_overlap - start_overlap).total_seconds())

    return overlap_seconds / bucket_seconds


def _collect_buckets(
    logs: list[dict],
    range_start: str,
    range_end: str,
    threshold: float,
    bucket_minutes: int,
) -> list[dict]:
    """将时间范围切分为固定大小的时间桶，并计算每个桶的密度和是否匹配阈值

    Args:
        logs: 活动日志列表
        range_start: 分析范围开始时间（ISO 格式）
        range_end: 分析范围结束时间（ISO 格式）
        threshold: 密度阈值
        bucket_minutes: 时间桶大小（分钟）

    Returns:
        list[dict]: 时间桶列表，每项包含 start, end, density, matched
    """
    start_dt = _to_dt(range_start)
    end_dt = _to_dt(range_end)
    bucket_span = timedelta(minutes=bucket_minutes)
    cursor = start_dt
    buckets = []

    while cursor < end_dt:
        bucket_end = min(cursor + bucket_span, end_dt)
        density = compute_bucket_density(cursor.isoformat(), bucket_end.isoformat(), logs)
        buckets.append(
            {
                "start": cursor,
                "end": bucket_end,
                "density": density,
                "matched": density >= threshold,
            }
        )
        cursor = bucket_end

    return buckets


def _build_segment_item(
    merged_buckets: list[dict],
    segment_type: str,
) -> dict:
    """根据合并后的时间桶列表构建单个时间段的基本信息

    Args:
        merged_buckets: 合并后的时间桶列表
        segment_type: 段类型标识（如 "active" 或 "long_computer_usage"）

    Returns:
        dict: 时间段信息，包含 start, end, duration_seconds, segment_type
    """
    segment_start = merged_buckets[0]["start"]
    segment_end = merged_buckets[-1]["end"]
    duration_seconds = int((segment_end - segment_start).total_seconds())

    return {
        "start": segment_start.isoformat(),
        "end": segment_end.isoformat(),
        "duration_seconds": duration_seconds,
        "segment_type": segment_type,
    }


def build_time_segments(
    logs: list[dict],
    range_start: str,
    range_end: str,
    threshold: float,
    min_duration_minutes: int,
    segment_type: str = "active",
    bucket_minutes: int = 10,
    max_bridge_buckets: int = 1,
) -> list[dict]:
    """识别并构建高密度时间段列表

    使用滑动窗口算法，将连续的高密度时间桶合并为时间段，
    允许少量低密度桶作为桥接（bridge），过滤掉时长不足的段。

    Args:
        logs: 活动日志列表，每项包含 start_time, end_time, duration
        range_start: 分析范围开始时间（ISO 格式）
        range_end: 分析范围结束时间（ISO 格式）
        threshold: 密度阈值，超过此值的桶被视为活跃
        min_duration_minutes: 最小段时长（分钟），短于此值的段会被过滤
        segment_type: 段类型标识（如 "active" 或 "long_computer_usage"），默认 "active"
        bucket_minutes: 时间桶大小（分钟），默认 10
        max_bridge_buckets: 最大桥接桶数量，默认 1

    Returns:
        list[dict]: 时间段列表，每项包含 start, end, duration_seconds, segment_type

    Example:
        >>> logs = [
        ...     {"start_time": "2026-04-19 09:00:00", "end_time": "2026-04-19 09:30:00", "duration": 1800},
        ...     {"start_time": "2026-04-19 09:30:00", "end_time": "2026-04-19 10:00:00", "duration": 1800},
        ... ]
        >>> segments = build_time_segments(
        ...     logs=logs,
        ...     range_start="2026-04-19 00:00:00",
        ...     range_end="2026-04-19 23:59:59",
        ...     threshold=0.6,
        ...     min_duration_minutes=6
        ... )
    """
    buckets = _collect_buckets(logs, range_start, range_end, threshold, bucket_minutes)
    segments: list[dict] = []
    current: list[dict] = []
    bridge_count = 0

    def flush_current() -> None:
        """将当前累积的时间桶列表转换为时间段（如果满足最小时长要求）"""
        if not current:
            return
        duration_seconds = int((current[-1]["end"] - current[0]["start"]).total_seconds())
        if duration_seconds >= min_duration_minutes * 60:
            segments.append(_build_segment_item(current, segment_type))

    for bucket in buckets:
        if bucket["matched"]:
            current.append(bucket)
            bridge_count = 0
            continue

        if current and bridge_count < max_bridge_buckets:
            current.append(bucket)
            bridge_count += 1
            continue

        flush_current()
        current = []
        bridge_count = 0

    flush_current()
    return segments
