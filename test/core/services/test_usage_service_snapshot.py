"""
Usage Service 快照测试

用于 provider 重构前后的行为验证。
测试所有调用 tokens_usage_provider 的 service 方法。
"""
import pytest
from syrupy.assertion import SnapshotAssertion

from lifeprism.server.services import usage_service


# ==================== 测试辅助函数 ====================

def sanitize_usage_stats(data: dict) -> dict:
    """清理动态字段，用于快照对比"""
    if data is None:
        return None

    result = {}
    # 排除动态字段（价格可能因配置变化）
    exclude_fields = set()

    for key, value in data.items():
        if key in exclude_fields:
            continue
        # 递归处理嵌套字典
        if isinstance(value, dict):
            result[key] = sanitize_usage_stats(value)
        # 递归处理列表
        elif isinstance(value, list):
            result[key] = [sanitize_usage_stats(item) if isinstance(item, dict) else item for item in value]
        else:
            result[key] = value

    return result


# ==================== 快照测试 ====================

class TestUsageServiceSnapshot:
    """Usage Service 快照测试"""

    def test_get_usage_stats_snapshot(self, use_tokens_usage_test_data, snapshot: SnapshotAssertion):
        """
        测试 get_usage_stats() 方法

        验证：
        - 获取完整的使用统计数据
        - 包含总览、7天统计、数据处理统计和其他消耗统计
        """
        # 使用固定日期进行测试
        test_date = "2026-01-15"
        result = usage_service.get_usage_stats(test_date)

        sanitized = sanitize_usage_stats(result.model_dump())
        assert sanitized == snapshot

    def test_get_usage_overview_snapshot(self, use_tokens_usage_test_data, snapshot: SnapshotAssertion):
        """
        测试 get_usage_overview() 方法

        验证：
        - 获取单日使用总览
        - 包含今日和全部的 token 使用情况
        """
        test_date = "2026-01-15"
        result = usage_service.get_usage_overview(test_date)

        sanitized = sanitize_usage_stats(result.model_dump())
        assert sanitized == snapshot

    def test_get_usage_stats_7days_snapshot(self, use_tokens_usage_test_data, snapshot: SnapshotAssertion):
        """
        测试 get_usage_stats_7days() 方法

        验证：
        - 获取最近7天的使用统计
        - 包含每天的总价格和总 token 数
        """
        test_date = "2026-01-15"
        result = usage_service.get_usage_stats_7days(test_date)

        sanitized = sanitize_usage_stats(result.model_dump())
        assert sanitized == snapshot

    def test_get_data_processing_usage_stats_snapshot(self, use_tokens_usage_test_data, snapshot: SnapshotAssertion):
        """
        测试 get_data_processing_usage_stats() 方法

        验证：
        - 获取数据处理使用统计（classification mode）
        - 包含处理项目数、平均 token 数、平均价格等
        """
        test_date = "2026-01-15"
        result = usage_service.get_data_processing_usage_stats(test_date)

        sanitized = sanitize_usage_stats(result.model_dump())
        assert sanitized == snapshot

    def test_get_other_usage_stats_snapshot(self, use_tokens_usage_test_data, snapshot: SnapshotAssertion):
        """
        测试 get_other_usage_stats() 方法

        验证：
        - 获取其他消耗使用统计（非 classification 的所有消耗）
        - 包含今日和全部的 token 使用情况
        """
        test_date = "2026-01-15"
        result = usage_service.get_other_usage_stats(test_date)

        sanitized = sanitize_usage_stats(result.model_dump())
        assert sanitized == snapshot


@pytest.fixture(scope="session", autouse=True)
def setup_timestamp():
    """设置测试时间戳"""
    import time
    pytest.timestamp = int(time.time())
