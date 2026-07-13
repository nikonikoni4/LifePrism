"""
Mood Aggregator - 心情数据聚合层

聚合 MoodTypeProvider, MoodEntryProvider, MoodImpactProvider
提供心情相关的统一数据视图
"""

from typing import Any

from lifeprism.repository.providers.mood_providers import (
    MoodEntryProvider,
    MoodImpactProvider,
    MoodTypeProvider,
    QueryOptions,
)
from lifeprism.utils import LazySingleton, get_logger
from lifeprism.utils.exceptions import DataAccessError

logger = get_logger(__name__)


class MoodAggregator:
    """
    心情聚合器

    职责：
    1. 聚合 mood_type、mood_entry、mood_impact 三个表的数据（核心价值）
    2. 提供统一的数据访问接口（透传 provider 方法）
    """

    def __init__(self):
        self.type_provider = MoodTypeProvider()
        self.entry_provider = MoodEntryProvider()
        self.impact_provider = MoodImpactProvider()

    # ==================== 聚合方法（核心价值）====================

    def get_mood_entry_with_type(self, entry_id: str) -> dict[str, Any] | None:
        """
        获取心情条目详情（包含类型信息）

        Args:
            entry_id: 心情条目 ID

        Returns:
            Optional[Dict]: 包含类型信息的心情条目，不存在返回 None
        """
        try:
            # 获取心情条目
            entry = self.entry_provider.get_mood_entry_by_id(entry_id)
            if not entry:
                return None

            # 获取心情类型
            mood_type = self.type_provider.get_mood_type_by_id(entry["mood_type_id"])
            if mood_type:
                entry["mood_type"] = mood_type

            return entry
        except Exception as e:
            logger.error("获取心情条目详情失败: entry_id=%s, error=%s", entry_id, e)
            raise DataAccessError(
                message="获取心情条目详情失败",
                details={"entry_id": entry_id, "error": str(e)},
                cause=e,
            ) from e

    def get_mood_entries_with_types(
        self, start_time: str | None = None, end_time: str | None = None
    ) -> list[dict[str, Any]]:
        """
        获取心情条目列表（每个包含类型信息）

        Args:
            start_time: 开始时间 UTC ISO 8601（可选）
            end_time: 结束时间 UTC ISO 8601（可选）

        Returns:
            List[Dict]: 包含类型信息的心情条目列表
        """
        try:
            # 获取心情条目列表
            entries = self.entry_provider.get_mood_entries(start_time, end_time)
            if not entries:
                return []

            # 获取所有心情类型（一次性查询）
            mood_types = self.type_provider.get_mood_types()
            type_map = {t["id"]: t for t in mood_types}

            # 为每个条目附加类型信息
            for entry in entries:
                mood_type_id = entry.get("mood_type_id")
                if mood_type_id and mood_type_id in type_map:
                    entry["mood_type"] = type_map[mood_type_id]

            return entries
        except Exception as e:
            logger.error(
                "获取心情条目列表失败: start=%s, end=%s, error=%s", start_time, end_time, e
            )
            raise DataAccessError(
                message="获取心情条目列表失败",
                details={"start_time": start_time, "end_time": end_time, "error": str(e)},
                cause=e,
            ) from e

    def get_mood_type_with_stats(self, mood_type_id: str) -> dict[str, Any] | None:
        """
        获取心情类型详情（包含使用统计）

        Args:
            mood_type_id: 心情类型 ID

        Returns:
            Optional[Dict]: 包含统计信息的心情类型，不存在返回 None
        """
        try:
            # 获取心情类型
            mood_type = self.type_provider.get_mood_type_by_id(mood_type_id)
            if not mood_type:
                return None

            # 获取使用统计
            entry_count = self.type_provider.count_entries_by_type(mood_type_id)
            mood_type["entry_count"] = entry_count if entry_count >= 0 else 0

            return mood_type
        except Exception as e:
            logger.error("获取心情类型详情失败: mood_type_id=%s, error=%s", mood_type_id, e)
            raise DataAccessError(
                message="获取心情类型详情失败",
                details={"mood_type_id": mood_type_id, "error": str(e)},
                cause=e,
            ) from e

    def get_mood_analysis_with_impacts(
        self, start_time: str | None = None, end_time: str | None = None
    ) -> dict[str, Any]:
        """
        获取心情分析（包含影响因素）

        Args:
            start_time: 开始时间 UTC ISO 8601（可选）
            end_time: 结束时间 UTC ISO 8601（可选）

        Returns:
            Dict: 包含心情条目、类型、影响因素的分析数据
        """
        try:
            # 获取心情条目（带类型）
            entries = self.get_mood_entries_with_types(start_time, end_time)

            # 获取所有影响因素
            impacts = self.impact_provider.get_mood_impacts()

            # 构建分析结果
            analysis = {
                "entries": entries,
                "impacts": impacts,
                "summary": {
                    "total_entries": len(entries),
                    "total_impacts": len(impacts),
                    "time_range": {"start": start_time, "end": end_time},
                },
            }

            return analysis
        except Exception as e:
            logger.error("获取心情分析失败: start=%s, end=%s, error=%s", start_time, end_time, e)
            raise DataAccessError(
                message="获取心情分析失败",
                details={"start_time": start_time, "end_time": end_time, "error": str(e)},
                cause=e,
            ) from e

    # ==================== MoodType 核心 CRUD 透传 ====================

    def query_mood_type(self, query_options: QueryOptions) -> tuple[list[dict[str, Any]], int]:
        """透传：查询心情类型"""
        return self.type_provider.query_mood_types(query_options)

    def create_mood_type(self, data: dict[str, Any]) -> str | None:
        """透传：创建心情类型"""
        return self.type_provider.create_mood_type(data)

    def update_mood_type(self, mood_type_id: str, data: dict[str, Any]) -> bool:
        """透传：更新心情类型"""
        return self.type_provider.update_mood_type(mood_type_id, data)

    def delete_mood_type(self, mood_type_id: str) -> bool:
        """透传：删除心情类型"""
        return self.type_provider.delete_mood_type(mood_type_id)

    def get_mood_types(self) -> list[dict[str, Any]]:
        """透传：获取所有心情类型"""
        return self.type_provider.get_mood_types()

    def get_mood_type_by_id(self, mood_type_id: str) -> dict[str, Any] | None:
        """透传：根据ID获取心情类型"""
        return self.type_provider.get_mood_type_by_id(mood_type_id)

    def count_entries_by_type(self, mood_type_id: str) -> int:
        """透传：统计某心情类型关联的记录数"""
        return self.type_provider.count_entries_by_type(mood_type_id)

    # ==================== MoodEntry 核心 CRUD 透传 ====================
    def query_mood_entry(self, query_options: QueryOptions) -> tuple[list[dict[str, Any]], int]:
        """透传：查询心情记录"""
        return self.entry_provider.query_mood_entries(query_options)

    def create_mood_entry(self, data: dict[str, Any]) -> str | None:
        """透传：创建心情记录"""
        return self.entry_provider.create_mood_entry(data)

    def update_mood_entry(self, entry_id: str, data: dict[str, Any]) -> bool:
        """透传：更新心情记录"""
        return self.entry_provider.update_mood_entry(entry_id, data)

    def delete_mood_entry(self, entry_id: str) -> bool:
        """透传：删除心情记录"""
        return self.entry_provider.delete_mood_entry(entry_id)

    def get_mood_entries(
        self, start_time: str | None = None, end_time: str | None = None
    ) -> list[dict[str, Any]]:
        """透传：获取心情记录列表"""
        return self.entry_provider.get_mood_entries(start_time, end_time)

    def get_mood_entry_by_id(self, entry_id: str) -> dict[str, Any] | None:
        """透传：根据ID获取心情记录"""
        return self.entry_provider.get_mood_entry_by_id(entry_id)

    # ==================== MoodImpact 核心 CRUD 透传 ====================

    def create_mood_impact(self, data: dict[str, Any]) -> int | None:
        """透传：创建影响因素"""
        return self.impact_provider.create_mood_impact(data)

    def delete_mood_impact(self, impact_id: int) -> bool:
        """透传：删除影响因素"""
        return self.impact_provider.delete_mood_impact(impact_id)

    def get_mood_impacts(self) -> list[dict[str, Any]]:
        """透传：获取所有影响因素"""
        return self.impact_provider.get_mood_impacts()


# ==================== 导出单例 ====================

mood_aggregator = LazySingleton(MoodAggregator)
