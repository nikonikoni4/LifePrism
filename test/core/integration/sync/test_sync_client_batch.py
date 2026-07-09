"""
SyncClient 分批拉取集成测试

测试 seam:
- Seam: SyncClient.pull_from_remote() - 分批拉取循环

验证 pull_from_remote() 实现了每表分批 1000 条的拉取逻辑，
同时保持 Last-Write-Wins 冲突解决行为不变。

参考: test/core/integration/sync/test_sync_client.py
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture(scope="module")
def initialized_db(test_data_path):
    """初始化数据库，创建所有表"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    from lifeprism.repository import lw_db_manager
    from lifeprism.repository.lw_table_manager import LWTableManager

    # 重置 update_at 缓存（确保测试使用最新配置）
    from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider

    LWBaseDataProvider._TABLES_WITH_UPDATE_AT = None

    manager = LWTableManager(db_manager=lw_db_manager)
    manager.init_database()

    yield lw_db_manager


@pytest.fixture
def sync_repository(initialized_db):
    """创建 SyncRepository 实例"""
    from lifeprism.repository.sync_repository import SyncRepository

    repo = SyncRepository(db_manager=initialized_db)
    yield repo


@pytest.fixture
def sync_client(initialized_db, sync_repository):
    """创建 SyncClient 实例"""
    from lifeprism.sync.sync_client import SyncClient

    client = SyncClient(db_manager=initialized_db, sync_repository=sync_repository)
    yield client


@pytest.fixture
def clean_tables(initialized_db):
    """清理同步表数据（测试后执行）"""
    sync_tables = ["todo_list"]
    yield
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        for table_name in sync_tables:
            cursor.execute(f"DELETE FROM {table_name}")
        conn.commit()


def _make_mock_response(json_data, status_code=200):
    """构建 mock httpx.Response 对象"""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    mock_resp.raise_for_status = MagicMock()
    if status_code >= 400:
        mock_resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return mock_resp


def _make_batched_side_effect(table_name, all_rows, batch_size=1000):
    """构建根据请求 offset 返回对应批次数据的 mock side_effect"""

    def side_effect(*args, **kwargs):
        offset = kwargs["json"]["offset"]
        limit = kwargs["json"]["limit"]
        batch = all_rows[offset : offset + limit]
        return _make_mock_response({"changes": {table_name: batch}})

    return side_effect


def _make_todo_row(row_id, content=None):
    """生成一条 todo_list 记录"""
    return {
        "id": row_id,
        "content": content or f"任务-{row_id}",
        "state": "pool",
        "created_at": "2026-07-01 10:00:00",
        "updated_at": "2026-07-01 10:00:00",
    }


# ==================== Seam: pull_from_remote() 分批拉取 ====================


