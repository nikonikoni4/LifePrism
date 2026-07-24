"""SyncClient 墓碑同步端到端测试（PRD 3 Slice 04）

测试场景（对齐 PRD S2 + 端到端验收标准）:
- 场景 1: TEXT 主键表删除 → Push 同步传播
- 场景 2: AUTOINCREMENT 表删除 → Push 同步传播（hash_id 墓碑）
- 场景 3: Pull 墓碑 → 本地执行 DELETE + 写副本
- 场景 4: Pull 墓碑 → AUTOINCREMENT 表按 hash_id 删除
- 场景 5: 墓碑 Pull 在数据 Pull 之前 + 不被数据 Pull 写回（US22）
- 场景 6: LWW 跳过（本地已有墓碑）
- 场景 7: Pull 失败事务回滚
- 场景 8: sync_once 失败时 last_sync_time 未更新（US18）
- 场景 9: 墓碑清理在同步成功后执行
- 场景 10: 动态表删除写墓碑（custom_record_aggregator）
- 场景 11: delete_entry 不存在记录不产生孤儿墓碑
- 场景 12: 级联删除同步传播所有级联表
- 场景 13: 重置 last_sync_time 后墓碑仍工作（US19）
- 场景 14: 全量首同步不传播墓碑（US20）
- 场景 15: 多表批量删除同步
- 场景 16: 空墓碑 Pull/Push 不报错

参考:
- PRD: .scratch/deletion-sync-03-tombstone/prd.md
- ADR: docs/adr/2026-07-22-deletion-sync-tombstone.md
- Prior art: test/core/integration/sync/test_sync_conflict_resolve.py
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture(scope="module")
def initialized_db(test_data_path):
    """初始化数据库，创建所有表"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    from lifeprism.repository import lw_db_manager
    from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider
    from lifeprism.repository.lw_table_manager import LWTableManager

    LWBaseDataProvider._TABLES_WITH_UPDATE_AT = None
    LWBaseDataProvider._TABLES_WITH_TIMESTAMPS = None

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
def mock_event_loop():
    """创建 mock 事件循环"""
    return MagicMock()


@pytest.fixture
def sync_client(initialized_db, sync_repository, mock_event_loop):
    """创建带 main_event_loop 的 SyncClient 实例"""
    from lifeprism.sync.sync_client import SyncClient

    client = SyncClient(
        db_manager=initialized_db,
        sync_repository=sync_repository,
        main_event_loop=mock_event_loop,
    )
    yield client


@pytest.fixture
def clean_tables(initialized_db):
    """每个测试前后清理 deletion_log + 相关业务表"""
    tables = [
        "deletion_log",
        "mood_entries",
        "timeline_custom_block",
        "diary",
        "habits",
        "habit_challenges",
        "habit_checkins",
    ]
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        for t in tables:
            cursor.execute(f"DELETE FROM {t}")
        conn.commit()
    yield
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        for t in tables:
            cursor.execute(f"DELETE FROM {t}")
        conn.commit()


@pytest.fixture
def clean_custom_records(initialized_db):
    """清理动态表相关数据（type + fields + 数据表）"""
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        # 查询所有动态表名并 DROP
        cursor.execute("SELECT slug FROM custom_record_types")
        slugs = [row[0] for row in cursor.fetchall()]
        for slug in slugs:
            cursor.execute(f"DROP TABLE IF EXISTS custom_{slug}")
        cursor.execute("DELETE FROM custom_record_fields")
        cursor.execute("DELETE FROM custom_record_types")
        cursor.execute("DELETE FROM deletion_log")
        conn.commit()
    yield
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT slug FROM custom_record_types")
        slugs = [row[0] for row in cursor.fetchall()]
        for slug in slugs:
            cursor.execute(f"DROP TABLE IF EXISTS custom_{slug}")
        cursor.execute("DELETE FROM custom_record_fields")
        cursor.execute("DELETE FROM custom_record_types")
        cursor.execute("DELETE FROM deletion_log")
        conn.commit()


# ==================== Helper ====================


