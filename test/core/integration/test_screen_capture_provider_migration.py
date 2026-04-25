"""
测试 screen_capture_provider 与 llm_dataset_provider 的查询结果一致性

目的：验证从 llm_dataset_provider.query_screenshots 迁移到
     screen_capture_provider.query_screenshots 后，查询结果保持一致
"""
import pytest
from datetime import datetime
from lifeprism.llm.providers.dataset_providers import llm_dataset_provider
from lifeprism.repository import screen_capture_repository


@pytest.mark.core
class TestScreenCaptureProviderMigration:
    """测试 screen_capture_provider 迁移后的一致性"""

    def test_query_screenshots_consistency_2026_04_19(self):
        """测试 2026-04-19 的查询结果一致性"""
        start_time = "2026-04-19 00:00:00"
        end_time = "2026-04-19 23:59:59"

        # 使用旧的 llm_dataset_provider 查询
        old_results = llm_dataset_provider.query_screenshots(
            start_time=start_time,
            end_time=end_time
        )

        # 使用新的 screen_capture_repository 查询
        new_results = screen_capture_repository.query_screenshots(
            start_time=start_time,
            end_time=end_time
        )

        # 验证结果数量一致
        assert len(old_results) == len(new_results), \
            f"结果数量不一致: old={len(old_results)}, new={len(new_results)}"

        # 验证每条记录的关键字段一致
        for old, new in zip(old_results, new_results):
            assert old['id'] == new['id'], f"ID 不一致: {old['id']} vs {new['id']}"
            assert old['captured_at'] == new['captured_at'], \
                f"captured_at 不一致: {old['captured_at']} vs {new['captured_at']}"
            assert old['file_path'] == new['file_path'], \
                f"file_path 不一致: {old['file_path']} vs {new['file_path']}"
            assert old.get('window_app') == new.get('window_app'), \
                f"window_app 不一致: {old.get('window_app')} vs {new.get('window_app')}"
            assert old.get('window_title') == new.get('window_title'), \
                f"window_title 不一致: {old.get('window_title')} vs {new.get('window_title')}"
            assert old.get('capture_reason') == new.get('capture_reason'), \
                f"capture_reason 不一致: {old.get('capture_reason')} vs {new.get('capture_reason')}"

    def test_query_screenshots_consistency_2026_04_20(self):
        """测试 2026-04-20 的查询结果一致性"""
        start_time = "2026-04-20 00:00:00"
        end_time = "2026-04-20 23:59:59"

        # 使用旧的 llm_dataset_provider 查询
        old_results = llm_dataset_provider.query_screenshots(
            start_time=start_time,
            end_time=end_time
        )

        # 使用新的 screen_capture_repository 查询
        new_results = screen_capture_repository.query_screenshots(
            start_time=start_time,
            end_time=end_time
        )

        # 验证结果数量一致
        assert len(old_results) == len(new_results), \
            f"结果数量不一致: old={len(old_results)}, new={len(new_results)}"

        # 验证每条记录的关键字段一致
        for old, new in zip(old_results, new_results):
            assert old['id'] == new['id'], f"ID 不一致: {old['id']} vs {new['id']}"
            assert old['captured_at'] == new['captured_at'], \
                f"captured_at 不一致: {old['captured_at']} vs {new['captured_at']}"
            assert old['file_path'] == new['file_path'], \
                f"file_path 不一致: {old['file_path']} vs {new['file_path']}"

    def test_query_screenshots_with_capture_reason_filter(self):
        """测试带 capture_reason 过滤的查询结果一致性"""
        start_time = "2026-04-19 00:00:00"
        end_time = "2026-04-20 23:59:59"
        capture_reason = "active"

        # 使用旧的 llm_dataset_provider 查询
        old_results = llm_dataset_provider.query_screenshots(
            start_time=start_time,
            end_time=end_time,
            capture_reason=capture_reason
        )

        # 使用新的 screen_capture_repository 查询
        new_results = screen_capture_repository.query_screenshots(
            start_time=start_time,
            end_time=end_time,
            capture_reason=capture_reason
        )

        # 验证结果数量一致
        assert len(old_results) == len(new_results), \
            f"结果数量不一致: old={len(old_results)}, new={len(new_results)}"

        # 验证所有记录的 capture_reason 都是 'active'
        for result in new_results:
            assert result.get('capture_reason') == 'active', \
                f"capture_reason 应该是 'active'，实际是 {result.get('capture_reason')}"

        # 验证每条记录的关键字段一致
        for old, new in zip(old_results, new_results):
            assert old['id'] == new['id'], f"ID 不一致: {old['id']} vs {new['id']}"
            assert old['captured_at'] == new['captured_at'], \
                f"captured_at 不一致: {old['captured_at']} vs {new['captured_at']}"

    def test_query_screenshots_time_range(self):
        """测试特定时间范围的查询结果一致性"""
        start_time = "2026-04-19 10:00:00"
        end_time = "2026-04-19 12:00:00"

        # 使用旧的 llm_dataset_provider 查询
        old_results = llm_dataset_provider.query_screenshots(
            start_time=start_time,
            end_time=end_time
        )

        # 使用新的 screen_capture_repository 查询
        new_results = screen_capture_repository.query_screenshots(
            start_time=start_time,
            end_time=end_time
        )

        # 验证结果数量一致
        assert len(old_results) == len(new_results), \
            f"结果数量不一致: old={len(old_results)}, new={len(new_results)}"

        # 验证所有记录都在时间范围内
        for result in new_results:
            captured_at = result['captured_at']
            assert start_time <= captured_at <= end_time, \
                f"captured_at {captured_at} 不在范围 [{start_time}, {end_time}] 内"

    def test_query_screenshots_empty_result(self):
        """测试空结果的一致性（查询未来日期）"""
        start_time = "2027-01-01 00:00:00"
        end_time = "2027-01-01 23:59:59"

        # 使用旧的 llm_dataset_provider 查询
        old_results = llm_dataset_provider.query_screenshots(
            start_time=start_time,
            end_time=end_time
        )

        # 使用新的 screen_capture_repository 查询
        new_results = screen_capture_repository.query_screenshots(
            start_time=start_time,
            end_time=end_time
        )

        # 验证都返回空列表
        assert len(old_results) == 0, f"old_results 应该为空，实际有 {len(old_results)} 条"
        assert len(new_results) == 0, f"new_results 应该为空，实际有 {len(new_results)} 条"
        assert old_results == new_results == []

    def test_query_screenshots_order_consistency(self):
        """测试查询结果的排序一致性（应该按时间升序）"""
        start_time = "2026-04-19 00:00:00"
        end_time = "2026-04-20 23:59:59"

        # 使用旧的 llm_dataset_provider 查询
        old_results = llm_dataset_provider.query_screenshots(
            start_time=start_time,
            end_time=end_time
        )

        # 使用新的 screen_capture_repository 查询
        new_results = screen_capture_repository.query_screenshots(
            start_time=start_time,
            end_time=end_time
        )

        # 验证排序一致性
        if len(old_results) > 1:
            # 验证旧结果是升序
            for i in range(len(old_results) - 1):
                assert old_results[i]['captured_at'] <= old_results[i + 1]['captured_at'], \
                    "old_results 不是按时间升序排列"

        if len(new_results) > 1:
            # 验证新结果是升序
            for i in range(len(new_results) - 1):
                assert new_results[i]['captured_at'] <= new_results[i + 1]['captured_at'], \
                    "new_results 不是按时间升序排列"

        # 验证两者顺序完全一致
        for old, new in zip(old_results, new_results):
            assert old['captured_at'] == new['captured_at'], \
                f"排序不一致: {old['captured_at']} vs {new['captured_at']}"
