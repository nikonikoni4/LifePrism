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

ALLOWED_DIRS = ['user','diary','agent']

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
        'api_base': '',  # 空=由 settings 界面按 provider 历史/默认值回填
        'input_tokens_cost': 0.0,
        'output_tokens_cost': 0.0,
        'classification_mode': 'classify_graph',
        'long_log_threshold': 600,
        'multi_purpose_app_names': ['chrome', 'msedge', 'firefox'],
        'aw_db_path': '~/AppData/Local/activitywatch/activitywatch/aw-server/peewee-sqlite.v2.db',
        'lifeprism_data_path': '',  # 空=使用默认路径
        'data_cleaning_threshold': 10,
        'poll_time': 1.0,
        'afk_timeout': 180.0,
        'exclude_titles': [],
        'model_history': {},  # 按服务商存储的模型历史 {provider_id: {api_base: '', models: [model1, model2, ...]}}
        'monitor_type': 'lifeprism',
        'scheduled_screenshot_interval_seconds': 60,
        'active_screenshot_frequency_level': 2,
        'keyboard_keepalive_seconds': 12,
        'mouse_keepalive_seconds': 6,
        'enter_screenshot_delay_ms': 700,
        'screenshot_retention_days': 3,
        'cleanup_check_interval_seconds': 86400,
        'is_vlm': {},  # Dict[str, bool], key = "provider_id/model_name"
        'screenshot_monitor': False,
        'screen_analysis_ignore': [],  # 截图分析忽略的分类 ID 列表
        'auto_diary_summary': False,  # 每日自动总结日记
    }
    
    def __new__(cls) -> 'SettingsManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def get_config_path(self)->Path:
        return self._config_path

        
    def _initialize(self) -> None:
        """初始化配置管理器"""
        self._config: Dict[str, Any] = {}
        self._warnings: List[Dict[str, str]] = []
        # 判断是否是开发环境
        self._is_dev = not getattr(sys, 'frozen', False)

        # 1. 解析配置文件基础路径（固定，不随数据迁移）
        self._config_base_path = self._resolve_config_base_path()
        
        self._config_path = self._config_base_path / 'config' / 'config.yaml' # 打包环境和开发环境都使用_config_base_path，命名都改为config.yaml
        # 2. 加载 yaml 配置
        self._load_config()

        # 3. 解析数据路径（优先级：yaml 配置 > 环境变量 > 默认路径）
        configured_path = self._config.get('lifeprism_data_path', '')
        if configured_path:
            self._lifeprism_data_path = Path(configured_path)
        else:
            self._lifeprism_data_path = self._resolve_default_data_path()

        # 4. 设置环境变量（供 Electron 等外部进程使用）
        os.environ['LIFEPRISM_DATA_PATH'] = str(self._lifeprism_data_path)

        # 5. 配置日志文件输出（logger 此前只有控制台输出）
        self._setup_logging()

        # 6. 检查数据路径安全性（仅打包环境）
        self._check_data_path_safety()

        # 7. 解析允许的工作目录路径
        self._allowed_dir_path = self._resolve_allowed_dir_paths()

    def _resolve_config_base_path(self) -> Path:
        """
        配置文件基础路径（固定，不随数据迁移）

        打包环境：%LOCALAPPDATA%/LifePrism/lifeprismData
        开发环境：localData
        """
        if getattr(sys, 'frozen', False):
            localappdata = os.environ.get('LOCALAPPDATA', '')
            if localappdata:
                return Path(localappdata) / 'LifePrism' / 'lifeprismData'
            # 后备：基于 exe 路径推算
            backend_dir = Path(sys.executable).parent
            app_dir = backend_dir.parent.parent
            root_dir = app_dir.parent
            return root_dir.parent / 'lifeprismData'
        return Path("localData")

    def _resolve_default_data_path(self) -> Path:
        """
        解析默认的 lifeprismData 路径（不依赖 yaml 配置）

        优先级:
        1. 环境变量 LIFEPRISM_DATA_PATH（由 Electron 启动时设置）
        2. 配置基础路径（打包环境：%LOCALAPPDATA%/LifePrism/lifeprismData，开发环境：localData）

        Returns:
            Path: lifeprismData 目录路径
        """
        # 1. 环境变量（Electron 启动后端时传入）
        data_env = os.environ.get('LIFEPRISM_DATA_PATH')
        if data_env:
            return Path(data_env)

        # 2. 默认与配置基础路径相同
        return self._config_base_path

    def _resolve_allowed_dir_paths(self) -> List[Path]:
        """
        解析允许的工作目录路径列表

        基于 lifeprism_data_path 和 ALLOWED_DIRS 计算允许访问的目录绝对路径

        Note: 必须在 _lifeprism_data_path 初始化后调用

        Returns:
            List[Path]: 允许的目录路径列表
        """
        allowed_paths: List[Path] = []
        for dir_name in ALLOWED_DIRS:
            allowed_paths.append((self._lifeprism_data_path / dir_name).resolve())
        return allowed_paths

    def _setup_logging(self) -> None:
        """配置日志文件输出"""
        from lifeprism.utils.logger import setup_file_logging

        # 日志写入 {_lifeprism_data_path}/debug_logs/ 
        setup_file_logging(self._lifeprism_data_path / 'debug_logs')
 

    def _check_data_path_safety(self) -> None:
        """检查数据路径是否位于安装目录内（仅打包环境）"""
        if self._is_dev:
            return
        try:
            # exe 位于 install_dir/resources/app/backend/xxx.exe
            backend_dir = Path(sys.executable).parent
            install_dir = backend_dir.parent.parent.parent
            resolved_data = self._lifeprism_data_path.resolve()
            resolved_install = install_dir.resolve()
            resolved_data.relative_to(resolved_install)
            # 没抛异常 = 数据路径在安装目录内
            self._warnings.append({
                "type": "data_path",
                "message": "数据路径位于安装目录内，更新版本时安装目录下的内容可能被删除，建议在设置中迁移数据路径"
            })
        except (ValueError, OSError):
            pass  # ValueError=不是子目录（安全），OSError=resolve失败（不阻塞启动）

    @property
    def warnings(self) -> List[str]:
        """获取系统警告列表"""
        return list(self._warnings)  # List[Dict[str, str]]
            
    
    def _load_config(self) -> None:
        """从 YAML 文件加载配置"""
        if self._config_path.exists():
            from lifeprism.config.migrations.config_migrator import run_config_migrations
            from lifeprism.config.migrations.scripts import SETTINGS_MIGRATIONS
            self._config = run_config_migrations(self._config_path, SETTINGS_MIGRATIONS) or {}
        else:
            self._config = self.DEFAULTS.copy()
            # 如果配置文件不存在，创建默认配置
            self._save_config()

        self._config['model_history'] = self._normalize_model_history(
            self._config.get('model_history')
        )
    
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

    def _normalize_model_history(
        self, raw_history: Optional[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        统一模型历史结构。

        兼容旧结构:
        {provider_id: [model1, model2]}

        新结构:
        {provider_id: {"api_base": "", "models": [model1, model2]}}
        """
        normalized: Dict[str, Dict[str, Any]] = {}
        if not isinstance(raw_history, dict):
            return normalized

        for provider_id, snapshot in raw_history.items():
            if isinstance(snapshot, list):
                models = [item for item in snapshot if isinstance(item, str) and item]
                normalized[provider_id] = {
                    "api_base": "",
                    "models": models,
                }
                continue

            if isinstance(snapshot, dict):
                raw_models = snapshot.get("models", snapshot.get("model", []))
                if isinstance(raw_models, list):
                    models = [item for item in raw_models if isinstance(item, str) and item]
                else:
                    models = []

                api_base = snapshot.get("api_base", "")
                normalized[provider_id] = {
                    "api_base": api_base if isinstance(api_base, str) else "",
                    "models": models,
                }

        return normalized
    
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
        # 验证 screenshot_retention_days
        if 'screenshot_retention_days' in updates:
            days = updates['screenshot_retention_days']
            if days < 3:
                raise ValueError(f"截图保留天数不能小于3天，当前值：{days}")

        # 验证 active_screenshot_frequency_level
        if 'active_screenshot_frequency_level' in updates:
            level = updates['active_screenshot_frequency_level']
            if level not in [1, 2, 3]:
                raise ValueError(f"频率等级必须是1、2或3，当前值：{level}")

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

            # 如果更新了 lifeprism_data_path，同步更新环境变量和内部路径
            if 'lifeprism_data_path' in updates:
                new_path = updates['lifeprism_data_path']
                if new_path:
                    self._lifeprism_data_path = Path(new_path)
                else:
                    self._lifeprism_data_path = self._resolve_default_data_path()
                os.environ['LIFEPRISM_DATA_PATH'] = str(self._lifeprism_data_path)
    
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

        # 添加计算属性（转为字符串供前端使用）
        result['lifeprism_data_path'] = str(self.lifeprism_data_path)

        # 移除已废弃的独立路径字段
        result.pop('lw_db_path', None)
        result.pop('chat_db_path', None)

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
    def api_base(self) -> str:
        return self.get('api_base')
    
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

    def is_multi_purpose_app(self, app_name: str) -> bool:
        if not app_name:
            return False
        normalized_name = app_name.lower()
        for multi_app in self.multi_purpose_app_names:
            if multi_app.lower() in normalized_name or normalized_name in multi_app.lower():
                return True
        return False

    @property
    def monitor_type(self) -> str:
        return self.get('monitor_type')
    
    @property
    def aw_db_path(self) -> Path:
        aw_path = os.path.expanduser(self.get('aw_db_path')) if self.get('aw_db_path') else ''
        return Path(aw_path) if aw_path else Path()

    @property
    def lw_db_path(self) -> Path:
        """获取 LifeWatch 数据库路径（自动推算，位于 lifeprismData/dataset/）"""
        return self._lifeprism_data_path / 'dataset' / 'lifewatch_ai.db'

    @property
    def chat_db_path(self) -> Path:
        """获取聊天历史数据库路径（自动推算，位于 lifeprismData/dataset/）"""
        return self._lifeprism_data_path / 'dataset' / 'chat_history.db'

    @property
    def data_cleaning_threshold(self) -> int:
        return self.get('data_cleaning_threshold')

    @property
    def lifeprism_data_path(self) -> Path:
        """获取 lifeprismData 目录路径（唯一数据源）"""
        return self._lifeprism_data_path

    @property
    def config_base_path(self) -> Path:
        """配置文件基础路径（固定，不随数据迁移）"""
        return self._config_base_path

    @property
    def custom_data_path(self) -> Path:
        """DEPRECATED: 使用 lifeprism_data_path 替代"""
        return self._lifeprism_data_path

    @property
    def allowed_dir_path(self) -> List[Path]:
        """获取允许的工作目录路径列表"""
        return self._allowed_dir_path

    @property
    def model_history(self) -> Dict[str, Dict[str, Any]]:
        """获取模型历史记录"""
        return self._normalize_model_history(self.get('model_history') or {})
    @property
    def channel_path(self) -> Path:
        """获取通道路径配置"""
        return self._lifeprism_data_path / 'channel'

    @property
    def session_path(self)->Path:
        return self._lifeprism_data_path / 'session'

    @property
    def auto_diary_summary(self)->bool:
        return self._config.get("auto_diary_summary",False)

    @property
    def token_limit(self)->int:
        return  50000 # 暂定50k

    def get_provider_history(self, provider_id: str) -> Dict[str, Any]:
        """获取指定服务商的历史快照。"""
        history = self.model_history
        return history.get(provider_id, {"api_base": "", "models": []})

    def get_model_history_for_provider(self, provider_id: str) -> List[str]:
        """
        获取指定服务商的模型历史

        Args:
            provider_id: 服务商 ID，如 "aliyun", "volcengine" 等

        Returns:
            模型名称列表
        """
        snapshot = self.get_provider_history(provider_id)
        return list(snapshot.get("models", []))

    def get_provider_api_base(self, provider_id: str) -> str:
        """获取指定服务商最近保存的 api_base。"""
        snapshot = self.get_provider_history(provider_id)
        api_base = snapshot.get("api_base", "")
        return api_base if isinstance(api_base, str) else ""

    def set_provider_api_base(self, provider_id: str, api_base: str) -> None:
        """更新指定服务商的 api_base，保留历史模型列表。"""
        if not provider_id:
            return

        history = self.model_history
        snapshot = history.get(provider_id, {"api_base": "", "models": []})
        snapshot["api_base"] = api_base or ""
        history[provider_id] = snapshot
        self.set('model_history', history)

    def add_model_to_history(
        self, provider_id: str, model: str, api_base: Optional[str] = None
    ) -> None:
        """
        将模型添加到历史记录

        Args:
            provider_id: 服务商 ID
            model: 模型名称/ID
            api_base: 当前 provider 对应的 API Base
        """
        if not model or not provider_id:
            return

        history = self.model_history
        snapshot = history.get(provider_id, {"api_base": "", "models": []})
        models = list(snapshot.get("models", []))

        # 如果已存在，先移除再添加到最前面
        if model in models:
            models.remove(model)
        models.insert(0, model)

        # 限制每个服务商最多保存 10 个历史模型
        snapshot["models"] = models[:10]
        if api_base is not None:
            snapshot["api_base"] = api_base or ""
        history[provider_id] = snapshot

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
        history = self.model_history
        snapshot = history.get(provider_id)
        if not snapshot:
            return False

        models = list(snapshot.get("models", []))
        if model in models:
            models.remove(model)
            snapshot["models"] = models
            history[provider_id] = snapshot
            self.set('model_history', history)
            return True
        return False

    def is_visual(self) -> bool:
        """
        判断当前配置的模型是否具备 VLM 能力

        Returns:
            bool: 当前模型是否支持图像理解
        """
        provider_id = self._get_provider_id_from_name(self.provider)
        if not provider_id or not self.model:
            return False
        key = f"{provider_id}/{self.model}"
        return self._config.get('is_vlm', {}).get(key, False)


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
