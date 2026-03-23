"""
LLM 服务商配置管理器（纯数据层）

职责：
1. 加载 providers.yaml → 缓存原始 dict 列表
2. 提供 get_raw_specs() 供 registry.py 构建 ProviderSpec
3. keyring 读写（get_api_key / set_api_key）
4. 提供 get_all_providers() 供 API 层返回前端展示数据

不导入任何 llm/ 模块，依赖方向：config → llm
"""

import sys
from pathlib import Path
from typing import Any

import keyring
import yaml

from lifeprism.utils import get_logger

logger = get_logger(__name__)

_KEYRING_SERVICE = "lifeprism"

DEFAULT_PROVIDER_CONFIG = {
    'allowed_providers': [
        'custom', 'volcengine', 'dashscope', 'deepseek', 
        'zhipu', 'moonshot', 'minimax', 'openai'
    ],
    'providers': [
        {
            'name': 'custom',
            'keywords': [],
            'env_key': '',
            'display_name': 'Custom',
            'litellm_prefix': '',
            'skip_prefixes': [],
            'env_extras': [],
            'is_gateway': False,
            'is_local': False,
            'detect_by_key_prefix': '',
            'detect_by_base_keyword': '',
            'default_api_base': '',
            'strip_model_prefix': False,
            'litellm_kwargs': {},
            'model_overrides': [],
            'is_oauth': False,
            'is_direct': True,
            'supports_prompt_caching': False,
            'default_model': ''
        },
        {
            'name': 'azure_openai',
            'keywords': ['azure', 'azure-openai'],
            'env_key': '',
            'display_name': 'Azure OpenAI',
            'litellm_prefix': '',
            'skip_prefixes': [],
            'env_extras': [],
            'is_gateway': False,
            'is_local': False,
            'detect_by_key_prefix': '',
            'detect_by_base_keyword': '',
            'default_api_base': '',
            'strip_model_prefix': False,
            'litellm_kwargs': {},
            'model_overrides': [],
            'is_oauth': False,
            'is_direct': True,
            'supports_prompt_caching': False,
            'default_model': ''
        },
        {
            'name': 'openrouter',
            'keywords': ['openrouter'],
            'env_key': 'api_key_openrouter',
            'display_name': 'OpenRouter',
            'litellm_prefix': 'openrouter',
            'skip_prefixes': [],
            'env_extras': [],
            'is_gateway': True,
            'is_local': False,
            'detect_by_key_prefix': 'sk-or-',
            'detect_by_base_keyword': 'openrouter',
            'default_api_base': 'https://openrouter.ai/api/v1',
            'strip_model_prefix': False,
            'litellm_kwargs': {},
            'model_overrides': [],
            'is_oauth': False,
            'is_direct': False,
            'supports_prompt_caching': True,
            'default_model': ''
        },
        {
            'name': 'aihubmix',
            'keywords': ['aihubmix'],
            'env_key': 'api_key_aihubmix',
            'display_name': 'AiHubMix',
            'litellm_prefix': 'openai',
            'skip_prefixes': [],
            'env_extras': [],
            'is_gateway': True,
            'is_local': False,
            'detect_by_key_prefix': '',
            'detect_by_base_keyword': 'aihubmix',
            'default_api_base': 'https://aihubmix.com/v1',
            'strip_model_prefix': True,
            'litellm_kwargs': {},
            'model_overrides': [],
            'is_oauth': False,
            'is_direct': False,
            'supports_prompt_caching': False,
            'default_model': ''
        },
        {
            'name': 'siliconflow',
            'keywords': ['siliconflow'],
            'env_key': 'api_key_siliconflow',
            'display_name': 'SiliconFlow',
            'litellm_prefix': 'openai',
            'skip_prefixes': [],
            'env_extras': [],
            'is_gateway': True,
            'is_local': False,
            'detect_by_key_prefix': '',
            'detect_by_base_keyword': 'siliconflow',
            'default_api_base': 'https://api.siliconflow.cn/v1',
            'strip_model_prefix': False,
            'litellm_kwargs': {},
            'model_overrides': [],
            'is_oauth': False,
            'is_direct': False,
            'supports_prompt_caching': False,
            'default_model': ''
        },
        {
            'name': 'volcengine',
            'keywords': ['volcengine', 'volces', 'ark'],
            'env_key': 'api_key_volcengine',
            'display_name': 'VolcEngine',
            'litellm_prefix': 'volcengine',
            'skip_prefixes': [],
            'env_extras': [],
            'is_gateway': True,
            'is_local': False,
            'detect_by_key_prefix': '',
            'detect_by_base_keyword': 'volces',
            'default_api_base': 'https://ark.cn-beijing.volces.com/api/v3',
            'strip_model_prefix': False,
            'litellm_kwargs': {},
            'model_overrides': [],
            'is_oauth': False,
            'is_direct': False,
            'supports_prompt_caching': False,
            'default_model': 'doubao-seed-1-6-251015'
        },
        {
            'name': 'volcengine_coding_plan',
            'keywords': ['volcengine-plan'],
            'env_key': 'api_key_volcengine',
            'display_name': 'VolcEngine Coding Plan',
            'litellm_prefix': 'volcengine',
            'skip_prefixes': [],
            'env_extras': [],
            'is_gateway': True,
            'is_local': False,
            'detect_by_key_prefix': '',
            'detect_by_base_keyword': '',
            'default_api_base': 'https://ark.cn-beijing.volces.com/api/coding/v3',
            'strip_model_prefix': True,
            'litellm_kwargs': {},
            'model_overrides': [],
            'is_oauth': False,
            'is_direct': False,
            'supports_prompt_caching': False,
            'default_model': ''
        },
        {
            'name': 'byteplus',
            'keywords': ['byteplus'],
            'env_key': 'api_key_byteplus',
            'display_name': 'BytePlus',
            'litellm_prefix': 'volcengine',
            'skip_prefixes': [],
            'env_extras': [],
            'is_gateway': True,
            'is_local': False,
            'detect_by_key_prefix': '',
            'detect_by_base_keyword': 'bytepluses',
            'default_api_base': 'https://ark.ap-southeast.bytepluses.com/api/v3',
            'strip_model_prefix': True,
            'litellm_kwargs': {},
            'model_overrides': [],
            'is_oauth': False,
            'is_direct': False,
            'supports_prompt_caching': False,
            'default_model': ''
        },
        {
            'name': 'byteplus_coding_plan',
            'keywords': ['byteplus-plan'],
            'env_key': 'api_key_byteplus',
            'display_name': 'BytePlus Coding Plan',
            'litellm_prefix': 'volcengine',
            'skip_prefixes': [],
            'env_extras': [],
            'is_gateway': True,
            'is_local': False,
            'detect_by_key_prefix': '',
            'detect_by_base_keyword': '',
            'default_api_base': 'https://ark.ap-southeast.bytepluses.com/api/coding/v3',
            'strip_model_prefix': True,
            'litellm_kwargs': {}, 'model_overrides': [], 'is_oauth': False, 'is_direct': False, 'supports_prompt_caching': False, 'default_model': ''}, {'name': 'anthropic', 'keywords': ['anthropic', 'claude'], 'env_key': 'api_key_anthropic', 'display_name': 'Anthropic', 'litellm_prefix': '', 'skip_prefixes': [], 'env_extras': [], 'is_gateway': False, 'is_local': False, 'detect_by_key_prefix': '', 'detect_by_base_keyword': '', 'default_api_base': '', 'strip_model_prefix': False, 'litellm_kwargs': {}, 'model_overrides': [], 'is_oauth': False, 'is_direct': False, 'supports_prompt_caching': True, 'default_model': 'claude-opus-4-5'}, {'name': 'openai', 'keywords': ['openai', 'gpt'], 'env_key': 'api_key_openai', 'display_name': 'OpenAI', 'litellm_prefix': '', 'skip_prefixes': [], 'env_extras': [], 'is_gateway': False, 'is_local': False, 'detect_by_key_prefix': '', 'detect_by_base_keyword': '', 'default_api_base': '', 'strip_model_prefix': False, 'litellm_kwargs': {}, 'model_overrides': [], 'is_oauth': False, 'is_direct': False, 'supports_prompt_caching': False, 'default_model': 'gpt-4o'}, {'name': 'openai_codex', 'keywords': ['openai-codex'], 'env_key': '', 'display_name': 'OpenAI Codex', 'litellm_prefix': '', 'skip_prefixes': [], 'env_extras': [], 'is_gateway': False, 'is_local': False, 'detect_by_key_prefix': '', 'detect_by_base_keyword': 'codex', 'default_api_base': 'https://chatgpt.com/backend-api', 'strip_model_prefix': False, 'litellm_kwargs': {}, 'model_overrides': [], 'is_oauth': True, 'is_direct': False, 'supports_prompt_caching': False, 'default_model': ''}, {'name': 'github_copilot', 'keywords': ['github_copilot', 'copilot'], 'env_key': '', 'display_name': 'Github Copilot', 'litellm_prefix': 'github_copilot', 'skip_prefixes': ['github_copilot/'], 'env_extras': [], 'is_gateway': False, 'is_local': False, 'detect_by_key_prefix': '', 'detect_by_base_keyword': '', 'default_api_base': '', 'strip_model_prefix': False, 'litellm_kwargs': {}, 'model_overrides': [], 'is_oauth': True, 'is_direct': False, 'supports_prompt_caching': False, 'default_model': ''}, {'name': 'deepseek', 'keywords': ['deepseek'], 'env_key': 'api_key_deepseek', 'display_name': 'DeepSeek', 'litellm_prefix': 'deepseek', 'skip_prefixes': ['deepseek/'], 'env_extras': [], 'is_gateway': False, 'is_local': False, 'detect_by_key_prefix': '', 'detect_by_base_keyword': '', 'default_api_base': 'https://api.deepseek.com', 'strip_model_prefix': False, 'litellm_kwargs': {}, 'model_overrides': [], 'is_oauth': False, 'is_direct': False, 'supports_prompt_caching': False, 'default_model': 'deepseek-chat'}, {'name': 'gemini', 'keywords': ['gemini'], 'env_key': 'api_key_gemini', 'display_name': 'Gemini', 'litellm_prefix': 'gemini', 'skip_prefixes': ['gemini/'], 'env_extras': [], 'is_gateway': False, 'is_local': False, 'detect_by_key_prefix': '', 'detect_by_base_keyword': '', 'default_api_base': '', 'strip_model_prefix': False, 'litellm_kwargs': {}, 'model_overrides': [], 'is_oauth': False, 'is_direct': False, 'supports_prompt_caching': False, 'default_model': 'gemini-2.0-flash'}, {'name': 'zhipu', 'keywords': ['zhipu', 'glm', 'zai'], 'env_key': 'api_key_zhipu', 'display_name': 'Zhipu AI', 'litellm_prefix': 'zai', 'skip_prefixes': ['zhipu/', 'zai/', 'openrouter/', 'hosted_vllm/'], 'env_extras': [['ZHIPUAI_API_KEY', '{api_key}']], 'is_gateway': False, 'is_local': False, 'detect_by_key_prefix': '', 'detect_by_base_keyword': '', 'default_api_base': 'https://open.bigmodel.cn/api/paas/v4', 'strip_model_prefix': False, 'litellm_kwargs': {}, 'model_overrides': [], 'is_oauth': False, 'is_direct': False, 'supports_prompt_caching': False, 'default_model': 'glm-5'}, {'name': 'dashscope', 'keywords': ['qwen', 'dashscope'], 'env_key': 'api_key_dashscope', 'display_name': 'DashScope', 'litellm_prefix': 'dashscope', 'skip_prefixes': ['dashscope/', 'openrouter/'], 'env_extras': [], 'is_gateway': False, 'is_local': False, 'detect_by_key_prefix': '', 'detect_by_base_keyword': '', 'default_api_base': '', 'strip_model_prefix': False, 'litellm_kwargs': {}, 'model_overrides': [], 'is_oauth': False, 'is_direct': False, 'supports_prompt_caching': False, 'default_model': 'qwen3.5-plus'}, {'name': 'moonshot', 'keywords': ['moonshot', 'kimi'], 'env_key': 'api_key_moonshot', 'display_name': 'Moonshot', 'litellm_prefix': 'moonshot', 'skip_prefixes': ['moonshot/', 'openrouter/'], 'env_extras': [['MOONSHOT_API_BASE', '{api_base}']], 'is_gateway': False, 'is_local': False, 'detect_by_key_prefix': '', 'detect_by_base_keyword': '', 'default_api_base': 'https://api.moonshot.cn/v1', 'strip_model_prefix': False, 'litellm_kwargs': {}, 'model_overrides': [['kimi-k2.5', {'temperature': 1.0}]], 'is_oauth': False, 'is_direct': False, 'supports_prompt_caching': False, 'default_model': 'kimi-k2.5'}, {'name': 'minimax', 'keywords': ['minimax'], 'env_key': 'api_key_minimax', 'display_name': 'MiniMax', 'litellm_prefix': 'minimax', 'skip_prefixes': ['minimax/', 'openrouter/'], 'env_extras': [], 'is_gateway': False, 'is_local': False, 'detect_by_key_prefix': '', 'detect_by_base_keyword': '', 'default_api_base': 'https://api.minimaxi.com/v1', 'strip_model_prefix': False, 'litellm_kwargs': {}, 'model_overrides': [], 'is_oauth': False, 'is_direct': False, 'supports_prompt_caching': False, 'default_model': 'MiniMax-M2.1'}, {'name': 'vllm', 'keywords': ['vllm'], 'env_key': 'api_key_vllm', 'display_name': 'vLLM/Local', 'litellm_prefix': 'hosted_vllm', 'skip_prefixes': [], 'env_extras': [], 'is_gateway': False, 'is_local': True, 'detect_by_key_prefix': '', 'detect_by_base_keyword': '', 'default_api_base': '', 'strip_model_prefix': False, 'litellm_kwargs': {}, 'model_overrides': [], 'is_oauth': False, 'is_direct': False, 'supports_prompt_caching': False, 'default_model': ''}, {'name': 'ollama', 'keywords': ['ollama', 'nemotron'], 'env_key': 'api_key_ollama', 'display_name': 'Ollama', 'litellm_prefix': 'ollama_chat', 'skip_prefixes': ['ollama/', 'ollama_chat/'], 'env_extras': [], 'is_gateway': False, 'is_local': True, 'detect_by_key_prefix': '', 'detect_by_base_keyword': '11434', 'default_api_base': 'http://localhost:11434', 'strip_model_prefix': False, 'litellm_kwargs': {}, 'model_overrides': [], 'is_oauth': False, 'is_direct': False, 'supports_prompt_caching': False, 'default_model': ''}, {'name': 'groq', 'keywords': ['groq'], 'env_key': 'api_key_groq', 'display_name': 'Groq', 'litellm_prefix': 'groq', 'skip_prefixes': ['groq/'], 'env_extras': [], 'is_gateway': False, 'is_local': False, 'detect_by_key_prefix': '', 'detect_by_base_keyword': '', 'default_api_base': '', 'strip_model_prefix': False, 'litellm_kwargs': {}, 'model_overrides': [], 'is_oauth': False, 'is_direct': False, 'supports_prompt_caching': False, 'default_model': ''}
    ]
}

