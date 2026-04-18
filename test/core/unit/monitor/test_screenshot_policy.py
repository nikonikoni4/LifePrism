import pytest

from lifeprism.monitor.screenshot import CaptureReason, get_frequency_policy


@pytest.mark.core
def test_get_frequency_policy_level_2():
    policy = get_frequency_policy(2)
    assert policy.first_active_after_seconds == 30
    assert policy.repeat_active_every_seconds == 60
    assert policy.enter_cooldown_seconds == 6


@pytest.mark.core
@pytest.mark.parametrize("invalid_level", [0, 4, -1, 999, 1.0, True, False])
def test_get_frequency_policy_invalid_level_raise_value_error(invalid_level):
    with pytest.raises(ValueError, match="active_screenshot_frequency_level"):
        get_frequency_policy(invalid_level)


@pytest.mark.core
def test_capture_reason_values_exactly_expected():
    assert {reason.value for reason in CaptureReason} == {
        "scheduled",
        "active",
        "enter",
    }
