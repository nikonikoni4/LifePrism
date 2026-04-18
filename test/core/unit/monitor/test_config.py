import pytest
from lifeprism.config.settings_manager import SettingsManager


@pytest.mark.core
def test_monitor_screenshot_settings_defaults():
    defaults = SettingsManager.DEFAULTS

    assert defaults["scheduled_screenshot_interval_seconds"] == 60
    assert defaults["active_screenshot_frequency_level"] == 2
    assert defaults["keyboard_keepalive_seconds"] == 12
    assert defaults["mouse_keepalive_seconds"] == 6
    assert defaults["enter_screenshot_delay_ms"] == 700
    assert defaults["screenshot_retention_days"] == 3
    assert defaults["cleanup_check_interval_seconds"] == 86400
