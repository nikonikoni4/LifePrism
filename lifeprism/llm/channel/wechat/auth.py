"""微信认证模块
本文件源自 https://github.com/HKUDS/nanobot.git，经 AI 改写适配 lifeprism 项目。
提供二维码登录和状态持久化功能，支持 token 管理。
"""

import json
import asyncio
import httpx
import qrcode
import keyring
from pathlib import Path
from typing import Any
from lifeprism.utils.logger import get_logger
from lifeprism.llm.channel.wechat.client import WechatClient
from lifeprism.llm.channel.wechat.exceptions import WechatAuthError

logger = get_logger(__name__)

# Keyring 配置
KEYRING_SERVICE_NAME = "lifeprism"
KEYRING_WECHAT_TOKEN_USERNAME = "wechat_bot_token"


class WechatAuth:
    """微信认证模块"""

    def __init__(self, client: WechatClient, state_file: Path):
        """初始化认证模块

        Args:
            client: 微信客户端实例
            state_file: 状态文件路径
        """
        self.client = client
        self.state_file = state_file

    def _print_qr_code(self, data: str) -> None:
        """在终端打印 QR 码

        Args:
            data: QR 码数据
        """
        qr = qrcode.QRCode()
        qr.add_data(data)
        qr.make()
        qr.print_ascii()
        logger.info("请使用微信扫描上方二维码登录")

    def _load_token_from_keyring(self) -> str:
        """从 keyring 加载 token

        Returns:
            token 字符串，失败返回空字符串
        """
        try:
            token = keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_WECHAT_TOKEN_USERNAME)
            return token if token else ""
        except (keyring.errors.KeyringError, OSError) as e:
            logger.debug(f"从 keyring 加载 token 失败: {e}")
            return ""

    def _save_token_to_keyring(self, token: str) -> bool:
        """保存 token 到 keyring

        Args:
            token: 要保存的 token

        Returns:
            是否成功
        """
        try:
            keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_WECHAT_TOKEN_USERNAME, token)
            logger.info("Token 已保存到 keyring")
            return True
        except (keyring.errors.KeyringError, OSError) as e:
            logger.error(f"保存 token 到 keyring 失败: {e}", exc_info=True)
            return False

    def _save_state_to_file(self, state: dict[str, Any]) -> None:
        """保存状态到文件（内部方法）

        Args:
            state: 要保存的状态字典

        Raises:
            OSError: 文件操作失败
            TypeError: JSON 序列化失败
        """
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2))

    def delete_token(self) -> bool:
        """删除保存的 token

        同时清理 keyring 和文件中的 token。

        Returns:
            是否成功
        """
        success = True

        # 1. 从 keyring 删除
        try:
            keyring.delete_password(KEYRING_SERVICE_NAME, KEYRING_WECHAT_TOKEN_USERNAME)
            logger.info("已从 keyring 删除 token")
        except keyring.errors.PasswordDeleteError:
            logger.debug("Keyring 中没有 token")
        except (keyring.errors.KeyringError, OSError) as e:
            logger.error(f"从 keyring 删除 token 失败: {e}", exc_info=True)
            success = False

        # 2. 从文件删除（如果存在）
        if self.state_file.exists():
            try:
                file_state = json.loads(self.state_file.read_text())
                if "token" in file_state:
                    file_state.pop("token")
                    self._save_state_to_file(file_state)
                    logger.info("已从文件删除 token")
            except (OSError, json.JSONDecodeError, TypeError) as e:
                logger.error(f"从文件删除 token 失败: {e}", exc_info=True)
                success = False

        return success

    def load_state(self) -> dict[str, Any]:
        """加载保存的状态

        优先级：
        1. keyring 中的 token（推荐）
        2. 文件中的 token（向后兼容，自动迁移）
        3. 空状态

        Returns:
            状态字典，包含 token 和 context_tokens
        """
        state = {"token": "", "context_tokens": {}}

        # 1. 尝试从 keyring 加载 token
        token_from_keyring = self._load_token_from_keyring()
        if token_from_keyring:
            state["token"] = token_from_keyring
            logger.info("从 keyring 加载 token 成功")

        # 2. 尝试从文件加载（向后兼容 + 迁移）
        if self.state_file.exists():
            try:
                file_state = json.loads(self.state_file.read_text())
                file_token = file_state.get("token", "")

                # 如果文件中有 token 但 keyring 中没有，执行迁移
                if file_token and not token_from_keyring:
                    logger.info("检测到文件中的 token，执行自动迁移到 keyring")
                    if self._save_token_to_keyring(file_token):
                        state["token"] = file_token
                        # 迁移成功后从文件中移除 token（保留 context_tokens）
                        file_state.pop("token", None)
                        self._save_state_to_file(file_state)
                        logger.info("Token 迁移完成，已从文件中移除")
                    else:
                        # keyring 不可用，fallback 到文件
                        logger.warning("Keyring 不可用，继续使用文件存储")
                        state["token"] = file_token
                elif file_token and token_from_keyring:
                    # 迁移已完成但文件清理失败的情况，重试清理
                    logger.info("检测到 keyring 和文件中都有 token，清理文件中的旧 token")
                    file_state.pop("token", None)
                    try:
                        self._save_state_to_file(file_state)
                        logger.info("文件中的旧 token 已清理")
                    except (OSError, TypeError) as e:
                        logger.warning(f"清理文件中的旧 token 失败: {e}")

                # 加载 context_tokens（始终从文件读取）
                state["context_tokens"] = file_state.get("context_tokens", {})

            except json.JSONDecodeError as e:
                logger.error(f"状态文件格式错误: {e}", exc_info=True)
                # 尝试备份损坏的文件
                try:
                    backup_path = self.state_file.with_suffix('.json.backup')
                    self.state_file.rename(backup_path)
                    logger.info(f"已备份损坏的状态文件到: {backup_path}")
                except OSError:
                    pass
            except OSError as e:
                logger.error(f"加载状态文件失败: {e}", exc_info=True)

        return state

    def save_state(self, state: dict[str, Any]) -> None:
        """保存状态

        策略：
        - token: 优先保存到 keyring，失败则 fallback 到文件
        - context_tokens: 保存到文件（动态会话数据）

        Args:
            state: 要保存的状态字典

        Raises:
            OSError: 文件操作失败
            TypeError: JSON 序列化失败
        """
        # 1. 保存 token 到 keyring
        token = state.get("token", "")
        if token and token.strip():  # 确保非空且非空白
            if not self._save_token_to_keyring(token):
                logger.warning("Keyring 保存失败，fallback 到文件存储")
                # Fallback: 保存到文件
                self._save_state_to_file(state)
                return

        # 2. 保存 context_tokens 到文件（不包含 token）
        file_state = {
            "context_tokens": state.get("context_tokens", {})
        }
        self._save_state_to_file(file_state)

    async def qr_login(self, timeout: int = 300) -> bool:
        """QR 码登录流程

        Args:
            timeout: 超时时间（秒），默认 300 秒

        Returns:
            登录是否成功
        """
        try:
            # 获取 QR 码
            data = await self.client.api_get("ilink/bot/get_bot_qrcode", params={"bot_type": "3"}, auth=False)
            qrcode_id = data.get("qrcode", "")
            qrcode_img = data.get("qrcode_img_content", qrcode_id)
            if not qrcode_id:
                logger.error("获取 QR 码失败")
                return False

            self._print_qr_code(qrcode_img)

            # 轮询状态
            start_time = asyncio.get_event_loop().time()
            while True:
                if asyncio.get_event_loop().time() - start_time > timeout:
                    logger.error(f"登录超时（{timeout}秒）")
                    return False

                status_data = await self.client.api_get(
                    "ilink/bot/get_qrcode_status",
                    params={"qrcode": qrcode_id},
                    auth=False
                )
                status = status_data.get("status", "")

                if status == "confirmed":
                    token = status_data.get("bot_token", "")
                    if token:
                        self.client.token = token
                        state = self.load_state()
                        state["token"] = token
                        try:
                            self.save_state(state)
                            logger.info("登录成功")
                            return True
                        except (OSError, TypeError) as e:
                            logger.error(f"保存登录状态失败: {e}")
                            return False
                elif status == "expired":
                    logger.error("QR 码已过期")
                    return False
                elif status == "scanning":
                    logger.info("用户正在扫描二维码")

                await asyncio.sleep(1)
        except (httpx.HTTPStatusError, httpx.RequestError, RuntimeError) as e:
            logger.error(f"登录网络错误: {e}", exc_info=True)
            raise WechatAuthError(f"登录失败: {e}") from e
        except (KeyError, ValueError) as e:
            logger.error(f"登录响应解析错误: {e}", exc_info=True)
            raise WechatAuthError(f"登录响应格式错误: {e}") from e
