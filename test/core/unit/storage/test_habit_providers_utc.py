"""
Habit Providers UTC 时区迁移测试

验证 Issue #3: Repository 层各 Provider 迁移
测试 seam: HabitChallengeProvider.mark_in_progress_challenge_failed /
          HabitCheckinProvider.create_checkin

确保时间戳字段（finished_at / updated_at / completed_at）以 UTC ISO 8601 格式写入。
"""
import re

import pytest

from lifeprism.repository.providers.common_query_options import QueryOptions
from lifeprism.repository.providers.habit_providers import (
    HabitChallengeProvider,
    HabitCheckinProvider,
    HabitProvider,
)

pytestmark = pytest.mark.core


# UTC ISO 8601 格式：2026-07-11T16:29:54.123456+00:00
UTC_ISO_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00$")


@pytest.fixture
def habit_provider(test_data_path):
    """创建 HabitProvider 实例"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()
    return HabitProvider()


@pytest.fixture
def challenge_provider(test_data_path):
    """创建 HabitChallengeProvider 实例"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()
    return HabitChallengeProvider()


@pytest.fixture
def checkin_provider(test_data_path):
    """创建 HabitCheckinProvider 实例"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()
    return HabitCheckinProvider()


def _create_habit(provider: HabitProvider, name: str = "测试习惯") -> str:
    """创建测试用习惯，返回 habit_id"""
    return provider.create_habit({"name": name, "frequency_type": "daily"})


def _create_challenge(
    provider: HabitChallengeProvider,
    habit_id: str,
    start_date: str = "2026-01-01",
    end_date: str = "2026-02-01",
) -> str:
    """创建测试用挑战，返回 challenge_id"""
    return provider.create_challenge(
        {
            "habit_id": habit_id,
            "challenge_weeks": 4,
            "required_completions": 20,
            "from_level": 0,
            "to_level": 1,
            "start_date": start_date,
            "end_date": end_date,
            "status": "in_progress",
        }
    )


def _cleanup(habit_provider, challenge_provider, checkin_provider, habit_id, checkin_date=None):
    """清理测试数据"""
    if checkin_date:
        try:
            checkin_provider.delete_checkin(habit_id, checkin_date)
        except Exception:
            pass
    try:
        challenge_provider.delete_by_habit_id(habit_id)
    except Exception:
        pass
    try:
        habit_provider.delete_habit(habit_id)
    except Exception:
        pass


# ==================== mark_in_progress_challenge_failed 测试 ====================


class TestMarkInProgressChallengeFailedUtcTimestamps:
    """测试 mark_in_progress_challenge_failed 写入的 UTC 时间戳格式"""

    def test_finished_at_is_utc_iso8601(self, habit_provider, challenge_provider):
        """finished_at 应为 UTC ISO 8601 格式（带 +00:00 时区标识）"""
        habit_id = _create_habit(habit_provider, "失败挑战习惯")
        challenge_id = _create_challenge(challenge_provider, habit_id)

        try:
            result = challenge_provider.mark_in_progress_challenge_failed(
                habit_id, challenge_id
            )
            assert result is True

            challenge = challenge_provider.get_challenge_by_id(challenge_id)
            assert challenge is not None
            assert challenge["status"] == "failed"

            finished_at = challenge["finished_at"]
            assert finished_at is not None, "finished_at 不应为 None"
            assert UTC_ISO_PATTERN.match(finished_at), (
                f"finished_at 应为 UTC ISO 8601 格式，实际: {finished_at}"
            )
        finally:
            challenge_provider.delete_by_habit_id(habit_id)
            habit_provider.delete_habit(habit_id)

    def test_updated_at_is_utc_iso8601(self, habit_provider, challenge_provider):
        """updated_at 应为 UTC ISO 8601 格式（带 +00:00 时区标识）"""
        habit_id = _create_habit(habit_provider, "失败挑战习惯2")
        challenge_id = _create_challenge(challenge_provider, habit_id)

        try:
            result = challenge_provider.mark_in_progress_challenge_failed(
                habit_id, challenge_id
            )
            assert result is True

            challenge = challenge_provider.get_challenge_by_id(challenge_id)
            assert challenge is not None

            updated_at = challenge["updated_at"]
            assert updated_at is not None, "updated_at 不应为 None"
            assert UTC_ISO_PATTERN.match(updated_at), (
                f"updated_at 应为 UTC ISO 8601 格式，实际: {updated_at}"
            )
        finally:
            challenge_provider.delete_by_habit_id(habit_id)
            habit_provider.delete_habit(habit_id)


# ==================== create_checkin 测试 ====================


class TestCreateCheckinUtcTimestamps:
    """测试 create_checkin 写入的 UTC 时间戳格式"""

    def test_completed_at_is_utc_iso8601(
        self, habit_provider, challenge_provider, checkin_provider
    ):
        """completed_at 应为 UTC ISO 8601 格式（带 +00:00 时区标识）"""
        habit_id = _create_habit(habit_provider, "打卡习惯")
        challenge_id = _create_challenge(challenge_provider, habit_id)
        checkin_date = "2026-01-15"

        try:
            checkin_id = checkin_provider.create_checkin(
                {
                    "habit_id": habit_id,
                    "challenge_id": challenge_id,
                    "date": checkin_date,
                }
            )
            assert checkin_id is not None

            # 通过通用查询获取打卡记录
            options = QueryOptions(filters={"id": checkin_id})
            records, _ = checkin_provider.query_habit_checkins(options)
            assert len(records) == 1

            completed_at = records[0]["completed_at"]
            assert completed_at is not None, "completed_at 不应为 None"
            assert UTC_ISO_PATTERN.match(completed_at), (
                f"completed_at 应为 UTC ISO 8601 格式，实际: {completed_at}"
            )
        finally:
            _cleanup(
                habit_provider,
                challenge_provider,
                checkin_provider,
                habit_id,
                checkin_date,
            )
