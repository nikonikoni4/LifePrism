"""
Mood Aggregator - 心情数据聚合层

聚合 MoodTypeProvider, MoodEntryProvider, MoodImpactProvider
提供心情相关的统一数据视图
"""
from typing import Optional, List, Dict, Any
from lifeprism.storage.providers.mood_providers import (
    mood_type_provider,
    mood_entry_provider,
    mood_impact_provider,
)
from lifeprism.utils import get_logger

logger = get_logger(__name__)


class MoodAggregator:
    """
    心情聚合器

    职责：聚合 mood_type、mood_entry、mood_impact 三个表的数据
    """

    def __init__(self):
        self.type_provider = mood_type_provider
        self.entry_provider = mood_entry_provider
        self.impact_provider = mood_impact_provider

    def get_mood_entry_with_type(self, entry_id: str) -> Optional[Dict[str, Any]]:
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
            mood_type = self.type_provider.get_mood_type_by_id(entry['mood_type_id'])
            if mood_type:
                entry['mood_type'] = mood_type

            return entry
        except Exception as e:
            logger.error(f"获取心情条目详情失败 (entry_id={entry_id}): {e}")
            return None

    def get_mood_entries_with_types(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取心情条目列表（每个包含类型信息）

        Args:
            start_date: 开始日期 YYYY-MM-DD（可选）
            end_date: 结束日期 YYYY-MM-DD（可选）

        Returns:
            List[Dict]: 包含类型信息的心情条目列表
        """
        try:
            # 获取心情条目列表
            entries = self.entry_provider.get_mood_entries(start_date, end_date)
            if not entries:
                return []

            # 获取所有心情类型（一次性查询）
            mood_types = self.type_provider.get_mood_types()
            type_map = {t['id']: t for t in mood_types}

            # 为每个条目附加类型信息
            for entry in entries:
                mood_type_id = entry.get('mood_type_id')
                if mood_type_id and mood_type_id in type_map:
                    entry['mood_type'] = type_map[mood_type_id]

            return entries
        except Exception as e:
            logger.error(f"获取心情条目列表失败 (start={start_date}, end={end_date}): {e}")
            return []

    def get_mood_type_with_stats(self, mood_type_id: str) -> Optional[Dict[str, Any]]:
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
            mood_type['entry_count'] = entry_count if entry_count >= 0 else 0

            return mood_type
        except Exception as e:
            logger.error(f"获取心情类型详情失败 (mood_type_id={mood_type_id}): {e}")
            return None

    def get_mood_analysis_with_impacts(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取心情分析（包含影响因素）

        Args:
            start_date: 开始日期 YYYY-MM-DD（可选）
            end_date: 结束日期 YYYY-MM-DD（可选）

        Returns:
            Dict: 包含心情条目、类型、影响因素的分析数据
        """
        try:
            # 获取心情条目（带类型）
            entries = self.get_mood_entries_with_types(start_date, end_date)

            # 获取所有影响因素
            impacts = self.impact_provider.get_mood_impacts()

            # 构建分析结果
            analysis = {
                'entries': entries,
                'impacts': impacts,
                'summary': {
                    'total_entries': len(entries),
                    'total_impacts': len(impacts),
                    'date_range': {
                        'start': start_date,
                        'end': end_date
                    }
                }
            }

            return analysis
        except Exception as e:
            logger.error(f"获取心情分析失败 (start={start_date}, end={end_date}): {e}")
            return {
                'entries': [],
                'impacts': [],
                'summary': {
                    'total_entries': 0,
                    'total_impacts': 0,
                    'date_range': {'start': start_date, 'end': end_date}
                }
            }


# ==================== 导出单例 ====================

from lifeprism.utils import LazySingleton

mood_aggregator = LazySingleton(MoodAggregator)