class ProviderManager:
    """
    服务商配置管理器（单例）

    数据来源：lifeprism/config/providers.yaml（开发）
            或 config_base_path/config/providers.yaml（打包）
    """

    _instance: "ProviderManager | None" = None

    def __new__(cls) -> "ProviderManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        self._raw_specs: list[dict[str, Any]] = []
        self._allowed_providers: list[str] = []

        is_dev = not getattr(sys, "frozen", False)

        if is_dev:
            config_path = Path(__file__).parent / "providers.yaml"
        else:
            from lifeprism.config.settings_manager import settings
            config_path = Path(settings.config_base_path) / "config" / "providers.yaml"

        if not config_path.exists():
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(DEFAULT_PROVIDER_CONFIG, f, allow_unicode=True, sort_keys=False)
            logger.info(f"providers.yaml not found, created from DEFAULT_PROVIDER_CONFIG: {config_path}")

        self._load_config(config_path)

    def _load_config(self, config_path: Path) -> None:
        try:
            with open(config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            self._raw_specs = data.get("providers", [])
            self._allowed_providers = data.get("allowed_providers", [])
            logger.debug(f"Loaded {len(self._raw_specs)} providers from {config_path}")
        except Exception:
            logger.exception(f"Failed to load providers.yaml from {config_path}")
            self._raw_specs = []
            self._allowed_providers = []

    # ------------------------------------------------------------------
    # 供 registry.py 使用
    # ------------------------------------------------------------------

    def get_raw_specs(self) -> list[dict[str, Any]]:
        """返回 yaml 中全部 provider 的原始 dict 列表，供 registry 构建 ProviderSpec。"""
        return self._raw_specs

    def get_allowed_providers(self) -> list[str]:
        """返回 allowed_providers 白名单（有序）。"""
        return self._allowed_providers

    # ------------------------------------------------------------------
    # keyring 读写
    # ------------------------------------------------------------------

    def get_api_key(self, provider_name: str) -> str | None:
        """
        从 keyring 读取 provider 的 API key。
        env_key 为空（如 custom）时返回 None。
        """
        env_key = self._get_env_key(provider_name)
        if not env_key:
            return None
        return keyring.get_password(_KEYRING_SERVICE, env_key)

    def set_api_key(self, provider_name: str, api_key: str) -> None:
        """将 API key 写入 keyring。"""
        env_key = self._get_env_key(provider_name)
        if not env_key:
            logger.warning(f"Provider '{provider_name}' has no env_key, skipping keyring write")
            return
        keyring.set_password(_KEYRING_SERVICE, env_key, api_key)

    def delete_api_key(self, provider_name: str) -> None:
        """从 keyring 删除 API key。"""
        env_key = self._get_env_key(provider_name)
        if not env_key:
            return
        try:
            keyring.delete_password(_KEYRING_SERVICE, env_key)
        except keyring.errors.PasswordDeleteError:
            pass

    def _get_env_key(self, provider_name: str) -> str:
        """从 raw_specs 中查找 provider 的 env_key。"""
        for spec in self._raw_specs:
            if spec.get("name") == provider_name:
                return spec.get("env_key", "")
        return ""

    # ------------------------------------------------------------------
    # 供 API 层使用
    # ------------------------------------------------------------------

    def get_all_providers(self, allowed_only: bool = True) -> list[dict[str, Any]]:
        """
        返回 provider 展示信息列表，供前端使用。
        allowed_only=True 时只返回白名单中的 provider。
        """
        specs = self._raw_specs
        if allowed_only and self._allowed_providers:
            allowed_set = set(self._allowed_providers)
            specs = [s for s in specs if s.get("name") in allowed_set]
            # 按 allowed_providers 顺序排序
            order = {name: i for i, name in enumerate(self._allowed_providers)}
            specs = sorted(specs, key=lambda s: order.get(s.get("name", ""), 999))

        return [
            {
                "name": s.get("name", ""),
                "display_name": s.get("display_name", ""),
                "default_model": s.get("default_model", ""),
                "default_api_base": s.get("default_api_base", ""),
                "has_api_key": bool(s.get("env_key", "")),
            }
            for s in specs
        ]

    def get_default_provider(self) -> str:
        """返回白名单中第一个 provider name。"""
        return self._allowed_providers[0] if self._allowed_providers else ""


# 全局单例
provider_manager = ProviderManager()
