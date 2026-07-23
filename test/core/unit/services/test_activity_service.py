"""
activity_service 单记录操作迁移测试（Slice 03）

验证 activity_service 中 3 个单记录方法从 server_lw_data_provider 迁移到
computer_usage_repository 后的行为正确性。

被测方法：
1. get_activity_log_detail → computer_usage_repository.get_computer_usage_by_id_with_names
2. update_log_category → computer_usage_repository.update_computer_usage（含 updated_at bug 修复）
3. delete_log → computer_usage_repository.delete_computer_usage（含写墓碑）

依据 issue: .scratch/deletion-sync-02a-statistical/issues/03-activity-service-single-record-migration.md
依据 PRD: .scratch/deletion-sync-02a-statistical/prd.md
"""

import pytest

from lifeprism.server.services import activity_service

pytestmark = pytest.mark.core


# ==================== 共用工具函数 ====================


def _create_user_app_behavior_log(db):
    """创建 user_app_behavior_log 表（含 hash_id 字段，按 USER_APP_BEHAVIOR_LOG_CONFIG schema）"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_app_behavior_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash_id TEXT NOT NULL UNIQUE,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                duration INTEGER,
                app TEXT NOT NULL,
                title TEXT,
                is_multipurpose_app INTEGER DEFAULT 0,
                category_id TEXT,
                sub_category_id TEXT,
                link_to_goal_id TEXT DEFAULT NULL,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(app, start_time),
                CHECK(end_time > start_time)
            )
            """
        )
        conn.commit()


def _create_category_tables(db):
    """创建 category / sub_category 表（aggregator 关联查询用）"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS category (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                color TEXT NOT NULL,
                state INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sub_category (
                id TEXT PRIMARY KEY,
                category_id TEXT NOT NULL,
                name TEXT NOT NULL,
                state INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.commit()


def _create_deletion_log(db):
    """创建 deletion_log 表（验证写墓碑用）"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS deletion_log (
                id TEXT PRIMARY KEY,
                target_table TEXT NOT NULL,
                record_id TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(target_table, record_id)
            )
            """
        )
        conn.commit()


def _clear_tables(db, table_names):
    """清理指定表的数据"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        for name in table_names:
            cursor.execute(f"DELETE FROM {name}")
        conn.commit()


def _insert_category(db, category_id, name, color="#5B8FF9"):
    """插入一条 category 记录"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO category (id, name, color) VALUES (?, ?, ?)",
            (category_id, name, color),
        )
        conn.commit()


def _insert_sub_category(db, sub_id, category_id, name):
    """插入一条 sub_category 记录"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sub_category (id, category_id, name) VALUES (?, ?, ?)",
            (sub_id, category_id, name),
        )
        conn.commit()


def _insert_log_via_generic_insert(provider, **kwargs):
    """通过 _generic_insert 插入测试记录，返回 record_id（字符串）

    自动生成 hash_id / created_at / updated_at。
    """
    defaults = {
        "start_time": "2026-07-23T10:00:00.000000+00:00",
        "end_time": "2026-07-23T11:00:00.000000+00:00",
        "duration": 3600,
        "app": "test_app.exe",
        "title": "Test Title",
        "is_multipurpose_app": 0,
    }
    defaults.update(kwargs)
    return provider._generic_insert(defaults)


def _query_single_field(db, field, table, where_clause, params):
    """查询单个字段值（用于断言验证）"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT {field} FROM {table} WHERE {where_clause}",
            params,
        )
        row = cursor.fetchone()
    return row[0] if row else None


def _count_tombstones(db, target_table):
    """查询 deletion_log 中的墓碑数量"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM deletion_log WHERE target_table = ?",
            (target_table,),
        )
        return cursor.fetchone()[0]


def _get_tombstone_record_ids(db, target_table):
    """查询 deletion_log 中指定表的所有墓碑 record_id"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT record_id FROM deletion_log WHERE target_table = ?",
            (target_table,),
        )
        return [row[0] for row in cursor.fetchall()]


# ==================== Fixtures ====================


@pytest.fixture
def service_fixture(test_data_path):
    """初始化测试环境：创建表 + 清理数据 + 刷新 category 缓存

    使用模块级 computer_usage_repository 单例（与 activity_service 相同的实例），
    确保 activity_service 调用的就是测试中设置的数据。
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.repository import computer_usage_repository

    settings._initialize()

    db = computer_usage_repository.computer_usage_provider.db

    # 创建测试所需的表
    _create_user_app_behavior_log(db)
    _create_category_tables(db)
    _create_deletion_log(db)

    # 清理旧数据
    _clear_tables(db, ["user_app_behavior_log", "category", "sub_category", "deletion_log"])

    yield computer_usage_repository

    # 清理表数据
    _clear_tables(db, ["user_app_behavior_log", "category", "sub_category", "deletion_log"])


