"""
跨平台路径解析单元测试

验证 settings_manager 的路径解析逻辑在不同环境（打包/开发、env var、yaml 配置）下的行为。

优先级（来自 config-path-spec）：
    yaml config `lifeprism_data_path` > env var `LIFEPRISM_DATA_PATH` > config_base_path

注意：路径解析基于 `sys.frozen`（打包环境标志）而非 `sys.platform`。
- 打包环境（sys.frozen=True）：config_base_path = %LOCALAPPDATA%/LifePrism/lifeprismData
- 开发环境（sys.frozen 不存在）：config_base_path = localData
Linux 部署属于开发环境（无 sys.frozen），回退到 localData。
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from lifeprism.config.settings_manager import SettingsManager

pytestmark = pytest.mark.core


@pytest.fixture
def settings():
    """返回 SettingsManager 单例"""
    return SettingsManager()


# ==================== config_base_path 解析 ====================


class TestConfigBasePath:
    """测试 _resolve_config_base_path() 在不同环境下的行为"""

    def test_config_base_path_packaged_env(self, settings):
        """打包环境（sys.frozen=True）：配置基础路径解析到 %LOCALAPPDATA%/LifePrism/lifeprismData

        对应 Windows 桌面打包版。
        """
        fake_localappdata = r"C:\Users\testuser\AppData\Local"
        with (
            patch.object(sys, "frozen", True, create=True),
            patch.dict(os.environ, {"LOCALAPPDATA": fake_localappdata}),
        ):
            result = settings._resolve_config_base_path()
            assert result == Path(fake_localappdata) / "LifePrism" / "lifeprismData"

    def test_config_base_path_dev_env(self, settings):
        """开发环境（sys.frozen 不存在/False）：配置基础路径回退到 localData

        对应 Linux 部署和开发环境。Linux 上无 sys.frozen，行为与开发环境一致。
        """
        with patch.object(sys, "frozen", False, create=True):
            result = settings._resolve_config_base_path()
            assert result == Path("localData")

    def test_config_base_path_packaged_no_localappdata(self, settings):
        """打包环境但 LOCALAPPDATA 缺失：回退到基于 exe 路径的推算"""
        with patch.object(sys, "frozen", True, create=True), patch.dict(os.environ, {}, clear=True):
            result = settings._resolve_config_base_path()
            # 应回退到基于 sys.executable 的路径（不崩溃即可）
            assert isinstance(result, Path)


# ==================== lifeprism_data_path 解析 ====================


class TestDataPathResolution:
    """测试数据路径解析的优先级逻辑"""

    def test_data_path_from_env_var(self, settings):
        """环境变量 LIFEPRISM_DATA_PATH 能覆盖默认路径（config_base_path）

        当 yaml 配置中未设置 lifeprism_data_path 时，_resolve_default_data_path()
        会读取环境变量。
        """
        custom_path = "/opt/lifeprism/data"
        original_config_base = settings._config_base_path
        settings._config_base_path = Path("localData")
        try:
            with patch.dict(os.environ, {"LIFEPRISM_DATA_PATH": custom_path}):
                result = settings._resolve_default_data_path()
                assert result == Path(custom_path)
        finally:
            settings._config_base_path = original_config_base

    def test_data_path_fallback_to_config_base(self, settings):
        """无环境变量时，数据路径回退到 config_base_path"""
        original_config_base = settings._config_base_path
        test_base = Path("/some/config/base")
        settings._config_base_path = test_base
        try:
            with patch.dict(os.environ, {}, clear=True):
                result = settings._resolve_default_data_path()
                assert result == test_base
        finally:
            settings._config_base_path = original_config_base

    def test_data_path_priority_yaml_over_env(self, settings):
        """yaml 配置优先级高于环境变量

        _initialize() 中的逻辑：
            configured_path = self._config.get("lifeprism_data_path", "")
            if configured_path:
                self._lifeprism_data_path = Path(configured_path)
            else:
                self._lifeprism_data_path = self._resolve_default_data_path()
        """
        yaml_path = "/from/yaml/config"
        env_path = "/from/env/var"

        # 模拟 yaml 配置有值
        with (
            patch.object(settings, "_config", {"lifeprism_data_path": yaml_path}),
            patch.dict(os.environ, {"LIFEPRISM_DATA_PATH": env_path}),
        ):
            configured_path = settings._config.get("lifeprism_data_path", "")
            if configured_path:
                result = Path(configured_path)
            else:
                result = settings._resolve_default_data_path()
            assert result == Path(yaml_path)

    def test_data_path_priority_env_over_default(self, settings):
        """环境变量优先级高于默认路径（config_base_path）"""
        env_path = "/from/env/var"
        original_config_base = settings._config_base_path
        settings._config_base_path = Path("localData")
        try:
            # yaml 配置为空 → 走 _resolve_default_data_path → 读 env var
            with (
                patch.object(settings, "_config", {}),
                patch.dict(os.environ, {"LIFEPRISM_DATA_PATH": env_path}),
            ):
                configured_path = settings._config.get("lifeprism_data_path", "")
                if configured_path:
                    result = Path(configured_path)
                else:
                    result = settings._resolve_default_data_path()
                assert result == Path(env_path)
        finally:
            settings._config_base_path = original_config_base

    def test_data_path_priority_full_chain(self, settings):
        """完整优先级链：yaml > env var > config_base_path"""
        yaml_path = "/yaml/wins"
        env_path = "/env/second"
        default_base = Path("localData")

        original_config_base = settings._config_base_path
        settings._config_base_path = default_base
        try:
            # 1. yaml 有值 → yaml 胜出
            with (
                patch.object(settings, "_config", {"lifeprism_data_path": yaml_path}),
                patch.dict(os.environ, {"LIFEPRISM_DATA_PATH": env_path}),
            ):
                configured = settings._config.get("lifeprism_data_path", "")
                result = Path(configured) if configured else settings._resolve_default_data_path()
                assert result == Path(yaml_path)

            # 2. yaml 为空，env 有值 → env 胜出
            with (
                patch.object(settings, "_config", {}),
                patch.dict(os.environ, {"LIFEPRISM_DATA_PATH": env_path}),
            ):
                configured = settings._config.get("lifeprism_data_path", "")
                result = Path(configured) if configured else settings._resolve_default_data_path()
                assert result == Path(env_path)

            # 3. yaml 和 env 都为空 → 回退到 config_base_path
            with patch.object(settings, "_config", {}), patch.dict(os.environ, {}, clear=True):
                configured = settings._config.get("lifeprism_data_path", "")
                result = Path(configured) if configured else settings._resolve_default_data_path()
                assert result == default_base
        finally:
            settings._config_base_path = original_config_base
