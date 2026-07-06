from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from lifeprism.llm.schemas.summary_context_schemas import SummaryContext
from lifeprism.llm.summary_context.builder import build_summary_context
from lifeprism.llm.summary_context.service import (
    get_daily_summary_context,
    get_monthly_summary_context,
    get_weekly_summary_context,
)


def get_summary_context(
    summary_type: Literal["daily", "weekly", "monthly"],
    target_date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    timezone: str = "Asia/Hong_Kong",
) -> SummaryContext:
    """
    获取总结上下文的统一入口

    Args:
        summary_type: 总结类型 (daily/weekly/monthly)
        target_date: 目标日期 (用于 daily，格式: YYYY-MM-DD)
        start_date: 开始日期 (用于 weekly/monthly，格式: YYYY-MM-DD)
        end_date: 结束日期 (用于 weekly/monthly，格式: YYYY-MM-DD)
        timezone: 时区 (默认: Asia/Hong_Kong)

    Returns:
        SummaryContext: 结构化的总结上下文

    Examples:
        # 日报
        get_summary_context("daily", target_date="2026-04-04")

        # 周报
        get_summary_context("weekly", start_date="2026-03-31", end_date="2026-04-06")

        # 月报
        get_summary_context("monthly", start_date="2026-03-01", end_date="2026-03-31")
    """

    if summary_type == "daily":
        if not target_date:
            target_date = date.today().isoformat()
        raw_context = get_daily_summary_context(target_date, timezone)

    elif summary_type == "weekly":
        if not start_date or not end_date:
            # 默认取本周（周一到周日）
            today = date.today()
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            start_date = start_of_week.isoformat()
            end_date = end_of_week.isoformat()
        raw_context = get_weekly_summary_context(start_date, end_date, timezone)

    elif summary_type == "monthly":
        if not start_date or not end_date:
            # 默认取本月
            today = date.today()
            start_of_month = today.replace(day=1)
            next_month = (
                start_of_month.replace(month=start_of_month.month + 1)
                if start_of_month.month < 12
                else start_of_month.replace(year=start_of_month.year + 1, month=1)
            )
            end_of_month = next_month - timedelta(days=1)
            start_date = start_of_month.isoformat()
            end_date = end_of_month.isoformat()
        raw_context = get_monthly_summary_context(start_date, end_date, timezone)

    else:
        raise ValueError(f"Invalid summary_type: {summary_type}")

    return build_summary_context(raw_context)


# Tool 定义（用于 Claude Agent SDK）
SUMMARY_TOOLS = [
    {
        "name": "get_daily_summary",
        "description": "获取指定日期的日报总结上下文，包括活动数据、执行情况、用户记录等结构化信息",
        "input_schema": {
            "type": "object",
            "properties": {
                "target_date": {
                    "type": "string",
                    "description": "目标日期，格式: YYYY-MM-DD，例如: 2026-04-04。不传则默认为今天",
                },
                "timezone": {
                    "type": "string",
                    "description": "时区，默认: Asia/Hong_Kong",
                    "default": "Asia/Hong_Kong",
                },
            },
        },
    },
    {
        "name": "get_weekly_summary",
        "description": "获取指定日期范围的周报总结上下文，包括一周内的活动模式、执行情况等",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "开始日期，格式: YYYY-MM-DD。不传则默认为本周一",
                },
                "end_date": {
                    "type": "string",
                    "description": "结束日期，格式: YYYY-MM-DD。不传则默认为本周日",
                },
                "timezone": {
                    "type": "string",
                    "description": "时区，默认: Asia/Hong_Kong",
                    "default": "Asia/Hong_Kong",
                },
            },
        },
    },
    {
        "name": "get_monthly_summary",
        "description": "获取指定月份的月报总结上下文，包括整月的活动趋势、执行情况等",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "开始日期（月初），格式: YYYY-MM-DD。不传则默认为本月1日",
                },
                "end_date": {
                    "type": "string",
                    "description": "结束日期（月末），格式: YYYY-MM-DD。不传则默认为本月最后一天",
                },
                "timezone": {
                    "type": "string",
                    "description": "时区，默认: Asia/Hong_Kong",
                    "default": "Asia/Hong_Kong",
                },
            },
        },
    },
]


def execute_tool(tool_name: str, tool_input: dict) -> dict:
    """
    执行 tool 调用

    Args:
        tool_name: 工具名称
        tool_input: 工具输入参数

    Returns:
        dict: 工具执行结果（SummaryContext 的字典形式）
    """

    if tool_name == "get_daily_summary":
        context = get_summary_context(
            summary_type="daily",
            target_date=tool_input.get("target_date"),
            timezone=tool_input.get("timezone", "Asia/Hong_Kong"),
        )
    elif tool_name == "get_weekly_summary":
        context = get_summary_context(
            summary_type="weekly",
            start_date=tool_input.get("start_date"),
            end_date=tool_input.get("end_date"),
            timezone=tool_input.get("timezone", "Asia/Hong_Kong"),
        )
    elif tool_name == "get_monthly_summary":
        context = get_summary_context(
            summary_type="monthly",
            start_date=tool_input.get("start_date"),
            end_date=tool_input.get("end_date"),
            timezone=tool_input.get("timezone", "Asia/Hong_Kong"),
        )
    else:
        raise ValueError(f"Unknown tool: {tool_name}")

    return context.model_dump()
