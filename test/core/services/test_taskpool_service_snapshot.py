"""
TaskPool Service 快照测试

在重构 TodoProvider 前捕获当前行为，确保重构后行为不变
"""
import pytest
from syrupy.assertion import SnapshotAssertion

from lifeprism.server.services.taskpool_service import (
    get_taskpool,
    get_todos_by_date,
    create_todo_v2,
    update_todo_with_writeback,
    delete_todo,
)


class TestTaskpoolServiceSnapshot:
    """TaskPool Service 快照测试"""

    def test_get_taskpool_snapshot(self, snapshot: SnapshotAssertion):
        """测试获取任务池列表"""
        result = get_taskpool(state='pool')
        assert result == snapshot

    def test_get_todos_by_date_snapshot(self, snapshot: SnapshotAssertion):
        """测试按日期获取任务"""
        result = get_todos_by_date(date='2026-04-24')
        assert result == snapshot

    def test_create_and_delete_todo(self):
        """测试创建和删除任务"""
        data = {
            'content': f"测试任务-{pytest.timestamp}",
            'state': 'pool'
        }
        result = create_todo_v2(data)
        assert result is not None
        assert result.id is not None

        # 清理
        if result and result.id:
            success = delete_todo(result.id)
            assert success == True

    def test_update_todo(self):
        """测试更新任务"""
        # 创建
        create_data = {
            'content': f"测试更新-{pytest.timestamp}",
            'state': 'pool'
        }
        created = create_todo_v2(create_data)
        assert created is not None

        # 更新
        if created and created.id:
            update_data = {
                'content': "更新后的内容",
                'color': "#FF6B6B"
            }
            result = update_todo_with_writeback(created.id, update_data)
            assert result is not None

            # 清理
            delete_todo(created.id)


@pytest.fixture(scope="session", autouse=True)
def setup_timestamp():
    """设置测试时间戳"""
    import time
    pytest.timestamp = int(time.time())
