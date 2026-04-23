"""
Goal Service 快照测试

在重构 GoalProvider 前捕获当前行为，确保重构后行为不变
"""
import pytest
from syrupy.assertion import SnapshotAssertion

from lifeprism.server.services.goal_service import goal_service
from lifeprism.server.schemas.goal_schemas import (
    CreateGoalRequest,
    UpdateGoalRequest,
)


class TestGoalServiceSnapshot:
    """Goal Service 快照测试"""

    def test_get_goals_snapshot(self, snapshot: SnapshotAssertion):
        """测试获取目标列表"""
        result = goal_service.get_goals(page=1, page_size=10)
        assert result == snapshot

    def test_create_and_delete_goal(self):
        """测试创建和删除目标"""
        request = CreateGoalRequest(
            name=f"测试目标-{pytest.timestamp}",
            content="这是一个测试目标"
        )
        result = goal_service.create_goal(request)
        assert result is not None

        # 清理
        if result:
            success = goal_service.delete_goal(result.id)
            assert success == True

    def test_update_goal(self):
        """测试更新目标"""
        # 创建
        create_request = CreateGoalRequest(
            name=f"测试更新-{pytest.timestamp}",
            content="原始内容"
        )
        created = goal_service.create_goal(create_request)
        assert created is not None

        # 更新
        if created:
            update_request = UpdateGoalRequest(
                content="更新后的内容",
                color="#FF6B6B"
            )
            result = goal_service.update_goal(created.id, update_request)
            assert result is not None

            # 清理
            goal_service.delete_goal(created.id)


@pytest.fixture(scope="session", autouse=True)
def setup_timestamp():
    """设置测试时间戳"""
    import time
    pytest.timestamp = int(time.time())