def _make_mock_response(json_data, status_code=200):
    """构建 mock httpx.Response 对象"""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    mock_resp.raise_for_status = MagicMock()
    if status_code >= 400:
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}", request=MagicMock(), response=mock_resp
        )
    return mock_resp


def _insert_mood_entry(db, entry_id="mood-test1234", score=5):
    """直接 SQL 插入 mood_entries 记录（TEXT PK 表）"""
    now = datetime.now(timezone.utc).isoformat()
    with db.get_connection() as conn:
        conn.execute(
            "INSERT INTO mood_entries (id, mood_type_id, score, event_time, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (entry_id, "mt-test", score, now, now, now),
        )
        conn.commit()


def _insert_diary(db, date_str="2026-07-23"):
    """直接 SQL 插入 diary 记录（TEXT PK 表）"""
    now = datetime.now(timezone.utc).isoformat()
    with db.get_connection() as conn:
        conn.execute(
            "INSERT INTO diary (date, mood, importance, word_count, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (date_str, "happy", "normal", 100, now, now),
        )
        conn.commit()


def _get_tombstones(db, target_table=None):
    """查询 deletion_log 中的墓碑"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        if target_table:
            cursor.execute(
                "SELECT target_table, record_id, source FROM deletion_log WHERE target_table = ?",
                (target_table,),
            )
        else:
            cursor.execute(
                "SELECT target_table, record_id, source FROM deletion_log"
            )
        return [dict(zip(["target_table", "record_id", "source"], row, strict=False)) for row in cursor.fetchall()]


def _count_records(db, table, where_field=None, where_value=None):
    """查询表中记录数"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        if where_field:
            cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {where_field} = ?", (where_value,))
        else:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
        return cursor.fetchone()[0]


# ==================== 第一组：基本删除传播 ====================


class TestTombstonePush:
    """墓碑 Push 同步测试"""

    def test_text_pk_table_delete_pushes_tombstone(
        self, initialized_db, sync_client, clean_tables
    ):
        """场景 1: TEXT 主键表删除 → Push 同步传播"""
        from lifeprism.repository import mood_repository

        # Arrange: 插入 mood_entries 记录并删除（写墓碑）
        _insert_mood_entry(initialized_db, entry_id="mood-push01")
        mood_repository.delete_mood_entry("mood-push01")

        # 验证墓碑已写入
        tombstones = _get_tombstones(initialized_db, "mood_entries")
        assert len(tombstones) == 1
        assert tombstones[0]["record_id"] == "mood-push01"
        assert tombstones[0]["source"] == "local"

        # Act: 调用 _push_deletion_log，mock httpx 捕获请求
        with patch("lifeprism.sync.sync_client.httpx.post") as mock_post:
            mock_post.return_value = _make_mock_response(
                {"success": True, "applied_count": 1, "skipped_count": 0}
            )
            sync_client._push_deletion_log("http://remote", "api-key", "")

        # Assert: httpx 被调用，payload 含 1 条墓碑
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "/push-deletion-log" in call_args[1]["url"] or "/push-deletion-log" in call_args[0][0]
        payload = call_args[1].get("json") or call_args[0].get("json")
        assert len(payload["tombstones"]) == 1
        assert payload["tombstones"][0]["target_table"] == "mood_entries"
        assert payload["tombstones"][0]["record_id"] == "mood-push01"
        assert payload["tombstones"][0]["source"] == "local"

    def test_autoincrement_table_delete_pushes_tombstone(
        self, initialized_db, sync_client, clean_tables
    ):
        """场景 2: AUTOINCREMENT 表删除 → Push 同步传播（hash_id 墓碑）"""
        from lifeprism.repository import custom_block_repository

        # Arrange: 通过 provider 创建 timeline_custom_block 记录（自动生成 hash_id）
        block = custom_block_repository.create_custom_block(
            {
                "content": "test block",
                "start_time": "2026-07-23T10:00:00+00:00",
                "end_time": "2026-07-23T11:00:00+00:00",
                "duration": 3600,
                "color": "#ff0000",
                "category_id": 1,
                "sub_category_id": 1,
            }
        )
        block_id = block["id"]
        # 查询 hash_id
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT hash_id FROM timeline_custom_block WHERE id = ?", (block_id,)
            )
            hash_id = cursor.fetchone()[0]

        # 删除（写墓碑，record_id = hash_id）
        custom_block_repository.delete_custom_block(block_id)

        # 验证墓碑
        tombstones = _get_tombstones(initialized_db, "timeline_custom_block")
        assert len(tombstones) == 1
        assert tombstones[0]["record_id"] == hash_id
        assert tombstones[0]["record_id"].startswith("tcb-")
        assert tombstones[0]["source"] == "local"

        # Act: Push
        with patch("lifeprism.sync.sync_client.httpx.post") as mock_post:
            mock_post.return_value = _make_mock_response(
                {"success": True, "applied_count": 1, "skipped_count": 0}
            )
            sync_client._push_deletion_log("http://remote", "api-key", "")

        # Assert
        mock_post.assert_called_once()
        payload = mock_post.call_args[1].get("json") or mock_post.call_args[0].get("json")
        assert payload["tombstones"][0]["record_id"] == hash_id


