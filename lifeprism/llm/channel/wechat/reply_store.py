"""微信回复凭据存储

职责：
- 持有刚收到的新 context_token 内存缓存（凭据未落库前立即可用）
- 通过 wechat_account_state_repository 持久化 context_token
- 将旧 account.json 的用户数据迁移到 wechat_account_state 数据库表

参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md 决策 4
"""

import json
from pathlib import Path
from typing import Any, Protocol

from lifeprism.repository import wechat_account_state_repository
from lifeprism.utils import get_logger

logger = get_logger(__name__)


class _AccountStateRepository(Protocol):
    """wechat_account_state repository 的最小依赖契约（便于测试注入）。"""

    def get_state(self, wechat_user_id: str) -> dict[str, Any] | None: ...

    def save_context_token(self, wechat_user_id: str, context_token: str) -> bool: ...

    def save_session_reference(self, wechat_user_id: str, session_id: str) -> bool: ...

    def save_state(
        self,
        wechat_user_id: str,
        context_token: str | None,
        last_session_id: str | None,
    ) -> bool: ...


class WechatReplyStore:
    """微信回复凭据存储（context_token 内存缓存 + 数据库持久化）"""

    def __init__(self, repository: _AccountStateRepository | None = None) -> None:
        """
        初始化凭据存储

        Args:
            repository: wechat_account_state repository；缺省使用全局单例
                wechat_account_state_repository
        """
        self._repository = repository or wechat_account_state_repository
        # 刚收到的新凭据内存缓存：{wechat_user_id: context_token}
        self._token_cache: dict[str, str] = {}

    def get_token(self, wechat_user_id: str) -> str:
        """
        获取微信用户当前 context_token

        优先返回内存缓存（刚收到的新凭据），缓存缺失时回落数据库。

        Args:
            wechat_user_id: 微信用户 ID

        Returns:
            context_token 字符串；不存在时返回空字符串
        """
        cached = self._token_cache.get(wechat_user_id)
        if cached:
            return cached
        state = self._repository.get_state(wechat_user_id)
        if not state:
            return ""
        return state.get("context_token") or ""

    def remember(self, wechat_user_id: str, context_token: str) -> None:
        """
        记录刚收到的 context_token

        空 token 视为无效凭据，不覆盖已有缓存或数据库记录。

        Args:
            wechat_user_id: 微信用户 ID
            context_token: 新收到的 context_token

        Raises:
            RuntimeError: 持久化失败（repository.save_context_token 返回 False）
        """
        if not context_token or not context_token.strip():
            logger.debug("忽略空 context_token: wechat_user_id=%s", wechat_user_id)
            return
        self._token_cache[wechat_user_id] = context_token
        if not self._repository.save_context_token(wechat_user_id, context_token):
            logger.error("保存 context_token 失败: wechat_user_id=%s", wechat_user_id)
            raise RuntimeError(f"保存微信 context_token 失败: {wechat_user_id}")
        logger.info("已记录微信 context_token: wechat_user_id=%s", wechat_user_id)

    def migrate_legacy(self, path: Path) -> None:
        """
        将旧 account.json 用户数据迁移到数据库

        迁移规则：
        - 仅迁移数据库中尚不存在的用户，已存在用户不覆盖
        - 支持新格式 user_data 与旧格式 context_tokens
        - last_session_id 仅在此兼容迁移中写入
        - 不处理 token 字段（由原 auth 模块负责）
        - 完成后将文件重命名为 account.json.bak

        Args:
            path: 旧 account.json 文件路径；不存在时不操作
        """
        if not path.exists():
            logger.debug("旧 account.json 不存在，跳过迁移: %s", path)
            return

        try:
            file_state = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.error("读取旧 account.json 失败: path=%s, error=%s", path, e, exc_info=True)
            return

        user_data = self._extract_user_data(file_state)
        migrated = 0
        for wechat_user_id, data in user_data.items():
            if self._repository.get_state(wechat_user_id) is not None:
                logger.debug("用户已存在，跳过迁移: wechat_user_id=%s", wechat_user_id)
                continue
            saved = self._repository.save_state(
                wechat_user_id=wechat_user_id,
                context_token=data.get("context_token"),
                last_session_id=data.get("last_session_id"),
            )
            if not saved:
                raise RuntimeError(f"迁移微信用户状态失败: {wechat_user_id}")
            migrated += 1
        logger.info("account.json 迁移完成: 迁移 %s 个用户, path=%s", migrated, path)

        self._rename_to_bak(path)

    @staticmethod
    def _extract_user_data(file_state: dict[str, Any]) -> dict[str, dict[str, str | None]]:
        """
        从旧 account.json 内容提取用户数据（兼容新旧格式）

        Args:
            file_state: account.json 解析后的字典

        Returns:
            {wechat_user_id: {"context_token": ..., "last_session_id": ...}}
        """
        if "user_data" in file_state:
            raw = file_state.get("user_data") or {}
            return {
                wechat_user_id: {
                    "context_token": info.get("context_token"),
                    "last_session_id": info.get("last_session_id"),
                }
                for wechat_user_id, info in raw.items()
            }
        if "context_tokens" in file_state:
            raw = file_state.get("context_tokens") or {}
            return {
                wechat_user_id: {"context_token": token, "last_session_id": None}
                for wechat_user_id, token in raw.items()
            }
        return {}

    @staticmethod
    def _rename_to_bak(path: Path) -> None:
        """将旧 account.json 重命名为 account.json.bak"""
        try:
            bak_path = path.with_suffix(".json.bak")
            path.rename(bak_path)
            logger.info("已将 account.json 重命名为 %s", bak_path.name)
        except OSError as e:
            logger.error("重命名 account.json 失败: error=%s", e, exc_info=True)
