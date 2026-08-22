"""
RawBehaviorAnalysisProvider UTC 时间戳测试

测试 seam: RawBehaviorAnalysisProvider.batch_create_raw_behaviors

确保批量插入的原始行为分析记录 updated_at 字段以 UTC ISO 8601 格式写入
（非 NULL）。NULL 的 updated_at 行无法被增量同步（WHERE updated_at > ?
恒为假），对应 2026-08-21 bug：raw_behavior_analysis 手写 INSERT 漏写
updated_at，持续产生不可同步的 NULL 行。
"""

import re

import pytest

pytestmark = pytest.mark.core


# UTC ISO 8601 格式：2026-07-11T16:29:54.123456+00:00
UTC_ISO_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00$")


@pytest.fixture
def provider(test_data_path):
    """创建 RawBehaviorAnalysisProvider 实例"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()
    from lifeprism.repository.providers.raw_behavior_analysis_provider import (
        RawBehaviorAnalysisProvider,
    )

    return RawBehaviorAnalysisProvider()


@pytest.fixture
def sample_records():
    """生成测试记录（start_time 为主键；end_time 必须大于 start_time，表有 CHECK 约束）"""
    return [
        {
            "start_time": "2026-08-20 10:30:00",
            "end_time": "2026-08-20 10:35:00",
            "behavior": "working",
            "screen_count": 3,
        },
        {
            "start_time": "2026-08-20 11:30:00",
            "end_time": "2026-08-20 11:35:00",
            "behavior": "learning",
            "screen_count": 1,
        },
    ]


@pytest.fixture
def cleanup_records(provider, sample_records):
    """清理测试数据（前后各清一次，保证重复运行幂等）"""
    def _delete():
        with provider.db.get_connection() as conn:
            cursor = conn.cursor()
            for record in sample_records:
                cursor.execute(
                    "DELETE FROM raw_behavior_analysis WHERE start_time = ?",
                    (record["start_time"],),
                )
            conn.commit()

    _delete()
    yield
    _delete()


class TestBatchCreateRawBehaviorsUtcTimestamps:
    """测试 batch_create_raw_behaviors 写入的时间戳格式"""

    def test_updated_at_is_utc_iso8601(self, provider, sample_records, cleanup_records):
        """批量插入后每行的 updated_at 应为非 NULL 且 UTC ISO 8601 格式"""
        affected = provider.batch_create_raw_behaviors(sample_records)
        assert affected == 2

        with provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT start_time, created_at, updated_at FROM raw_behavior_analysis "
                "WHERE start_time IN (?, ?)",
                (sample_records[0]["start_time"], sample_records[1]["start_time"]),
            )
            rows = cursor.fetchall()
        assert len(rows) == 2
        for start_time, created_at, updated_at in rows:
            assert created_at is not None, f"created_at 不应为 None: {start_time}"
            assert UTC_ISO_PATTERN.match(created_at), (
                f"created_at 应为 UTC ISO 8601 格式，实际: {created_at}"
            )
            assert updated_at is not None, (
                f"updated_at 不应为 None（NULL 行无法被增量同步）: {start_time}"
            )
            assert UTC_ISO_PATTERN.match(updated_at), (
                f"updated_at 应为 UTC ISO 8601 格式，实际: {updated_at}"
            )
