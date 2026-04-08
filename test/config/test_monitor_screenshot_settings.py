from lifeprism.config.settings_manager import SettingsManager
from lifeprism.server.schemas.setting_schemas import UpdateSettingsRequest
from lifeprism.server.services.setting_service import _DATA_SUBDIRS
from lifeprism.server.services.setting_service import get_settings


def test_settings_manager_default_screenshot_settings():
    defaults = SettingsManager.DEFAULTS
    expected_values = {
        "scheduled_screenshot_interval_seconds": 60,
        "active_screenshot_frequency_level": 2,
        "keyboard_keepalive_seconds": 12,
        "mouse_keepalive_seconds": 6,
        "enter_screenshot_delay_ms": 700,
        "screenshot_retention_days": 3,
        "cleanup_check_interval_seconds": 86400,
    }
    for key, expected in expected_values.items():
        assert defaults.get(key) == expected, f"{key} 默认值不正确"


def test_setting_service_data_subdirs_include_screenshots():
    assert "screenshots" in _DATA_SUBDIRS, "setting_service._DATA_SUBDIRS 缺少 screenshots 子目录"


def test_get_settings_exposes_screenshot_config_fields():
    settings_view = get_settings()

    assert settings_view.scheduled_screenshot_interval_seconds == 60
    assert settings_view.active_screenshot_frequency_level == 2
    assert settings_view.keyboard_keepalive_seconds == 12
    assert settings_view.mouse_keepalive_seconds == 6
    assert settings_view.enter_screenshot_delay_ms == 700
    assert settings_view.screenshot_retention_days == 3
    assert settings_view.cleanup_check_interval_seconds == 86400


def test_update_settings_request_accepts_screenshot_config_fields():
    request = UpdateSettingsRequest(
        scheduled_screenshot_interval_seconds=120,
        active_screenshot_frequency_level=3,
        keyboard_keepalive_seconds=15,
        mouse_keepalive_seconds=7,
        enter_screenshot_delay_ms=900,
        screenshot_retention_days=5,
        cleanup_check_interval_seconds=43200,
    )

    dumped = request.model_dump(exclude_none=True)

    assert dumped["scheduled_screenshot_interval_seconds"] == 120
    assert dumped["active_screenshot_frequency_level"] == 3
    assert dumped["keyboard_keepalive_seconds"] == 15
    assert dumped["mouse_keepalive_seconds"] == 7
    assert dumped["enter_screenshot_delay_ms"] == 900
    assert dumped["screenshot_retention_days"] == 5
    assert dumped["cleanup_check_interval_seconds"] == 43200
