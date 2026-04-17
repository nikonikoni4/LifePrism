from __future__ import annotations

from typing import Any


def _determine_coverage_level(has_data: bool, item_count: int) -> str:
    """根据数据存在性和数量判断覆盖等级。

    Args:
        has_data: 是否有数据
        item_count: 数据项数量

    Returns:
        str: 覆盖等级，可能值为 "none", "low", "medium", "high"
    """
    if not has_data or item_count == 0:
        return "none"
    if item_count < 3:
        return "low"
    if item_count < 10:
        return "medium"
    return "high"


def build_coverage_context(
    activity_logs: list[dict[str, Any]],
    todos: list[dict[str, Any]],
    habits: list[dict[str, Any]],
    habit_checkins: list[dict[str, Any]],
    custom_blocks: list[dict[str, Any]],
    diaries: list[dict[str, Any]],
    mood_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """构建数据覆盖度上下文，评估各维度数据的完整性和质量。

    分析各类数据源的存在性和数量，计算活动、执行、主观输入三个维度的覆盖等级，
    并生成总体覆盖等级和限制项列表，用于 AI 总结时判断数据可信度。

    Args:
        activity_logs: 活动日志列表
        todos: 待办事项列表
        habits: 习惯列表
        habit_checkins: 习惯打卡记录列表
        custom_blocks: 自定义时间块列表
        diaries: 日记列表
        mood_entries: 心情记录列表

    Returns:
        dict: 包含以下键的字典：
            - has_*: 各类数据的存在性标志（布尔值）
            - *_coverage_level: 各维度覆盖等级（"none", "low", "medium", "high"）
            - overall_coverage_level: 总体覆盖等级
            - limitations: 限制项列表，说明缺失的数据类型及影响
    """

    has_activity_data = len(activity_logs) > 0
    has_todo_data = len(todos) > 0
    has_goal_data = False  # 第一阶段不作为主证据
    has_habit_data = len(habits) > 0
    has_custom_blocks = len(custom_blocks) > 0
    has_diary = len(diaries) > 0
    has_diary_ai_summary = any(d.get("ai_summary") for d in diaries)
    has_mood = len(mood_entries) > 0
    has_screenshot_data = False  # 第一阶段不支持

    # 计算各维度覆盖等级
    activity_coverage_level = _determine_coverage_level(has_activity_data, len(activity_logs))

    execution_item_count = len(todos) + len(habit_checkins)
    execution_coverage_level = _determine_coverage_level(
        has_todo_data or has_habit_data,
        execution_item_count
    )

    authored_item_count = len(custom_blocks) + len(diaries) + len(mood_entries)
    authored_coverage_level = _determine_coverage_level(
        has_custom_blocks or has_diary or has_mood,
        authored_item_count
    )

    # 计算总体覆盖等级
    coverage_scores = {
        "none": 0,
        "low": 1,
        "medium": 2,
        "high": 3,
    }

    avg_score = (
        coverage_scores[activity_coverage_level] * 0.5 +
        coverage_scores[execution_coverage_level] * 0.3 +
        coverage_scores[authored_coverage_level] * 0.2
    )

    if avg_score >= 2.5:
        overall_coverage_level = "high"
    elif avg_score >= 1.5:
        overall_coverage_level = "medium"
    elif avg_score >= 0.5:
        overall_coverage_level = "low"
    else:
        overall_coverage_level = "none"

    # 构建限制项列表
    limitations: list[dict[str, str]] = []

    if not has_custom_blocks:
        limitations.append({
            "code": "missing_custom_blocks",
            "message": "缺少 timeline custom block，无法准确确认部分时间段的具体任务内容"
        })

    if not has_diary:
        limitations.append({
            "code": "missing_diary",
            "message": "缺少日记记录，无法获取用户主观记录的重点事项"
        })

    if not has_mood:
        limitations.append({
            "code": "missing_mood",
            "message": "缺少心情记录，无法结合主观状态解释行为变化"
        })

    if not has_activity_data:
        limitations.append({
            "code": "missing_activity_data",
            "message": "缺少活动数据，无法分析电脑使用模式"
        })

    if not has_todo_data and not has_habit_data:
        limitations.append({
            "code": "missing_execution_data",
            "message": "缺少 todo 和 habit 数据，无法分析执行情况"
        })

    return {
        "has_activity_data": has_activity_data,
        "has_todo_data": has_todo_data,
        "has_goal_data": has_goal_data,
        "has_habit_data": has_habit_data,
        "has_custom_blocks": has_custom_blocks,
        "has_diary": has_diary,
        "has_diary_ai_summary": has_diary_ai_summary,
        "has_mood": has_mood,
        "has_screenshot_data": has_screenshot_data,
        "activity_coverage_level": activity_coverage_level,
        "execution_coverage_level": execution_coverage_level,
        "authored_coverage_level": authored_coverage_level,
        "overall_coverage_level": overall_coverage_level,
        "limitations": limitations,
    }
