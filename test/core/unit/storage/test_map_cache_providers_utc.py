"""
Map Cache Providers UTC 时区迁移测试

验证 Issue #3: Repository 层各 Provider 迁移
测试 seam:
  - MultiPurposeMapCacheProvider.batch_update_multi_purpose_map_cache
  - SinglePurposeMapCacheProvider.batch_update_single_purpose_map_cache

确保批量更新时 updated_at 字段以 UTC ISO 8601 格式写入。
"""
import re
import uuid

import pytest

from lifeprism.repository.providers.map_cache_providers import (
    MultiPurposeMapCacheProvider,
    SinglePurposeMapCacheProvider,
)

pytestmark = pytest.mark.core


# UTC ISO 8601 格式：2026-07-11T16:29:54.123456+00:00
UTC_ISO_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00$")


@pytest.fixture
def multi_purpose_provider(test_data_path):
    """创建 MultiPurposeMapCacheProvider 实例"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()
    return MultiPurposeMapCacheProvider()


@pytest.fixture
def single_purpose_provider(test_data_path):
    """创建 SinglePurposeMapCacheProvider 实例"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()
    return SinglePurposeMapCacheProvider()


def _generate_id(prefix: str = "m") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _create_multi_record(cache_id=None):
    if cache_id is None:
        cache_id = _generate_id("m")
    suffix = cache_id.split("-")[1] if "-" in cache_id else cache_id[:8]
    return {
        "id": cache_id,
        "app": f"test-{suffix}.exe",
        "title": f"Title {suffix}",
        "app_description": "desc",
        "title_analysis": "analysis",
        "category_id": "cat-1",
        "sub_category_id": "sub-1",
        "state": 1,
        "link_to_goal_id": None,
    }


def _create_single_record(cache_id=None):
    if cache_id is None:
        cache_id = _generate_id("s")
    suffix = cache_id.split("-")[1] if "-" in cache_id else cache_id[:8]
    return {
        "id": cache_id,
        "app": f"single-{suffix}.exe",
        "title": f"Single {suffix}",
        "app_description": "desc",
        "category_id": "cat-1",
        "sub_category_id": "sub-1",
        "state": 1,
    }


# ==================== batch_update_multi_purpose_map_cache 测试 ====================


class TestBatchUpdateMultiPurposeMapCacheUtcTimestamps:
    """测试 batch_update_multi_purpose_map_cache 写入的 UTC 时间戳格式"""

    def test_updated_at_is_utc_iso8601(self, multi_purpose_provider):
        """批量更新后 updated_at 应为 UTC ISO 8601 格式"""
        cache_ids = [_generate_id("m") for _ in range(2)]
        for cache_id in cache_ids:
            multi_purpose_provider.create_multi_purpose_map_cache(
                _create_multi_record(cache_id)
            )

        try:
            update_data = {"state": 0}
            count = multi_purpose_provider.batch_update_multi_purpose_map_cache(
                cache_ids, update_data
            )
            assert count == 2

            record = multi_purpose_provider.get_multi_purpose_map_cache_by_id(
                cache_ids[0]
            )
            assert record is not None
            updated_at = record["updated_at"]
            assert updated_at is not None, "updated_at 不应为 None"
            assert UTC_ISO_PATTERN.match(updated_at), (
                f"updated_at 应为 UTC ISO 8601 格式，实际: {updated_at}"
            )
        finally:
            multi_purpose_provider.batch_delete_multi_purpose_map_cache(cache_ids)


# ==================== batch_update_single_purpose_map_cache 测试 ====================


class TestBatchUpdateSinglePurposeMapCacheUtcTimestamps:
    """测试 batch_update_single_purpose_map_cache 写入的 UTC 时间戳格式"""

    def test_updated_at_is_utc_iso8601(self, single_purpose_provider):
        """批量更新后 updated_at 应为 UTC ISO 8601 格式"""
        cache_ids = [_generate_id("s") for _ in range(2)]
        for cache_id in cache_ids:
            single_purpose_provider.create_single_purpose_map_cache(
                _create_single_record(cache_id)
            )

        try:
            update_data = {"state": 0}
            count = single_purpose_provider.batch_update_single_purpose_map_cache(
                cache_ids, update_data
            )
            assert count == 2

            record = single_purpose_provider.get_single_purpose_map_cache_by_id(
                cache_ids[0]
            )
            assert record is not None
            updated_at = record["updated_at"]
            assert updated_at is not None, "updated_at 不应为 None"
            assert UTC_ISO_PATTERN.match(updated_at), (
                f"updated_at 应为 UTC ISO 8601 格式，实际: {updated_at}"
            )
        finally:
            single_purpose_provider.batch_delete_single_purpose_map_cache(cache_ids)
