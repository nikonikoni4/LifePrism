from lifeprism.utils import LazySingleton
from lifeprism.repository.providers.common_query_options import QueryOptions
from lifeprism.repository.providers.tokens_usage_provider import TokensUsageProvider
from lifeprism.repository.providers.diary_provider import DiaryProvider
from lifeprism.repository.providers.plan_doc_provider import PlanDocProvider
from lifeprism.repository.providers.timeline_provider import TimelineProvider
from lifeprism.repository.providers.todo_provider import TodoProvider
from lifeprism.repository.providers.behavior_analysis_provider import BehaviorAnalysisProvider
from lifeprism.repository.providers.raw_behavior_analysis_provider import RawBehaviorAnalysisProvider
tokens_usage_provider : TokensUsageProvider = LazySingleton(TokensUsageProvider)
diary_provider : DiaryProvider= LazySingleton(DiaryProvider)
timeline_provider : TimelineProvider= LazySingleton(TimelineProvider)
behavior_analysis_provider :BehaviorAnalysisProvider= LazySingleton(BehaviorAnalysisProvider)
raw_behavior_analysis_provider :RawBehaviorAnalysisProvider= LazySingleton(RawBehaviorAnalysisProvider)

__all__ = [
    "tokens_usage_provider",
    "diary_provider",
    "timeline_provider",
    'behavior_analysis_provider',
    'raw_behavior_analysis_provider',
    'QueryOptions',
]
