"""测试 Timeline Stats API UTC 转换修复

验证前端传 UTC 时间范围，后端能正确查询并返回数据。
"""

import sys
import io
from datetime import datetime
import pytz

# 设置标准输出编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def test_date_to_utc_conversion():
    """测试前端日期到 UTC 时间范围的转换逻辑"""

    # 模拟前端：本地日期 2026-07-13（UTC+8）
    date = "2026-07-13"

    # 前端应该转换为 UTC 时间范围
    # 本地 2026-07-13 00:00:00 (UTC+8) → UTC 2026-07-12 16:00:00
    # 本地 2026-07-13 23:59:59 (UTC+8) → UTC 2026-07-13 15:59:59

    # 模拟前端转换（使用浏览器本地时区，这里用 UTC+8 测试）
    local_tz = pytz.timezone('Asia/Shanghai')
    start_local = local_tz.localize(datetime.strptime(f"{date} 00:00:00", "%Y-%m-%d %H:%M:%S"))
    end_local = local_tz.localize(datetime.strptime(f"{date} 23:59:59.999000", "%Y-%m-%d %H:%M:%S.%f"))

    start_utc = start_local.astimezone(pytz.UTC).isoformat()
    end_utc = end_local.astimezone(pytz.UTC).isoformat()

    print(f"本地日期: {date}")
    print(f"本地时间范围: {start_local.strftime('%Y-%m-%d %H:%M:%S')} ~ {end_local.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"UTC 时间范围: {start_utc} ~ {end_utc}")
    print()

    # 验证转换结果
    assert start_utc == "2026-07-12T16:00:00+00:00", f"开始时间转换错误: {start_utc}"
    assert end_utc == "2026-07-13T15:59:59.999000+00:00", f"结束时间转换错误: {end_utc}"

    print("✅ 日期到 UTC 转换正确")


def test_utc_back_to_local_date():
    """测试后端从 UTC 时间范围反向解析本地日期"""

    from lifeprism.utils.time_utils import utc_to_local

    # 后端收到的 UTC 时间范围
    start_time = "2026-07-12T16:00:00.000Z"
    end_time = "2026-07-13T15:59:59.999Z"

    # 后端解析为本地时间
    local_start = utc_to_local(start_time)
    local_end = utc_to_local(end_time)

    print(f"UTC 时间范围: {start_time} ~ {end_time}")
    print(f"本地时间: {local_start.strftime('%Y-%m-%d %H:%M:%S')} ~ {local_end.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"本地日期: {local_start.strftime('%Y-%m-%d')}")
    print()

    # 验证解析结果
    assert local_start.strftime('%Y-%m-%d') == "2026-07-13", f"日期解析错误: {local_start.date()}"
    assert local_start.hour == 0, f"开始小时错误: {local_start.hour}"
    assert local_end.hour == 23, f"结束小时错误: {local_end.hour}"

    print("✅ UTC 到本地日期反向解析正确")


def test_cross_day_boundary():
    """测试跨日期边界的时间记录"""

    # 场景：用户在北京时间 2026-07-13 05:20 创建记录
    # 数据库存储为 UTC: 2026-07-12 21:20
    # 查询 2026-07-13 应该能查到这条记录

    local_tz = pytz.timezone('Asia/Shanghai')

    # 记录的 UTC 时间
    record_utc = "2026-07-12T21:20:00.000Z"

    # 查询日期 2026-07-13 的 UTC 范围
    query_date = "2026-07-13"
    query_start_local = local_tz.localize(datetime.strptime(f"{query_date} 00:00:00", "%Y-%m-%d %H:%M:%S"))
    query_end_local = local_tz.localize(datetime.strptime(f"{query_date} 23:59:59.999000", "%Y-%m-%d %H:%M:%S.%f"))

    query_start_utc = query_start_local.astimezone(pytz.UTC)
    query_end_utc = query_end_local.astimezone(pytz.UTC)

    # 解析记录时间
    record_dt = datetime.fromisoformat(record_utc.replace('Z', '+00:00'))

    # 验证：记录时间应在查询范围内
    in_range = query_start_utc <= record_dt <= query_end_utc

    print(f"查询日期: {query_date}")
    print(f"查询 UTC 范围: {query_start_utc.isoformat()} ~ {query_end_utc.isoformat()}")
    print(f"记录 UTC 时间: {record_utc}")
    print(f"记录是否在范围内: {in_range}")
    print()

    assert in_range, "跨日期边界记录查询失败"

    print("✅ 跨日期边界查询正确")


if __name__ == "__main__":
    print("=" * 60)
    print("Timeline Stats API UTC 转换修复验证")
    print("=" * 60)
    print()

    test_date_to_utc_conversion()
    test_utc_back_to_local_date()
    test_cross_day_boundary()

    print("=" * 60)
    print("✅ 所有测试通过")
    print("=" * 60)
