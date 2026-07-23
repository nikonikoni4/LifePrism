"""
Habit Aggregator - 习惯数据聚合层

聚合 HabitProvider, HabitChallengeProvider, HabitCheckinProvider
提供习惯相关的统一数据视图
"""

from datetime import datetime, timedelta
from typing import Any

from lifeprism.repository.providers.habit_providers import (
    HabitChallengeProvider,
    HabitCheckinProvider,
    HabitProvider,
)
from lifeprism.utils import LazySingleton, get_logger

logger = get_logger(__name__)


class HabitAggregator:
    """
    习惯聚合器

    职责：
    1. 聚合 habit、challenge、checkin 三个表的数据（核心价值）
    2. 提供统一的数据访问接口（透传 provider 方法）
    """

    def __init__(self):
        self.habit_provider = HabitProvider()
        self.challenge_provider = HabitChallengeProvider()
        self.checkin_provider = HabitCheckinProvider()

    # ==================== 聚合方法（核心价值）====================

    def get_habit_with_challenge(self, habit_id: str) -> dict[str, Any] | None:
        """
        获取习惯详情（包含当前挑战信息）

        Args:
            habit_id: 习惯 ID

        Returns:
            包含 habit 和 current_challenge 的字典，不存在返回 None
        """
        habit = self.habit_provider.get_habit_by_id(habit_id)
        if not habit:
            return None

        # 获取当前进行中的挑战
        current_challenge = self.challenge_provider.get_current_challenge(habit_id)
        habit["current_challenge"] = current_challenge

        return habit

    def get_habits_with_challenges(self, status: str | None = None) -> list[dict[str, Any]]:
        """
        获取习惯列表（每个习惯包含当前挑战）

        Args:
            status: 状态过滤（'active'|'paused'），None 返回全部

        Returns:
            习惯列表，每个包含 current_challenge 字段
        """
        habits = self.habit_provider.get_habits(status)

        # 为每个习惯获取当前进行中的挑战
        # 注意：这里使用循环查询是因为 HabitChallengeProvider 没有提供批量查询接口
        # 如果未来需要优化性能，应在 Provider 层添加批量查询方法
        for habit in habits:
            current_challenge = self.challenge_provider.get_current_challenge(habit["id"])
            habit["current_challenge"] = current_challenge

        return habits

    def get_habit_with_stats(self, habit_id: str, days: int = 30) -> dict[str, Any] | None:
        """
        获取习惯详情（包含打卡统计）

        Args:
            habit_id: 习惯 ID
            days: 统计最近多少天

        Returns:
            包含 habit 和 stats 的字典
        """
        habit = self.habit_provider.get_habit_by_id(habit_id)
        if not habit:
            return None

        # 获取最近的打卡记录
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)

        checkins = self.checkin_provider.get_checkins_in_date_range(
            start_date=start_date.isoformat(), end_date=end_date.isoformat(), habit_ids=[habit_id]
        )

        habit["stats"] = {
            "total_checkins": len(checkins),
            "recent_checkins": checkins[:7] if len(checkins) > 7 else checkins,
        }

        return habit

    def create_habit_with_challenge(
        self, habit_data: dict[str, Any], challenge_data: dict[str, Any] | None = None
    ) -> str:
        """
        创建习惯并可选创建初始挑战

        Args:
            habit_data: 习惯数据
            challenge_data: 挑战数据（可选）

        Returns:
            新创建的 habit_id
        """
        # 创建习惯
        habit_id = self.habit_provider.create_habit(habit_data)

        # 如果提供了挑战数据，创建挑战
        if challenge_data:
            challenge_data["habit_id"] = habit_id
            self.challenge_provider.create_challenge(challenge_data)

        logger.info("创建习惯 %s，包含挑战: %s", habit_id, challenge_data is not None)
        return habit_id

    # ==================== Habit 核心 CRUD 透传 ====================

    def insert_habit(self, data: dict[str, Any]) -> str:
        """透传：插入习惯"""
        return self.habit_provider.create_habit(data)

    def update_habit(self, habit_id: str, data: dict[str, Any]) -> bool:
        """透传：更新习惯"""
        return self.habit_provider.update_habit(habit_id, data)

    def delete_habit(self, habit_id: str) -> bool:
        """透传：删除习惯

        注意：级联删除挑战和打卡的逻辑在 Service 层
        （habit_service.delete_habit），Aggregator 不负责跨表级联。
        """
        return self.habit_provider.delete_habit(habit_id)

    def get_habits(self, status: str | None = None) -> list[dict[str, Any]]:
        """透传：查询习惯列表"""
        return self.habit_provider.get_habits(status)

    def get_habit_by_id(self, habit_id: str) -> dict[str, Any] | None:
        """透传：根据ID获取习惯"""
        return self.habit_provider.get_habit_by_id(habit_id)

    # ==================== HabitChallenge 核心 CRUD 透传 ====================

    def create_challenge(self, data: dict[str, Any]) -> str:
        """透传：创建挑战"""
        return self.challenge_provider.create_challenge(data)

    def update_challenge(self, challenge_id: str, data: dict[str, Any]) -> bool:
        """透传：更新挑战"""
        return self.challenge_provider.update_challenge(challenge_id, data)

    def delete_challenge_by_habit(self, habit_id: str) -> bool:
        """透传：删除习惯的所有挑战"""
        return self.challenge_provider.delete_by_habit_id(habit_id)

    def get_challenges_by_habit(self, habit_id: str) -> list[dict[str, Any]]:
        """透传：获取习惯的所有挑战"""
        return self.challenge_provider.get_challenges_by_habit(habit_id)

    def get_challenge_by_id(self, challenge_id: str) -> dict[str, Any] | None:
        """透传：根据ID获取挑战"""
        return self.challenge_provider.get_challenge_by_id(challenge_id)

    def get_current_challenge(self, habit_id: str) -> dict[str, Any] | None:
        """透传：获取习惯当前进行中的挑战"""
        return self.challenge_provider.get_current_challenge(habit_id)

    def get_challenge_history(
        self, habit_id: str, status: str | None = None
    ) -> list[dict[str, Any]]:
        """透传：获取习惯的挑战历史"""
        return self.challenge_provider.get_challenge_history(habit_id, status)

    def get_expired_in_progress_challenges(self, today: str) -> list[dict[str, Any]]:
        """透传：获取所有到期的进行中挑战"""
        return self.challenge_provider.get_expired_in_progress_challenges(today)

    def mark_in_progress_challenge_failed(self, habit_id: str, challenge_id: str) -> bool:
        """透传：将进行中的挑战标记为失败"""
        return self.challenge_provider.mark_in_progress_challenge_failed(habit_id, challenge_id)

    # ==================== HabitCheckin 核心 CRUD 透传 ====================

    def create_checkin(self, data: dict[str, Any]) -> str | None:
        """透传：创建打卡记录"""
        return self.checkin_provider.create_checkin(data)

    def delete_checkin(self, habit_id: str, checkin_date: str) -> bool:
        """透传：删除打卡记录"""
        return self.checkin_provider.delete_checkin(habit_id, checkin_date)

    def delete_checkin_by_habit(self, habit_id: str) -> bool:
        """透传：删除习惯的所有打卡记录"""
        return self.checkin_provider.delete_by_habit_id(habit_id)

    def get_checkin_by_date(self, habit_id: str, checkin_date: str) -> dict[str, Any] | None:
        """透传：根据日期获取打卡记录"""
        return self.checkin_provider.get_checkin_by_date(habit_id, checkin_date)

    def get_checkin_dates_by_challenge(self, habit_id: str, challenge_id: str) -> list[str]:
        """透传：获取挑战期内的所有打卡日期"""
        return self.checkin_provider.get_checkin_dates_by_challenge(habit_id, challenge_id)

    def get_checkins_in_date_range(
        self, start_date: str, end_date: str, habit_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """透传：查询日期范围内的打卡记录"""
        return self.checkin_provider.get_checkins_in_date_range(start_date, end_date, habit_ids)

    def get_today_checkins(self, habit_ids: list[str]) -> dict[str, bool]:
        """透传：批量查询今日打卡状态"""
        return self.checkin_provider.get_today_checkins(habit_ids)

    def count_checkins_by_challenge(self, challenge_id: str) -> int:
        """透传：统计挑战期内的打卡次数"""
        return self.checkin_provider.count_checkins_by_challenge(challenge_id)


# ==================== 导出单例 ====================

habit_aggregator = LazySingleton(HabitAggregator)
