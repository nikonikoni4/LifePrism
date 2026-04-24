from lifeprism.utils import LazySingleton
from lifeprism.storage.providers.tokens_usage_provider import TokensUsageProvider
from lifeprism.storage.providers.diary_provider import DiaryProvider
from lifeprism.storage.providers.plan_doc_provider import PlanDocProvider
from lifeprism.storage.providers.timeline_provider import TimelineProvider
from lifeprism.storage.providers.todo_provider import TodoProvider

tokens_usage_provider : TokensUsageProvider = LazySingleton(TokensUsageProvider)
diary_provider : DiaryProvider= LazySingleton(DiaryProvider)
plan_doc_provider : PlanDocProvider= LazySingleton(PlanDocProvider)
timeline_provider : TimelineProvider= LazySingleton(TimelineProvider)
todo_provider : TodoProvider = LazySingleton(TodoProvider)


__all__ = [
    "tokens_usage_provider",
    "diary_provider",
    "plan_doc_provider",
    "timeline_provider",
    "todo_provider",

]