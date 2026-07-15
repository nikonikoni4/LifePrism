"""
WechatAccountState Provider - 微信账户状态数据访问层

职责：提供 wechat_account_state 表的所有数据访问接口
替代原 channel/wechat/account.json 文件存储方式，加入 SYNC_TABLES 自动走数据库同步的记录级 LWW。

参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md 决策 4
"""

from typing import Any

from lifeprism.repository.base_providers import LWBaseDataProvider
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import DataAccessError

from .common_query_options import QueryOptions

logger = get_logger(__name__)


class WechatAccountStateProvider(LWBaseDataProvider):
    """
    微信账户状态数据提供者

    职责：提供 wechat_account_state 表的所有数据访问接口
    注意：wechat_user_id 作为主键（设计上支持多微信用户，当前实际只有单用户）

    替代原 channel/wechat/account.json 文件存储方式，
    加入 SYNC_TABLES 自动走数据库同步的记录级 LWW。
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "wechat_account_state"
    _PRIMARY_KEY = "wechat_user_id"  # ✅ wechat_account_state 表使用 wechat_user_id 作为主键
    _DATE_FIELD = None  # ❌ wechat_account_state 表没有 date 字段
    _TIME_FIELD = None  # ❌ wechat_account_state 表没有 time 字段
    _ON_CONFLICT = "replace"  # 冲突时替换（基于 wechat_user_id 主键）

    _FILTER_FIELDS: set[str] = {
        "wechat_user_id",
        "context_token",
        "last_session_id",
        "created_at",
        "updated_at",
    }
    _ORDER_FIELDS: set[str] = {"wechat_user_id", "created_at", "updated_at"}
    _SELECT_FIELDS: set[str] = {
        "wechat_user_id",
        "context_token",
        "last_session_id",
        "created_at",
        "updated_at",
    }
    _UPDATE_FIELDS: set[str] = {
        "context_token",
        "last_session_id",
    }

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    # ==================== 核心方法 ====================

    def get_state(self, wechat_user_id: str) -> dict[str, Any] | None:
        """
        查询指定微信用户的状态（context_token + last_session_id）

        Args:
            wechat_user_id: 微信用户 ID（主键）

        Returns:
            状态字典，包含 context_token、last_session_id、updated_at 等字段；
            不存在时返回 None

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            options = QueryOptions(filters={"wechat_user_id": wechat_user_id})
            results, _ = self._generic_query(options)
            return results[0] if results else None
        except Exception as e:
            logger.error("查询微信账户状态失败: wechat_user_id=%s, error=%s", wechat_user_id, e)
            raise DataAccessError(f"查询微信账户状态 {wechat_user_id} 失败") from e

    def get_all_states(self) -> list[dict[str, Any]]:
        """
        查询所有微信用户的状态

        Returns:
            状态字典列表，每项包含 wechat_user_id、context_token、last_session_id、updated_at

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            options = QueryOptions()
            results, _ = self._generic_query(options)
            return results
        except Exception as e:
            logger.error("查询所有微信账户状态失败: error=%s", e)
            raise DataAccessError("查询所有微信账户状态失败") from e

    def save_state(
        self,
        wechat_user_id: str,
        context_token: str | None,
        last_session_id: str | None,
    ) -> bool:
        """
        保存微信用户的状态（context_token + last_session_id）

        基于 wechat_user_id 主键使用 INSERT OR REPLACE 语义：
        - 不存在时插入新记录
        - 已存在时替换（更新）记录
        - updated_at 由 timestamps=True 配置自动管理（_generic_insert 会注入当前 UTC ISO 时间）

        Args:
            wechat_user_id: 微信用户 ID（主键）
            context_token: 微信对话上下文 token（可为 None）
            last_session_id: 最后一次会话 ID（可为 None）

        Returns:
            是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            insert_data = {
                "wechat_user_id": wechat_user_id,
                "context_token": context_token,
                "last_session_id": last_session_id,
            }
            self._generic_insert(insert_data)
            logger.info("保存微信账户状态成功")
            return True
        except Exception as e:
            logger.error(
                "保存微信账户状态失败: wechat_user_id=%s, error=%s",
                wechat_user_id,
                e,
            )
            raise DataAccessError(f"保存微信账户状态 {wechat_user_id} 失败") from e
