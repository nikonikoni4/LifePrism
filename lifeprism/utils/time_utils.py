"""时间处理工具函数 - UTC 时区迁移统一入口

核心原则：
- 时间戳字段（created_at、updated_at、finished_at、paused_at 等）使用 UTC
- 日期字段（date、start_date、end_date 等 YYYY-MM-DD 格式）保持用户本地时区日期
"""

from datetime import date, datetime, timezone

import pytz

from lifeprism.config import LOCAL_TIMEZONE


def get_local_today() -> date:
    """获取用户本地时区的今天日期

    用于"今天"/"昨天"等语义场景，确保用户在 UTC+ 时区午夜前后
    看到的日期与预期一致。

    Returns:
        date: 用户本地时区的今天日期对象
    """
    local_tz = pytz.timezone(LOCAL_TIMEZONE)
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
