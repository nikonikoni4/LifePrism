"""
Data Processing Service 快照测试

用于 provider 重构前后的行为验证。
测试所有调用 map_cache_providers 的 service 方法。
"""
import pytest
from syrupy.assertion import SnapshotAssertion

from lifeprism.server.services.data_processing_service import DataProcessingService


# ==================== 快照测试 ====================

class TestDataProcessingServiceSnapshot:
    """Data Processing Service 快照测试"""

    @pytest.fixture(scope="class")
    def service(self):
        """创建 DataProcessingService 实例"""
        return DataProcessingService()

    def test_load_category_map_cache_snapshot(self, service, snapshot: SnapshotAssertion):
        """
        测试 load_category_map_cache_V2() 方法（通过内部调用）

        验证：
        - 加载 category_map_cache 数据
        """
        # 直接调用 server_lw_data_provider 的方法
        result = service.server_lw_data_provider.load_category_map_cache_V2()

        # 跳过空数据测试
        if result is None or result.empty:
            pytest.skip("测试数据为空，跳过快照测试")

        # 转换为字典列表并排序
        sanitized_data = sorted(
            result.to_dict('records'),
            key=lambda x: x.get('id', '')
        )

        # 清理动态字段
        for item in sanitized_data:
            item.pop('created_at', None)
            item.pop('updated_at', None)

        assert sanitized_data == snapshot


@pytest.fixture(scope="session", autouse=True)
def setup_timestamp():
    """设置测试时间戳"""
    import time
    pytest.timestamp = int(time.time())
