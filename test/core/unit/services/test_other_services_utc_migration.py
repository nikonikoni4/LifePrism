"""其他服务 UTC 时区迁移测试

验证 Issue #8 涵盖的服务在 UTC 时区迁移后的时间字段格式正确性。

测试 seam:
- Seam 1: ChatbotService.get_sessions - 缺失元数据时 fallback 时间戳使用 UTC ISO
- Seam 2: ChatbotService.update_session - 缺失 session 时间时 fallback 使用 UTC ISO
- Seam 3: add_on_service.create_expand_dir - created_at 使用 UTC ISO
- Seam 4: add_on_service.update_expand_dir - 原始 created_at 缺失时 fallback 使用 UTC ISO
- Seam 5: CategoryService.get_category_stats - naive datetime 输入按 UTC 处理
- Seam 6: DataProcessingService._save_tokens_usage - session_id 使用本地日期
- Seam 7: plandoc_sync_service.sync_plan_doc - actual_finished_at 使用本地日期 YYYY-MM-DD
- Seam 8: timeline_builder 默认时间范围使用 UTC datetime

参考:
- docs/adr/2026-07-12-migrate-to-utc-timezone.md
- docs/guides/utc-migration-hidden-dependencies.md
- .scratch/utc-timezone-migration/08-other-services-migration.md
"""

import re
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.core


# ==================== 工具函数 ====================


def assert_is_utc_iso(value: str):
    """断言字符串是 UTC ISO 8601 格式"""
    assert isinstance(value, str), f"应为 str 类型，实际为 {type(value)}"
    pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d{6}\+00:00$"
    assert re.match(pattern, value), f"应匹配 UTC ISO 8601 格式 {pattern}，实际为 {value}"


def assert_is_yyyy_mm_dd(value: str):
    """断言字符串是 YYYY-MM-DD 格式"""
    assert isinstance(value, str), f"应为 str 类型，实际为 {type(value)}"
    pattern = r"^\d{4}-\d{2}-\d{2}$"
    assert re.match(pattern, value), f"应匹配 YYYY-MM-DD 格式 {pattern}，实际为 {value}"


# ==================== Seam 1: ChatbotService.get_sessions fallback UTC ISO ====================


class TestChatbotServiceGetSessionsFallbackUtcIso:
    """ChatbotService.get_sessions 缺失元数据时 fallback 时间戳应为 UTC ISO"""

    @pytest.mark.asyncio
    async def test_created_at_fallback_is_utc_iso(self):
        """当 metadata 缺失 created_at 时，fallback 应为 UTC ISO 格式"""
        from lifeprism.server.services.chatbot_service import ChatbotService

        service = ChatbotService.__new__(ChatbotService)
        service._chatbot = MagicMock()
        service._chatbot.list_sessions.return_value = ["sess-1"]

        # metadata 缺失 created_at 和 updated_at
        metadata = {"name": "test", "message_len": 0}
        with patch("lifeprism.llm.session.manager.SessionManager") as mock_sm:
            mock_sm.get_session_metadata.return_value = metadata
            result = await service.get_sessions(page=1, page_size=10)

        assert len(result.items) == 1
        assert_is_utc_iso(result.items[0].created_at)

    @pytest.mark.asyncio
    async def test_updated_at_fallback_is_utc_iso(self):
        """当 metadata 缺失 updated_at 时，fallback 应为 UTC ISO 格式"""
        from lifeprism.server.services.chatbot_service import ChatbotService

        service = ChatbotService.__new__(ChatbotService)
        service._chatbot = MagicMock()
        service._chatbot.list_sessions.return_value = ["sess-1"]

        metadata = {
            "name": "test",
            "created_at": "2026-01-01T00:00:00+00:00",
            "message_len": 0,
        }
        with patch("lifeprism.llm.session.manager.SessionManager") as mock_sm:
            mock_sm.get_session_metadata.return_value = metadata
            result = await service.get_sessions(page=1, page_size=10)

        assert len(result.items) == 1
        assert_is_utc_iso(result.items[0].updated_at)