# ==================== 墓碑 Pull ====================


class TestTombstonePull:
    """墓碑 Pull 同步测试"""

    def test_pull_tombstone_deletes_record_and_writes_copy(
        self, initialized_db, sync_client, clean_tables
    ):
        """场景 3: Pull 墓碑 → 本地执行 DELETE + 写副本"""
        # Arrange: 本地插入 1 条 mood_entries 记录
        _insert_mood_entry(initialized_db, entry_id="mood-pull01")
        assert _count_records(initialized_db, "mood_entries", "id", "mood-pull01") == 1

        # mock httpx 返回 1 条云端墓碑
        cloud_tombstone = {
            "target_table": "mood_entries",
            "record_id": "mood-pull01",
            "source": "local",
            "created_at": "2026-07-23T12:00:00+00:00",
            "updated_at": "2026-07-23T12:00:00+00:00",
            "id": "dl-cloud001",
        }

        with patch("lifeprism.sync.sync_client.httpx.post") as mock_post:
            mock_post.return_value = _make_mock_response({"tombstones": [cloud_tombstone]})

            # Act
            sync_client._pull_deletion_log("http://remote", "api-key", "")

        # Assert: 记录被删除
        assert _count_records(initialized_db, "mood_entries", "id", "mood-pull01") == 0

        # Assert: deletion_log 新增 1 条 source=cloud 副本
        tombstones = _get_tombstones(initialized_db, "mood_entries")
        assert len(tombstones) == 1
        assert tombstones[0]["source"] == "cloud"
        assert tombstones[0]["record_id"] == "mood-pull01"

    def test_pull_tombstone_autoincrement_by_hash_id(
        self, initialized_db, sync_client, clean_tables
    ):
        """场景 4: Pull 墓碑 → AUTOINCREMENT 表按 hash_id 删除"""
        from lifeprism.repository import custom_block_repository

        # Arrange: 创建 timeline_custom_block 记录
        block = custom_block_repository.create_custom_block(
            {
                "content": "test block for pull",
                "start_time": "2026-07-23T10:00:00+00:00",
                "end_time": "2026-07-23T11:00:00+00:00",
                "duration": 3600,
                "color": "#ff0000",
                "category_id": 1,
                "sub_category_id": 1,
            }
        )
        block_id = block["id"]
        hash_id = block["hash_id"]
        assert hash_id.startswith("tcb-")

        # mock httpx 返回云端墓碑（record_id = hash_id）
        cloud_tombstone = {
            "target_table": "timeline_custom_block",
            "record_id": hash_id,
            "source": "local",
            "created_at": "2026-07-23T12:00:00+00:00",
            "updated_at": "2026-07-23T12:00:00+00:00",
            "id": "dl-cloud002",
        }

        with patch("lifeprism.sync.sync_client.httpx.post") as mock_post:
            mock_post.return_value = _make_mock_response({"tombstones": [cloud_tombstone]})

            # Act
            sync_client._pull_deletion_log("http://remote", "api-key", "")

        # Assert: 记录被删除（按 hash_id 删除，非按 id）
        assert _count_records(initialized_db, "timeline_custom_block", "id", block_id) == 0

        # Assert: deletion_log 新增 cloud 副本
        tombstones = _get_tombstones(initialized_db, "timeline_custom_block")
        assert len(tombstones) == 1
        assert tombstones[0]["source"] == "cloud"
        assert tombstones[0]["record_id"] == hash_id


