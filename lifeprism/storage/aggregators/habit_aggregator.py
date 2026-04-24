"""
Habit Aggregator - 习惯数据聚合层

聚合 HabitProvider, HabitChallengeProvider, HabitCheckinProvider
提供习惯相关的统一数据视图
"""
from typing import Optional, List, Dict, Any
from lifeprism.storage.providers.habit_providers import (
    habit_provider,
    habit_challenge_provider,
    habit_checkin_provider,
)
from lifeprism.utils import get_logger

logger = get_logger(__name__)


class HabitAggregator:
    """
    习惯聚合器

    职责：聚合 habit、challenge、checkin 三个表的数据
    """

    def __init__(self):
        self.habit_provider = habit_provider
        self.challenge_provider = habit_challenge_provider
        self.checkin_provider = habit_checkin_provider

    def get_habit_with_challenge(self, habit_id: str) -> Optional[Dict[str, Any]]:
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

        # 获取当前活跃的挑战
        challenges = self.challenge_provider.get_challenges_by_habit(
            habit_id, status='active'
        )
        habit['current_challenge'] = challenges[0] if challenges else None

        return habit

    def get_habits_with_challenges(
        self, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取习惯列表（每个习惯包含当前挑战）

        Args:
            status: 状态过滤（'active'|'paused'），None 返回全部

        Returns:
            习惯列表，每个包含 current_challenge 字段
        """
        habits = self.habit_provider.get_habits(status)

        # 批量获取所有习惯的挑战
        for habit in habits:
            challenges = self.challenge_provider.get_challenges_by_habit(
                habit['id'], status='active'
            )
            habit['current_challenge'] = challenges[0] if challenges else None

        return habits

    def get_habit_with_stats(
        self, habit_id: str, days: int = 30
    ) -> Optional[Dict[str, Any]]:
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
        from datetime import datetime, timedelta
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)

        checkins = self.checkin_provider.get_checkins_by_habit(
            habit_id,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat()
        )

        habit['stats'] = {
            'total_checkins': len(checkins),
            'recent_checkins': checkins[:7] if len(checkins) > 7 else checkins,
        }

        return habit

    def create_habit_with_challenge(
        self, habit_data: Dict[str, Any], challenge_data: Optional[Dict[str, Any]] = None
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
            challenge_data['habit_id'] = habit_id
            self.challenge_provider.create_challenge(challenge_data)

        logger.info(f"创建习惯 {habit_id}，包含挑战: {challenge_data is not None}")
        return habit_id
