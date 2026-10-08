"""会话引用存储

职责：把渠道收发路由（ConversationRoute）映射到业务 Session ID。

边界：
- 只读写会话引用，不缓存微信回复凭据（context_token 由 reply_store 负责）；
- 不写 SQL，只调用 repository 单例方法；
- 不导入微信 channel。

参考 Flow: docs/flows/2026-10-08-wechat-conversation-hitl-flow.md
"""

from __future__ import annotations

from typing import Any, Protocol

from lifeprism.llm.conversation.types import ConversationRoute
from lifeprism.utils import get_logger

logger = get_logger(__name__)


class _AccountStateRepository(Protocol):
    """wechat_account_state repository 的最小依赖契约（便于测试注入）。"""

    def get_state(self, wechat_user_id: str) -> dict[str, Any] | None: ...

    def save_session_reference(self, wechat_user_id: str, session_id: str) -> bool: ...


class SessionReferences(Protocol):
    """会话引用读写契约；实现不得持有微信回复凭据。"""

    def get(self, route: ConversationRoute) -> str | None: ...

    def set(self, route: ConversationRoute, session_id: str) -> None: ...


class WechatSessionReferences:
    """微信会话引用：读写 wechat_account_state 的 last_session_id 字段。"""

    def __init__(self, repository: _AccountStateRepository | None = None) -> None:
        """
        初始化微信会话引用存储

        Args:
            repository: wechat_account_state repository；缺省时惰性使用全局单例
                wechat_account_state_repository
        """
        if repository is None:
            # 惰性导入：避免模块导入期触发数据库初始化
            from lifeprism.repository import wechat_account_state_repository

            repository = wechat_account_state_repository
        self._repository = repository

    def get(self, route: ConversationRoute) -> str | None:
        """
        读取 route 对应会话的 last_session_id

        Args:
            route: 会话收发路由，recipient_id 作为微信用户主键

        Returns:
            会话 ID；无记录、空串或字段缺失时返回 None
        """
        state = self._repository.get_state(route.recipient_id)
        if not state:
            return None
        return state.get("last_session_id") or None

    def set(self, route: ConversationRoute, session_id: str) -> None:
        """
        只更新 last_session_id 字段，不触碰 context_token

        Args:
            route: 会话收发路由，recipient_id 作为微信用户主键
            session_id: 目标会话 ID

        Raises:
            RuntimeError: 保存失败（save_session_reference 返回假值）
        """
        if not self._repository.save_session_reference(route.recipient_id, session_id):
            logger.error(
                "保存微信会话引用失败: recipient_id=%s, session_id=%s",
                route.recipient_id,
                session_id,
            )
            raise RuntimeError(f"保存微信会话引用失败: {route.recipient_id}")
        logger.info(
            "已保存微信会话引用: recipient_id=%s, session_id=%s",
            route.recipient_id,
            session_id,
        )
