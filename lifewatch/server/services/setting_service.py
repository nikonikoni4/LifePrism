"""
Settings 服务层 - 配置管理业务逻辑

封装 SettingsManager 的操作，提供给 API 层使用
"""
from typing import Dict, Any

from lifewatch.config.settings_manager import settings
from lifewatch.server.schemas.setting_schemas import (
    SettingItems,
    UpdateSettingsRequest,
)
from lifewatch.utils import get_logger

logger = get_logger(__name__)


class SettingService:
    """配置服务类"""
    
    def get_settings(self) -> SettingItems:
        """
        获取所有配置 (API Key 脱敏显示)
        
        Returns:
            SettingItems: 完整配置，API Key 已脱敏
        """
        config = settings.get_for_display()
        return SettingItems(**config)
    
    def update_settings(self, request: UpdateSettingsRequest) -> SettingItems:
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
            settings.update(updates)
        return self.get_settings()
    
    def update_api_key(self, api_key: str) -> bool:
        """
        更新 API Key (安全存储到 keyring)
        
        Args:
            api_key: 新的 API Key
            
        Returns:
            bool: 是否成功
        """
        logger.info("正在更新 API Key...")
        settings.set('api_key', api_key)
        logger.info("API Key 已安全保存到系统密钥管理器")
        return True
    
    def validate_api_key(self) -> bool:
        """
        检查 API Key 是否已配置
        
        Returns:
            bool: API Key 是否存在
        """
        return settings.api_key is not None


# 创建全局单例
setting_service = SettingService()
