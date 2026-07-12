"""目标/习惯/任务池服务 UTC 时区迁移测试

验证服务层在 UTC 时区迁移后的时间字段格式正确性。

测试 seam:
- Seam 1: GoalService._calculate_days_started - 使用本地日期计算天数
- Seam 2: GoalService._should_update_time_invested - UTC 阈值比较，兼容旧格式
- Seam 3: GoalService._auto_update_time_invested - time_invested_updated_at 使用 UTC ISO
- Seam 4: GoalService.update_milestone - finish_time 使用本地日期 YYYY-MM-DD
- Seam 5: HabitService._cancel_current_challenge - finished_at 使用 UTC ISO
- Seam 6: HabitService.pause_habit - paused_at 使用 UTC ISO
- Seam 7: taskpool_service.update_todo_with_writeback - actual_finished_at 使用本地日期

参考:
- docs/adr/2026-07-12-migrate-to-utc-timezone.md
- docs/guides/utc-migration-hidden-dependencies.md
- .scratch/utc-timezone-migration/07-goal-habit-diary-service-migration.md
"""
import re
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.core


# ==================== 工具函数 ====================


def assert_is_utc_iso(value: str):
    """断言字符串是 UTC ISO 8601 格式"""
    assert isinstance(value, str), f"应为 str 类型，实际为 {type(value)}"
    pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d{6}\+00:00$"
    assert re.match(pattern, value), (
        f"应匹配 UTC ISO 8601 格式 {pattern}，实际为 {value}"
    )


def assert_is_yyyy_mm_dd(value: str):
    """断言字符串是 YYYY-MM-DD 格式"""
    assert isinstance(value, str), f"应为 str 类型，实际为 {type(value)}"
    pattern = r"^\d{4}-\d{2}-\d{2}$"
    assert re.match(pattern, value), (
        f"应匹配 YYYY-MM-DD 格式 {pattern}，实际为 {value}"
    )


# ==================== Seam 1: _calculate_days_started 使用本地日期 ====================


class TestCalculateDaysStartedUsesLocalDate:
    """GoalService._calculate_days_started 应使用本地时区日期计算天数"""

    def test_returns_zero_for_today(self):
        """开始日期为今天时，天数应为 0"""
        from lifeprism.server.services.goal_service import GoalService
        from lifeprism.utils.time_utils import get_local_today

        service = GoalService.__new__(GoalService)
        today_str = get_local_today().isoformat()
        result = service._calculate_days_started(today_str)
        assert result == 0

    def test_returns_correct_days_for_past_date(self):
        """开始日期为 3 天前时，天数应为 3"""
        from lifeprism.server.services.goal_service import GoalService
        from lifeprism.utils.time_utils import get_local_today

        service = GoalService.__new__(GoalService)
        start = get_local_today() - timedelta(days=3)
        result = service._calculate_days_started(start.isoformat())
        assert result == 3

    def test_returns_none_for_no_start_date(self):
        """无开始日期时返回 None"""
        from lifeprism.server.services.goal_service import GoalService

        service = GoalService.__new__(GoalService)
        assert service._calculate_days_started(None) is None
        assert service._calculate_days_started("") is None


# ==================== Seam 2: _should_update_time_invested UTC 阈值比较 ====================


class TestShouldUpdateTimeInvestedUsesUtcThreshold:
    """GoalService._should_update_time_invested 应使用 UTC 阈值比较"""

    def test_returns_true_when_no_timestamp(self):
        """无时间戳时应返回 True（需要更新）"""
        from lifeprism.server.services.goal_service import GoalService

        service = GoalService.__new__(GoalService)
        item = {"track_time_automatically": 1, "link_to_category_id": "cat-1"}
        assert service._should_update_time_invested(item) is True

    def test_returns_true_for_old_format_timestamp_over_24h(self):
        """旧格式（空格分隔）时间戳超过 24 小时应返回 True"""
        from lifeprism.server.services.goal_service import GoalService

        service = GoalService.__new__(GoalService)
        old_time = (datetime.now(timezone.utc) - timedelta(hours=25)).strftime("%Y-%m-%d %H:%M:%S")
        item = {
            "track_time_automatically": 1,
            "link_to_category_id": "cat-1",
            "time_invested_updated_at": old_time,
        }
        assert service._should_update_time_invested(item) is True

    def test_returns_false_for_new_iso_format_within_24h(self):
        """新 ISO 格式时间戳在 24 小时内应返回 False"""
        from lifeprism.server.services.goal_service import GoalService

        service = GoalService.__new__(GoalService)
        recent_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        item = {
            "track_time_automatically": 1,
            "link_to_category_id": "cat-1",
            "time_invested_updated_at": recent_time,
        }
        assert service._should_update_time_invested(item) is False

    def test_returns_true_for_new_iso_format_over_24h(self):
        """新 ISO 格式时间戳超过 24 小时应返回 True"""
        from lifeprism.server.services.goal_service import GoalService

        service = GoalService.__new__(GoalService)
        old_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        item = {
            "track_time_automatically": 1,
            "link_to_category_id": "cat-1",
            "time_invested_updated_at": old_time,
        }
        assert service._should_update_time_invested(item) is True

    def test_returns_false_for_auto_track_disabled(self):
        """未开启自动追踪时应返回 False"""
        from lifeprism.server.services.goal_service import GoalService

        service = GoalService.__new__(GoalService)
        item = {"track_time_automatically": 0, "link_to_category_id": "cat-1"}
        assert service._should_update_time_invested(item) is False


