"""
run_mode 配置单元测试

验证 settings.run_mode 的读取逻辑：
1. 默认值为 "full"（_runtime_config 未注入时）
2. set_runtime_config 注入后返回注入值
3. _runtime_config 被 patch 时返回 patch 值
"""

from unittest.mock import patch

import pytest

from lifeprism.config.settings_manager import settings

pytestmark = pytest.mark.core


class TestRunModeConfig:
    """测试 run_mode 配置读取"""

    def test_run_mode_default_is_full(self):
        """_runtime_config 为空时默认返回 full"""
        with patch.object(settings, "_runtime_config", {}):
            assert settings.run_mode == "full"

    def test_run_mode_from_runtime_config_web_demo(self):
        """_runtime_config 注入 web_demo 时返回 web_demo"""
        with patch.object(settings, "_runtime_config", {"run_mode": "web_demo"}):
            assert settings.run_mode == "web_demo"

    def test_run_mode_from_runtime_config_agent_only(self):
        """_runtime_config 注入 agent_only 时返回 agent_only"""
        with patch.object(settings, "_runtime_config", {"run_mode": "agent_only"}):
            assert settings.run_mode == "agent_only"

    def test_run_mode_from_set_runtime_config(self):
        """set_runtime_config() 方法注入后能正确读取"""
        with patch.object(settings, "_runtime_config", {}):
            settings.set_runtime_config("run_mode", "web_demo")
            assert settings.run_mode == "web_demo"

    def test_run_mode_full_explicit(self):
        """_runtime_config 显式注入 full 时返回 full"""
        with patch.object(settings, "_runtime_config", {"run_mode": "full"}):
            assert settings.run_mode == "full"
