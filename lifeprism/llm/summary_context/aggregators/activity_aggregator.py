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
    return datetime.fromisoformat(value)


def compute_bucket_density(bucket_start: str, bucket_end: str, logs: list[dict]) -> float:
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
    total_by_category: dict[str, int] = defaultdict(int)
    name_by_category: dict[str, str] = {}

    for row in logs:
        category_id = row.get("category_id") or "cat-unknown"
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
        category_id = row.get("category_id") or "cat-unknown"
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
    buckets = _collect_buckets(logs, range_start, range_end, threshold)
    segments: list[dict] = []
    current: list[dict] = []
    bridge_count = 0

    def flush_current() -> None:
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

if __name__ == "__main__":
    print(build_activity_context())