# ==================== 墓碑顺序与不被回写 ====================


class TestTombstoneOrdering:
    """墓碑顺序测试"""

    def test_tombstone_pull_before_data_pull_not_written_back(
        self, initialized_db, sync_client, clean_tables
    ):
        """场景 5: 墓碑 Pull 在数据 Pull 之前 + 不被数据 Pull 写回（US22）

        US22 保证：云端已删除记录 → 云端数据 Pull 端点不返回该记录
        （因记录已从云端 DB 物理删除）。本地墓碑 Pull 先执行 DELETE，
        随后数据 Pull 不会重新拉回该记录。

        本测试 mock 数据 Pull 不写回已删记录（模拟云端正确行为），
        验证墓碑 Pull 在数据 Pull 之前执行且记录最终不存在。
        """
        from lifeprism.config.settings_manager import get_setting, set_setting

        # Arrange: 本地插入 1 条 mood_entries 记录
        _insert_mood_entry(initialized_db, entry_id="mood-order01")

        # mock sync_once 的各步骤
        cloud_tombstone = {
            "target_table": "mood_entries",
            "record_id": "mood-order01",
            "source": "local",
            "created_at": "2026-07-23T12:00:00+00:00",
            "updated_at": "2026-07-23T12:00:00+00:00",
            "id": "dl-order01",
        }

        # 记录调用顺序
        call_order = []

        def mock_pull_from_remote(*args, **kwargs):
            call_order.append("pull_from_remote")
            # 模拟云端正确行为：已删记录不返回（不写回）

        def mock_push_to_remote(*args, **kwargs):
            call_order.append("push_to_remote")

        def mock_sync_files(*args, **kwargs):
            call_order.append("sync_files")

        # 预设 last_sync_time
        set_setting("sync.last_sync_time", "2026-07-22T00:00:00+00:00")
        set_setting("sync.remote_url", "http://remote")
        set_setting("sync.sync_api_key", "test-key")

        with (
            patch("lifeprism.sync.sync_client.httpx.post") as mock_post,
            patch.object(sync_client, "_check_cloud_initialized", return_value=True),
            patch.object(sync_client, "_sync_dynamic_tables_definitions", return_value=[]),
            patch.object(sync_client, "pull_from_remote", side_effect=mock_pull_from_remote),
            patch.object(sync_client, "_push_deletion_log"),
            patch.object(sync_client, "push_to_remote", side_effect=mock_push_to_remote),
            patch.object(sync_client, "_sync_files_full_flow", side_effect=mock_sync_files),
            patch.object(sync_client, "_cleanup_deletion_log"),
            patch("lifeprism.sync.sync_config.get_sync_api_key", return_value="test-key"),
        ):
            # /pull-deletion-log 返回墓碑
            def post_side_effect(url, **kwargs):
                if "pull-deletion-log" in url:
                    call_order.append("_pull_deletion_log")
                    return _make_mock_response({"tombstones": [cloud_tombstone]})
                return _make_mock_response({"tombstones": []})

            mock_post.side_effect = post_side_effect

            # Act: 调用 sync_once
            sync_client.sync_once()

        # Assert: 最终本地无该记录（墓碑 Pull 删除后，数据 Pull 未写回）
        assert _count_records(initialized_db, "mood_entries", "id", "mood-order01") == 0

        # Assert: 调用顺序为 _pull_deletion_log 在 pull_from_remote 之前
        pull_idx = call_order.index("_pull_deletion_log")
        data_pull_idx = call_order.index("pull_from_remote")
        assert pull_idx < data_pull_idx, f"墓碑 Pull 应在数据 Pull 之前，实际顺序: {call_order}"


# ==================== LWW 与失败处理 ====================