# ==================== Seam 3: _auto_update_time_invested 写入 UTC ISO ====================


class TestAutoUpdateTimeInvestedWritesUtcIso:
    """GoalService._auto_update_time_invested 应将 time_invested_updated_at 写为 UTC ISO"""

    def test_time_invested_updated_at_is_utc_iso(self):
        """自动更新后 time_invested_updated_at 应为 UTC ISO 格式"""
        from lifeprism.server.services.goal_service import GoalService

        service = GoalService.__new__(GoalService)
        service.goal_repository = MagicMock()

        item = {
            "id": "goal-test1",
            "track_time_automatically": 1,
            "link_to_category_id": "cat-1",
            "time_invested_updated_at": None,
        }
        result = service._auto_update_time_invested(item)
        assert_is_utc_iso(result["time_invested_updated_at"])


# ==================== Seam 4: update_milestone 写入本地日期 ====================


class TestUpdateMilestoneWritesLocalDate:
    """GoalService.update_milestone 应将 finish_time 写为本地日期 YYYY-MM-DD"""

    def test_finish_time_is_yyyy_mm_dd(self):
        """里程碑完成时 finish_time 应为 YYYY-MM-DD 格式"""
        from lifeprism.server.services.goal_service import GoalService

        service = GoalService.__new__(GoalService)
        service.goal_repository = MagicMock()

        milestones_json = '[{"id": "ms-1", "content": "test", "state": 0, "finish_time": null, "order_index": 0}]'
        service.goal_repository.get_goal_by_id.return_value = {
            "id": "goal-test1",
            "name": "test",
            "milestones": milestones_json,
        }
        service.goal_repository.update_goal.return_value = True
        service.get_goal_detail = MagicMock(return_value=None)

        service.update_milestone("goal-test1", "ms-1", 1)

        # 验证 update_goal 被调用时传入了 finish_time
        call_args = service.goal_repository.update_goal.call_args
        update_data = call_args[0][1]
        milestones = update_data.get("milestones", "[]")
        import json

        ms_list = json.loads(milestones)
        finish_time = ms_list[0].get("finish_time")
        assert_is_yyyy_mm_dd(finish_time)


# ==================== Seam 5: HabitService._cancel_current_challenge 写入 UTC ISO ====================


class TestHabitServiceTimestampsAreUtcIso:
    """HabitService 时间戳字段应为 UTC ISO 格式"""

    def test_cancel_current_challenge_finished_at_is_utc_iso(self):
        """_cancel_current_challenge 的 finished_at 应为 UTC ISO 格式"""
        from lifeprism.server.services.habit_service import HabitService

        service = HabitService.__new__(HabitService)

        with patch("lifeprism.server.services.habit_service.habit_repository") as mock_repo:
            mock_repo.get_current_challenge.return_value = {"id": "ch-1", "habit_id": "h-1"}
            mock_repo.update_challenge.return_value = True

            service._cancel_current_challenge("h-1")

            call_args = mock_repo.update_challenge.call_args
            update_data = call_args[0][1]
            assert "finished_at" in update_data
            assert_is_utc_iso(update_data["finished_at"])


# ==================== Seam 6: HabitService.pause_habit 写入 UTC ISO ====================


class TestHabitServicePauseWritesUtcIso:
    """HabitService.pause_habit 的 paused_at 应为 UTC ISO 格式"""

    def test_pause_habit_paused_at_is_utc_iso(self):
        """pause_habit 的 paused_at 应为 UTC ISO 格式"""
        from lifeprism.server.services.habit_service import HabitService

        service = HabitService.__new__(HabitService)
        service._habit_name_map = {}

        with patch("lifeprism.server.services.habit_service.habit_repository") as mock_repo:
            mock_repo.get_habit_by_id.return_value = {
                "id": "h-1",
                "name": "test",
                "description": None,
                "frequency_type": "daily",
                "frequency_config": None,
                "current_level": 0,
                "status": "active",
                "value_id": None,
                "commitment_id": None,
                "created_at": "2026-01-01T00:00:00+00:00",
                "paused_at": None,
            }
            mock_repo.get_current_challenge.return_value = None
            mock_repo.update_habit.return_value = True

            # Mock get_habit_detail to avoid internal repository calls
            with patch.object(service, "get_habit_detail") as mock_detail:
                mock_detail.return_value = MagicMock()
                service.pause_habit("h-1")

            call_args = mock_repo.update_habit.call_args
            update_data = call_args[0][1]
            assert "paused_at" in update_data
            assert_is_utc_iso(update_data["paused_at"])


# ==================== Seam 7: taskpool_service actual_finished_at 使用本地日期 ====================


class TestTaskpoolServiceActualFinishedAtUsesLocalDate:
    """taskpool_service.update_todo_with_writeback 的 actual_finished_at 应为本地日期"""

    def test_actual_finished_at_is_yyyy_mm_dd(self):
        """任务完成时 actual_finished_at 应为 YYYY-MM-DD 格式"""
        from lifeprism.server.services import taskpool_service

        with patch("lifeprism.server.services.taskpool_service.todo_repository") as mock_repo:
            mock_repo.get_todo_by_id.return_value = {
                "id": "todo-1",
                "content": "test",
                "state": "scheduled",
                "plan_doc_id": None,
            }
            mock_repo.update_todo.return_value = True

            taskpool_service.update_todo_with_writeback("todo-1", {"state": "completed"})

            call_args = mock_repo.update_todo.call_args
            updates = call_args[0][1]
            assert "actual_finished_at" in updates
            assert_is_yyyy_mm_dd(updates["actual_finished_at"])
