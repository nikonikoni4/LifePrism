"""微信 API HTTP 客户端模块
本文件源自 https://github.com/HKUDS/nanobot.git，经 AI 改写适配 lifeprism 项目。
"""

import base64
import os

import httpx

from lifeprism.utils.logger import get_logger

logger = get_logger(__name__)

ILINK_APP_ID = "bot"
ILINK_APP_CLIENT_VERSION = 0x020101  # 2.1.1
BASE_INFO = {"channel_version": "2.1.1"}


class WechatClient:
    """微信 API HTTP 客户端

    提供与微信 API 交互的基础 HTTP 功能，包括请求头构建、GET/POST 请求等。

    Attributes:
        base_url: API 基础 URL
        token: 认证 token
    """

    def __init__(self, base_url: str, token: str = ""):
        """初始化客户端

        Args:
            base_url: API 基础 URL
            token: 认证 token，默认为空
        """
        self.base_url = base_url
        self.token = token
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self._client = httpx.AsyncClient(timeout=60.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        if self._client:
            await self._client.aclose()

    @staticmethod
    def _random_wechat_uin() -> str:
        """生成随机 UIN

        Returns:
            Base64 编码的随机 UIN 字符串
        """
        uint32 = int.from_bytes(os.urandom(4), "big")
        return base64.b64encode(str(uint32).encode()).decode()

    def _make_headers(self, auth: bool = True) -> dict[str, str]:
        """构建请求头

        Args:
            auth: 是否包含认证信息，默认为 True

        Returns:
            请求头字典
        """
        headers = {
            "X-WECHAT-UIN": self._random_wechat_uin(),
            "Content-Type": "application/json",
            "AuthorizationType": "ilink_bot_token",
            "iLink-App-Id": ILINK_APP_ID,
            "iLink-App-ClientVersion": str(ILINK_APP_CLIENT_VERSION),
        }
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def api_get(self, endpoint: str, params: dict | None = None, auth: bool = True) -> dict:
        """发送 GET 请求

        Args:
            endpoint: API 端点路径
            params: 查询参数，默认为 None
            auth: 是否需要认证，默认为 True

        Returns:
            响应 JSON 数据

        Raises:
            RuntimeError: 客户端未初始化
            httpx.HTTPStatusError: HTTP 请求失败
        """
        if not self._client:
            raise RuntimeError("Client not initialized")
        url = f"{self.base_url}/{endpoint}"
        resp = await self._client.get(url, params=params, headers=self._make_headers(auth=auth))
        resp.raise_for_status()
        return resp.json()

    async def api_post(self, endpoint: str, body: dict | None = None, auth: bool = True) -> dict:
        """发送 POST 请求

        Args:
            endpoint: API 端点路径
            body: 请求体数据，默认为 None
            auth: 是否需要认证，默认为 True

        Returns:
            响应 JSON 数据

        Raises:
            RuntimeError: 客户端未初始化
            httpx.HTTPStatusError: HTTP 请求失败
        """
        if not self._client:
            raise RuntimeError("Client not initialized")
        url = f"{self.base_url}/{endpoint}"
        payload = body or {}
        if "base_info" not in payload:
            payload["base_info"] = BASE_INFO
        resp = await self._client.post(url, json=payload, headers=self._make_headers(auth=auth))
        resp.raise_for_status()
        return resp.json()
