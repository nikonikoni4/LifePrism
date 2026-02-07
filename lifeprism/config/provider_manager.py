"""
LLM 服务商配置管理器

负责加载和管理 providers.yaml 配置文件
统一管理所有服务商的 ID、名称映射、能力配置等
"""

import os
import sys
import shutil
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field

from lifeprism.utils import get_logger

logger = get_logger(__name__)


@dataclass
class ProviderInfo:
    """服务商信息"""
    provider_id: str           # 内部标识，如 "aliyun"
    name: str                  # 显示名称，如 "阿里云百炼 (Aliyun)"
    base_url: str              # API 基础 URL
    default_model: str         # 默认模型
    env_key_name: str          # 环境变量名称，如 "DASHSCOPE_API_KEY"
    capabilities: Set[str] = field(default_factory=set)  # 能力集合
    notes: str = ""            # 备注信息


class ProviderManager:
    """
    服务商配置管理器（单例）

    负责：
    1. 加载 providers.yaml 配置文件
    2. 提供 provider_id ↔ name 的双向映射
    3. 提供服务商列表、能力查询等接口
    4. 打包环境下自动将配置复制到 lifeprismData/config
    """

    _instance: Optional['ProviderManager'] = None

    def __new__(cls) -> 'ProviderManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """初始化配置管理器"""
        self._providers: Dict[str, ProviderInfo] = {}
        self._default_provider_id: str = "aliyun"
        self._config_path: Optional[Path] = None

        self._is_dev = not getattr(sys, 'frozen', False)

        # 从 settings 获取数据路径（settings_manager 已在此之前初始化）
        from lifeprism.config.settings_manager import settings

        # 获取源配置文件路径（开发环境中的配置）
        self._source_config_path = Path(__file__).parent / 'providers.yaml'

        if self._is_dev:
            # 开发环境：直接使用 lifeprism/config/providers.yaml
            self._config_path = self._source_config_path
        else:
            # 打包环境：使用固定配置路径下的 providers.yaml
            self._config_path = Path(settings.config_base_path) / 'config' / 'providers.yaml'
            # 确保配置文件存在（如果不存在则从源复制）
            self._ensure_config_exists()

        self._load_config()

    def _ensure_config_exists(self) -> None:
        """
        确保打包环境下配置文件存在

        如果 lifeprismData/config/providers.yaml 不存在，
        则从源文件（打包时嵌入的配置）复制过去
        """
        if not self._config_path.exists():
            self._config_path.parent.mkdir(parents=True, exist_ok=True)

            # 在打包环境中，源配置文件应该在 resources/backend/lifeprism/config/
            if getattr(sys, 'frozen', False):
                # PyInstaller 打包后的路径
                bundle_dir = Path(sys.executable).parent
                frozen_source = bundle_dir / 'lifeprism' / 'config' / 'providers.yaml'
                if frozen_source.exists():
                    shutil.copy2(frozen_source, self._config_path)
                    logger.info(f"已从打包资源复制配置到: {self._config_path}")
                else:
                    # 如果打包资源中也没有，创建默认配置
                    self._create_default_config()
            else:
                # 开发环境直接复制
                if self._source_config_path.exists():
                    shutil.copy2(self._source_config_path, self._config_path)
                    logger.info(f"已从源复制配置到: {self._config_path}")
                else:
                    self._create_default_config()

    def _create_default_config(self) -> None:
        """创建默认配置文件"""
        default_config = {
            'providers': {
                'aliyun': {
                    'name': '阿里云百炼 (Aliyun)',
                    'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                    'default_model': 'qwen-plus-latest',
                    'env_key_name': 'DASHSCOPE_API_KEY',
                    'capabilities': ['web_search', 'thinking', 'streaming', 'tool_calling']
                },
                'volcengine': {
                    'name': '火山引擎 (VolcEngine)',
                    'base_url': 'https://ark.cn-beijing.volces.com/api/v3',
                    'default_model': 'ep-xxxxxxxxxx',
                    'env_key_name': 'ARK_API_KEY',
                    'capabilities': ['web_search', 'thinking', 'streaming', 'tool_calling'],
                    'notes': '火山引擎需要使用 Endpoint ID（格式：ep-xxx）而不是模型名称'
                },
                'openai': {
                    'name': 'OpenAI',
                    'base_url': 'https://api.openai.com/v1',
                    'default_model': 'gpt-4o',
                    'env_key_name': 'OPENAI_API_KEY',
                    'capabilities': ['streaming', 'tool_calling']
                },
                'minimax': {
                    'name': 'MiniMax',
                    'base_url': 'https://api.minimax.chat/v1',
                    'default_model': 'MiniMax-M2.1',
                    'env_key_name': 'MINIMAX_API_KEY',
                    'capabilities': ['streaming', 'tool_calling']
                }
            },
            'default_provider': 'aliyun'
        }

        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_path, 'w', encoding='utf-8') as f:
            yaml.dump(
                default_config,
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False
            )
        logger.info(f"已创建默认配置: {self._config_path}")

    def _load_config(self, _retry: bool = True) -> None:
        """从 YAML 文件加载配置"""
        try:
            if self._config_path.exists():
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}

                self._default_provider_id = config.get('default_provider', 'aliyun')

                providers_config = config.get('providers', {})
                self._providers = {}

                for provider_id, provider_data in providers_config.items():
                    capabilities = set(provider_data.get('capabilities', []))
                    self._providers[provider_id] = ProviderInfo(
                        provider_id=provider_id,
                        name=provider_data.get('name', provider_id),
                        base_url=provider_data.get('base_url', ''),
                        default_model=provider_data.get('default_model', ''),
                        env_key_name=provider_data.get('env_key_name', ''),
                        capabilities=capabilities,
                        notes=provider_data.get('notes', '')
                    )

                logger.info(f"已加载 {len(self._providers)} 个服务商配置")
            else:
                if _retry:
                    logger.warning(f"配置文件不存在: {self._config_path}，尝试创建默认配置")
                    self._create_default_config()
                    self._load_config(_retry=False)
                else:
                    logger.error("无法加载或创建配置文件，使用空配置")
                    self._providers = {}

        except Exception as e:
            logger.error(f"加载服务商配置失败: {e}")
            self._providers = {}

    def reload(self) -> None:
        """重新加载配置文件"""
        self._load_config()

    # ===================== 查询方法 =====================

    def get_provider(self, provider_id: str) -> Optional[ProviderInfo]:
        """
        根据 provider_id 获取服务商信息

        Args:
            provider_id: 服务商 ID，如 "aliyun"

        Returns:
            ProviderInfo 或 None
        """
        return self._providers.get(provider_id)

    def get_provider_by_name(self, name: str) -> Optional[ProviderInfo]:
        """
        根据显示名称获取服务商信息

        Args:
            name: 显示名称，如 "阿里云百炼 (Aliyun)"

        Returns:
            ProviderInfo 或 None
        """
        for provider in self._providers.values():
            if provider.name == name:
                return provider
        return None

    def get_provider_id(self, name_or_id: str) -> str:
        """
        将名称或 ID 统一转换为 provider_id

        Args:
            name_or_id: 可以是显示名称或 provider_id

        Returns:
            provider_id，如果未找到则返回默认值
        """
        # 已经是 ID
        if name_or_id in self._providers:
            return name_or_id

        # 尝试按名称查找
        provider = self.get_provider_by_name(name_or_id)
        if provider:
            return provider.provider_id

        # 返回默认值
        logger.warning(f"未知的服务商 '{name_or_id}'，使用默认服务商 '{self._default_provider_id}'")
        return self._default_provider_id

    def get_provider_name(self, provider_id: str) -> str:
        """
        根据 provider_id 获取显示名称

        Args:
            provider_id: 服务商 ID

        Returns:
            显示名称，如果未找到则返回 provider_id 本身
        """
        provider = self.get_provider(provider_id)
        return provider.name if provider else provider_id

    @property
    def default_provider_id(self) -> str:
        """获取默认服务商 ID"""
        return self._default_provider_id

    @property
    def provider_list(self) -> List[str]:
        """获取服务商显示名称列表（用于前端下拉框）"""
        return [p.name for p in self._providers.values()]

    @property
    def provider_id_list(self) -> List[str]:
        """获取服务商 ID 列表"""
        return list(self._providers.keys())

    @property
    def name_to_id_map(self) -> Dict[str, str]:
        """获取 name -> id 映射字典"""
        return {p.name: p.provider_id for p in self._providers.values()}

    @property
    def id_to_name_map(self) -> Dict[str, str]:
        """获取 id -> name 映射字典"""
        return {p.provider_id: p.name for p in self._providers.values()}

    def get_all_providers(self) -> List[Dict[str, Any]]:
        """
        获取所有服务商信息（用于 API 返回）

        Returns:
            服务商信息列表
        """
        return [
            {
                'provider_id': p.provider_id,
                'name': p.name,
                'base_url': p.base_url,
                'default_model': p.default_model,
                'env_key_name': p.env_key_name,
                'capabilities': list(p.capabilities),
                'notes': p.notes
            }
            for p in self._providers.values()
        ]

    def get_keyring_username(self, provider_id: str) -> str:
        """
        获取服务商对应的 keyring 用户名

        Args:
            provider_id: 服务商 ID

        Returns:
            keyring 用户名，格式为 "api_key_{provider_id}"
        """
        return f"api_key_{provider_id}"

    def get_all_keyring_usernames(self) -> Dict[str, str]:
        """
        获取所有服务商的 keyring 用户名映射

        Returns:
            provider_id -> keyring_username 映射
        """
        return {pid: self.get_keyring_username(pid) for pid in self._providers.keys()}


# 全局单例实例
provider_manager = ProviderManager()