class TestPullBatched:
    """Seam: pull_from_remote() - 分批拉取循环"""

    def test_pull_batched_multiple_batches(
        self, sync_client, initialized_db, clean_tables
    ):
        """分批拉取：大数据集(>1000条)分多批拉取"""
        # Arrange: 生成 2500 条记录
        all_rows = [_make_todo_row(f"todo-batch-{i:04d}") for i in range(2500)]

        with patch(
            "lifeprism.sync.sync_client.httpx.post",
            side_effect=_make_batched_side_effect("todo_list", all_rows),
        ) as mock_post:
            # Act
            sync_client.pull_from_remote(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-01 00:00:00",
                tables=["todo_list"],
            )

        # Assert: 3 批请求（1000 + 1000 + 500）
        assert mock_post.call_count == 3
        # 验证 offset 递增
        offsets = [
            call.kwargs["json"]["offset"] for call in mock_post.call_args_list
        ]
        assert offsets == [0, 1000, 2000]
        # 验证每次请求只发送一张表
        for call in mock_post.call_args_list:
            assert call.kwargs["json"]["tables"] == ["todo_list"]
            assert call.kwargs["json"]["limit"] == 1000
        # 验证所有记录已写入本地数据库
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM todo_list")
            assert cursor.fetchone()[0] == 2500

    def test_pull_batched_last_batch_partial(
        self, sync_client, initialized_db, clean_tables
    ):
        """分批拉取：最后一批 < 1000 条时正确退出"""
        # Arrange: 1500 条记录（1000 + 500）
        all_rows = [_make_todo_row(f"todo-partial-{i:04d}") for i in range(1500)]

        with patch(
            "lifeprism.sync.sync_client.httpx.post",
            side_effect=_make_batched_side_effect("todo_list", all_rows),
        ) as mock_post:
            # Act
            sync_client.pull_from_remote(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-01 00:00:00",
                tables=["todo_list"],
            )

        # Assert: 2 批请求（1000 + 500）
        assert mock_post.call_count == 2
        offsets = [
            call.kwargs["json"]["offset"] for call in mock_post.call_args_list
        ]
        assert offsets == [0, 1000]
        # 验证全部记录已写入
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM todo_list")
            assert cursor.fetchone()[0] == 1500

    def test_pull_batched_empty_table_no_requests_beyond_first(
        self, sync_client, initialized_db, clean_tables
    ):
        """分批拉取：空表只发一次请求"""
        # Arrange: 远程返回空数据
        mock_response = _make_mock_response({"changes": {}})

        with patch(
            "lifeprism.sync.sync_client.httpx.post", return_value=mock_response
        ) as mock_post:
            # Act
            sync_client.pull_from_remote(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-01 00:00:00",
                tables=["todo_list"],
            )

        # Assert: 只调用 1 次（空表不需要继续分批）
        assert mock_post.call_count == 1
        # 验证请求包含 offset 和 limit 参数
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["json"]["offset"] == 0
        assert call_kwargs["json"]["limit"] == 1000

    def test_pull_batched_lww_preserved(
        self, sync_client, initialized_db, clean_tables
    ):
        """分批拉取：LWW 冲突解决仍然生效"""
        # Arrange: 本地已有一条记录（本地已修改，updated_at > last_sync_time）
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO todo_list (id, content, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    "todo-lww-batch",
                    "本地修改内容",
                    "scheduled",
                    "2026-07-01 09:00:00",
                    "2026-07-01 12:00:00",
                ),
            )
            conn.commit()

        # 远程记录 updated_at = 11:00 < 本地 12:00 → 保留本地
        remote_row = {
            "id": "todo-lww-batch",
            "content": "远程较旧内容",
            "state": "pool",
            "created_at": "2026-07-01 09:00:00",
            "updated_at": "2026-07-01 11:00:00",
        }
        mock_response = _make_mock_response({"changes": {"todo_list": [remote_row]}})

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=mock_response):
            # Act: last_sync_time = 10:00，本地 updated_at = 12:00 > last_sync_time → 本地已修改
            sync_client.pull_from_remote(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-01 10:00:00",
                tables=["todo_list"],
            )

        # Assert: 本地保留，未被远程覆盖
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content, state FROM todo_list WHERE id = ?",
                ("todo-lww-batch",),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "本地修改内容"
            assert row[1] == "scheduled"

    def test_pull_batched_logs_progress(
        self, sync_client, initialized_db, clean_tables, caplog
    ):
        """分批拉取：日志记录分批进度"""
        # Arrange: 1500 条记录（2 批）
        all_rows = [_make_todo_row(f"todo-log-{i:04d}") for i in range(1500)]

        with caplog.at_level(logging.DEBUG):
            with patch(
                "lifeprism.sync.sync_client.httpx.post",
                side_effect=_make_batched_side_effect("todo_list", all_rows),
            ):
                # Act
                sync_client.pull_from_remote(
                    remote_url="http://test:8000",
                    api_key="test-key",
                    last_sync_time="2026-07-01 00:00:00",
                    tables=["todo_list"],
                )

        # Assert: 日志包含分批进度信息
        log_messages = [record.getMessage() for record in caplog.records]
        # 应该有 "开始拉取表" 的日志
        assert any("开始拉取表" in msg for msg in log_messages), (
            "日志应包含 '开始拉取表' 信息"
        )
        # 应该有 "拉取完成" 的日志
        assert any("拉取完成" in msg for msg in log_messages), (
            "日志应包含 '拉取完成' 信息"
        )
        # 应该有分批进度日志（包含 offset 信息）
        assert any("分批拉取" in msg for msg in log_messages), (
            "日志应包含 '分批拉取' 进度信息"
        )