# ==================== 1. get_activity_log_detail 测试 ====================


class TestGetActivityLogDetail:
    """get_activity_log_detail 迁移后行为测试"""

    def test_returns_none_when_not_found(self, service_fixture):
        """不存在的 ID 返回 None"""
        result = activity_service.get_activity_log_detail("99999")
        assert result is None

    def test_returns_log_with_category_names(self, service_fixture):
        """存在的 ID 返回日志详情，含 category_name / sub_category_name"""
        repo = service_fixture
        db = repo.computer_usage_provider.db

        # 插入分类数据
        _insert_category(db, "cat-1", "工作")
        _insert_sub_category(db, "sub-1", "cat-1", "编程")
        # 刷新 aggregator 的分类缓存
        repo._refresh_cache()

        # 插入日志记录（通过 _generic_insert 自动生成 hash_id）
        record_id = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="code.exe",
            title="main.py",
            category_id="cat-1",
            sub_category_id="sub-1",
        )

        result = activity_service.get_activity_log_detail(str(record_id))

        assert result is not None
        assert result.id == str(record_id)
        assert result.start_time == "2026-07-12T02:00:00+00:00"
        assert result.end_time == "2026-07-12T03:00:00+00:00"
        assert result.duration == 3600
        assert result.app == "code.exe"
        assert result.title == "main.py"
        assert result.category_id == "cat-1"
        assert result.category == "工作"
        assert result.sub_category_id == "sub-1"
        assert result.sub_category == "编程"

    def test_returns_log_without_category(self, service_fixture):
        """无分类的日志，category_id / category 为 None"""
        repo = service_fixture
        repo._refresh_cache()

        record_id = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="unknown.exe",
        )

        result = activity_service.get_activity_log_detail(str(record_id))

        assert result is not None
        assert result.category_id is None
        assert result.category is None
        assert result.sub_category_id is None
        assert result.sub_category is None

    def test_does_not_use_server_lw_data_provider(self, service_fixture, monkeypatch):
        """验证不通过 server_lw_data_provider 调用（迁移验证）

        如果 activity_service 仍调用 server_lw_data_provider.get_activity_log_by_id，
        此测试会因 RuntimeError 而失败。
        """
        from lifeprism.server.providers import server_lw_data_provider

        def _explode(*args, **kwargs):
            raise RuntimeError("server_lw_data_provider.get_activity_log_by_id 不应被调用")

        monkeypatch.setattr(server_lw_data_provider, "get_activity_log_by_id", _explode)

        repo = service_fixture
        repo._refresh_cache()
        record_id = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="not_via_provider.exe",
        )

        # 如果仍走 server_lw_data_provider，会抛 RuntimeError
        result = activity_service.get_activity_log_detail(str(record_id))
        assert result is not None
        assert result.app == "not_via_provider.exe"


# ==================== 2. update_log_category 测试 ====================


