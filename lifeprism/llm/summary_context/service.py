from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from lifeprism.llm.providers.summary_read_provider import summary_read_provider
from lifeprism.llm.summary_context.aggregators.activity_aggregator import build_activity_context
from lifeprism.llm.summary_context.aggregators.authored_aggregator import build_authored_context
from lifeprism.llm.summary_context.aggregators.coverage_aggregator import build_coverage_context
from lifeprism.llm.summary_context.aggregators.execution_aggregator import build_execution_context


DAY_WINDOW_START_HOUR = 4


def _compute_day_window(target_date: str, timezone: str = "Asia/Hong_Kong") -> tuple[str, str]:
    """计算单日分析窗口 (4:00 - 次日 4:00)。

    使用 4:00 作为一天的起点，避免凌晨睡眠时间被切分到两天。

    Args:
        target_date: 目标日期（ISO 格式，如 "2026-04-04"）
        timezone: 时区（暂未使用，预留参数）

    Returns:
        tuple[str, str]: (开始时间, 结束时间)，均为 ISO 格式
    """
    base_date = datetime.fromisoformat(target_date)
    start_dt = base_date.replace(hour=DAY_WINDOW_START_HOUR, minute=0, second=0, microsecond=0)
    end_dt = start_dt + timedelta(days=1)
    return start_dt.isoformat(), end_dt.isoformat()


def _build_uncertainty_context(coverage: dict[str, Any]) -> dict[str, Any]:
    """根据覆盖度构建不确定性上下文，提示 AI 总结时注意数据局限性。

    Args:
        coverage: 覆盖度上下文字典

    Returns:
        dict: 包含以下键的字典：
            - confidence_level: 置信度等级（"low", "medium", "high"）
            - visible_messages: 可见的限制说明列表
            - inference_warnings: 推理警告列表
    """
    overall_level = coverage["overall_coverage_level"]

    confidence_map = {
        "none": "low",
        "low": "low",
        "medium": "medium",
        "high": "high",
    }

    visible_messages = [item["message"] for item in coverage["limitations"]]

    inference_warnings = []
    if not coverage["has_custom_blocks"]:
        inference_warnings.append(
            "关于电脑使用节奏的结论基于活动密度分段，而非真实睡眠或作息数据。"
        )

    return {
        "confidence_level": confidence_map[overall_level],
        "visible_messages": visible_messages,
        "inference_warnings": inference_warnings,
    }


def get_daily_summary_context(target_date: str, timezone: str = "Asia/Hong_Kong") -> dict[str, Any]:
    """获取日报总结上下文。

    读取指定日期的所有相关数据（活动、待办、习惯、日记、心情等），
    聚合为结构化的总结上下文，供 AI 生成日报使用。

    Args:
        target_date: 目标日期（ISO 格式，如 "2026-04-04"）
        timezone: 时区（默认 "Asia/Hong_Kong"）

    Returns:
        dict: 包含以下键的字典：
            - summary_type: "daily"
            - range: 时间范围信息
            - coverage: 数据覆盖度上下文
            - activity: 活动上下文
            - execution: 执行上下文
            - authored: 主观输入上下文
            - uncertainty: 不确定性上下文
    """

    # 计算时间窗口
    start_time, end_time = _compute_day_window(target_date, timezone)
    start_date = target_date
    end_date = target_date

    # 读取数据
    activity_logs = summary_read_provider.get_activity_logs_by_range(start_time, end_time)
    todos = summary_read_provider.get_todos_by_range(start_date, end_date)
    habits = summary_read_provider.get_habits()
    habit_checkins = summary_read_provider.get_habit_checkins_by_range(start_date, end_date)
    custom_blocks = summary_read_provider.get_custom_blocks_by_range(start_date, end_date)
    diaries = summary_read_provider.get_diaries_by_range(start_date, end_date)
    mood_entries = summary_read_provider.get_mood_entries_by_range(start_date, end_date)

    # 聚合数据
    coverage = build_coverage_context(
        activity_logs=activity_logs,
        todos=todos,
        habits=habits,
        habit_checkins=habit_checkins,
        custom_blocks=custom_blocks,
        diaries=diaries,
        mood_entries=mood_entries,
    )

    activity = build_activity_context(
        logs=activity_logs,
        range_start=start_time,
        range_end=end_time,
    )

    execution = build_execution_context(
        todos=todos,
        habits=habits,
        habit_checkins=habit_checkins,
        start_date=start_date,
        end_date=end_date,
    )

    authored = build_authored_context(
        custom_blocks=custom_blocks,
        diaries=diaries,
        mood_entries=mood_entries,
    )

    uncertainty = _build_uncertainty_context(coverage)

    return {
        "summary_type": "daily",
        "range": {
            "start": start_time,
            "end": end_time,
            "timezone": timezone,
            "day_window_mode": "4_to_4",
        },
        "coverage": coverage,
        "activity": activity,
        "execution": execution,
        "authored": authored,
        "uncertainty": uncertainty,
    }


