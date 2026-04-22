"""测试 lifeprism.llm.utils 模块的数据密度计算和时间段识别功能"""
import pytest
from datetime import datetime

from lifeprism.llm.utils.density_utils import (
    compute_bucket_density,
    build_time_segments,
)
from lifeprism.llm.summary_context.aggregators.activity_aggregator import (
    _build_segments,
)


@pytest.mark.core
class TestComputeBucketDensity:
    """测试时间桶密度计算"""

    def test_empty_logs(self):
        """测试空日志列表"""
        density = compute_bucket_density(
            bucket_start="2026-04-19 09:00:00",
            bucket_end="2026-04-19 09:10:00",
            logs=[]
        )
        assert density == 0.0

    def test_full_coverage(self):
        """测试完全覆盖的情况"""
        logs = [
            {
                "start_time": "2026-04-19 09:00:00",
                "end_time": "2026-04-19 09:10:00",
                "duration": 600
            }
        ]
        density = compute_bucket_density(
            bucket_start="2026-04-19 09:00:00",
            bucket_end="2026-04-19 09:10:00",
            logs=logs
        )
        assert density == 1.0

    def test_partial_coverage(self):
        """测试部分覆盖的情况"""
        logs = [
            {
                "start_time": "2026-04-19 09:00:00",
                "end_time": "2026-04-19 09:05:00",
                "duration": 300
            }
        ]
        density = compute_bucket_density(
            bucket_start="2026-04-19 09:00:00",
            bucket_end="2026-04-19 09:10:00",
            logs=logs
        )
        assert density == 0.5

    def test_multiple_logs_overlap(self):
        """测试多条日志重叠的情况"""
        logs = [
            {
                "start_time": "2026-04-19 09:00:00",
                "end_time": "2026-04-19 09:03:00",
                "duration": 180
            },
            {
                "start_time": "2026-04-19 09:05:00",
                "end_time": "2026-04-19 09:08:00",
                "duration": 180
            }
        ]
        density = compute_bucket_density(
            bucket_start="2026-04-19 09:00:00",
            bucket_end="2026-04-19 09:10:00",
            logs=logs
        )
        # 3分钟 + 3分钟 = 6分钟，总共10分钟
        assert density == 0.6

    def test_log_outside_bucket(self):
        """测试日志完全在时间桶外的情况"""
        logs = [
            {
                "start_time": "2026-04-19 08:00:00",
                "end_time": "2026-04-19 08:30:00",
                "duration": 1800
            }
        ]
        density = compute_bucket_density(
            bucket_start="2026-04-19 09:00:00",
            bucket_end="2026-04-19 09:10:00",
            logs=logs
        )
        assert density == 0.0


@pytest.mark.core
class TestBuildTimeSegments:
    """测试时间段识别功能"""

    def test_empty_logs(self):
        """测试空日志列表"""
        segments = build_time_segments(
            logs=[],
            range_start="2026-04-19 00:00:00",
            range_end="2026-04-19 23:59:59",
            threshold=0.6,
            min_duration_minutes=6
        )
        assert segments == []

    def test_single_high_density_segment(self):
        """测试单个高密度时间段"""
        logs = [
            {"start_time": "2026-04-19 09:00:00", "end_time": "2026-04-19 09:30:00", "duration": 1800},
        ]
        segments = build_time_segments(
            logs=logs,
            range_start="2026-04-19 00:00:00",
            range_end="2026-04-19 23:59:59",
            threshold=0.6,
            min_duration_minutes=6
        )
        assert len(segments) > 0
        assert segments[0]["segment_type"] == "active"
        assert "start" in segments[0]
        assert "end" in segments[0]
        assert "duration_seconds" in segments[0]

    def test_filter_short_segments(self):
        """测试过滤短时间段"""
        logs = [
            {"start_time": "2026-04-19 09:00:00", "end_time": "2026-04-19 09:03:00", "duration": 180},
        ]
        segments = build_time_segments(
            logs=logs,
            range_start="2026-04-19 00:00:00",
            range_end="2026-04-19 23:59:59",
            threshold=0.6,
            min_duration_minutes=10  # 最小10分钟
        )
        # 3分钟的活动应该被过滤掉
        assert len(segments) == 0

    def test_custom_segment_type(self):
        """测试自定义段类型"""
        logs = [
            {"start_time": "2026-04-19 09:00:00", "end_time": "2026-04-19 10:00:00", "duration": 3600},
        ]
        segments = build_time_segments(
            logs=logs,
            range_start="2026-04-19 00:00:00",
            range_end="2026-04-19 23:59:59",
            threshold=0.7,
            min_duration_minutes=30,
            segment_type="long_computer_usage"
        )
        assert len(segments) > 0
        assert segments[0]["segment_type"] == "long_computer_usage"