class TestLWWAndFailure:
    """LWW 与失败处理测试"""

    def test_lww_skip_when_local_tombstone_exists(
        self, initialized_db, sync_client, clean_tables
    ):
        """场景 6: LWW 跳过（本地已有墓碑）"""
        from lifeprism.repository import deletion_log_repository

        # Arrange: 本地预先写入墓碑（source=local）
        deletion_log_repository.create_tombstone(
            "mood_entries", "mood-lww01", source="local"
        )

        # mock httpx 返回同 (target_table, record_id) 的云端墓碑
        cloud_tombstone = {
            "target_table": "mood_entries",
            "record_id": "mood-lww01",
            "source": "local",
            "created_at": "2026-07-23T14:00:00+00:00",
            "updated_at": "2026-07-23T14:00:00+00:00",
            "id": "dl-cloud-lww",
        }

        with patch("lifeprism.sync.sync_client.httpx.post") as mock_post:
            mock_post.return_value = _make_mock_response({"tombstones": [cloud_tombstone]})

            # Act
            sync_client._pull_deletion_log("http://remote", "api-key", "")

        # Assert: 不覆盖本地墓碑（INSERT OR IGNORE 保留旧墓碑）
        tombstones = _get_tombstones(initialized_db, "mood_entries")
        assert len(tombstones) == 1
        assert tombstones[0]["source"] == "local"  # 仍是本地旧墓碑

    def test_pull_failure_rolls_back_transaction(
        self, initialized_db, sync_client, clean_tables
    ):
        """场景 7: Pull 失败事务回滚

        使用 sqlite3.OperationalError 模拟真实 DB 失败。
        get_connection() 捕获 sqlite3.Error 后 rollback 并重新抛出为 DataAccessError。
        """
        from lifeprism.utils.exceptions import DataAccessError

        # Arrange: 本地插入 2 条记录
        _insert_mood_entry(initialized_db, entry_id="mood-rb01")
        _insert_mood_entry(initialized_db, entry_id="mood-rb02")

        # mock httpx 返回 2 条墓碑
        tombstones = [
            {
                "target_table": "mood_entries",
                "record_id": "mood-rb01",
                "source": "local",
                "created_at": "2026-07-23T12:00:00+00:00",
                "updated_at": "2026-07-23T12:00:00+00:00",
                "id": "dl-rb01",
            },
            {
                "target_table": "mood_entries",
                "record_id": "mood-rb02",
                "source": "local",
                "created_at": "2026-07-23T12:00:00+00:00",
                "updated_at": "2026-07-23T12:00:00+00:00",
                "id": "dl-rb02",
            },
        ]

        # mock execute_tombstone_delete_with_cursor 在第 2 条抛 sqlite3 错误
        import sqlite3 as _sqlite3

        original_method = sync_client.sync_repository.execute_tombstone_delete_with_cursor
        call_count = {"n": 0}

        def failing_delete(cursor, target_table, record_id):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise _sqlite3.OperationalError("模拟第 2 条删除失败")
            return original_method(cursor, target_table, record_id)

        with (
            patch("lifeprism.sync.sync_client.httpx.post") as mock_post,
            patch.object(
                sync_client.sync_repository,
                "execute_tombstone_delete_with_cursor",
                side_effect=failing_delete,
            ),
        ):
            mock_post.return_value = _make_mock_response({"tombstones": tombstones})

            # Act: 预期抛 DataAccessError（get_connection 将 sqlite3.Error 包装为 DataAccessError）
            with pytest.raises(DataAccessError, match="模拟第 2 条删除失败"):
                sync_client._pull_deletion_log("http://remote", "api-key", "")

        # Assert: 第 1 条 DELETE 也被回滚（事务未 commit）
        assert _count_records(initialized_db, "mood_entries", "id", "mood-rb01") == 1
        assert _count_records(initialized_db, "mood_entries", "id", "mood-rb02") == 1

        # Assert: deletion_log 无 cloud 副本（事务回滚）
        tombstones_after = _get_tombstones(initialized_db, "mood_entries")
        assert len(tombstones_after) == 0

    def test_sync_once_failure_keeps_last_sync_time(
        self, initialized_db, sync_client, clean_tables
    ):
        """场景 8: sync_once 失败时 last_sync_time 未更新（US18）"""
        from lifeprism.config.settings_manager import get_setting, set_setting

        # Arrange: 预设 last_sync_time
        preset_time = "2026-07-22T00:00:00+00:00"
        set_setting("sync.last_sync_time", preset_time)
        set_setting("sync.remote_url", "http://remote")

        with (
            patch("lifeprism.sync.sync_client.httpx.post") as mock_post,
            patch("lifeprism.sync.sync_config.get_sync_api_key", return_value="test-key"),
            patch.object(sync_client, "_check_cloud_initialized", return_value=True),
            patch.object(sync_client, "_sync_dynamic_tables_definitions", return_value=[]),
        ):
            # /pull-deletion-log 抛 HTTPStatusError
            mock_post.side_effect = httpx.HTTPStatusError(
                "HTTP 500", request=MagicMock(), response=MagicMock(status_code=500)
            )

            # Act: 预期 sync_once 抛异常
            with pytest.raises(httpx.HTTPStatusError):
                sync_client.sync_once()

        # Assert: last_sync_time 仍为预设值（未更新）
        assert get_setting("sync.last_sync_time") == preset_time