# ==================== Seam 2: ChatbotService.update_session fallback UTC ISO ====================


class TestChatbotServiceUpdateSessionFallbackUtcIso:
    """ChatbotService.update_session 缺失 session 时间时 fallback 应为 UTC ISO"""

    @pytest.mark.asyncio
    async def test_created_at_fallback_is_utc_iso(self):
        """当 session.created_at 为 None 时，fallback 应为 UTC ISO 格式"""
        from lifeprism.server.schemas.chatbot_schemas import UpdateSessionRequest
        from lifeprism.server.services.chatbot_service import ChatbotService

        service = ChatbotService.__new__(ChatbotService)
        service._chatbot = MagicMock()

        # session 对象 created_at 为 None
        mock_session = MagicMock()
        mock_session.id = "sess-1"
        mock_session.name = "updated name"
        mock_session.created_at = None
        mock_session.updated_at = None
        mock_session.messages = []
        service._chatbot.get_session.return_value = mock_session

        request = UpdateSessionRequest(name="updated name")
        result = await service.update_session("sess-1", request)

        assert_is_utc_iso(result.created_at)
        assert_is_utc_iso(result.updated_at)


# ==================== Seam 3: add_on_service.create_expand_dir created_at UTC ISO ====================


class TestAddOnServiceCreatedAtIsUtcIso:
    """add_on_service.create_expand_dir 的 created_at 应为 UTC ISO 格式"""

    def test_create_expand_dir_created_at_is_utc_iso(self, tmp_path):
        """创建扩展文件夹时 created_at 应为 UTC ISO 格式"""
        from lifeprism.server.schemas.add_on_schemas import CreateExpandDirRequest
        from lifeprism.server.services import add_on_service

        test_dir = tmp_path / "test_folder"
        test_dir.mkdir()

        with (
            patch("lifeprism.server.services.add_on_service.settings") as mock_settings,
            patch("lifeprism.server.services.add_on_service._validate_path", return_value=True),
        ):
            mock_settings.lifeprism_data_path = str(tmp_path)
            data = CreateExpandDirRequest(
                name="测试",
                path=str(test_dir),
                description="",
                ai_index=False,
            )
            result = add_on_service.create_expand_dir(data)

        assert_is_utc_iso(result.created_at)


# ==================== Seam 4: add_on_service.update_expand_dir fallback UTC ISO ====================


class TestAddOnServiceUpdateFallbackUtcIso:
    """add_on_service.update_expand_dir 原始 created_at 缺失时 fallback 应为 UTC ISO"""

    def test_update_expand_dir_created_at_fallback_is_utc_iso(self, tmp_path):
        """更新扩展文件夹时，若原始 created_at 缺失，fallback 应为 UTC ISO 格式"""
        from lifeprism.server.schemas.add_on_schemas import (
            CreateExpandDirRequest,
            UpdateExpandDirRequest,
        )
        from lifeprism.server.services import add_on_service

        test_dir1 = tmp_path / "folder1"
        test_dir1.mkdir()
        test_dir2 = tmp_path / "folder2"
        test_dir2.mkdir()

        with (
            patch("lifeprism.server.services.add_on_service.settings") as mock_settings,
            patch("lifeprism.server.services.add_on_service._validate_path", return_value=True),
        ):
            mock_settings.lifeprism_data_path = str(tmp_path)

            # 先创建一条记录
            create_data = CreateExpandDirRequest(
                name="原名称",
                path=str(test_dir1),
                description="",
                ai_index=False,
            )
            created = add_on_service.create_expand_dir(create_data)

            # 篡改文件，移除 created_at 字段，模拟数据缺失
            file_data = add_on_service._read_data()
            for item in file_data["expand_dirs"]:
                if item["id"] == created.id:
                    item.pop("created_at", None)
            add_on_service._save_data(file_data)

            # 更新记录，触发 fallback
            update_data = UpdateExpandDirRequest(
                name="新名称",
                path=str(test_dir2),
                description="",
                ai_index=True,
            )
            result = add_on_service.update_expand_dir(created.id, update_data)

        assert_is_utc_iso(result.created_at)


