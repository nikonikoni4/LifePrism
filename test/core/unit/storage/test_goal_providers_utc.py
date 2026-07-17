"""
Goal Providers UTC 时区迁移测试

验证 Issue #3: Repository 层各 Provider 迁移
测试 seam: GoalProvider.update_time_invested

确保 time_invested_updated_at 字段以 UTC ISO 8601 格式写入。
"""

import re

import pytest

from lifeprism.repository.providers.goal_providers import GoalProvider

pytestmark = pytest.mark.core


# UTC ISO 8601 格式：2026-07-11T16:29:54.123456+00:00
UTC_ISO_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00$")


@pytest.fixture
def goal_provider(test_data_path):
    """创建 GoalProvider 实例"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()
    return GoalProvider()


def _create_goal(provider: GoalProvider, name: str = "测试目标") -> str:
    """创建测试用目标，返回 goal_id"""
    return provider.create_goal({"name": name})


# ==================== update_time_invested 测试 ====================


class TestUpdateTimeInvestedUtcTimestamps:
    """测试 update_time_invested 写入的 UTC 时间戳格式"""

    def test_time_invested_updated_at_is_utc_iso8601(self, goal_provider):
        """time_invested_updated_at 应为 UTC ISO 8601 格式（带 +00:00 时区标识）"""
        goal_id = _create_goal(goal_provider, "时间投入目标")

        try:
            result = goal_provider.update_time_invested(goal_id, 3600)
            assert result is True

            goal = goal_provider.get_goal_by_id(goal_id)
            assert goal is not None

            time_invested_updated_at = goal["time_invested_updated_at"]
            assert time_invested_updated_at is not None, "time_invested_updated_at 不应为 None"
            assert UTC_ISO_PATTERN.match(time_invested_updated_at), (
                f"time_invested_updated_at 应为 UTC ISO 8601 格式，实际: {time_invested_updated_at}"
            )
        finally:
            goal_provider.delete_goal(goal_id)