def get_weekly_summary_context(start_date: str, end_date: str, timezone: str = "Asia/Hong_Kong") -> dict[str, Any]:
    """获取周报总结上下文。

    读取指定日期范围内的所有相关数据，聚合为结构化的总结上下文，供 AI 生成周报使用。

    Args:
        start_date: 开始日期（ISO 格式，如 "2026-03-31"）
        end_date: 结束日期（ISO 格式，如 "2026-04-06"）
        timezone: 时区（默认 "Asia/Hong_Kong"）

    Returns:
        dict: 包含以下键的字典：
            - summary_type: "weekly"
            - range: 时间范围信息
            - coverage: 数据覆盖度上下文
            - activity: 活动上下文
            - execution: 执行上下文
            - authored: 主观输入上下文
            - uncertainty: 不确定性上下文
    """

    # 计算时间窗口（周报使用第一天的 4:00 到最后一天的次日 4:00）
    start_dt = datetime.fromisoformat(start_date).replace(
        hour=DAY_WINDOW_START_HOUR, minute=0, second=0, microsecond=0
    )
    end_dt = datetime.fromisoformat(end_date).replace(
        hour=DAY_WINDOW_START_HOUR, minute=0, second=0, microsecond=0
    ) + timedelta(days=1)

    start_time = start_dt.isoformat()
    end_time = end_dt.isoformat()

    # 读取数据
    activity_logs = summary_read_provider.get_activity_logs_by_range(start_time, end_time)
    todos = summary_read_provider.get_todos_by_range(start_date, end_date)
    habits = summary_read_provider.get_habits()
    habit_checkins = summary_read_provider.get_habit_checkins_by_range(start_date, end_date)
    custom_blocks = summary_read_provider.get_custom_blocks_by_range(start_date, end_date)
    diaries = summary_read_provider.get_diaries_by_range(start_date, end_date)
    mood_entries = summary_read_provider.get_mood_entries_by_range(start_date, end_date)

    # 聚合数据
    coverage = build_coverage_context(
        activity_logs=activity_logs,
        todos=todos,
        habits=habits,
        habit_checkins=habit_checkins,
        custom_blocks=custom_blocks,
        diaries=diaries,
        mood_entries=mood_entries,
    )

    activity = build_activity_context(
        logs=activity_logs,
        range_start=start_time,
        range_end=end_time,
    )

    execution = build_execution_context(
        todos=todos,
        habits=habits,
        habit_checkins=habit_checkins,
        start_date=start_date,
        end_date=end_date,
    )

    authored = build_authored_context(
        custom_blocks=custom_blocks,
        diaries=diaries,
        mood_entries=mood_entries,
    )

    uncertainty = _build_uncertainty_context(coverage)

    return {
        "summary_type": "weekly",
        "range": {
            "start": start_time,
            "end": end_time,
            "timezone": timezone,
            "day_window_mode": "4_to_4",
        },
        "coverage": coverage,
        "activity": activity,
        "execution": execution,
        "authored": authored,
        "uncertainty": uncertainty,
    }


def get_monthly_summary_context(start_date: str, end_date: str, timezone: str = "Asia/Hong_Kong") -> dict[str, Any]:
    """获取月报总结上下文。

    读取指定月份的所有相关数据，聚合为结构化的总结上下文，供 AI 生成月报使用。

    Args:
        start_date: 开始日期（通常为月初，ISO 格式，如 "2026-03-01"）
        end_date: 结束日期（通常为月末，ISO 格式，如 "2026-03-31"）
        timezone: 时区（默认 "Asia/Hong_Kong"）

    Returns:
        dict: 包含以下键的字典：
            - summary_type: "monthly"
            - range: 时间范围信息
            - coverage: 数据覆盖度上下文
            - activity: 活动上下文
            - execution: 执行上下文
            - authored: 主观输入上下文
            - uncertainty: 不确定性上下文
    """

    # 计算时间窗口
    start_dt = datetime.fromisoformat(start_date).replace(
        hour=DAY_WINDOW_START_HOUR, minute=0, second=0, microsecond=0
    )
    end_dt = datetime.fromisoformat(end_date).replace(
        hour=DAY_WINDOW_START_HOUR, minute=0, second=0, microsecond=0
    ) + timedelta(days=1)

    start_time = start_dt.isoformat()
    end_time = end_dt.isoformat()

    # 读取数据
    activity_logs = summary_read_provider.get_activity_logs_by_range(start_time, end_time)
    todos = summary_read_provider.get_todos_by_range(start_date, end_date)
    habits = summary_read_provider.get_habits()
    habit_checkins = summary_read_provider.get_habit_checkins_by_range(start_date, end_date)
    custom_blocks = summary_read_provider.get_custom_blocks_by_range(start_date, end_date)
    diaries = summary_read_provider.get_diaries_by_range(start_date, end_date)
    mood_entries = summary_read_provider.get_mood_entries_by_range(start_date, end_date)

    # 聚合数据
    coverage = build_coverage_context(
        activity_logs=activity_logs,
        todos=todos,
        habits=habits,
        habit_checkins=habit_checkins,
        custom_blocks=custom_blocks,
        diaries=diaries,
        mood_entries=mood_entries,
    )

    activity = build_activity_context(
        logs=activity_logs,
        range_start=start_time,
        range_end=end_time,
    )

    execution = build_execution_context(
        todos=todos,
        habits=habits,
        habit_checkins=habit_checkins,
        start_date=start_date,
        end_date=end_date,
    )

    authored = build_authored_context(
        custom_blocks=custom_blocks,
        diaries=diaries,
        mood_entries=mood_entries,
    )

    uncertainty = _build_uncertainty_context(coverage)

    return {
        "summary_type": "monthly",
        "range": {
            "start": start_time,
            "end": end_time,
            "timezone": timezone,
            "day_window_mode": "4_to_4",
        },
        "coverage": coverage,
        "activity": activity,
        "execution": execution,
        "authored": authored,
        "uncertainty": uncertainty,
    }
