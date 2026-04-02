from lifeprism.llm.summary_context.aggregators.activity_aggregator import (
    build_activity_context,
    compute_bucket_density,
)


def _log(start_time: str, end_time: str, duration: int, category_id: str, category_name: str):
    return {
        "start_time": start_time,
        "end_time": end_time,
        "duration": duration,
        "category_id": category_id,
        "category_name": category_name,
    }


def test_compute_bucket_density_uses_overlap_seconds():
    density = compute_bucket_density(
        bucket_start="2026-04-02T09:00:00+08:00",
        bucket_end="2026-04-02T09:10:00+08:00",
        logs=[
            _log("2026-04-02T09:05:00+08:00", "2026-04-02T09:10:00+08:00", 300, "cat-work", "工作")
        ],
    )
    assert round(density, 2) == 0.5


def test_active_segments_allow_one_bridge_bucket():
    logs = [
        _log("2026-04-02T09:00:00+08:00", "2026-04-02T09:10:00+08:00", 600, "cat-work", "工作"),
        _log("2026-04-02T09:20:00+08:00", "2026-04-02T09:40:00+08:00", 1200, "cat-work", "工作"),
    ]
    context = build_activity_context(
        logs=logs,
        range_start="2026-04-02T09:00:00+08:00",
        range_end="2026-04-02T10:00:00+08:00",
    )
    assert len(context["active_segments"]) == 1
    assert context["active_segments"][0]["duration_seconds"] == 2400


def test_long_usage_requires_high_density_and_sixty_minutes():
    logs = [
        _log("2026-04-02T13:00:00+08:00", "2026-04-02T14:10:00+08:00", 4200, "cat-work", "工作")
    ]
    context = build_activity_context(
        logs=logs,
        range_start="2026-04-02T13:00:00+08:00",
        range_end="2026-04-02T14:30:00+08:00",
    )
    assert len(context["long_computer_usage_segments"]) == 1
    assert context["long_computer_usage_segments"][0]["segment_type"] == "long_computer_usage"


def test_work_entertainment_mix_uses_category_ids_not_names():
    logs = [
        _log("2026-04-02T18:00:00+08:00", "2026-04-02T18:20:00+08:00", 1200, "cat-work", "工作"),
        _log("2026-04-02T18:20:00+08:00", "2026-04-02T18:40:00+08:00", 1200, "cat-entertainment", "娱乐"),
    ]
    context = build_activity_context(
        logs=logs,
        range_start="2026-04-02T18:00:00+08:00",
        range_end="2026-04-02T19:00:00+08:00",
    )
    assert context["work_entertainment_mix"]["should_analyze"] is True
