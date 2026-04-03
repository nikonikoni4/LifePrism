from lifeprism.monitor.screenshot.models import FrequencyPolicy

_POLICIES = {
    1: FrequencyPolicy(
        level=1,
        first_active_after_seconds=45,
        repeat_active_every_seconds=90,
        enter_cooldown_seconds=8,
    ),
    2: FrequencyPolicy(
        level=2,
        first_active_after_seconds=30,
        repeat_active_every_seconds=60,
        enter_cooldown_seconds=6,
    ),
    3: FrequencyPolicy(
        level=3,
        first_active_after_seconds=20,
        repeat_active_every_seconds=40,
        enter_cooldown_seconds=4,
    ),
}


def get_frequency_policy(level: int) -> FrequencyPolicy:
    if type(level) is not int:
        raise ValueError(f"invalid active_screenshot_frequency_level: {level}")
    try:
        return _POLICIES[level]
    except KeyError as exc:
        raise ValueError(
            f"invalid active_screenshot_frequency_level: {level}"
        ) from exc