# ==================== 墓碑清理 ====================


class TestTombstoneCleanup:
    """墓碑清理测试"""

    def test_cleanup_old_tombstones(self, initialized_db, sync_client, clean_tables):
        """场景 9: 墓碑清理在同步成功后执行"""
        from lifeprism.repository import deletion_log_repository

        # Arrange: 插入 2 条墓碑
        # 旧墓碑（created_at 早于 last_sync_time）
        deletion_log_repository.create_tombstone(
            "mood_entries", "mood-old01", source="local", created_at="2026-07-01T00:00:00+00:00"
        )
        # 新墓碑（created_at 晚于 last_sync_time）
        deletion_log_repository.create_tombstone(
            "mood_entries", "mood-new01", source="local", created_at="2026-07-23T20:00:00+00:00"
        )

        last_sync_time = "2026-07-22T00:00:00+00:00"

        with patch("lifeprism.sync.sync_client.httpx.post") as mock_post:
            mock_post.return_value = _make_mock_response(
                {"success": True, "cleaned_count": 1}
            )

            # Act
            sync_client._cleanup_deletion_log("http://remote", "api-key", last_sync_time)

        # Assert: 本地仅旧墓碑被清理，新墓碑保留
        tombstones = _get_tombstones(initialized_db, "mood_entries")
        assert len(tombstones) == 1
        assert tombstones[0]["record_id"] == "mood-new01"

        # Assert: httpx cleanup 端点被调用
        mock_post.assert_called_once()
        call_url = mock_post.call_args[1].get("url") or mock_post.call_args[0][0]
        assert "cleanup-deletion-log" in call_url


# ==================== 动态表与级联删除 ====================


