"""测试 s004 配置迁移"""
from lifeprism.config.migrations.scripts import s004_add_monitor_config


def test_check_if_applied_both_fields_exist():
    """测试两个字段都存在时，迁移已应用"""
    data = {
        'active_screenshot_frequency_level': 2,
        'screenshot_retention_days': 7,
    }
    assert s004_add_monitor_config.check_if_applied(data) is True


def test_check_if_applied_missing_fields():
    """测试缺少字段时，迁移未应用"""
    assert s004_add_monitor_config.check_if_applied({}) is False
    assert s004_add_monitor_config.check_if_applied({'active_screenshot_frequency_level': 2}) is False
    assert s004_add_monitor_config.check_if_applied({'screenshot_retention_days': 7}) is False


def test_upgrade_adds_missing_fields():
    """测试迁移添加缺失字段"""
    data = {}
    result = s004_add_monitor_config.upgrade(data)

    assert result['active_screenshot_frequency_level'] == 2
    assert result['screenshot_retention_days'] == 7


def test_upgrade_preserves_existing_fields():
    """测试迁移保留已存在的字段"""
    data = {
        'active_screenshot_frequency_level': 1,
        'screenshot_retention_days': 10,
        'other_field': 'value',
    }
    result = s004_add_monitor_config.upgrade(data)

    assert result['active_screenshot_frequency_level'] == 1
    assert result['screenshot_retention_days'] == 10
    assert result['other_field'] == 'value'