class TestUpdateLogCategory:
    """update_log_category 迁移后行为测试（含 updated_at bug 修复）"""

    def test_updates_category_successfully(self, service_fixture):
        """更新存在的记录返回 True，字段被更新"""
        repo = service_fixture
        record_id = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="code.exe",
        )

        result = activity_service.update_log_category(str(record_id), "cat-1", "sub-1")

        assert result is True
        log = activity_service.get_activity_log_detail(str(record_id))
        assert log.category_id == "cat-1"
        assert log.sub_category_id == "sub-1"

    def test_returns_false_when_not_found(self, service_fixture):
        """更新不存在的记录返回 False（保持原 API 契约）

        迁移后底层 update_by_filter 返回 rowcount=0，
        Service 层据此返回 False。
        """
        result = activity_service.update_log_category("99999", "cat-1", None)
        assert result is False

    def test_none_sub_category_clears_to_null(self, service_fixture):
        """sub_category_id=None 清除为 NULL（前端"选择 -- Select --"场景）

        验证修复后行为：None → 清除为 NULL（而非跳过不修改）。
        先插入有 sub_category_id 的记录，再更新时传 None，验证被清除。
        """
        repo = service_fixture
        record_id = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="code.exe",
            category_id="cat-original",
            sub_category_id="sub-original",
        )

        # 更新时 sub_category_id=None → 应清除为 NULL
        result = activity_service.update_log_category(str(record_id), "cat-new", None)

        assert result is True
        log = activity_service.get_activity_log_detail(str(record_id))
        assert log.category_id == "cat-new"
        assert log.sub_category_id is None  # 被清除为 NULL

    def test_auto_updates_updated_at_bugfix(self, service_fixture):
        """bug 修复验证：迁移后 updated_at 字段被显式更新

        依据 PRD "update_event_category 的 updated_at 行为变化"：
        原方法用原生 SQL UPDATE，不更新 updated_at；
        迁移到 update_by_filter 后显式传入 updated_at，触发云端 LWW 同步。
        """
        repo = service_fixture
        db = repo.computer_usage_provider.db

        record_id = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="code.exe",
        )

        # 设置初始 updated_at（一个明显旧的时间）
        original_updated_at = "2026-01-01T00:00:00+00:00"
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE user_app_behavior_log SET updated_at = ? WHERE id = ?",
                (original_updated_at, record_id),
            )
            conn.commit()

        # 执行分类更新
        activity_service.update_log_category(str(record_id), "cat-1", None)

        # 验证：updated_at 应被自动更新（不等于原值）
        updated_at = _query_single_field(
            db, "updated_at", "user_app_behavior_log", "id = ?", (record_id,)
        )
        assert updated_at != original_updated_at, (
            f"bug 修复：updated_at 应被自动更新，原值 {original_updated_at}，实际 {updated_at}"
        )

    def test_does_not_use_server_lw_data_provider(self, service_fixture, monkeypatch):
        """验证不通过 server_lw_data_provider 调用（迁移验证）"""
        from lifeprism.server.providers import server_lw_data_provider

        def _explode(*args, **kwargs):
            raise RuntimeError("server_lw_data_provider.update_event_category 不应被调用")

        monkeypatch.setattr(server_lw_data_provider, "update_event_category", _explode)

        repo = service_fixture
        record_id = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="not_via_provider.exe",
        )

        # 如果仍走 server_lw_data_provider，会抛 RuntimeError
        result = activity_service.update_log_category(str(record_id), "cat-1", None)
        assert result is True


# ==================== 3. delete_log 测试 ====================


class TestDeleteLog:
    """delete_log 迁移后行为测试（含写墓碑到 deletion_log）"""

    def test_deletes_existing_event(self, service_fixture):
        """删除存在的记录返回 True，记录消失"""
        repo = service_fixture
        record_id = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="code.exe",
        )

        result = activity_service.delete_log(str(record_id))

        assert result is True
        assert activity_service.get_activity_log_detail(str(record_id)) is None

    def test_returns_false_when_not_found(self, service_fixture):
        """删除不存在的记录返回 False"""
        result = activity_service.delete_log("99999")
        assert result is False

    def test_writes_tombstone_to_deletion_log(self, service_fixture):
        """迁移后删除时写墓碑到 deletion_log 表（record_id = hash_id）

        依据 issue 验收标准：delete_log 迁移后删除时写墓碑到 deletion_log 表。
        AUTOINCREMENT 表（user_app_behavior_log）的墓碑 record_id 使用 hash_id。
        """
        repo = service_fixture
        db = repo.computer_usage_provider.db

        record_id = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="tombstone_test.exe",
        )
        # 获取 hash_id（墓碑 record_id 应为 hash_id）
        record = repo.get_computer_usage_by_id(str(record_id))
        hash_id = record["hash_id"]

        # 删除前：deletion_log 应无墓碑
        assert _count_tombstones(db, "user_app_behavior_log") == 0

        # 执行删除
        activity_service.delete_log(str(record_id))

        # 验证：deletion_log 应有 1 条墓碑
        count = _count_tombstones(db, "user_app_behavior_log")
        assert count == 1, f"应写入 1 条墓碑，实际: {count}"

        # 验证：墓碑 record_id = hash_id
        tombstone_record_ids = _get_tombstone_record_ids(db, "user_app_behavior_log")
        assert hash_id in tombstone_record_ids, (
            f"墓碑 record_id 应为 hash_id '{hash_id}'，实际: {tombstone_record_ids}"
        )

    def test_does_not_use_server_lw_data_provider(self, service_fixture, monkeypatch):
        """验证不通过 server_lw_data_provider 调用（迁移验证）"""
        from lifeprism.server.providers import server_lw_data_provider

        def _explode(*args, **kwargs):
            raise RuntimeError("server_lw_data_provider.delete_event 不应被调用")

        monkeypatch.setattr(server_lw_data_provider, "delete_event", _explode)

        repo = service_fixture
        record_id = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="not_via_provider.exe",
        )

        # 如果仍走 server_lw_data_provider，会抛 RuntimeError
        result = activity_service.delete_log(str(record_id))
        assert result is True


