"""
Plan Doc Service 快照测试

测试 plan_doc_service 的核心功能，确保重构后行为一致
"""

from datetime import datetime

import pytest
from syrupy.assertion import SnapshotAssertion

from lifeprism.server.schemas.goal_schemas import (
    CreatePlanDocRequest,
    UpdatePlanDocRequest,
)
from lifeprism.server.services.plan_doc_service import (
    create_plan_doc,
    delete_plan_doc,
    get_plan_doc_detail,
    get_plan_docs,
    get_plan_docs_by_goal,
    update_plan_doc,
)


class TestPlanDocServiceSnapshot:
    """Plan Doc Service 快照测试"""

    def test_get_plan_docs_snapshot(self, snapshot: SnapshotAssertion):
        """测试获取所有计划书列表"""
        result = get_plan_docs()
        assert result == snapshot

    def test_create_and_delete_plan_doc(self):
        """测试创建和删除计划书"""
        # 创建测试数据
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        request = CreatePlanDocRequest(
            id=f"test-plan-{timestamp}",
            goal_id="test-goal",
            content=f"# 测试计划书\n\n这是测试内容-{timestamp}",
        )

        # 创建
        result = create_plan_doc(request)
        assert result is not None
        assert result.id == request.id
        assert result.content == request.content

        # 删除
        success = delete_plan_doc(result.id)
        assert success == True

    def test_update_plan_doc(self):
        """测试更新计划书"""
        # 先创建一个测试记录
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        create_request = CreatePlanDocRequest(
            id=f"test-update-{timestamp}", goal_id="test-goal", content="# 原始内容"
        )
        created = create_plan_doc(create_request)

        if created:
            # 更新内容
            update_request = UpdatePlanDocRequest(
                content="# 更新后的内容\n\n新增段落", status="active"
            )
            result = update_plan_doc(created.id, update_request)
            assert result is not None
            assert result.content == update_request.content
            assert result.status == "active"

            # 清理
            delete_plan_doc(created.id)
