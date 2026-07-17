"""测试配置验证逻辑"""

import pytest

from lifeprism.config.settings_manager import SettingsManager


def test_screenshot_retention_days_validation():
    """测试截图保留天数验证"""
    settings = SettingsManager()

    # 测试小于3天应该报错
    with pytest.raises(ValueError, match="截图保留天数不能小于3天"):
        settings.update({"screenshot_retention_days": 2})

    # 测试等于3天应该通过
    settings.update({"screenshot_retention_days": 3})
    assert settings.get("screenshot_retention_days") == 3

    # 测试大于3天应该通过
    settings.update({"screenshot_retention_days": 7})
    assert settings.get("screenshot_retention_days") == 7


def test_frequency_level_validation():
    """测试频率等级验证"""
    settings = SettingsManager()

    # 测试无效等级应该报错
    with pytest.raises(ValueError, match="频率等级必须是1、2或3"):
        settings.update({"active_screenshot_frequency_level": 0})

    with pytest.raises(ValueError, match="频率等级必须是1、2或3"):
        settings.update({"active_screenshot_frequency_level": 4})

    # 测试有效等级应该通过
    for level in [1, 2, 3]:
        settings.update({"active_screenshot_frequency_level": level})
        assert settings.get("active_screenshot_frequency_level") == level
