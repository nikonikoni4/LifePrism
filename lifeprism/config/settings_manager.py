"""
配置管理器 - 负责读取和修改 settings.yaml 配置

API Key 读取优先级:
1. 环境变量 (LIFEWATCH_API_KEY)
2. 系统密钥管理器 (keyring)
3. settings.yaml 配置文件 (不推荐，仅作为后备)
"""

import os
import sys
import yaml
import keyring
from pathlib import Path
from typing import Any, Optional, List, Dict
from functools import lru_cache

# Keyring 服务名称
KEYRING_SERVICE_NAME = "lifeprism"
KEYRING_API_KEY_USERNAME = "api_key"  # 保留向后兼容


class SettingsManager:
    """配置管理器单例"""
    
    _instance: Optional['SettingsManager'] = None

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
        'long_log_threshold': 600,
        'multi_purpose_app_names': ['chrome', 'msedge', 'firefox'],
        'aw_db_path': '~/AppData/Local/activitywatch/activitywatch/aw-server/peewee-sqlite.v2.db',
        'lw_db_path': '~/AppData/Local/lifeprism/data/lifewatch_ai.db',
        'chat_db_path': '~/AppData/Local/lifeprism/data/chat_history.db',
        'data_cleaning_threshold': 10,
        'model_history': {},  # 按服务商存储的模型历史 {provider_id: [model1, model2, ...]}
    }
    
    def __new__(cls) -> 'SettingsManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self) -> None:
        """初始化配置管理器"""
        self._config: Dict[str, Any] = {}

        # 判断是否是开发环境
        self._is_dev = not getattr(sys, 'frozen', False)

        # 始终解析 customData 路径（开发和打包环境都需要）
        self._custom_data_path = self._resolve_custom_data_path()

        # 根据环境设置默认路径

        if self._is_dev:
            # 开发环境：使用 lifeprism/config/settings.yaml
            self._config_path = Path(__file__).parent / 'settings.yaml'
        else:
            # 打包环境：使用 customData/config/config.yaml
            self._config_path = self._custom_data_path / 'config' / 'config.yaml'
            self.DEFAULTS['lw_db_path'] = str(self._custom_data_path / 'dataset' / 'lifewatch_ai.db')
            self.DEFAULTS['chat_db_path'] = str(self._custom_data_path / 'dataset' / 'chat_history.db')


        self._load_config()
    
    def _resolve_custom_data_path(self) -> Path:
        """
        解析 customData 目录的路径
        
        优先级:
        1. 环境变量 CUSTOM_DATA_PATH (由 Electron 传入)
        2. 基于 sys.executable 推算 (打包环境后备)
        3. 开发环境: frontend/customData
        """
        # 1. 优先使用 Electron 传入的环境变量
        custom_data_env = os.environ.get('CUSTOM_DATA_PATH')
        if custom_data_env:
            return Path(custom_data_env)
        
        # 2. 打包环境：通过 exe 路径推算
        if getattr(sys, 'frozen', False):
            # sys.executable = .../LifePrism/app/resources/backend/lifeprism-backend.exe
            backend_dir = Path(sys.executable).parent   # .../app/resources/backend
            app_dir = backend_dir.parent.parent          # .../app
            root_dir = app_dir.parent                    # .../LifePrism
            return root_dir / 'customData'
        
        # 3. 开发环境
        project_root = Path(__file__).parent.parent.parent
        return project_root / 'frontend' / 'customData'
            
    
    def _load_config(self) -> None:
        """从 YAML 文件加载配置"""
        if self._config_path.exists():
            with open(self._config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = self.DEFAULTS.copy()
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
        """从系统密钥管理器获取 API Key（向后兼容）"""
        try:
            return keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_API_KEY_USERNAME)
        except Exception:
            return None

    def _get_api_key_from_keyring_by_provider(self, provider_id: str) -> Optional[str]:
        """从系统密钥管理器获取指定服务商的 API Key"""
        try:
            # 延迟导入避免循环依赖
            from lifeprism.config.provider_manager import provider_manager
            username = provider_manager.get_keyring_username(provider_id)
            if username:
                return keyring.get_password(KEYRING_SERVICE_NAME, username)
            return None
        except Exception:
            return None

    def _set_api_key_to_keyring(self, api_key: str) -> bool:
        """将 API Key 保存到系统密钥管理器（向后兼容）"""
        try:
            keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_API_KEY_USERNAME, api_key)
            return True
        except Exception as e:
            print(f"Warning: Failed to save API key to keyring: {e}")
            return False

    def _set_api_key_to_keyring_by_provider(self, provider_id: str, api_key: str) -> bool:
        """将 API Key 保存到系统密钥管理器（按服务商）"""
        try:
            # 延迟导入避免循环依赖
            from lifeprism.config.provider_manager import provider_manager
            username = provider_manager.get_keyring_username(provider_id)
            if username:
                keyring.set_password(KEYRING_SERVICE_NAME, username, api_key)
                return True
            return False
        except Exception as e:
            print(f"Warning: Failed to save API key for {provider_id} to keyring: {e}")
            return False

    def _delete_api_key_from_keyring(self) -> bool:
        """从系统密钥管理器删除 API Key（向后兼容）"""
        try:
            keyring.delete_password(KEYRING_SERVICE_NAME, KEYRING_API_KEY_USERNAME)
            return True
        except keyring.errors.PasswordDeleteError:
            return False
        except Exception:
            return False

    def _delete_api_key_from_keyring_by_provider(self, provider_id: str) -> bool:
        """从系统密钥管理器删除指定服务商的 API Key"""
        try:
            # 延迟导入避免循环依赖
            from lifeprism.config.provider_manager import provider_manager
            username = provider_manager.get_keyring_username(provider_id)
            if username:
                keyring.delete_password(KEYRING_SERVICE_NAME, username)
                return True
            return False
        except keyring.errors.PasswordDeleteError:
            return False
        except Exception:
            return False

    def get_api_key(self, provider_id: Optional[str] = None) -> Optional[str]:
        """
        获取 API Key

        优先级:
        1. 环境变量 LIFEWATCH_API_KEY
        2. 按服务商存储的 keyring（如果指定了 provider_id）
        3. 通用 keyring（向后兼容）

        Args:
            provider_id: 服务商 ID，如 "aliyun", "openai" 等

        Returns:
            API Key 或 None
        """
        # 1. 检查环境变量
        env_value = os.getenv('LIFEWATCH_API_KEY')
        if env_value:
            return env_value

        # 2. 按服务商获取
        if provider_id:
            provider_key = self._get_api_key_from_keyring_by_provider(provider_id)
            if provider_key:
                return provider_key

        # 3. 向后兼容：获取通用 key
        return self._get_api_key_from_keyring()

    def set_api_key(self, api_key: str, provider_id: Optional[str] = None) -> bool:
        """
        设置 API Key

        Args:
            api_key: API Key 值
            provider_id: 服务商 ID，如果为 None 则保存到通用位置

        Returns:
            是否成功
        """
        if provider_id:
            return self._set_api_key_to_keyring_by_provider(provider_id, api_key)
        return self._set_api_key_to_keyring(api_key)
    
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

        # 根据当前 provider 获取对应的 API key
        current_provider = config.get('provider', '')
        provider_id = self._get_provider_id_from_name(current_provider)

        # 优先获取当前 provider 的 API key
        api_key = None
        if provider_id:
            api_key = self._get_api_key_from_keyring_by_provider(provider_id)
        if not api_key:
            api_key = self._get_api_key_from_keyring()

        # 隐藏 api_key
        if api_key:
            if len(api_key) > 8:
                config['api_key'] = f"{api_key[:4]}...{api_key[-4:]}"
            else:
                config['api_key'] = "***"
        else:
            config['api_key'] = None

        return config

    def _get_provider_id_from_name(self, provider_name: str) -> Optional[str]:
        """
        从 provider 显示名称获取 provider_id

        Args:
            provider_name: 显示名称，如 "阿里云百炼 (Aliyun)"

        Returns:
            provider_id，如 "aliyun"
        """
        # 延迟导入避免循环依赖
        from lifeprism.config.provider_manager import provider_manager
        return provider_manager.name_to_id_map.get(provider_name)
    
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
        return os.path.expanduser(self.get('aw_db_path')) if self.get('aw_db_path') else ''
    
    @property
    def lw_db_path(self) -> str:
        """获取 LifeWatch 数据库路径"""
        path = self.get('lw_db_path')
        return os.path.expanduser(path) if path else ''

    @property
    def chat_db_path(self) -> str:
        """获取聊天历史数据库路径"""
        path = self.get('chat_db_path')
        return os.path.expanduser(path) if path else ''
    
    @property
    def data_cleaning_threshold(self) -> int:
        return self.get('data_cleaning_threshold')

    @property
    def custom_data_path(self) -> Path:
        """获取 customData 目录的绝对路径"""
        return self._custom_data_path

    @property
    def model_history(self) -> Dict[str, List[str]]:
        """获取模型历史记录"""
        return self.get('model_history') or {}

    def get_model_history_for_provider(self, provider_id: str) -> List[str]:
        """
        获取指定服务商的模型历史

        Args:
            provider_id: 服务商 ID，如 "aliyun", "volcengine" 等

        Returns:
            模型名称列表
        """
        history = self.model_history
        return history.get(provider_id, [])

    def add_model_to_history(self, provider_id: str, model: str) -> None:
        """
        将模型添加到历史记录

        Args:
            provider_id: 服务商 ID
            model: 模型名称/ID
        """
        if not model or not provider_id:
            return

        history = self.get('model_history') or {}
        if provider_id not in history:
            history[provider_id] = []

        # 如果已存在，先移除再添加到最前面
        if model in history[provider_id]:
            history[provider_id].remove(model)
        history[provider_id].insert(0, model)

        # 限制每个服务商最多保存 10 个历史模型
        history[provider_id] = history[provider_id][:10]

        self.set('model_history', history)

    def remove_model_from_history(self, provider_id: str, model: str) -> bool:
        """
        从历史记录中删除模型

        Args:
            provider_id: 服务商 ID
            model: 模型名称/ID

        Returns:
            是否删除成功
        """
        history = self.get('model_history') or {}
        if provider_id in history and model in history[provider_id]:
            history[provider_id].remove(model)
            self.set('model_history', history)
            return True
        return False


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