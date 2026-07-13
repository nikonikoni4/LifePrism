"""时间处理工具函数 - UTC 时区迁移统一入口

核心原则：
- 时间戳字段（created_at、updated_at、finished_at、paused_at 等）使用 UTC
- 日期字段（date、start_date、end_date 等 YYYY-MM-DD 格式）保持用户本地时区日期
"""

from datetime import date, datetime, timezone

import pytz

from lifeprism.config import get_user_timezone


def get_local_today() -> date:
    """获取用户本地时区的今天日期

    用于"今天"/"昨天"等语义场景，确保用户在 UTC+ 时区午夜前后
    看到的日期与预期一致。

    Returns:
        date: 用户本地时区的今天日期对象
    """
    local_tz = pytz.timezone(get_user_timezone())
    return datetime.now(local_tz).date()


def get_utc_now_iso() -> str:
    """获取当前 UTC 时间的 ISO 8601 格式字符串

    用于所有时间戳字段（created_at、updated_at、finished_at、paused_at 等），
    返回带时区标识的 ISO 8601 字符串，确保 LWW 字符串比较正确。

    Returns:
        str: UTC ISO 8601 格式时间戳，如 "2026-07-11T16:29:54.123456+00:00"
    """
    return datetime.now(timezone.utc).isoformat()


def parse_iso_to_aware(iso_string: str) -> datetime:
    """将 ISO 8601 字符串解析为 aware datetime

    API 层接收到的时间参数可能是：
    - 带 UTC 时区标识: "2026-07-01T10:00:00+00:00"
    - 带 Z 后缀: "2026-07-01T10:00:00Z"
    - 不带时区（naive）: "2026-07-01T10:00:00"

    对于 naive 字符串，假设为 UTC 并补充时区信息（不转换时间值，仅补充 tzinfo）。
    这样可以确保所有解析后的 datetime 都是 aware，避免后续比较时出现
    "can't compare offset-naive and offset-aware datetimes" 错误。

    Args:
        iso_string: ISO 8601 格式的时间字符串

    Returns:
        datetime: 带时区信息的 datetime 对象（naive 输入会被假设为 UTC）
    """
    dt = datetime.fromisoformat(iso_string)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def local_to_utc_iso(local_str: str, format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """将本地时间字符串转换为 UTC ISO 8601 格式字符串

    偏移量由 get_user_timezone() 动态决定，用于定时任务构造本地时间后转 UTC 查库、
    Repository 层修复等场景。

    Args:
        local_str: 本地时间字符串（如 "2026-07-12 04:00:00"）
        format: 输入字符串的解析格式，默认 "%Y-%m-%d %H:%M:%S"

    Returns:
        str: UTC ISO 8601 格式字符串（如 "2026-07-11T20:00:00+00:00"）
    """
    tz = pytz.timezone(get_user_timezone())
    dt = datetime.strptime(local_str, format)
    try:
        dt = tz.localize(dt)
    except pytz.exceptions.NonExistentTimeError:
        # DST 夏令时跳变间隙（如 spring-forward 时 02:30 不存在），向前调整
        dt = tz.localize(dt, is_dst=False)
    except pytz.exceptions.AmbiguousTimeError:
        # DST 冬令时回退重叠（如 fall-back 时 01:30 出现两次），使用标准时间
        dt = tz.localize(dt, is_dst=False)
    return dt.astimezone(timezone.utc).isoformat()


def build_local_datetime(date_str: str, time_str: str = "00:00:00") -> str:
    """根据日期和时间构造本地时间字符串

    用于定时任务构造本地时间字符串（替代 f"{date} {time}" 硬拼接）。
    输出为面向 AI/用户的格式，无时区标识。

    Args:
        date_str: 日期字符串，格式 YYYY-MM-DD
        time_str: 时间字符串，格式 HH:MM:SS，默认 "00:00:00"

    Returns:
        str: 本地时间字符串 "YYYY-MM-DD HH:MM:SS"
    """
    combined = f"{date_str} {time_str}"
    datetime.strptime(combined, "%Y-%m-%d %H:%M:%S")
    return combined


def utc_to_local(utc_iso: str) -> datetime:
    """将 UTC ISO 8601 时间字符串转换为本地时区 datetime 对象

    用于需要进一步处理本地时间的场景（如提取小时、日期等）。

    Args:
        utc_iso: UTC ISO 8601 时间字符串（如 "2026-07-11T20:00:00+00:00"）

    Returns:
        datetime: 本地时区的 datetime 对象（带时区信息）
    """
    dt = parse_iso_to_aware(utc_iso)
    tz = pytz.timezone(get_user_timezone())
    return dt.astimezone(tz)


def utc_to_local_display(utc_iso: str) -> str:
    """将 UTC ISO 8601 时间字符串转换为本地时区显示格式

    用于后端将 UTC ISO 转为本地时间显示（AI 工具输出、日志等）。
    复用 parse_iso_to_aware 处理 +00:00、Z 后缀、带偏移输入。

    Args:
        utc_iso: UTC ISO 8601 时间字符串（如 "2026-07-11T20:00:00+00:00"）

    Returns:
        str: 本地时间字符串 "YYYY-MM-DD HH:MM:SS"（面向 AI/用户格式）
    """
    local_dt = utc_to_local(utc_iso)
    return local_dt.strftime("%Y-%m-%d %H:%M:%S")


def build_utc_time_range(local_date: str) -> tuple[str, str]:
    """根据本地日期构造当天的 UTC 时间范围

    用于 Repository 层按日期查询时间戳字段时，将本地日期转为 UTC 时间范围。
    范围为当天 00:00:00 ~ 23:59:59 对应的 UTC 时间。

    Args:
        local_date: 本地日期字符串，格式 YYYY-MM-DD

    Returns:
        tuple[str, str]: (utc_start_iso, utc_end_iso)
    """
    start_utc = local_to_utc_iso(f"{local_date} 00:00:00")
    end_utc = local_to_utc_iso(f"{local_date} 23:59:59")
    return (start_utc, end_utc)
