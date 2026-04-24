"""
Goal Aggregator - 目标数据聚合层

聚合 GoalProvider, GoalStatsProvider
提供目标相关的统一数据视图
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from lifeprism.repository.providers.goal_providers import (
    GoalProvider,
    GoalStatsProvider,
)
from lifeprism.utils import get_logger

logger = get_logger(__name__)


class GoalAggregator:
    """
    目标聚合器

    职责：
    1. 聚合 goal、goal_stats 两个表的数据（核心价值）
    2. 提供统一的数据访问接口（透传 provider 方法）
    """

    def __init__(self):
        self.goal_provider = GoalProvider()
        self.stats_provider = GoalStatsProvider()

    # ==================== 聚合方法（核心价值）====================

    def get_goal_with_stats(
        self, goal_id: str, stats_limit: int = 30
    ) -> Optional[Dict[str, Any]]:
        """
        获取目标详情（包含统计数据）

        Args:
            goal_id: 目标 ID
            stats_limit: 返回最近多少天的统计数据

        Returns:
            包含 goal 和 stats 的字典，不存在返回 None
        """
        goal = self.goal_provider.get_goal_by_id(goal_id)
        if not goal:
            return None

        # 获取统计数据
        stats = self.stats_provider.get_stats_by_goal(goal_id, limit=stats_limit)
        goal['stats'] = stats

        return goal

    def get_goals_with_latest_stats(
        self, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取目标列表（每个包含最新统计）

        Args:
            status: 状态过滤（'active'|'completed'|'archived'），None 返回全部

        Returns:
            目标列表，每个包含 latest_stat 字段
        """
        # 获取目标列表
        goals, _ = self.goal_provider.get_goals(status=status, page=1, page_size=1000)

        # 为每个目标获取最新的统计数据
        for goal in goals:
            stats = self.stats_provider.get_stats_by_goal(goal['id'], limit=1)
            goal['latest_stat'] = stats[0] if stats else None

        return goals

    # ==================== Goal 核心 CRUD 透传 ====================

    def create_goal(self, data: Dict[str, Any]) -> Optional[str]:
        """透传：创建目标"""
        return self.goal_provider.create_goal(data)

    def update_goal(self, goal_id: str, data: Dict[str, Any]) -> bool:
        """透传：更新目标"""
        return self.goal_provider.update_goal(goal_id, data)

    def delete_goal(self, goal_id: str) -> bool:
        """透传：删除目标"""
        return self.goal_provider.delete_goal(goal_id)

    def get_goals(self, status: Optional[str] = None, category_id: Optional[str] = None, page: int = 1, page_size: int = 20):
        """透传：获取目标列表"""
        return self.goal_provider.get_goals(status=status, category_id=category_id, page=page, page_size=page_size)

    def get_goal_by_id(self, goal_id: str) -> Optional[Dict[str, Any]]:
        """透传：根据ID获取目标"""
        return self.goal_provider.get_goal_by_id(goal_id)

    def reorder_goals(self, goal_ids: List[str]) -> bool:
        """透传：重排序目标"""
        return self.goal_provider.reorder_goals(goal_ids)

    def get_active_goals(self) -> List[Dict[str, Any]]:
        """透传：获取所有活跃目标"""
        return self.goal_provider.get_active_goals()

    def get_active_goals_with_category(self) -> List[Dict[str, Any]]:
        """透传：获取绑定了分类的活跃目标"""
        return self.goal_provider.get_active_goals_with_category()

    def get_active_goals_for_classify(self) -> List[Dict[str, Any]]:
        """透传：获取用于分类的活跃目标"""
        return self.goal_provider.get_active_goals_for_classify()

    def calculate_time_invested(self, goal_id: str) -> int:
        """透传：计算目标的投入时间（秒）"""
        return self.goal_provider.calculate_time_invested(goal_id)

    def update_time_invested(self, goal_id: str, time_invested: int) -> bool:
        """透传：更新目标的投入时间"""
        return self.goal_provider.update_time_invested(goal_id, time_invested)

    # ==================== GoalStats 核心 CRUD 透传 ====================

    def create_goal_stat(self, data: Dict[str, Any]) -> bool:
        """透传：创建目标统计"""
        return self.stats_provider.create_goal_stat(data)

    def update_goal_stat(self, stat_id: str, data: Dict[str, Any]) -> bool:
        """透传：更新目标统计"""
        return self.stats_provider.update_goal_stat(stat_id, data)

    def delete_goal_stat(self, stat_id: str) -> bool:
        """透传：删除目标统计"""
        return self.stats_provider.delete_goal_stat(stat_id)

    def get_stats_by_goal(self, goal_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        """透传：获取目标的统计数据"""
        return self.stats_provider.get_stats_by_goal(goal_id, limit=limit)

    def get_cumulative_stats(self, goal_id: str, date: str) -> Optional[Dict[str, Any]]:
        """透传：获取累计统计"""
        return self.stats_provider.get_cumulative_stats(goal_id, date)

    def sync_stats_to_date(self, goal_id: str, target_date: str, start_date: Optional[str] = None) -> bool:
        """透传：同步统计数据到指定日期"""
        return self.stats_provider.sync_stats_to_date(goal_id=goal_id, target_date=target_date, start_date=start_date)

    # ==================== 事务性聚合方法 ====================

    def sync_goal_stats(
        self, goal_id: str, target_date: str, start_date: Optional[str] = None
    ) -> bool:
        """
        同步目标统计数据到指定日期

        Args:
            goal_id: 目标 ID
            target_date: 目标日期 (YYYY-MM-DD)
            start_date: 起始日期 (YYYY-MM-DD)，用于新目标时从特定日期开始统计

        Returns:
            bool: 是否成功
        """
        try:
            # 验证目标是否存在
            goal = self.goal_provider.get_goal_by_id(goal_id)
            if not goal:
                logger.error(f"目标 {goal_id} 不存在")
                return False

            # 调用 stats_provider 的同步方法
            success = self.stats_provider.sync_stats_to_date(
                goal_id=goal_id,
                target_date=target_date,
                start_date=start_date
            )

            if success:
                logger.info(f"目标 {goal_id} 统计数据同步成功")
            return success

        except Exception as e:
            logger.error(f"同步目标 {goal_id} 统计数据失败: {e}")
            return False


# ==================== 导出单例 ====================

from lifeprism.utils import LazySingleton

goal_aggregator = LazySingleton(GoalAggregator)
