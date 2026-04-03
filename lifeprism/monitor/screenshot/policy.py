from lifeprism.monitor.screenshot.models import FrequencyPolicy

# ==================== 固定业务规则：截图频率策略参数 ====================
# 这些参数是精心设计的业务规则，不应通过配置文件修改
# 用户只能通过 settings.active_screenshot_frequency_level (1/2/3) 选择策略级别
#
# 参数说明：
# - level: 策略等级（1=低频 2=中频 3=高频）
# - first_active_after_seconds: 用户开始活动后，首次截图的延迟时间（秒）
# - repeat_active_every_seconds: 持续活动期间，重复截图的间隔时间（秒）
# - enter_cooldown_seconds: 按下 Enter 键后的冷却时间（秒），避免连续截图
# ========================================================================
_POLICIES = {
    1: FrequencyPolicy(
        level=1,
        first_active_after_seconds=45,  # 首次活动后 45 秒截图
        repeat_active_every_seconds=90,  # 持续活动每 90 秒截图
        enter_cooldown_seconds=8,  # Enter 键冷却 8 秒
    ),
    2: FrequencyPolicy(
        level=2,
        first_active_after_seconds=30,  # 首次活动后 30 秒截图
        repeat_active_every_seconds=60,  # 持续活动每 60 秒截图
        enter_cooldown_seconds=6,  # Enter 键冷却 6 秒
    ),
    3: FrequencyPolicy(
        level=3,
        first_active_after_seconds=20,  # 首次活动后 20 秒截图
        repeat_active_every_seconds=40,  # 持续活动每 40 秒截图
        enter_cooldown_seconds=4,  # Enter 键冷却 4 秒
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