# ==================== 4. batch_update_log_category 测试 ====================


class TestBatchUpdateLogCategory:
    """batch_update_log_category 迁移后行为测试

    迁移路径：server_lw_data_provider.batch_update_event_category
              → computer_usage_repository.batch_update_computer_usage
    """

    def test_batch_updates_multiple_logs(self, service_fixture):
        """批量更新多条记录，返回更新数量，字段被更新"""
        repo = service_fixture
        id1 = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="app1.exe",
        )
        id2 = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T03:00:00+00:00",
            end_time="2026-07-12T04:00:00+00:00",
            duration=3600,
            app="app2.exe",
        )
        id3 = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T04:00:00+00:00",
            end_time="2026-07-12T05:00:00+00:00",
            duration=3600,
            app="app3.exe",
        )

        result = activity_service.batch_update_log_category(
            [str(id1), str(id2), str(id3)], "cat-1", "sub-1"
        )

        assert result == 3
        for rid in [id1, id2, id3]:
            log = activity_service.get_activity_log_detail(str(rid))
            assert log.category_id == "cat-1"
            assert log.sub_category_id == "sub-1"

    def test_empty_list_returns_zero(self, service_fixture):
        """空列表返回 0"""
        result = activity_service.batch_update_log_category([], "cat-1", None)
        assert result == 0

    def test_partial_match_returns_count(self, service_fixture):
        """部分 ID 不存在时，返回实际更新数量"""
        repo = service_fixture
        id1 = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="app1.exe",
        )

        result = activity_service.batch_update_log_category([str(id1), "99999"], "cat-1", None)

        assert result == 1

    def test_none_sub_category_clears_to_null_batch(self, service_fixture):
        """批量更新时 sub_category_id=None 清除为 NULL

        验证修复后行为：None → 清除为 NULL（而非跳过不修改）。
        """
        repo = service_fixture
        id1 = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="app1.exe",
            category_id="cat-original",
            sub_category_id="sub-original",
        )
        id2 = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T03:00:00+00:00",
            end_time="2026-07-12T04:00:00+00:00",
            duration=3600,
            app="app2.exe",
            category_id="cat-original",
            sub_category_id="sub-original",
        )

        # 批量更新时 sub_category_id=None → 应清除为 NULL
        result = activity_service.batch_update_log_category([str(id1), str(id2)], "cat-new", None)

        assert result == 2
        for rid in [id1, id2]:
            log = activity_service.get_activity_log_detail(str(rid))
            assert log.category_id == "cat-new"
            assert log.sub_category_id is None  # 被清除为 NULL

    def test_auto_updates_updated_at_batch(self, service_fixture):
        """批量更新时 updated_at 被显式更新（bug 修复，与单条一致）"""
        repo = service_fixture
        db = repo.computer_usage_provider.db

        id1 = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="app1.exe",
        )

        # 设置初始 updated_at（一个明显旧的时间）
        original_updated_at = "2026-01-01T00:00:00+00:00"
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE user_app_behavior_log SET updated_at = ? WHERE id = ?",
                (original_updated_at, id1),
            )
            conn.commit()

        # 执行批量分类更新
        activity_service.batch_update_log_category([str(id1)], "cat-1", None)

        # 验证：updated_at 应被显式更新（不等于原值）
        updated_at = _query_single_field(
            db, "updated_at", "user_app_behavior_log", "id = ?", (id1,)
        )
        assert updated_at != original_updated_at, (
            f"bug 修复：批量更新 updated_at 应被显式更新，"
            f"原值 {original_updated_at}，实际 {updated_at}"
        )

    def test_does_not_use_server_lw_data_provider(self, service_fixture, monkeypatch):
        """验证不通过 server_lw_data_provider 调用（迁移验证）"""
        from lifeprism.server.providers import server_lw_data_provider

        def _explode(*args, **kwargs):
            raise RuntimeError("server_lw_data_provider.batch_update_event_category 不应被调用")

        monkeypatch.setattr(server_lw_data_provider, "batch_update_event_category", _explode)

        repo = service_fixture
        record_id = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="not_via_provider.exe",
        )

        result = activity_service.batch_update_log_category([str(record_id)], "cat-1", None)
        assert result == 1