@pytest.mark.core
class TestConsistencyWithActivityAggregator:
    """测试与 activity_aggregator._build_segments 的一致性"""

    def test_consistency_with_default_params(self):
        """测试默认参数下的一致性"""
        logs = [
            {"start_time": "2026-04-19 09:00:00", "end_time": "2026-04-19 09:30:00", "duration": 1800},
            {"start_time": "2026-04-19 09:30:00", "end_time": "2026-04-19 10:00:00", "duration": 1800},
            {"start_time": "2026-04-19 14:00:00", "end_time": "2026-04-19 14:20:00", "duration": 1200},
        ]
        range_start = "2026-04-19 00:00:00"
        range_end = "2026-04-19 23:59:59"
        threshold = 0.6
        min_duration_minutes = 6

        # 调用新工具函数
        new_segments = build_time_segments(
            logs=logs,
            range_start=range_start,
            range_end=range_end,
            threshold=threshold,
            min_duration_minutes=min_duration_minutes,
            segment_type="active",
            bucket_minutes=10,
            max_bridge_buckets=1
        )

        # 调用原有函数
        old_segments = _build_segments(
            logs=logs,
            range_start=range_start,
            range_end=range_end,
            threshold=threshold,
            min_duration_minutes=min_duration_minutes,
            segment_type="active"
        )

        # 验证数量一致
        assert len(new_segments) == len(old_segments), \
            f"时间段数量不一致: new={len(new_segments)}, old={len(old_segments)}"

        # 验证每个时间段的关键字段一致
        for i, (new_seg, old_seg) in enumerate(zip(new_segments, old_segments)):
            assert new_seg["start"] == old_seg["start"], \
                f"第{i}个时间段的start不一致: new={new_seg['start']}, old={old_seg['start']}"
            assert new_seg["end"] == old_seg["end"], \
                f"第{i}个时间段的end不一致: new={new_seg['end']}, old={old_seg['end']}"
            assert new_seg["duration_seconds"] == old_seg["duration_seconds"], \
                f"第{i}个时间段的duration_seconds不一致: new={new_seg['duration_seconds']}, old={old_seg['duration_seconds']}"
            assert new_seg["segment_type"] == old_seg["segment_type"], \
                f"第{i}个时间段的segment_type不一致: new={new_seg['segment_type']}, old={old_seg['segment_type']}"

    def test_consistency_with_custom_params(self):
        """测试自定义参数下的一致性"""
        logs = [
            {"start_time": "2026-04-19 09:00:00", "end_time": "2026-04-19 11:00:00", "duration": 7200},
            {"start_time": "2026-04-19 14:00:00", "end_time": "2026-04-19 16:00:00", "duration": 7200},
        ]
        range_start = "2026-04-19 00:00:00"
        range_end = "2026-04-19 23:59:59"
        threshold = 0.7
        min_duration_minutes = 60

        # 需要修改 activity_aggregator 的全局参数
        import lifeprism.llm.summary_context.aggregators.activity_aggregator as agg_module
        original_bucket_minutes = agg_module.TIME_BUCKET_MINUTES
        original_max_bridge = agg_module.MAX_BRIDGE_BUCKETS

        try:
            agg_module.TIME_BUCKET_MINUTES = 10
            agg_module.MAX_BRIDGE_BUCKETS = 1

            # 调用新工具函数
            new_segments = build_time_segments(
                logs=logs,
                range_start=range_start,
                range_end=range_end,
                threshold=threshold,
                min_duration_minutes=min_duration_minutes,
                segment_type="long_computer_usage",
                bucket_minutes=10,
                max_bridge_buckets=1
            )

            # 调用原有函数
            old_segments = _build_segments(
                logs=logs,
                range_start=range_start,
                range_end=range_end,
                threshold=threshold,
                min_duration_minutes=min_duration_minutes,
                segment_type="long_computer_usage"
            )

            # 验证一致性
            assert len(new_segments) == len(old_segments)
            for new_seg, old_seg in zip(new_segments, old_segments):
                assert new_seg["start"] == old_seg["start"]
                assert new_seg["end"] == old_seg["end"]
                assert new_seg["duration_seconds"] == old_seg["duration_seconds"]

        finally:
            # 恢复原始参数
            agg_module.TIME_BUCKET_MINUTES = original_bucket_minutes
            agg_module.MAX_BRIDGE_BUCKETS = original_max_bridge

    def test_consistency_with_real_scenario(self):
        """测试真实场景下的一致性（模拟 screenshot_analysis_v2.py 的使用场景）"""
        # 模拟真实的活动日志数据
        logs = [
            {"start_time": "2026-04-19 09:00:00", "end_time": "2026-04-19 09:15:00", "duration": 900, "app": "Chrome", "title": "Google"},
            {"start_time": "2026-04-19 09:15:00", "end_time": "2026-04-19 09:30:00", "duration": 900, "app": "VSCode", "title": "main.py"},
            {"start_time": "2026-04-19 09:35:00", "end_time": "2026-04-19 09:45:00", "duration": 600, "app": "Chrome", "title": "GitHub"},
            {"start_time": "2026-04-19 14:00:00", "end_time": "2026-04-19 14:30:00", "duration": 1800, "app": "Cursor", "title": "test.py"},
        ]
        range_start = "2026-04-19 00:00:00"
        range_end = "2026-04-19 23:59:59"
        threshold = 0.6
        min_duration_minutes = 6

        # 修改全局参数以匹配 screenshot_analysis_v2.py
        import lifeprism.llm.summary_context.aggregators.activity_aggregator as agg_module
        original_bucket_minutes = agg_module.TIME_BUCKET_MINUTES
        original_max_bridge = agg_module.MAX_BRIDGE_BUCKETS
        original_threshold = agg_module.ACTIVE_SEGMENT_DENSITY_THRESHOLD
        original_min_duration = agg_module.ACTIVE_SEGMENT_MIN_DURATION_MINUTES

        try:
            agg_module.TIME_BUCKET_MINUTES = 10
            agg_module.MAX_BRIDGE_BUCKETS = 0
            agg_module.ACTIVE_SEGMENT_DENSITY_THRESHOLD = 0.6
            agg_module.ACTIVE_SEGMENT_MIN_DURATION_MINUTES = 6

            # 调用新工具函数
            new_segments = build_time_segments(
                logs=logs,
                range_start=range_start,
                range_end=range_end,
                threshold=threshold,
                min_duration_minutes=min_duration_minutes,
                segment_type="active",
                bucket_minutes=10,
                max_bridge_buckets=0
            )

            # 调用原有函数
            old_segments = _build_segments(
                logs=logs,
                range_start=range_start,
                range_end=range_end,
                threshold=threshold,
                min_duration_minutes=min_duration_minutes,
                segment_type="active"
            )

            # 验证一致性
            assert len(new_segments) == len(old_segments), \
                f"真实场景下时间段数量不一致: new={len(new_segments)}, old={len(old_segments)}"

            for i, (new_seg, old_seg) in enumerate(zip(new_segments, old_segments)):
                assert new_seg["start"] == old_seg["start"], \
                    f"真实场景第{i}个时间段的start不一致"
                assert new_seg["end"] == old_seg["end"], \
                    f"真实场景第{i}个时间段的end不一致"
                assert new_seg["duration_seconds"] == old_seg["duration_seconds"], \
                    f"真实场景第{i}个时间段的duration_seconds不一致"

        finally:
            # 恢复原始参数
            agg_module.TIME_BUCKET_MINUTES = original_bucket_minutes
            agg_module.MAX_BRIDGE_BUCKETS = original_max_bridge
            agg_module.ACTIVE_SEGMENT_DENSITY_THRESHOLD = original_threshold
            agg_module.ACTIVE_SEGMENT_MIN_DURATION_MINUTES = original_min_duration
