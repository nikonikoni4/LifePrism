"""
Timeline Service 快照测试

测试 timeline_service 的核心功能，确保重构后行为一致
"""
import pytest
from syrupy.assertion import SnapshotAssertion
from datetime import datetime

from lifeprism.server.services.timeline_service import (
    get_custom_block,
    get_custom_blocks_by_time_range,
    create_custom_block,
    update_custom_block,
    delete_custom_block,
)
from lifeprism.server.schemas.timeline_schemas import (
    UserCustomBlockCreate,
    UserCustomBlockUpdate,
)


class TestTimelineServiceSnapshot:
    """Timeline Service 快照测试"""

    def test_get_custom_blocks_by_date_snapshot(self, snapshot: SnapshotAssertion):
        """测试获取指定日期的自定义时间块列表"""
        # 转换日期为 UTC 时间范围
        start_time = "2026-04-24T00:00:00.000Z"
        end_time = "2026-04-24T23:59:59.999Z"
        result = get_custom_blocks_by_time_range(start_time=start_time, end_time=end_time)
        assert result == snapshot

    def test_create_and_delete_custom_block(self):
        """测试创建和删除自定义时间块"""
        # 创建测试数据
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        data = UserCustomBlockCreate(
            start_time="2026-04-24T10:00:00",
            end_time="2026-04-24T11:00:00",
            duration=60,
            content=f"测试时间块-{timestamp}",
            color="#FF6B6B",
            category_id=None,
            sub_category_id=None,
            todo_id=None
        )

        # 创建
        result = create_custom_block(data)
        assert result is not None
        assert result.data is not None

        # 删除
        if result.data and result.data.id:
            success = delete_custom_block(result.data.id)
            assert success == True

    def test_update_custom_block(self):
        """测试更新自定义时间块"""
        # 先创建一个测试记录
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        create_data = UserCustomBlockCreate(
            start_time="2026-04-24T12:00:00",
            end_time="2026-04-24T13:00:00",
            duration=60,
            content=f"测试更新-{timestamp}",
            color="#4ECDC4",
            category_id=None,
            sub_category_id=None,
            todo_id=None
        )
        created = create_custom_block(create_data)

        if created.data and created.data.id:
            # 更新内容
            update_data = UserCustomBlockUpdate(
                content="更新后的内容",
                color="#95E1D3"
            )
            result = update_custom_block(created.data.id, update_data)
            assert result is not None
            assert result.data.content == "更新后的内容"
            assert result.data.color == "#95E1D3"

            # 清理
            delete_custom_block(created.data.id)
