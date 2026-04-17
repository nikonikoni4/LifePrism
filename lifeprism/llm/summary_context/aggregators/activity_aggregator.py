from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta


TIME_BUCKET_MINUTES = 10
MAX_BRIDGE_BUCKETS = 1
ACTIVE_SEGMENT_DENSITY_THRESHOLD = 0.2
ACTIVE_SEGMENT_MIN_DURATION_MINUTES = 30
LONG_USAGE_DENSITY_THRESHOLD = 0.7
LONG_USAGE_MIN_DURATION_MINUTES = 60
WORK_CATEGORY_IDS = {"cat-work", "cat-study"}
ENTERTAINMENT_CATEGORY_IDS = {"cat-entertainment"}


def _to_dt(value: str) -> datetime:
    """将 ISO 格式字符串转换为 datetime 对象"""
    return datetime.fromisoformat(value)


def compute_bucket_density(bucket_start: str, bucket_end: str, logs: list[dict]) -> float:
    """计算时间桶内的活动密度。

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


def _build_category_breakdown(logs: list[dict]) -> list[dict]:
    """构建分类时长分布列表（按时长降序排列）"""
    total_by_category: dict[str, int] = defaultdict(int)
    name_by_category: dict[str, str] = {}

    for row in logs:
        category_id = row.get("category_id")
        # 过滤掉无效的 category_id（None, nan, 空字符串等）
        if not category_id or (isinstance(category_id, float) and category_id != category_id):
            category_id = "cat-unknown"

        seconds = int(row.get("duration", 0))
        total_by_category[category_id] += seconds
        name_by_category[category_id] = row.get("category_name") or "未分类"

    total_seconds = sum(total_by_category.values())
    items: list[dict] = []
    for category_id, seconds in sorted(total_by_category.items(), key=lambda x: x[1], reverse=True):
        items.append(
            {
                "category_id": category_id,
                "category_name": name_by_category[category_id],
                "seconds": seconds,
                "ratio": 0.0 if total_seconds == 0 else round(seconds / total_seconds, 4),
            }
        )
    return items


def _build_category_breakdown_for_segment(
    logs: list[dict],
    segment_start: datetime,
    segment_end: datetime,
) -> list[dict]:
    """构建特定时间段内的分类时长分布（只统计与时间段重叠的部分）"""
    total_by_category: dict[str, int] = defaultdict(int)
    name_by_category: dict[str, str] = {}

    for row in logs:
        row_start = _to_dt(row["start_time"])
        row_end = _to_dt(row["end_time"])
        overlap_start = max(segment_start, row_start)
        overlap_end = min(segment_end, row_end)
        if overlap_end <= overlap_start:
            continue

        overlap_seconds = int((overlap_end - overlap_start).total_seconds())
        category_id = row.get("category_id")
        # 过滤掉无效的 category_id（None, nan, 空字符串等）
        if not category_id or (isinstance(category_id, float) and category_id != category_id):
            category_id = "cat-unknown"

        total_by_category[category_id] += overlap_seconds
        name_by_category[category_id] = row.get("category_name") or "未分类"

    total_seconds = sum(total_by_category.values())
    items: list[dict] = []
    for category_id, seconds in sorted(total_by_category.items(), key=lambda x: x[1], reverse=True):
        items.append(
            {
                "category_id": category_id,
                "category_name": name_by_category[category_id],
                "seconds": seconds,
                "ratio": 0.0 if total_seconds == 0 else round(seconds / total_seconds, 4),
            }
        )
    return items


def _collect_buckets(logs: list[dict], range_start: str, range_end: str, threshold: float) -> list[dict]:
    """将时间范围切分为固定大小的时间桶，并计算每个桶的密度和是否匹配阈值"""
    start_dt = _to_dt(range_start)
    end_dt = _to_dt(range_end)
    bucket_span = timedelta(minutes=TIME_BUCKET_MINUTES)
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
    logs: list[dict],
    threshold: float,
    segment_type: str,
) -> dict:
    """根据合并后的时间桶列表构建单个活动段的详细信息"""
    segment_start = merged_buckets[0]["start"]
    segment_end = merged_buckets[-1]["end"]
    duration_seconds = int((segment_end - segment_start).total_seconds())

    segment_logs = []
    for row in logs:
        row_start = _to_dt(row["start_time"])
        row_end = _to_dt(row["end_time"])
        if row_start < segment_end and row_end > segment_start:
            segment_logs.append(row)

    return {
        "start": segment_start.isoformat(),
        "end": segment_end.isoformat(),
        "duration_seconds": duration_seconds,
        "segment_type": segment_type,
        "density_threshold": threshold,
        "bridge_bucket_count": sum(1 for item in merged_buckets if not item["matched"]),
        "top_categories": _build_category_breakdown_for_segment(segment_logs, segment_start, segment_end)[:3],
    }


def _build_segments(
    logs: list[dict],
    range_start: str,
    range_end: str,
    threshold: float,
    min_duration_minutes: int,
    segment_type: str,
) -> list[dict]:
    """识别并构建活动段列表。

    使用滑动窗口算法，将连续的高密度时间桶合并为活动段，
    允许少量低密度桶作为桥接（bridge），过滤掉时长不足的段。

    Args:
        logs: 活动日志列表
        range_start: 分析范围开始时间（ISO 格式）
        range_end: 分析范围结束时间（ISO 格式）
        threshold: 密度阈值，超过此值的桶被视为活跃
        min_duration_minutes: 最小段时长（分钟），短于此值的段会被过滤
        segment_type: 段类型标识（如 "active" 或 "long_computer_usage"）

    Returns:
        list[dict]: 活动段列表，每项包含 start, end, duration_seconds, top_categories 等
    """
    buckets = _collect_buckets(logs, range_start, range_end, threshold)
    segments: list[dict] = []
    current: list[dict] = []
    bridge_count = 0

    def flush_current() -> None:
        """将当前累积的时间桶列表转换为活动段（如果满足最小时长要求）"""
        if not current:
            return
        duration_seconds = int((current[-1]["end"] - current[0]["start"]).total_seconds())
        if duration_seconds >= min_duration_minutes * 60:
            segments.append(_build_segment_item(current, logs, threshold, segment_type))

    for bucket in buckets:
        if bucket["matched"]:
            current.append(bucket)
            continue

        if current and bridge_count < MAX_BRIDGE_BUCKETS:
            current.append(bucket)
            bridge_count += 1
            continue

        flush_current()
        current = []
        bridge_count = 0

    flush_current()
    return segments


def build_activity_context(logs: list[dict], range_start: str, range_end: str) -> dict:
    """构建活动上下文，包含总时长、分类分布、活动段、长时间使用段等。

    这是活动数据聚合的主入口函数，将原始活动日志转换为结构化的分析结果，
    用于 AI 总结时理解用户的电脑使用模式。

    Args:
        logs: 活动日志列表，每项包含 start_time, end_time, duration, category_id, category_name
        range_start: 分析范围开始时间（ISO 格式）
        range_end: 分析范围结束时间（ISO 格式）

    Returns:
        dict: 包含以下键的字典：
            - total_active_seconds: 总活跃秒数
            - category_breakdown: 分类时长分布列表
            - active_segments: 活跃时间段列表（密度阈值 0.2，最小 30 分钟）
            - long_computer_usage_segments: 长时间使用段列表（密度阈值 0.7，最小 60 分钟）
            - work_entertainment_mix: 工作娱乐混合分析标志
    """
    category_breakdown = _build_category_breakdown(logs)
    category_ids = {item["category_id"] for item in category_breakdown}
    has_work = bool(category_ids & WORK_CATEGORY_IDS)
    has_entertainment = bool(category_ids & ENTERTAINMENT_CATEGORY_IDS)

    return {
        "total_active_seconds": sum(int(row.get("duration", 0)) for row in logs),
        "category_breakdown": category_breakdown,
        "active_segments": _build_segments(
            logs=logs,
            range_start=range_start,
            range_end=range_end,
            threshold=ACTIVE_SEGMENT_DENSITY_THRESHOLD,
            min_duration_minutes=ACTIVE_SEGMENT_MIN_DURATION_MINUTES,
            segment_type="active",
        ),
        "long_computer_usage_segments": _build_segments(
            logs=logs,
            range_start=range_start,
            range_end=range_end,
            threshold=LONG_USAGE_DENSITY_THRESHOLD,
            min_duration_minutes=LONG_USAGE_MIN_DURATION_MINUTES,
            segment_type="long_computer_usage",
        ),
        "work_entertainment_mix": {
            "should_analyze": has_work and has_entertainment,
            "reason": "ready" if has_work and has_entertainment else "missing_required_main_categories",
        },
    }
