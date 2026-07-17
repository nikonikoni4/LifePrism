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
    exclude_fields = {"created_at", "updated_at"}

    for key, value in data.items():
        if key in exclude_fields:
            continue
        # 递归处理子分类列表
        if key == "subcategories" and isinstance(value, list):
            result[key] = [sanitize_category_item(item) for item in value]
        else:
            result[key] = value

    return result


def sanitize_category_tree(items: list) -> list:
    """清理分类树的动态字段"""
    return sorted([sanitize_category_item(item) for item in items], key=lambda x: x.get("id", ""))


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

    def test_get_category_map_cache_list_snapshot(self, snapshot: SnapshotAssertion):
        """
        测试 get_category_map_cache_list() 方法

        验证：
        - 获取 category_map_cache 列表（第一页）
        """
        result = category_service.get_category_map_cache_list(page=1, page_size=10)

        # 跳过空数据测试
        if not result.data:
            pytest.skip("测试数据为空，跳过快照测试")

        # 清理动态字段
        sanitized_data = {
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
            "total_pages": result.total_pages,
            "items": sorted(
                [
                    {k: v for k, v in item.model_dump().items() if k != "created_at"}
                    for item in result.data
                ],
                key=lambda x: x.get("id", ""),
            ),
        }
        assert sanitized_data == snapshot

    def test_update_category_map_cache_snapshot(self, snapshot: SnapshotAssertion):
        """
        测试 update_category_map_cache() 方法

        验证：
        - 更新单条 category_map_cache 记录
        """
        # 先获取一条记录
        result = category_service.get_category_map_cache_list(page=1, page_size=1)
        if not result.data:
            pytest.skip("测试数据为空，跳过快照测试")

        record_id = result.data[0].id
        original_sub_category_id = result.data[0].sub_category_id

        # 更新记录（只更新 sub_category_id）
        update_result = category_service.update_category_map_cache(
            record_id=record_id, update_fields={"sub_category_id": "1-1"}
        )

        # 获取更新后的记录
        updated_result = category_service.get_category_map_cache_list(page=1, page_size=1)

        # 恢复原始数据
        category_service.update_category_map_cache(
            record_id=record_id, update_fields={"sub_category_id": original_sub_category_id}
        )

        sanitized_data = {
            "update_success": update_result,
            "updated_record": {
                k: v for k, v in updated_result.data[0].model_dump().items() if k != "created_at"
            },
        }
        assert sanitized_data == snapshot

    def test_delete_and_batch_delete_category_map_cache_snapshot(self, snapshot: SnapshotAssertion):
        """
        测试 delete_category_map_cache() 和 batch_delete_category_map_cache() 方法

        验证：
        - 删除操作返回正确的结果
        - 注意：这个测试不会真正删除数据，只测试方法调用
        """
        # 获取前两条记录
        result = category_service.get_category_map_cache_list(page=1, page_size=2)
        if len(result.data) < 2:
            pytest.skip("测试数据不足，跳过快照测试")

        # 测试单条删除（使用不存在的ID，避免真正删除数据）
        delete_result = category_service.delete_category_map_cache("non-existent-id")

        # 测试批量删除（使用不存在的ID，避免真正删除数据）
        batch_delete_result = category_service.batch_delete_category_map_cache(
            ["non-existent-id-1", "non-existent-id-2"]
        )

        sanitized_data = {
            "single_delete_result": delete_result,
            "batch_delete_result": batch_delete_result,
        }
        assert sanitized_data == snapshot


@pytest.fixture(scope="session", autouse=True)
def setup_timestamp():
    """设置测试时间戳"""
    import time

    pytest.timestamp = int(time.time())
