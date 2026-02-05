"""
Settings 服务层 - 配置管理业务逻辑

纯函数模块，封装 SettingsManager 的操作，提供给 API 层使用
"""
from typing import Dict, Any, Optional, List

from lifeprism.config.settings_manager import settings
from lifeprism.config.settings import SUPPORT_PROVIDER, PROVIDER_ID_MAP
from lifeprism.server.schemas.setting_schemas import (
    SettingItems,
    UpdateSettingsRequest,
)
from lifeprism.utils import get_logger

logger = get_logger(__name__)


def get_settings() -> SettingItems:
    """
    获取所有配置 (API Key 脱敏显示)

    Returns:
        SettingItems: 完整配置，API Key 已脱敏
    """
    config = settings.get_for_display()
    # 添加 provider_list (来自常量配置)
    config['provider_list'] = SUPPORT_PROVIDER
    # 添加 model_history
    config['model_history'] = settings.model_history
    return SettingItems(**config)


def update_settings(request: UpdateSettingsRequest) -> SettingItems:
    """
    批量更新配置 (不包含 api_key)

    只更新请求中非 None 的字段

    Args:
        request: 更新配置请求

    Returns:
        SettingItems: 更新后的完整配置
    """
    updates = request.model_dump(exclude_none=True)
    if updates:
        logger.info(f"更新配置: {list(updates.keys())}")

        # 如果同时更新了 provider 和 model，将模型添加到历史
        provider = updates.get('provider')
        model = updates.get('model')
        if provider and model:
            # 将显示名称转换为 provider_id
            provider_id = PROVIDER_ID_MAP.get(provider, provider.lower())
            settings.add_model_to_history(provider_id, model)
            logger.info(f"已将模型 {model} 添加到 {provider_id} 的历史记录")

        settings.update(updates)
    return get_settings()


def update_api_key(api_key: str, provider_id: Optional[str] = None) -> bool:
    """
    更新 API Key (安全存储到 keyring)

    Args:
        api_key: 新的 API Key
        provider_id: 服务商 ID 或显示名称，如 "aliyun", "火山引擎 (VolcEngine)" 等。
                     如果为 None，则保存到通用位置（向后兼容）

    Returns:
        bool: 是否成功
    """
    if provider_id:
        # 延迟导入避免循环依赖
        from lifeprism.llm.utils import get_provider_id as _get_provider_id
        # 将显示名称转换为 provider_id（如果传入的是显示名称）
        actual_provider_id = _get_provider_id(provider_id)
        logger.info(f"正在更新 {actual_provider_id} 的 API Key...")
        settings.set_api_key(api_key, actual_provider_id)
        logger.info(f"{actual_provider_id} 的 API Key 已安全保存到系统密钥管理器")
    else:
        logger.info("正在更新 API Key...")
        settings.set('api_key', api_key)
        logger.info("API Key 已安全保存到系统密钥管理器")
    return True


def validate_api_key(provider_id: Optional[str] = None) -> bool:
    """
    检查 API Key 是否已配置

    Args:
        provider_id: 服务商 ID，如果为 None 则检查通用 API Key

    Returns:
        bool: API Key 是否存在
    """
    if provider_id:
        return settings.get_api_key(provider_id) is not None
    return settings.api_key is not None


def get_model_history(provider_id: str) -> List[str]:
    """
    获取指定服务商的模型历史

    Args:
        provider_id: 服务商 ID

    Returns:
        模型名称列表
    """
    return settings.get_model_history_for_provider(provider_id)


def remove_model_from_history(provider_id: str, model: str) -> bool:
    """
    从历史记录中删除模型

    Args:
        provider_id: 服务商 ID
        model: 模型名称/ID

    Returns:
        是否删除成功
    """
    result = settings.remove_model_from_history(provider_id, model)
    if result:
        logger.info(f"已从 {provider_id} 的历史记录中删除模型 {model}")
    return result