class TestDynamicAndCascade:
    """动态表与级联删除测试"""

    def test_dynamic_table_delete_writes_tombstone(
        self, initialized_db, clean_custom_records
    ):
        """场景 10: 动态表删除写墓碑（custom_record_aggregator）"""
        from lifeprism.repository import custom_record_repository

        # Arrange: 创建自定义记录类型
        type_id = custom_record_repository.create_type(
            name="测试类型",
            slug="testdyn",
            fields=[{"field_name": "值", "field_key": "value", "field_type": "text"}],
        )

        # 录入 entry
        entry_id = custom_record_repository.create_entry(type_id, {"value": "test"})

        # Act: 删除 entry
        result = custom_record_repository.delete_entry(type_id, entry_id)

        # Assert: 删除成功
        assert result is True

        # Assert: deletion_log 新增 1 条
        tombstones = _get_tombstones(initialized_db, "custom_testdyn")
        assert len(tombstones) == 1
        assert tombstones[0]["record_id"] == entry_id
        assert tombstones[0]["source"] == "local"

        # Assert: 记录已物理删除
        assert _count_records(initialized_db, "custom_testdyn", "id", entry_id) == 0

    def test_delete_nonexistent_entry_no_orphan_tombstone(
        self, initialized_db, clean_custom_records
    ):
        """场景 11: delete_entry 不存在记录不产生孤儿墓碑"""
        from lifeprism.repository import custom_record_repository
        from lifeprism.repository.exceptions import EntityNotFoundError

        # Arrange: 创建类型
        type_id = custom_record_repository.create_type(
            name="测试类型",
            slug="testorphan",
            fields=[{"field_name": "值", "field_key": "value", "field_type": "text"}],
        )

        # Act: 删除不存在的 entry
        with pytest.raises(EntityNotFoundError):
            custom_record_repository.delete_entry(type_id, "cre-nonexist")

        # Assert: deletion_log 无新增
        tombstones = _get_tombstones(initialized_db, "custom_testorphan")
        assert len(tombstones) == 0

    def test_cascade_delete_propagates_all_tables(
        self, initialized_db, sync_client, clean_tables
    ):
        """场景 12: 级联删除同步传播所有级联表"""
        from lifeprism.repository import habit_repository

        # Arrange: 插入 habit + habit_challenges + habit_checkins 各 1 条
        now = datetime.now(timezone.utc).isoformat()
        with initialized_db.get_connection() as conn:
            conn.execute(
                "INSERT INTO habits (id, name, frequency_type, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("habit-cascade01", "测试习惯", "daily", now, now),
            )
            conn.execute(
                "INSERT INTO habit_challenges "
                "(id, habit_id, challenge_weeks, required_completions, from_level, to_level, "
                "start_date, end_date, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "hc-cascade01",
                    "habit-cascade01",
                    4,
                    3,
                    0,
                    1,
                    "2026-07-01",
                    "2026-07-29",
                    now,
                    now,
                ),
            )
            conn.execute(
                "INSERT INTO habit_checkins "
                "(id, habit_id, challenge_id, date, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("hci-cascade01", "habit-cascade01", "hc-cascade01", "2026-07-23", now, now),
            )
            conn.commit()

        # 逐表删除（模拟调用方级联删除，各写墓碑）
        habit_repository.delete_habit("habit-cascade01")
        habit_repository.delete_challenge_by_habit("habit-cascade01")
        habit_repository.delete_checkin_by_habit("habit-cascade01")

        # Act: Push
        with patch("lifeprism.sync.sync_client.httpx.post") as mock_post:
            mock_post.return_value = _make_mock_response(
                {"success": True, "applied_count": 3, "skipped_count": 0}
            )
            sync_client._push_deletion_log("http://remote", "api-key", "")

        # Assert: payload 含 3 条墓碑
        mock_post.assert_called_once()
        payload = mock_post.call_args[1].get("json") or mock_post.call_args[0].get("json")
        target_tables = {t["target_table"] for t in payload["tombstones"]}
        assert target_tables == {"habits", "habit_challenges", "habit_checkins"}
        assert len(payload["tombstones"]) == 3


# ==================== 边界场景 ====================