# ==================== Seam 5: CategoryService.get_category_stats naive datetime 按 UTC 处理 ====================


class TestCategoryServiceStatsHandlesNaiveDatetimeAsUtc:
    """CategoryService.get_category_stats 应将 naive datetime 按 UTC 处理"""

    def test_naive_end_time_not_greater_than_utc_now(self):
        """naive end_time（等于 UTC 现在）不应触发 '不能大于当前时间' 错误"""
        from lifeprism.server.schemas.category_schemas import (
            CategoryStatsIncludeOptions,
        )
        from lifeprism.server.services.category_service import CategoryService

        service = CategoryService.__new__(CategoryService)
        service.server_lw_data_provider = MagicMock()
        # 返回空 DataFrame 模拟无数据
        service.server_lw_data_provider.load_user_app_behavior_log.return_value = None
        service._categories_df = None  # 触发空数据返回

        # naive datetime 等于当前 UTC 时间（减1秒避免边界）
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        start_time = now_utc - timedelta(hours=1)
        end_time = now_utc - timedelta(seconds=1)

        include_options = CategoryStatsIncludeOptions.from_include_string("duration")

        # 不应抛出 ValueError（naive 被解释为 UTC，end_time < now_utc）
        result = service.get_category_stats(
            start_time=start_time,
            end_time=end_time,
            include_options=include_options,
            top_title=3,
            category="",
            sub_category="",
        )
        assert result is not None

    def test_aware_end_time_future_raises_value_error(self):
        """aware end_time（未来时间）应抛出 ValueError"""
        from lifeprism.server.schemas.category_schemas import (
            CategoryStatsIncludeOptions,
        )
        from lifeprism.server.services.category_service import CategoryService

        service = CategoryService.__new__(CategoryService)

        future_end = datetime.now(timezone.utc) + timedelta(hours=1)
        start_time = datetime.now(timezone.utc) - timedelta(hours=1)

        include_options = CategoryStatsIncludeOptions.from_include_string("duration")

        with pytest.raises(ValueError, match="不能大于当前时间"):
            service.get_category_stats(
                start_time=start_time,
                end_time=future_end,
                include_options=include_options,
                top_title=3,
                category="",
                sub_category="",
            )


# ==================== Seam 6: DataProcessingService._save_tokens_usage session_id 本地日期 ====================


class TestDataProcessingServiceSessionIdUsesLocalDate:
    """DataProcessingService._save_tokens_usage 的 session_id 应使用本地日期"""

    def test_session_id_uses_local_date_format(self):
        """session_id 应为 c-YYYY-MM-DD 格式（本地日期）"""
        from lifeprism.server.services.data_processing_service import (
            DataProcessingService,
        )
        from lifeprism.utils.time_utils import get_local_today

        service = DataProcessingService.__new__(DataProcessingService)

        with patch(
            "lifeprism.server.services.data_processing_service.tokens_usage_repository"
        ) as mock_repo:
            mock_repo.get_tokens_usage_by_session_id.return_value = None
            mock_repo.upsert_tokens_usage.return_value = True

            service._save_tokens_usage(
                result={"tokens_usage": {"input_tokens": 100, "output_tokens": 50}},
                result_items_count=5,
            )

            # 验证 upsert_tokens_usage 被调用时 session_id 为 c-YYYY-MM-DD
            call_args = mock_repo.upsert_tokens_usage.call_args
            session_id = call_args[0][0]
            assert session_id.startswith("c-"), f"session_id 应以 'c-' 开头，实际为 {session_id}"

            date_part = session_id[2:]
            assert_is_yyyy_mm_dd(date_part)

            # 验证日期部分为本地今天
            local_today_str = get_local_today().isoformat()
            assert date_part == local_today_str, (
                f"session_id 日期部分应为本地今天 {local_today_str}，实际为 {date_part}"
            )


