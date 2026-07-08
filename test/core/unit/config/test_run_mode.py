"""
run_mode 配置单元测试

验证 settings.run_mode 的读取逻辑：
1. 默认值为 "full"
2. 环境变量 LIFEPRISM_RUN_MODE 优先于配置文件值
3. 环境变量未设置时回退到配置文件值
4. 环境变量和配置文件都未设置时回退到默认值 "full"
"""

import os
from unittest.mock import patch

import pytest

from lifeprism.config.settings_manager import settings

pytestmark = pytest.mark.core


class TestRunModeConfig:
    """测试 run_mode 配置读取"""

    def test_run_mode_default_is_full(self):
        """默认 run_mode 为 full"""
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(settings, "_config", {}):
                assert settings.run_mode == "full"

    def test_run_mode_from_env_var(self):
        """环境变量 LIFEPRISM_RUN_MODE 优先于配置文件"""
        with patch.dict(os.environ, {"LIFEPRISM_RUN_MODE": "web_demo"}):
            with patch.object(settings, "_config", {"run_mode": "agent_only"}):
                assert settings.run_mode == "web_demo"

    def test_run_mode_from_config_when_env_not_set(self):
        """环境变量未设置时，回退到配置文件值"""
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(settings, "_config", {"run_mode": "agent_only"}):
                assert settings.run_mode == "agent_only"

    def test_run_mode_env_overrides_default(self):
        """环境变量覆盖默认值"""
        with patch.dict(os.environ, {"LIFEPRISM_RUN_MODE": "web_demo"}):
            with patch.object(settings, "_config", {}):
                assert settings.run_mode == "web_demo"

    def test_run_mode_agent_only_from_env(self):
        """环境变量设置为 agent_only"""
        with patch.dict(os.environ, {"LIFEPRISM_RUN_MODE": "agent_only"}):
            with patch.object(settings, "_config", {}):
                assert settings.run_mode == "agent_only"
