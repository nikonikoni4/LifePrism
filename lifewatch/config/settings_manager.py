"""
配置管理器 - 负责读取和修改 settings.yaml 配置

API Key 读取优先级:
1. 环境变量 (LIFEWATCH_API_KEY)
2. 系统密钥管理器 (keyring)
3. settings.yaml 配置文件 (不推荐，仅作为后备)
"""

import os
import yaml
import keyring
from pathlib import Path
from typing import Any, Optional, List, Dict
from functools import lru_cache

# Keyring 服务名称
KEYRING_SERVICE_NAME = "lifewatch-ai"
KEYRING_API_KEY_USERNAME = "api_key"


class SettingsManager:
    """配置管理器单例"""
    
    _instance: Optional['SettingsManager'] = None
    _config: Dict[str, Any] = {}
    _config_path: Path
    
    # 环境变量映射 (yaml_key -> env_var_name)
    ENV_VAR_MAPPING = {
        'api_key': 'LIFEWATCH_API_KEY',
    }
    
    # 默认配置值
    DEFAULTS = {
        'user_name': '默认用户',
        'api_key': None,
        'provider': '',
        'model': '',
        'input_tokens_cost': 0.0,
        'output_tokens_cost': 0.0,
        'classification_mode': 'classify_graph',
        'long_log_threshold': 3600,
        'multi_purpose_app_names': ['chrome', 'msedge', 'firefox'],
        'aw_db_path': '',
        'lw_db_path': '',
        'chat_db_path': '',
        'data_cleaning_threshold': 10,
    }
    
    def __new__(cls) -> 'SettingsManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self) -> None:
        """初始化配置管理器"""
        # 配置文件路径
        self._config_path = Path(__file__).parent / 'settings.yaml'
        self._load_config()
    
    def _load_config(self) -> None:
        """从 YAML 文件加载配置"""
        if self._config_path.exists():
            with open(self._config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = {}
            # 如果配置文件不存在，创建默认配置
            self._save_config()
    
    def _save_config(self) -> None:
        """保存配置到 YAML 文件"""
        # 确保目录存在
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self._config_path, 'w', encoding='utf-8') as f:
            yaml.dump(
                self._config, 
                f, 
                allow_unicode=True, 
                default_flow_style=False,
                sort_keys=False
            )
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        优先级: 环境变量 > keyring(仅api_key) > yaml配置 > 默认值
        
        Args:
            key: 配置键名
            default: 默认值 (如果未提供，使用 DEFAULTS 中的值)
            
        Returns:
            配置值
        """
        # 1. 检查环境变量
        if key in self.ENV_VAR_MAPPING:
            env_value = os.getenv(self.ENV_VAR_MAPPING[key])
            if env_value:
                return env_value
        
        # 2. 对于 api_key，优先从 keyring 获取
        if key == 'api_key':
            keyring_value = self._get_api_key_from_keyring()
            if keyring_value:
                return keyring_value
        
        # 3. 检查 yaml 配置
        if key in self._config and self._config[key] is not None:
            return self._config[key]
        
        # 4. 返回默认值
        if default is not None:
            return default
        return self.DEFAULTS.get(key)
    
    def _get_api_key_from_keyring(self) -> Optional[str]:
        """从系统密钥管理器获取 API Key"""
        try:
            return keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_API_KEY_USERNAME)
        except Exception:
            return None
    
    def _set_api_key_to_keyring(self, api_key: str) -> bool:
        """将 API Key 保存到系统密钥管理器"""
        try:
            keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_API_KEY_USERNAME, api_key)
            return True
        except Exception as e:
            print(f"Warning: Failed to save API key to keyring: {e}")
            return False
    
    def _delete_api_key_from_keyring(self) -> bool:
        """从系统密钥管理器删除 API Key"""
        try:
            keyring.delete_password(KEYRING_SERVICE_NAME, KEYRING_API_KEY_USERNAME)
            return True
        except keyring.errors.PasswordDeleteError:
            return False
        except Exception:
            return False
    
    def set(self, key: str, value: Any, save: bool = True) -> None:
        """
        设置配置值
        
        对于 api_key，会保存到系统密钥管理器而非 yaml 文件
        
        Args:
            key: 配置键名
            value: 配置值
            save: 是否立即保存到文件 (api_key 忽略此参数，始终保存到 keyring)
        """
        # api_key 特殊处理：保存到 keyring
        if key == 'api_key':
            if value:
                self._set_api_key_to_keyring(value)
            else:
                self._delete_api_key_from_keyring()
            # 不保存到 yaml 文件
            return
        
        self._config[key] = value
        if save:
            self._save_config()
    
    def update(self, updates: Dict[str, Any], save: bool = True) -> None:
        """
        批量更新配置
        
        Args:
            updates: 要更新的配置字典
            save: 是否立即保存到文件
        """
        # 分离出 api_key
        if 'api_key' in updates:
            api_key = updates.pop('api_key')
            if api_key:
                self._set_api_key_to_keyring(api_key)
            else:
                self._delete_api_key_from_keyring()
        
        # 更新其他配置
        if updates:
            self._config.update(updates)
            if save:
                self._save_config()
    
    def reload(self) -> None:
        """重新加载配置文件"""
        self._load_config()
    
    def get_all(self) -> Dict[str, Any]:
        """
        获取所有配置 (合并默认值)
        
        Returns:
            完整的配置字典
        """
        result = self.DEFAULTS.copy()
        result.update(self._config)
        
        # 应用环境变量覆盖
        for key, env_var in self.ENV_VAR_MAPPING.items():
            env_value = os.getenv(env_var)
            if env_value:
                result[key] = env_value
        
        # 从 keyring 获取 api_key
        keyring_api_key = self._get_api_key_from_keyring()
        if keyring_api_key:
            result['api_key'] = keyring_api_key
        
        return result
    
    def get_for_display(self) -> Dict[str, Any]:
        """
        获取用于显示的配置 (隐藏敏感信息)
        
        Returns:
            用于前端显示的配置字典
        """
        config = self.get_all()
        
        # 隐藏 api_key
        if config.get('api_key'):
            key = config['api_key']
            if len(key) > 8:
                config['api_key'] = f"{key[:4]}...{key[-4:]}"
            else:
                config['api_key'] = "***"
        
        return config
    
    # ===================== 便捷属性访问 =====================
    
    @property
    def user_name(self) -> str:
        return self.get('user_name')
    
    @property
    def api_key(self) -> Optional[str]:
        return self.get('api_key')
    
    @property
    def provider(self) -> str:
        return self.get('provider')
    
    @property
    def model(self) -> str:
        return self.get('model')
    
    @property
    def input_tokens_cost(self) -> float:
        return self.get('input_tokens_cost')
    
    @property
    def output_tokens_cost(self) -> float:
        return self.get('output_tokens_cost')
    
    @property
    def classification_mode(self) -> str:
        return self.get('classification_mode')
    
    @property
    def long_log_threshold(self) -> int:
        return self.get('long_log_threshold')
    
    @property
    def multi_purpose_app_names(self) -> List[str]:
        return self.get('multi_purpose_app_names')
    
    @property
    def aw_db_path(self) -> str:
        return self.get('aw_db_path')
    
    @property
    def lw_db_path(self) -> str:
        return self.get('lw_db_path')
    
    @property
    def chat_db_path(self) -> str:
        return self.get('chat_db_path')
    
    @property
    def data_cleaning_threshold(self) -> int:
        return self.get('data_cleaning_threshold')


# 全局单例实例
settings = SettingsManager()


# ===================== 便捷函数 =====================

def get_setting(key: str, default: Any = None) -> Any:
    """获取配置值的便捷函数"""
    return settings.get(key, default)


def set_setting(key: str, value: Any) -> None:
    """设置配置值的便捷函数"""
    settings.set(key, value)


def get_api_key() -> Optional[str]:
    """获取 API Key 的便捷函数"""
    return settings.api_key


def get_all_settings() -> Dict[str, Any]:
    """获取所有配置的便捷函数"""
    return settings.get_all()


if __name__ == '__main__':
    print(settings.model)