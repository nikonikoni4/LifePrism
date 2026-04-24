"""
Category Service 快照测试

用于 provider 重构前后的行为验证。
测试所有调用 category_provider 的 service 方法。
"""
import pytest
from syrupy.assertion import SnapshotAssertion

from lifeprism.server.services.category_service import category_service


# ==================== 测试辅助函数 ====================

def sanitize_category_item(data: dict) -> dict:
    """清理动态字段，用于快照对比"""
    if data is None:
        return None

    result = {}
    # 排除动态字段
    exclude_fields = {'created_at', 'updated_at'}

    for key, value in data.items():
        if key in exclude_fields:
            continue
        # 递归处理子分类列表
        if key == 'subcategories' and isinstance(value, list):
            result[key] = [sanitize_category_item(item) for item in value]
        else:
            result[key] = value

    return result


def sanitize_category_tree(items: list) -> list:
    """清理分类树的动态字段"""
    return sorted(
        [sanitize_category_item(item) for item in items],
        key=lambda x: x.get('id', '')
    )


# ==================== 快照测试 ====================

class TestCategoryServiceSnapshot:
    """Category Service 快照测试"""

    def test_get_category_tree_depth_1_snapshot(self, snapshot: SnapshotAssertion):
        """
        测试 get_category_tree(depth=1) 方法

        验证：
        - 获取主分类列表（不含子分类）
        """
        result = category_service.get_category_tree(depth=1)

        # 跳过空数据测试
        if not result.data:
            pytest.skip("测试数据为空，跳过快照测试")

        sanitized_items = sanitize_category_tree([item.model_dump() for item in result.data])
        assert sanitized_items == snapshot

    def test_get_category_tree_depth_2_snapshot(self, snapshot: SnapshotAssertion):
        """
        测试 get_category_tree(depth=2) 方法

        验证：
        - 获取主分类列表（含子分类）
        """
        result = category_service.get_category_tree(depth=2)

        # 跳过空数据测试
        if not result.data:
            pytest.skip("测试数据为空，跳过快照测试")

        sanitized_items = sanitize_category_tree([item.model_dump() for item in result.data])
        assert sanitized_items == snapshot


@pytest.fixture(scope="session", autouse=True)
def setup_timestamp():
    """设置测试时间戳"""
    import time
    pytest.timestamp = int(time.time())