# ==================== 5. batch_delete_logs 测试 ====================


class TestBatchDeleteLogs:
    """batch_delete_logs 迁移后行为测试（含写墓碑到 deletion_log）

    迁移路径：server_lw_data_provider.batch_delete_events（原生 SQL DELETE，无墓碑）
              → computer_usage_repository.batch_delete_computer_usage
              （走 _generic_batch_delete，N 条记录对应 N 条墓碑）
    """

    def test_batch_deletes_multiple_logs(self, service_fixture):
        """批量删除多条记录，返回删除数量，记录消失"""
        repo = service_fixture
        id1 = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="app1.exe",
        )
        id2 = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T03:00:00+00:00",
            end_time="2026-07-12T04:00:00+00:00",
            duration=3600,
            app="app2.exe",
        )
        id3 = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T04:00:00+00:00",
            end_time="2026-07-12T05:00:00+00:00",
            duration=3600,
            app="app3.exe",
        )

        result = activity_service.batch_delete_logs([str(id1), str(id2), str(id3)])

        assert result == 3
        for rid in [id1, id2, id3]:
            assert activity_service.get_activity_log_detail(str(rid)) is None

    def test_writes_n_tombstones_for_n_records(self, service_fixture):
        """批量删除 N 条记录时写 N 条墓碑到 deletion_log（record_id = hash_id）

        依据 issue 验收标准：batch_delete_logs 迁移后批量删除时写墓碑到
        deletion_log 表（N 条记录对应 N 条墓碑）。
        AUTOINCREMENT 表（user_app_behavior_log）的墓碑 record_id 使用 hash_id。
        """
        repo = service_fixture
        db = repo.computer_usage_provider.db

        id1 = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="tomb1.exe",
        )
        id2 = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T03:00:00+00:00",
            end_time="2026-07-12T04:00:00+00:00",
            duration=3600,
            app="tomb2.exe",
        )
        id3 = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T04:00:00+00:00",
            end_time="2026-07-12T05:00:00+00:00",
            duration=3600,
            app="tomb3.exe",
        )
        # 收集 hash_id（墓碑 record_id 应为 hash_id）
        hash_ids = []
        for rid in [id1, id2, id3]:
            record = repo.get_computer_usage_by_id(str(rid))
            hash_ids.append(record["hash_id"])

        # 删除前：deletion_log 应无墓碑
        assert _count_tombstones(db, "user_app_behavior_log") == 0

        # 执行批量删除
        activity_service.batch_delete_logs([str(id1), str(id2), str(id3)])

        # 验证：deletion_log 应有 3 条墓碑
        count = _count_tombstones(db, "user_app_behavior_log")
        assert count == 3, f"应写入 3 条墓碑，实际: {count}"

        # 验证：墓碑 record_id 集合 = hash_id 集合
        tombstone_record_ids = _get_tombstone_record_ids(db, "user_app_behavior_log")
        assert set(tombstone_record_ids) == set(hash_ids), (
            f"墓碑 record_id 应为 hash_id 集合 {hash_ids}，实际: {tombstone_record_ids}"
        )

    def test_empty_list_returns_zero(self, service_fixture):
        """空列表返回 0"""
        result = activity_service.batch_delete_logs([])
        assert result == 0

    def test_partial_match_returns_count(self, service_fixture):
        """部分 ID 不存在时，返回实际删除数量"""
        repo = service_fixture
        id1 = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="app1.exe",
        )

        result = activity_service.batch_delete_logs([str(id1), "99999"])

        assert result == 1
        assert activity_service.get_activity_log_detail(str(id1)) is None

    def test_does_not_use_server_lw_data_provider(self, service_fixture, monkeypatch):
        """验证不通过 server_lw_data_provider 调用（迁移验证）"""
        from lifeprism.server.providers import server_lw_data_provider

        def _explode(*args, **kwargs):
            raise RuntimeError("server_lw_data_provider.batch_delete_events 不应被调用")

        monkeypatch.setattr(server_lw_data_provider, "batch_delete_events", _explode)

        repo = service_fixture
        record_id = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="not_via_provider.exe",
        )

        # 如果仍走 server_lw_data_provider，会抛 RuntimeError
        result = activity_service.batch_delete_logs([str(record_id)])
        assert result == 1


