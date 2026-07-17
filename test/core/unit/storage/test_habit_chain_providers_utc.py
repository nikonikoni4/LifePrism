"""
Habit Chain Providers UTC 时区迁移测试

验证 Issue #3: Repository 层各 Provider 迁移
测试 seam: HabitChainNodeProvider.batch_update_sort_order

确保 updated_at 字段以 UTC ISO 8601 格式写入。
"""

import re

import pytest

from lifeprism.repository.providers.habit_chain_providers import (
    HabitChainNodeProvider,
    HabitChainProvider,
)

pytestmark = pytest.mark.core


# UTC ISO 8601 格式：2026-07-11T16:29:54.123456+00:00
UTC_ISO_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00$")


@pytest.fixture
def chain_provider(test_data_path):
    """创建 HabitChainProvider 实例"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()
    return HabitChainProvider()


@pytest.fixture
def node_provider(test_data_path):
    """创建 HabitChainNodeProvider 实例"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()
    return HabitChainNodeProvider()


# ==================== batch_update_sort_order 测试 ====================


class TestBatchUpdateSortOrderUtcTimestamps:
    """测试 batch_update_sort_order 写入的 UTC 时间戳格式"""

    def test_updated_at_is_utc_iso8601(self, chain_provider, node_provider):
        """updated_at 应为 UTC ISO 8601 格式（带 +00:00 时区标识）"""
        chain_id = chain_provider.create_chain({"name": "测试链条"})

        node_id_1 = node_provider.create_node(
            {"chain_id": chain_id, "sort_order": 1, "name": "节点1"}
        )
        node_id_2 = node_provider.create_node(
            {"chain_id": chain_id, "sort_order": 2, "name": "节点2"}
        )

        try:
            updates = [
                {"node_id": node_id_1, "sort_order": 10},
                {"node_id": node_id_2, "sort_order": 20},
            ]
            result = node_provider.batch_update_sort_order(updates)
            assert result is True

            node_1 = node_provider.get_node_by_id(node_id_1)
            assert node_1 is not None
            updated_at = node_1["updated_at"]
            assert updated_at is not None, "updated_at 不应为 None"
            assert UTC_ISO_PATTERN.match(updated_at), (
                f"updated_at 应为 UTC ISO 8601 格式，实际: {updated_at}"
            )
        finally:
            chain_provider.delete_chain(chain_id)