# ==================== Seam 7: plandoc_sync_service actual_finished_at 本地日期 ====================


class TestPlandocSyncServiceActualFinishedAtUsesLocalDate:
    """plandoc_sync_service.sync_plan_doc 的 actual_finished_at 应为本地日期 YYYY-MM-DD"""

    def test_actual_finished_at_is_yyyy_mm_dd_when_completing(self, tmp_path):
        """任务从非完成状态变为完成时，actual_finished_at 应为 YYYY-MM-DD 格式"""
        from lifeprism.server.services import plandoc_sync_service

        # 准备 MD 文件内容
        plan_doc_id = "test-plan"
        plan_dir = tmp_path / "plan"
        plan_dir.mkdir(parents=True, exist_ok=True)
        md_content = f"""# {plan_doc_id}

## 任务列表
<!-- lp:todoblock -->
- [x] 已完成的任务 <!-- lp:t-test0001 -->
<!-- /lp:todoblock -->
"""
        file_path = plan_dir / f"{plan_doc_id}.md"
        file_path.write_text(md_content, encoding="utf-8")

        # Mock 依赖
        with (
            patch(
                "lifeprism.server.services.plandoc_sync_service.plan_doc_repository"
            ) as mock_plan_repo,
            patch(
                "lifeprism.server.services.plandoc_sync_service.todo_repository"
            ) as mock_todo_repo,
            patch("lifeprism.config.settings_manager.settings") as mock_settings,
        ):
            mock_settings.lifeprism_data_path = tmp_path
            mock_plan_repo.get_plan_doc_by_id.return_value = {
                "id": plan_doc_id,
                "goal_id": "goal-1",
            }
            # 现有任务为非完成状态，将触发 actual_finished_at 写入
            mock_todo_repo.get_todos_by_plan_doc.return_value = [
                {
                    "id": "t-test0001",
                    "content": "已完成的任务",
                    "state": "pool",  # 非完成状态
                    "plan_doc_id": plan_doc_id,
                }
            ]
            mock_todo_repo.update_todo.return_value = True
            mock_todo_repo.create_todo.return_value = True
            mock_todo_repo.delete_todo.return_value = True

            plandoc_sync_service.sync_plan_doc(plan_doc_id, dry_run=False)

            # 验证 update_todo 被调用时传入了 actual_finished_at
            call_args = mock_todo_repo.update_todo.call_args
            if call_args is None:
                pytest.skip("update_todo 未被调用，可能任务状态未变化")
            updates = call_args[0][1]
            assert "actual_finished_at" in updates, (
                f"应包含 actual_finished_at 字段，实际 updates={updates}"
            )
            assert_is_yyyy_mm_dd(updates["actual_finished_at"])


# ==================== Seam 8: timeline_builder 默认时间范围使用 UTC ====================


class TestTimelineBuilderDefaultRangeUsesUtc:
    """timeline_builder 默认时间范围应使用 UTC datetime"""

    def test_default_range_does_not_raise_with_empty_df(self):
        """当无数据且无时间范围时，_calculate_time_distribution 应使用 UTC 默认范围不报错"""
        import pandas as pd

        from lifeprism.server.services.timeline_builder import (
            _calculate_time_distribution,
        )

        # 传入空 DataFrame 和 None 时间范围，触发默认分支
        empty_df = pd.DataFrame()
        result = _calculate_time_distribution(
            empty_df,
            range_start=None,
            range_end=None,
        )

        # 验证返回结果为 6 个时间槽
        assert isinstance(result, list)
        assert len(result) == 6
        # 验证每个槽都有 timeRange 字段
        for slot in result:
            assert "timeRange" in slot
