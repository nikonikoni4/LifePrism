"""
LLM 使用统计数据提供者
继承 LWBaseDataProvider，专门负责 token 使用量的记录与查询
"""
import logging
from typing import Any

from lifeprism.storage import LWBaseDataProvider
from lifeprism.utils import LazySingleton

logger = logging.getLogger(__name__)


class LLMUsageDataProvider(LWBaseDataProvider):
    """
    LLM 使用统计数据提供者
    """

    def __init__(self, db_manager=None):
        """
        初始化 LLM 使用统计数据提供者
        """
        super().__init__(db_manager)

    def save_usage(self, session_id: str, usage: dict[str, Any], mode: str = 'chatbot') -> int:
        """
        保存或更新单个会话的 token 使用情况

        Args:
            session_id: 会话 ID
            usage: 包含 prompt_tokens, completion_tokens, total_tokens 的字典
            mode: 模式 ('chatbot' 或 'classification')

        Returns:
            int: 受影响的行数
        """
        if not session_id or not usage:
            return 0

        # 适配 LWBaseDataProvider.upsert_session_tokens_usage 的参数要求
        usage_data = {
            'input_tokens': usage.get('prompt_tokens', 0),
            'output_tokens': usage.get('completion_tokens', 0),
            'total_tokens': usage.get('total_tokens', 0),
            'mode': mode
        }

        try:
            return self.upsert_session_tokens_usage(session_id, usage_data)
        except Exception as e:
            logger.error(f"[LLMUsageDataProvider] 保存 token 使用情况失败: {e}")
            return 0

    def batch_save_usage(self, usage_list: list[dict[str, Any]]) -> int:
        """
        批量保存 token 使用情况

        Args:
            usage_list: 包含统计数据的字典列表

        Returns:
            int: 插入的行数
        """
        if not usage_list:
            return 0

        try:
            return self.save_tokens_usage(usage_list)
        except Exception as e:
            logger.error(f"[LLMUsageDataProvider] 批量保存 token 使用情况失败: {e}")
            return 0


llm_usage_db_provider = LazySingleton(LLMUsageDataProvider)
