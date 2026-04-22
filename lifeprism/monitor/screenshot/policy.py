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
#
# 2026-04-21 更新：基于测试数据优化频率参数
# - 测试发现：稀释50%截图后语义质量无明显下降
# - 数据分析：62%的segment只有1张截图
# - 优化策略：降低第一张阈值（捕获短暂片段），提高后续间隔和Enter冷却（减少冗余）
# - 预期效果：减少60%截图，token从34万降至13-15万
# ========================================================================
_POLICIES = {
    1: FrequencyPolicy(
        level=1,
        first_active_after_seconds=60,  # 首次活动后 60 秒截图
        repeat_active_every_seconds=240,  # 持续活动每 240 秒（4分钟）截图
        enter_cooldown_seconds=120,  # Enter 键冷却 120 秒（2分钟）
    ),
    2: FrequencyPolicy(
        level=2,
        first_active_after_seconds=45,  # 首次活动后 45 秒截图
        repeat_active_every_seconds=180,  # 持续活动每 180 秒（3分钟）截图
        enter_cooldown_seconds=90,  # Enter 键冷却 90 秒（1.5分钟）
    ),
    3: FrequencyPolicy(
        level=3,
        first_active_after_seconds=30,  # 首次活动后 30 秒截图
        repeat_active_every_seconds=120,  # 持续活动每 120 秒（2分钟）截图
        enter_cooldown_seconds=60,  # Enter 键冷却 60 秒（1分钟）
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
