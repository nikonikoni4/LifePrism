from lifeprism.repository.providers.behavior_analysis_provider import BehaviorAnalysisProvider
from lifeprism.repository.providers.common_query_options import QueryOptions
from lifeprism.repository.providers.computer_usage_provider import ComputerUsageProvider
from lifeprism.repository.providers.custom_block_provider import CustomBlockProvider
from lifeprism.repository.providers.diary_provider import DiaryProvider
from lifeprism.repository.providers.raw_behavior_analysis_provider import (
    RawBehaviorAnalysisProvider,
)
from lifeprism.repository.providers.screen_capture_provider import ScreenCaptureProvider
from lifeprism.repository.providers.tokens_usage_provider import TokensUsageProvider
from lifeprism.utils import LazySingleton

tokens_usage_provider: TokensUsageProvider = LazySingleton(TokensUsageProvider)
diary_provider: DiaryProvider = LazySingleton(DiaryProvider)
computer_usage_provider: ComputerUsageProvider = LazySingleton(ComputerUsageProvider)
custom_block_provider: CustomBlockProvider = LazySingleton(CustomBlockProvider)
behavior_analysis_provider: BehaviorAnalysisProvider = LazySingleton(BehaviorAnalysisProvider)
raw_behavior_analysis_provider: RawBehaviorAnalysisProvider = LazySingleton(
    RawBehaviorAnalysisProvider
)
screen_capture_provider: ScreenCaptureProvider = LazySingleton(ScreenCaptureProvider)

__all__ = [
    "tokens_usage_provider",
    "diary_provider",
    "computer_usage_provider",
    "custom_block_provider",
    "behavior_analysis_provider",
    "raw_behavior_analysis_provider",
    "screen_capture_provider",
    "QueryOptions",
]
