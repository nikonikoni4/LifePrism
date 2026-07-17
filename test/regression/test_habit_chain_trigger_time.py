"""
回归测试：习惯链条 Timeline 节点触发时间计算逻辑

验证点（新版）：
1. 后端 _calculate_node_times 自动计算 calculated_time（填充结果）
2. _validate_chain_timeline_rules 验证相邻节点间距 >= 10min
3. 相邻节点间距 < 10min 时抛出 ValidationError
4. 计算结果通过 calculated_time 字段返回（不存库），trigger_time 保持原始值
"""

import pytest

from lifeprism.server.services.habit_chain_service import HabitChainService
from lifeprism.utils.exceptions import ValidationError


class TestChainTimelineTriggerTimeCalculation:
    def _make_node(
        self, id: int, sort_order: int, trigger_time: str | None, habit_id: str | None = None
    ):
        return {
            "id": id,
            "chain_id": 1,
            "sort_order": sort_order,
            "name": f"节点{id}",
            "trigger_time": trigger_time,
            "habit_id": habit_id,
        }

    # ============================================================================
    # 场景1：只给第一个节点触发时间（8:00），后续节点按默认30min递推
    # ============================================================================

    def test_calculate_only_first_node_has_time(self):
        """
        场景1：第一个节点8:00，其他节点无显式时间
        预期：后端计算 calculated_time
        - 节点1: 08:00 (显式，calculated_time=trigger_time)
        - 节点2: 08:30 (30min递推)
        - 节点3: 09:00 (30min递推)
        - 节点4: 09:30 (30min递推)
        - 节点5: 10:00 (30min递推)
        """
        service = HabitChainService()
        nodes = [
            self._make_node(1, 1, "08:00"),
            self._make_node(2, 2, None),
            self._make_node(3, 3, None),
            self._make_node(4, 4, None),
            self._make_node(5, 5, None),
        ]

        result = service._calculate_node_times(nodes)

        assert result[0]["calculated_time"] == "08:00"
        assert result[1]["calculated_time"] == "08:30"
        assert result[2]["calculated_time"] == "09:00"
        assert result[3]["calculated_time"] == "09:30"
        assert result[4]["calculated_time"] == "10:00"

    # ============================================================================
    # 场景2：第一节点8:00，第四节点9:00，中间节点平均分配
    # ============================================================================

    def test_calculate_with_gap_in_trigger_times(self):
        """
        场景2：第1节点8:00，第4节点9:00，中间2个节点平均分配
        - 总时长: 60min, 中间2个节点
        - 每段: 60min / 3 = 20min
        - 节点1: 08:00 (显式，calculated_time=08:00)
        - 节点2: 08:20 (20min间隔)
        - 节点3: 08:40 (20min间隔)
        - 节点4: 09:00 (显式，calculated_time=09:00)
        - 节点5: 09:30 (默认30min递推)
        """
        service = HabitChainService()
        nodes = [
            self._make_node(1, 1, "08:00"),
            self._make_node(2, 2, None),
            self._make_node(3, 3, None),
            self._make_node(4, 4, "09:00"),
            self._make_node(5, 5, None),
        ]

        result = service._calculate_node_times(nodes)

        assert result[0]["calculated_time"] == "08:00"
        assert result[1]["calculated_time"] == "08:20"
        assert result[2]["calculated_time"] == "08:40"
        assert result[3]["calculated_time"] == "09:00"
        assert result[4]["calculated_time"] == "09:30"

    # ============================================================================
    # 验证：相邻节点间距 < 10min 时抛出错误
    # ============================================================================

    def test_validate_gap_less_than_10min_fails(self):
        """
        验证：相邻节点间距5min < 10min，应报错
        """
        service = HabitChainService()
        nodes = [
            self._make_node(1, 1, "08:00"),
            self._make_node(2, 2, "08:05"),  # 间距5min
        ]

        with pytest.raises(ValidationError) as exc:
            service._validate_chain_timeline_rules(
                nodes, is_showing_in_timeline=True, error_code="TEST"
            )
        assert "间距不足" in str(exc.value)

    def test_validate_gap_equal_10min_passes(self):
        """
        验证：相邻节点间距10min = 10min，应通过
        """
        service = HabitChainService()
        nodes = [
            self._make_node(1, 1, "08:00"),
            self._make_node(2, 2, "08:10"),  # 间距10min
        ]

        service._validate_chain_timeline_rules(
            nodes, is_showing_in_timeline=True, error_code="TEST"
        )

    def test_validate_gap_greater_than_10min_passes(self):
        """
        验证：相邻节点间距15min > 10min，应通过
        """
        service = HabitChainService()
        nodes = [
            self._make_node(1, 1, "08:00"),
            self._make_node(2, 2, "08:15"),  # 间距15min
        ]

        service._validate_chain_timeline_rules(
            nodes, is_showing_in_timeline=True, error_code="TEST"
        )

    # ============================================================================
    # 验证：计算结果不存库（原始节点数据不变）
    # ============================================================================

    def test_calculated_time_not_persisted(self):
        """
        验证：_calculate_node_times 计算结果通过 calculated_time 字段返回（不存库）
        注意：原始 trigger_time 保持不变
        """
        service = HabitChainService()
        original_nodes = [
            self._make_node(1, 1, "08:00"),
            self._make_node(2, 2, None),
            self._make_node(3, 3, None),
        ]

        result = service._calculate_node_times(original_nodes)

        # 原始节点 trigger_time 未被修改（仍然是None）
        assert original_nodes[1]["trigger_time"] is None
        # 计算结果中 calculated_time 已填充
        assert result[1]["calculated_time"] == "08:30"
        assert result[2]["calculated_time"] == "09:00"
