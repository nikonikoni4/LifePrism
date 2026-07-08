"""云端配置生成器

从 keyring 读取所有 Key（LLM/微信/同步），生成完整的 cloud_init.yaml，
供用户复制到云端服务器初始化配置。

生成流程：
1. 生成或读取同步 API Key（优先从 keyring 读取，不存在则生成新的）
2. 从 keyring 读取所有 LLM Provider 的 API Key
3. 从 keyring 读取微信 Token
4. 构建完整配置 dict（monitor_type 强制为 none）
5. 保存到 {lifeprism_data_path}/cloud_init.yaml
"""

import secrets
from typing import Any

import yaml

from lifeprism.config.provider_manager import provider_manager
from lifeprism.config.settings_manager import settings
from lifeprism.sync.sync_config import get_sync_api_key, set_sync_api_key
from lifeprism.utils import get_logger

logger = get_logger(__name__)


class CloudConfigGenerator:
    """云端配置生成器

    从 keyring 读取所有 Key，生成完整的 cloud_init.yaml 配置文件。
    云端启动时读取该文件初始化配置，然后删除。
    """

    def __init__(self) -> None:
        """初始化配置生成器。"""
        pass

    def generate_cloud_config(self) -> tuple[str, bool]:
        """生成完整的云端配置文件 cloud_init.yaml。

        从 keyring 读取所有 Key（LLM/微信/同步），生成包含完整配置的 YAML 文件，
        保存到 {lifeprism_data_path}/cloud_init.yaml。

        Returns:
            tuple: (cloud_config_path, key_is_new)
            - cloud_config_path: 生成的配置文件路径
            - key_is_new: 同步 API Key 是否为新生成（True=新生成，False=已有）
        """
        # 1. 生成或读取同步 API Key
        sync_api_key, key_is_new = self._resolve_sync_api_key()
        logger.info("同步 API Key 已就绪, key_is_new=%s", key_is_new)

        # 2. 从 keyring 读取所有 LLM Provider 的 API Key
        providers_list = self._collect_provider_keys()

        # 3. 从 keyring 读取微信 Token
        wechat_token = self._load_wechat_token()

        # 4. 构建完整配置
        config = self._build_config(
            sync_api_key=sync_api_key,
            providers_list=providers_list,
            wechat_token=wechat_token,
        )

        # 5. 保存到文件
        cloud_config_path = self._save_config(config)

        logger.info("云端配置已生成: %s", cloud_config_path)
        return cloud_config_path, key_is_new

    def _resolve_sync_api_key(self) -> tuple[str, bool]:
        """生成或读取同步 API Key。

        优先从 keyring 读取已有 Key；如果不存在，生成新的 32 字节随机 Key 并保存。

        Returns:
            tuple: (api_key, key_is_new)
            - api_key: 同步 API Key 字符串
            - key_is_new: True 表示新生成，False 表示已有
        """
        existing_key = get_sync_api_key()
        if existing_key:
            return existing_key, False
        new_key = secrets.token_urlsafe(32)
        set_sync_api_key(new_key)
        return new_key, True

    def _collect_provider_keys(self) -> list[dict[str, Any]]:
        """从 keyring 读取所有 LLM Provider 的 API Key。

        遍历 providers.yaml 中的所有 provider，对每个有 env_key 的 provider
        调用 get_api_key() 读取 Key。只包含同时有 env_key 和 api_key 的 provider。

        Returns:
            provider 列表，每个元素包含 name、env_key、api_key。
        """
        providers_list: list[dict[str, Any]] = []
        all_providers = provider_manager.get_all_providers(allowed_only=False)
        for provider in all_providers:
            name = provider.get("name", "")
            if not name:
                continue
            env_key = provider_manager._get_env_key(name)
            if not env_key:
                continue
            api_key = provider_manager.get_api_key(name)
            if not api_key:
                continue
            providers_list.append(
                {
                    "name": name,
                    "env_key": env_key,
                    "api_key": api_key,
                }
            )
        return providers_list

    def _load_wechat_token(self) -> str:
        """从 keyring 读取微信 Token。

        Returns:
            token 字符串，不存在时返回空字符串。
        """
        from lifeprism.llm.channel.wechat.auth import WechatAuth

        return WechatAuth._load_token_from_keyring()

    def _build_config(
        self,
        sync_api_key: str,
        providers_list: list[dict[str, Any]],
        wechat_token: str,
    ) -> dict[str, Any]:
        """构建完整的云端配置 dict。

        Args:
            sync_api_key: 同步 API Key
            providers_list: provider 列表
            wechat_token: 微信 Token

        Returns:
            完整配置字典，结构如下：
            ```yaml
            llm:
              provider: anthropic
              model: claude-opus-4
            sync:
              enabled: true
              api_key: "lifeprism_sync_..."
            wechat_token: "wx_token_..."
            monitor_type: none
            providers:
              - name: anthropic
                env_key: api_key_anthropic
                api_key: "sk-ant-..."
            ```
        """
        return {
            "llm": {
                "provider": settings.get("provider", ""),
                "model": settings.get("model", ""),
            },
            "sync": {
                "enabled": True,
                "api_key": sync_api_key,
            },
            "wechat_token": wechat_token,
            "monitor_type": "none",  # 强制覆盖：云端必须禁用 Monitor
            "providers": providers_list,
        }

    def _save_config(self, config: dict[str, Any]) -> str:
        """将配置保存到 cloud_init.yaml。

        Args:
            config: 完整配置字典

        Returns:
            配置文件路径字符串
        """
        cloud_config_path = settings.lifeprism_data_path / "cloud_init.yaml"
        with open(cloud_config_path, "w", encoding="utf-8") as f:
            yaml.dump(
                config,
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )
        return str(cloud_config_path)