class TestEdgeCases:
    """边界场景测试"""

    def test_reset_last_sync_time_tombstone_still_works(
        self, initialized_db, sync_client, clean_tables
    ):
        """场景 13: 重置 last_sync_time 后墓碑仍工作（US19）"""
        from lifeprism.repository import deletion_log_repository

        # Arrange: 插入若干墓碑
        deletion_log_repository.create_tombstone(
            "mood_entries", "mood-reset01", source="local"
        )
        deletion_log_repository.create_tombstone(
            "mood_entries", "mood-reset02", source="cloud"
        )

        # Act: last_sync_time="" 模拟重置
        with patch("lifeprism.sync.sync_client.httpx.post") as mock_post:
            mock_post.return_value = _make_mock_response(
                {"success": True, "applied_count": 2, "skipped_count": 0}
            )
            sync_client._push_deletion_log("http://remote", "api-key", "")

        # Assert: get_tombstones_since("") 返回所有未清理墓碑，httpx 被调用
        mock_post.assert_called_once()
        payload = mock_post.call_args[1].get("json") or mock_post.call_args[0].get("json")
        # 只推送 source=local 的墓碑
        local_tombstones = [t for t in payload["tombstones"] if t["source"] == "local"]
        assert len(local_tombstones) >= 1

    def test_full_sync_does_not_propagate_tombstones(
        self, initialized_db, sync_client, clean_tables
    ):
        """场景 14: 全量首同步不传播墓碑（US20）"""
        from lifeprism.config.settings_manager import set_setting

        # Arrange: 设置配置
        set_setting("sync.remote_url", "http://remote")
        set_setting("sync.sync_api_key", "test-key")

        with (
            patch.object(sync_client, "_check_cloud_initialized", return_value=False),
            patch.object(sync_client, "_full_sync_to_cloud") as mock_full_sync,
            patch.object(sync_client, "_pull_deletion_log") as mock_pull,
            patch.object(sync_client, "_push_deletion_log") as mock_push,
            patch.object(sync_client, "_cleanup_deletion_log") as mock_cleanup,
            patch("lifeprism.sync.sync_config.get_sync_api_key", return_value="test-key"),
        ):
            # Act: 触发首同步路径
            sync_client.sync_once()

        # Assert: _full_sync_to_cloud 被调用
        mock_full_sync.assert_called_once()

        # Assert: 墓碑方法均未被调用
        mock_pull.assert_not_called()
        mock_push.assert_not_called()
        mock_cleanup.assert_not_called()


# ==================== 多表批量删除 ====================


class TestBatchDelete:
    """多表批量删除测试"""

    def test_multi_table_batch_delete_sync(
        self, initialized_db, sync_client, clean_tables
    ):
        """场景 15: 多表批量删除同步"""
        from lifeprism.repository import mood_repository, custom_block_repository

        # Arrange: 删除 mood_entries + timeline_custom_block + diary 各 1 条
        _insert_mood_entry(initialized_db, entry_id="mood-batch01")
        mood_repository.delete_mood_entry("mood-batch01")

        block = custom_block_repository.create_custom_block(
            {
                "content": "batch block",
                "start_time": "2026-07-23T10:00:00+00:00",
                "end_time": "2026-07-23T11:00:00+00:00",
                "duration": 3600,
                "color": "#ff0000",
                "category_id": 1,
                "sub_category_id": 1,
            }
        )
        custom_block_repository.delete_custom_block(block["id"])

        _insert_diary(initialized_db, date_str="2026-07-23")
        from lifeprism.repository import diary_repository
        diary_repository.delete_diary("2026-07-23")

        # Act: Push
        with patch("lifeprism.sync.sync_client.httpx.post") as mock_post:
            mock_post.return_value = _make_mock_response(
                {"success": True, "applied_count": 3, "skipped_count": 0}
            )
            sync_client._push_deletion_log("http://remote", "api-key", "")

        # Assert: payload 含 3 条墓碑
        mock_post.assert_called_once()
        payload = mock_post.call_args[1].get("json") or mock_post.call_args[0].get("json")
        target_tables = {t["target_table"] for t in payload["tombstones"]}
        assert "mood_entries" in target_tables
        assert "timeline_custom_block" in target_tables
        assert "diary" in target_tables
        assert len(payload["tombstones"]) == 3


# ==================== 空场景 ====================


class TestEmptyScenarios:
    """空场景测试"""

    def test_empty_tombstone_pull_and_push(
        self, initialized_db, sync_client, clean_tables
    ):
        """场景 16: 空墓碑 Pull/Push 不报错"""
        # Pull: mock httpx 返回空 tombstones
        with patch("lifeprism.sync.sync_client.httpx.post") as mock_post:
            mock_post.return_value = _make_mock_response({"tombstones": []})
            # 不应抛异常
            sync_client._pull_deletion_log("http://remote", "api-key", "")

        # Assert: httpx 被调用（Pull 总是发起请求）
        assert mock_post.call_count == 1

        # Push: 本地无 source=local 墓碑
        with patch("lifeprism.sync.sync_client.httpx.post") as mock_post_push:
            sync_client._push_deletion_log("http://remote", "api-key", "")

        # Assert: httpx 不被调用（本地查询为空时提前返回）
        mock_post_push.assert_not_called()