# ==================== 6. update_logs_by_app_title 测试 ====================


class TestUpdateLogsByAppTitle:
    """update_logs_by_app_title 迁移后行为测试

    迁移路径：server_lw_data_provider.update_logs_by_app_title
              → computer_usage_repository.update_by_filter(set_fields, where_conditions)

    2 类业务逻辑上移到 Service 层：
    1. goal_id 三态语义（None=不修改 / ""=清除为 NULL / "goal-xxx"=设置值）
    2. is_multipurpose_app 判断（True=加 title 条件 / False=不加）
    """

    def test_single_purpose_app_matches_by_app_only(self, service_fixture):
        """单用途应用：仅按 app 匹配（忽略 title）"""
        repo = service_fixture
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="code.exe",
            title="main.py",
        )
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T03:00:00+00:00",
            end_time="2026-07-12T04:00:00+00:00",
            duration=3600,
            app="code.exe",
            title="other.py",
        )
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T04:00:00+00:00",
            end_time="2026-07-12T05:00:00+00:00",
            duration=3600,
            app="other.exe",
            title="main.py",
        )

        result = activity_service.update_logs_by_app_title(
            app="code.exe",
            title=None,
            is_multipurpose_app=False,
            category_id="cat-1",
            sub_category_id="sub-1",
        )

        # 应更新 2 条（app=code.exe 的两条）
        assert result == 2

        # 验证：code.exe 的两条都被更新
        db = repo.computer_usage_provider.db
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT category_id, sub_category_id FROM user_app_behavior_log WHERE app = 'code.exe'"
            )
            rows = cursor.fetchall()
        assert len(rows) == 2
        for row in rows:
            assert tuple(row) == ("cat-1", "sub-1")

    def test_multi_purpose_app_matches_by_app_and_title(self, service_fixture):
        """多用途应用：按 app + title 匹配"""
        repo = service_fixture
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="browser.exe",
            title="work",
        )
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T03:00:00+00:00",
            end_time="2026-07-12T04:00:00+00:00",
            duration=3600,
            app="browser.exe",
            title="play",
        )

        result = activity_service.update_logs_by_app_title(
            app="browser.exe",
            title="work",
            is_multipurpose_app=True,
            category_id="cat-1",
        )

        # 应只更新 1 条（app=browser.exe + title=work）
        assert result == 1

        # 验证：只有 title=work 的记录被更新
        db = repo.computer_usage_provider.db
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT title, category_id FROM user_app_behavior_log WHERE app = 'browser.exe' ORDER BY title"
            )
            rows = cursor.fetchall()
        assert tuple(rows[0]) == ("play", None)  # 未更新
        assert tuple(rows[1]) == ("work", "cat-1")  # 已更新

    def test_multi_purpose_app_without_title_raises(self, service_fixture):
        """多用途应用未提供 title 时抛出 ValueError"""
        with pytest.raises(ValueError, match="多用途应用必须提供 title 参数"):
            activity_service.update_logs_by_app_title(
                app="browser.exe",
                title=None,
                is_multipurpose_app=True,
                category_id="cat-1",
            )

    # ---------- goal_id 三态语义测试（3 个用例）----------

    def test_goal_id_none_does_not_modify_link_to_goal_id(self, service_fixture):
        """goal_id=None：不修改 link_to_goal_id（三态之一：不修改）"""
        repo = service_fixture
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="code.exe",
            link_to_goal_id="goal-original",
        )

        activity_service.update_logs_by_app_title(
            app="code.exe",
            title=None,
            is_multipurpose_app=False,
            category_id="cat-1",
            goal_id=None,  # 不修改
        )

        db = repo.computer_usage_provider.db
        goal = _query_single_field(
            db,
            "link_to_goal_id",
            "user_app_behavior_log",
            "app = 'code.exe'",
            (),
        )
        assert goal == "goal-original"

    def test_goal_id_empty_string_clears_link_to_goal_id(self, service_fixture):
        """goal_id=''：清除 link_to_goal_id（设为 NULL）（三态之二：清除）

        update_by_filter 的 set_fields 中 None = 清除为 NULL（与
        update_computer_usage 的 None = 跳过不同），这正是 goal_id 三态
        语义所需要的。
        """
        repo = service_fixture
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="code.exe",
            link_to_goal_id="goal-original",
        )

        activity_service.update_logs_by_app_title(
            app="code.exe",
            title=None,
            is_multipurpose_app=False,
            category_id="cat-1",
            goal_id="",  # 清除
        )

        db = repo.computer_usage_provider.db
        goal = _query_single_field(
            db,
            "link_to_goal_id",
            "user_app_behavior_log",
            "app = 'code.exe'",
            (),
        )
        assert goal is None

    def test_goal_id_value_sets_link_to_goal_id(self, service_fixture):
        """goal_id='goal-xxx'：设置 link_to_goal_id（三态之三：设置值）"""
        repo = service_fixture
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="code.exe",
            link_to_goal_id=None,
        )

        activity_service.update_logs_by_app_title(
            app="code.exe",
            title=None,
            is_multipurpose_app=False,
            category_id="cat-1",
            goal_id="goal-new",  # 设置
        )

        db = repo.computer_usage_provider.db
        goal = _query_single_field(
            db,
            "link_to_goal_id",
            "user_app_behavior_log",
            "app = 'code.exe'",
            (),
        )
        assert goal == "goal-new"

    # ---------- 时间范围测试 ----------

    def test_time_range_filter(self, service_fixture):
        """按时间范围过滤匹配（start_time >= 过滤）"""
        repo = service_fixture
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="code.exe",
        )
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-13T02:00:00+00:00",
            end_time="2026-07-13T03:00:00+00:00",
            duration=3600,
            app="code.exe",
        )

        # 只更新 2026-07-13 之后的
        result = activity_service.update_logs_by_app_title(
            app="code.exe",
            title=None,
            is_multipurpose_app=False,
            category_id="cat-1",
            start_time="2026-07-13T00:00:00+00:00",
        )

        # 应只更新 1 条（2026-07-13 的那条）
        assert result == 1

    # ---------- 迁移验证测试 ----------

    def test_does_not_use_server_lw_data_provider(self, service_fixture, monkeypatch):
        """验证不通过 server_lw_data_provider 调用（迁移验证）"""
        from lifeprism.server.providers import server_lw_data_provider

        def _explode(*args, **kwargs):
            raise RuntimeError("server_lw_data_provider.update_logs_by_app_title 不应被调用")

        monkeypatch.setattr(server_lw_data_provider, "update_logs_by_app_title", _explode)

        repo = service_fixture
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="not_via_provider.exe",
        )

        # 如果仍走 server_lw_data_provider，会抛 RuntimeError
        result = activity_service.update_logs_by_app_title(
            app="not_via_provider.exe",
            title=None,
            is_multipurpose_app=False,
            category_id="cat-1",
        )
        assert result == 1

    def test_auto_updates_updated_at(self, service_fixture):
        """update_logs_by_app_title 也应更新 updated_at（LWW 同步修复）

        验证 Issue 6 修复：set_fields 中显式传入 updated_at。
        """
        repo = service_fixture
        db = repo.computer_usage_provider.db

        record_id = _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="app_for_updated_at.exe",
        )

        # 设置初始 updated_at（一个明显旧的时间）
        original_updated_at = "2026-01-01T00:00:00+00:00"
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE user_app_behavior_log SET updated_at = ? WHERE id = ?",
                (original_updated_at, record_id),
            )
            conn.commit()

        # 执行按应用标题批量更新
        activity_service.update_logs_by_app_title(
            app="app_for_updated_at.exe",
            title=None,
            is_multipurpose_app=False,
            category_id="cat-new",
        )

        # 验证：updated_at 应被显式更新（不等于原值）
        updated_at = _query_single_field(
            db, "updated_at", "user_app_behavior_log", "id = ?", (record_id,)
        )
        assert updated_at != original_updated_at, (
            f"Issue 6 修复：update_logs_by_app_title 应更新 updated_at，"
            f"原值 {original_updated_at}，实际 {updated_at}"
        )
