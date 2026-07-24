from lifeprism.repository.providers.behavior_analysis_provider import BehaviorAnalysisProvider
from lifeprism.repository.providers.being_provider import BeingProvider
from lifeprism.repository.providers.commitment_provider import CommitmentProvider
from lifeprism.repository.providers.common_query_options import QueryOptions
from lifeprism.repository.providers.computer_usage_provider import ComputerUsageProvider
from lifeprism.repository.providers.custom_block_provider import CustomBlockProvider
from lifeprism.repository.providers.deletion_log_provider import DeletionLogProvider
from lifeprism.repository.providers.diary_provider import DiaryProvider
from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
from lifeprism.repository.providers.journal_provider import JournalProvider
from lifeprism.repository.providers.raw_behavior_analysis_provider import (
    RawBehaviorAnalysisProvider,
)
from lifeprism.repository.providers.screen_capture_provider import ScreenCaptureProvider
from lifeprism.repository.providers.tokens_usage_provider import TokensUsageProvider
from lifeprism.repository.providers.value_provider import ValueProvider
from lifeprism.repository.providers.wechat_account_state_provider import (
    WechatAccountStateProvider,
)
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
wechat_account_state_provider: WechatAccountStateProvider = LazySingleton(
    WechatAccountStateProvider
)
file_sync_state_provider: FileSyncStateProvider = LazySingleton(FileSyncStateProvider)
journal_provider: JournalProvider = LazySingleton(JournalProvider)
commitment_provider: CommitmentProvider = LazySingleton(CommitmentProvider)
being_provider: BeingProvider = LazySingleton(BeingProvider)
value_provider: ValueProvider = LazySingleton(ValueProvider)
deletion_log_provider: DeletionLogProvider = LazySingleton(DeletionLogProvider)

__all__ = [
    "tokens_usage_provider",
    "diary_provider",
    "computer_usage_provider",
    "custom_block_provider",
    "behavior_analysis_provider",
    "raw_behavior_analysis_provider",
    "screen_capture_provider",
    "wechat_account_state_provider",
    "file_sync_state_provider",
    "journal_provider",
    "commitment_provider",
    "being_provider",
    "value_provider",
    "deletion_log_provider",
    "QueryOptions",
]
