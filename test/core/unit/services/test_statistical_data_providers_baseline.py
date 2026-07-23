"""
ServerLWDataProvider 基线测试

目的：在迁移到 ComputerUsageProvider/ComputerUsageAggregator + Service 层之前，
先补齐基线测试覆盖 statistical_data_providers.py 中 10 个业务使用方法的当前行为。
迁移后（Slice 03/04/05）此测试作为行为等价性对比基准。

依据 issue: .scratch/deletion-sync-02a-statistical/issues/01-delete-dead-code.md
依据 PRD: .scratch/deletion-sync-02a-statistical/prd.md（Testing Decisions > 测试策略）

10 个被测方法：
1. get_activity_log_by_id
2. update_event_category
3. delete_event
4. get_daily_active_time （含跨时区用例）
5. batch_update_event_category
6. batch_delete_events
7. update_logs_by_app_title
8. get_active_time
9. get_top_applications
10. get_top_title

注意：基线测试只覆盖"当前行为"（含已知缺陷，如 update_event_category 不更新 updated_at），
迁移后这些测试应仍然通过（行为等价），或明确标注行为变化（如 updated_at 修复）。
"""

import pytest

# 被测对象本身，从 lifeprism.server.providers 直接导入（issue 文件许可）
from lifeprism.server.providers.statistical_data_providers import ServerLWDataProvider

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture
def provider(test_data_path):
    """创建 ServerLWDataProvider 实例并初始化 user_app_behavior_log 等表

    表结构参考 USER_APP_BEHAVIOR_LOG_CONFIG / CATEGORY_CONFIG / SUB_CATEGORY_CONFIG，
    但只包含 10 个业务方法实际查询/更新涉及的字段（最小化，便于聚焦行为基线）。

    时区固定为 Asia/Shanghai（UTC+8），用于跨时区测试用例。
    """
    from lifeprism.config.settings_manager import settings

    settings._initialize()
    # 显式设置时区为 Asia/Shanghai，确保跨时区用例可重现
    settings.set("timezone", "Asia/Shanghai", save=False)

    p = ServerLWDataProvider()

    with p.db.get_connection() as conn:
        cursor = conn.cursor()
        # user_app_behavior_log 表（最小 schema，覆盖 10 个方法使用的字段）
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_app_behavior_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        # category 表（get_activity_log_by_id JOIN 用）
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
        # sub_category 表（get_activity_log_by_id JOIN 用）
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

    # 清理旧数据（避免不同测试间状态污染）
    _clear_all_tables(p)

    yield p

    # 清理表数据
    _clear_all_tables(p)


def _clear_all_tables(p):
    """清理所有测试表数据"""
    with p.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_app_behavior_log")
        cursor.execute("DELETE FROM category")
        cursor.execute("DELETE FROM sub_category")
        conn.commit()


def _insert_log(
    p,
    start_time,
    end_time,
    duration,
    app,
    title=None,
    category_id=None,
    sub_category_id=None,
    link_to_goal_id=None,
    is_multipurpose_app=0,
):
    """插入一条 user_app_behavior_log 记录，返回自增 id"""
    with p.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO user_app_behavior_log
            (start_time, end_time, duration, app, title, is_multipurpose_app,
             category_id, sub_category_id, link_to_goal_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                start_time,
                end_time,
                duration,
                app,
                title,
                is_multipurpose_app,
                category_id,
                sub_category_id,
                link_to_goal_id,
            ),
        )
        conn.commit()
        return cursor.lastrowid


def _insert_category(p, category_id, name, color="#5B8FF9"):
    """插入一条 category 记录"""
    with p.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO category (id, name, color) VALUES (?, ?, ?)",
            (category_id, name, color),
        )
        conn.commit()


def _insert_sub_category(p, sub_id, category_id, name):
    """插入一条 sub_category 记录"""
    with p.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sub_category (id, category_id, name) VALUES (?, ?, ?)",
            (sub_id, category_id, name),
        )
        conn.commit()


def _query_single_field(p, field, table, where_clause, params):
    """查询单个字段值（用于断言验证）"""
    with p.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT {field} FROM {table} WHERE {where_clause}",
            params,
        )
        row = cursor.fetchone()
    return row[0] if row else None


# ==================== 1. get_activity_log_by_id 基线 ====================


class TestGetActivityLogById:
    """get_activity_log_by_id 基线行为"""

    def test_returns_none_when_not_found(self, provider):
        """不存在的 ID 返回 None"""
        result = provider.get_activity_log_by_id("99999")
        assert result is None

    def test_returns_log_with_category_names(self, provider):
        """存在的 ID 返回日志详情，含 category_name / sub_category_name"""
        _insert_category(provider, "cat-1", "工作")
        _insert_sub_category(provider, "sub-1", "cat-1", "编程")

        log_id = _insert_log(
            provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="code.exe",
            title="main.py",
            category_id="cat-1",
            sub_category_id="sub-1",
        )

        result = provider.get_activity_log_by_id(str(log_id))

        assert result is not None
        assert result["id"] == str(log_id)
        assert result["start_time"] == "2026-07-12T02:00:00+00:00"
        assert result["end_time"] == "2026-07-12T03:00:00+00:00"
        assert result["duration"] == 3600
        assert result["app"] == "code.exe"
        assert result["title"] == "main.py"
        assert result["category_id"] == "cat-1"
        assert result["category_name"] == "工作"
        assert result["sub_category_id"] == "sub-1"
        assert result["sub_category_name"] == "编程"

    def test_returns_log_without_category(self, provider):
        """无分类的日志，category_id / category_name 为 None"""
        log_id = _insert_log(
            provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="unknown.exe",
        )

        result = provider.get_activity_log_by_id(str(log_id))

        assert result is not None
        assert result["category_id"] is None
        assert result["category_name"] is None
        assert result["sub_category_id"] is None
        assert result["sub_category_name"] is None


# ==================== 2. update_event_category 基线 ====================


class TestUpdateEventCategory:
    """update_event_category 基线行为"""

    def test_updates_category_successfully(self, provider):
        """更新存在的记录返回 True，字段被更新"""
        log_id = _insert_log(
            provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="code.exe",
        )

        result = provider.update_event_category(str(log_id), "cat-1", "sub-1")

        assert result is True
        log = provider.get_activity_log_by_id(str(log_id))
        assert log["category_id"] == "cat-1"
        assert log["sub_category_id"] == "sub-1"

    def test_returns_false_when_not_found(self, provider):
        """更新不存在的记录返回 False"""
        result = provider.update_event_category("99999", "cat-1")
        assert result is False

    def test_updates_without_sub_category(self, provider):
        """只更新主分类（sub_category_id 为 None）"""
        log_id = _insert_log(
            provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="code.exe",
        )

        result = provider.update_event_category(str(log_id), "cat-1", None)

        assert result is True
        log = provider.get_activity_log_by_id(str(log_id))
        assert log["category_id"] == "cat-1"
        assert log["sub_category_id"] is None

    def test_does_not_update_updated_at_baseline(self, provider):
        """基线行为：update_event_category 不更新 updated_at（迁移后会变，是 bug 修复）

        依据 PRD "update_event_category 的 updated_at 行为变化"：
        原方法用原生 SQL UPDATE，不更新 updated_at；
        迁移到 update_computer_usage 后会自动更新 updated_at（触发 LWW 同步）。
        """
        log_id = _insert_log(
            provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="code.exe",
        )

        # 设置初始 updated_at
        original_updated_at = "2026-01-01T00:00:00+00:00"
        with provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE user_app_behavior_log SET updated_at = ? WHERE id = ?",
                (original_updated_at, log_id),
            )
            conn.commit()

        # 执行分类更新
        provider.update_event_category(str(log_id), "cat-1")

        # 验证：基线行为下 updated_at 未变化
        updated_at = _query_single_field(
            provider, "updated_at", "user_app_behavior_log", "id = ?", (log_id,)
        )
        assert updated_at == original_updated_at, (
            f"基线行为：update_event_category 不应更新 updated_at，"
            f"预期 {original_updated_at}，实际 {updated_at}（迁移后此行为会变化）"
        )


# ==================== 3. delete_event 基线 ====================


class TestDeleteEvent:
    """delete_event 基线行为"""

    def test_deletes_existing_event(self, provider):
        """删除存在的记录返回 True，记录消失"""
        log_id = _insert_log(
            provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="code.exe",
        )

        result = provider.delete_event(str(log_id))

        assert result is True
        assert provider.get_activity_log_by_id(str(log_id)) is None

    def test_returns_false_when_not_found(self, provider):
        """删除不存在的记录返回 False"""
        result = provider.delete_event("99999")
        assert result is False


# ==================== 4. get_daily_active_time 基线（含跨时区用例）====================


class TestGetDailyActiveTime:
    """get_daily_active_time 基线行为（含跨时区用例）"""

    def test_basic_grouping_by_local_date(self, provider):
        """基本场景：按本地日期分组并计算百分比

        时区 Asia/Shanghai (UTC+8)：本地 2026-07-12 10:00 = UTC 2026-07-12 02:00
        """
        _insert_log(
            provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="app1.exe",
        )

        result = provider.get_daily_active_time("2026-07-12", "2026-07-12")

        assert len(result) == 1
        assert result[0]["date"] == "2026-07-12"
        # 3600 * 100 / 86400 = 4.166... → int = 4
        assert result[0]["active_time_percentage"] == 4

    def test_cross_timezone_utc_evening_to_local_next_day(self, provider):
        """跨时区用例：UTC 20:00 → 本地次日 04:00，应归属本地次日

        时区 Asia/Shanghai (UTC+8)：
        - UTC 2026-07-11T20:00:00+00:00 = 本地 2026-07-12 04:00:00

        get_daily_active_time("2026-07-12", "2026-07-12") 查询范围：
        - start_utc = local_to_utc_iso("2026-07-12 00:00:00") = "2026-07-11T16:00:00+00:00"
        - end_utc = local_to_utc_iso("2026-07-12 23:59:59") = "2026-07-12T15:59:59+00:00"

        该事件 (UTC 20:00) 落在查询范围内，且经 utc_to_local_display 转换后
        本地日期为 "2026-07-12"，应归属本地 2026-07-12（不是 UTC 日期 2026-07-11）。

        依据 PRD "已知风险 1"：迁移时必须保留 Python 层 utc_to_local_display 分组，
        禁止改用 SQL DATE(start_time) 分组（会按 UTC 日期分组导致跨时区错位）。
        """
        _insert_log(
            provider,
            start_time="2026-07-11T20:00:00+00:00",  # UTC 20:00 = 本地 2026-07-12 04:00
            end_time="2026-07-11T21:00:00+00:00",  # UTC 21:00 = 本地 2026-07-12 05:00
            duration=3600,
            app="cross_tz.exe",
        )

        result = provider.get_daily_active_time("2026-07-12", "2026-07-12")

        # 应归属本地 2026-07-12，不是 2026-07-11
        assert len(result) == 1, f"应只有 1 天的数据，实际 {len(result)}: {result}"
        assert result[0]["date"] == "2026-07-12", (
            f"UTC 20:00 的事件应归属本地次日 2026-07-12，实际归属 {result[0]['date']}"
        )
        # 3600 * 100 / 86400 = 4.166... → int = 4
        assert result[0]["active_time_percentage"] == 4

    def test_multi_day_range(self, provider):
        """多日范围：每天独立分组"""
        # Day 1: 本地 2026-07-12 (UTC 2026-07-12 02:00)
        _insert_log(
            provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="app1.exe",
        )
        # Day 2: 本地 2026-07-13 (UTC 2026-07-13 02:00)
        _insert_log(
            provider,
            start_time="2026-07-13T02:00:00+00:00",
            end_time="2026-07-13T03:00:00+00:00",
            duration=7200,
            app="app2.exe",
        )

        result = provider.get_daily_active_time("2026-07-12", "2026-07-13")

        assert len(result) == 2
        assert result[0]["date"] == "2026-07-12"
        assert result[0]["active_time_percentage"] == 4  # 3600*100/86400
        assert result[1]["date"] == "2026-07-13"
        assert result[1]["active_time_percentage"] == 8  # 7200*100/86400 = 8.33 → 8

    def test_empty_range_returns_empty_list(self, provider):
        """无数据时返回空列表"""
        result = provider.get_daily_active_time("2026-07-12", "2026-07-12")
        assert result == []

    def test_filters_by_category_id(self, provider):
        """按 category_id 筛选"""
        _insert_log(
            provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="app1.exe",
            category_id="cat-1",
        )
        _insert_log(
            provider,
            start_time="2026-07-12T03:00:00+00:00",
            end_time="2026-07-12T04:00:00+00:00",
            duration=1800,
            app="app2.exe",
            category_id="cat-2",
        )

        # 查询 cat-1
        result = provider.get_daily_active_time(
            "2026-07-12", "2026-07-12", category_id="cat-1"
        )
        assert len(result) == 1
        assert result[0]["date"] == "2026-07-12"
        # 只有 cat-1 的 3600 秒
        assert result[0]["active_time_percentage"] == 4

    def test_filters_by_sub_category_id(self, provider):
        """按 sub_category_id 筛选"""
        _insert_log(
            provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="app1.exe",
            category_id="cat-1",
            sub_category_id="sub-1",
        )
        _insert_log(
            provider,
            start_time="2026-07-12T03:00:00+00:00",
            end_time="2026-07-12T04:00:00+00:00",
            duration=1800,
            app="app2.exe",
            category_id="cat-1",
            sub_category_id="sub-2",
        )

        result = provider.get_daily_active_time(
            "2026-07-12", "2026-07-12", sub_category_id="sub-1"
        )
        assert len(result) == 1
        assert result[0]["active_time_percentage"] == 4  # 3600*100/86400


# ==================== 5. batch_update_event_category 基线 ====================


class TestBatchUpdateEventCategory:
    """batch_update_event_category 基线行为"""

    def test_batch_updates_multiple_events(self, provider):
        """批量更新多条记录，返回更新数量"""
        id1 = _insert_log(
            provider, "2026-07-12T02:00:00+00:00", "2026-07-12T03:00:00+00:00", 3600, "app1.exe"
        )
        id2 = _insert_log(
            provider, "2026-07-12T03:00:00+00:00", "2026-07-12T04:00:00+00:00", 3600, "app2.exe"
        )
        id3 = _insert_log(
            provider, "2026-07-12T04:00:00+00:00", "2026-07-12T05:00:00+00:00", 3600, "app3.exe"
        )

        result = provider.batch_update_event_category(
            [str(id1), str(id2), str(id3)], "cat-1", "sub-1"
        )

        assert result == 3
        for log_id in [id1, id2, id3]:
            log = provider.get_activity_log_by_id(str(log_id))
            assert log["category_id"] == "cat-1"
            assert log["sub_category_id"] == "sub-1"

    def test_empty_list_returns_zero(self, provider):
        """空列表返回 0"""
        result = provider.batch_update_event_category([], "cat-1")
        assert result == 0

    def test_partial_match_returns_count(self, provider):
        """部分 ID 不存在时，返回实际更新数量"""
        id1 = _insert_log(
            provider, "2026-07-12T02:00:00+00:00", "2026-07-12T03:00:00+00:00", 3600, "app1.exe"
        )

        # 包含一个不存在的 ID
        result = provider.batch_update_event_category([str(id1), "99999"], "cat-1")

        assert result == 1


# ==================== 6. batch_delete_events 基线 ====================


class TestBatchDeleteEvents:
    """batch_delete_events 基线行为"""

    def test_batch_deletes_multiple_events(self, provider):
        """批量删除多条记录，返回删除数量"""
        id1 = _insert_log(
            provider, "2026-07-12T02:00:00+00:00", "2026-07-12T03:00:00+00:00", 3600, "app1.exe"
        )
        id2 = _insert_log(
            provider, "2026-07-12T03:00:00+00:00", "2026-07-12T04:00:00+00:00", 3600, "app2.exe"
        )

        result = provider.batch_delete_events([str(id1), str(id2)])

        assert result == 2
        assert provider.get_activity_log_by_id(str(id1)) is None
        assert provider.get_activity_log_by_id(str(id2)) is None

    def test_empty_list_returns_zero(self, provider):
        """空列表返回 0"""
        result = provider.batch_delete_events([])
        assert result == 0

    def test_partial_match_returns_count(self, provider):
        """部分 ID 不存在时，返回实际删除数量"""
        id1 = _insert_log(
            provider, "2026-07-12T02:00:00+00:00", "2026-07-12T03:00:00+00:00", 3600, "app1.exe"
        )

        result = provider.batch_delete_events([str(id1), "99999"])

        assert result == 1


# ==================== 7. update_logs_by_app_title 基线 ====================


class TestUpdateLogsByAppTitle:
    """update_logs_by_app_title 基线行为"""

    def test_single_purpose_app_matches_by_app_only(self, provider):
        """单用途应用：仅按 app 匹配（忽略 title）"""
        _insert_log(
            provider,
            "2026-07-12T02:00:00+00:00",
            "2026-07-12T03:00:00+00:00",
            3600,
            "code.exe",
            title="main.py",
        )
        _insert_log(
            provider,
            "2026-07-12T03:00:00+00:00",
            "2026-07-12T04:00:00+00:00",
            3600,
            "code.exe",
            title="other.py",
        )
        _insert_log(
            provider,
            "2026-07-12T04:00:00+00:00",
            "2026-07-12T05:00:00+00:00",
            3600,
            "other.exe",
            title="main.py",
        )

        result = provider.update_logs_by_app_title(
            app="code.exe",
            title=None,
            is_multipurpose_app=False,
            category_id="cat-1",
            sub_category_id="sub-1",
        )

        # 应更新 2 条（app=code.exe 的两条）
        assert result == 2

        # 验证：code.exe 的两条都被更新
        with provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT category_id, sub_category_id FROM user_app_behavior_log WHERE app = 'code.exe'"
            )
            rows = cursor.fetchall()
        assert len(rows) == 2
        for row in rows:
            assert row[0] == "cat-1"
            assert row[1] == "sub-1"

    def test_multi_purpose_app_matches_by_app_and_title(self, provider):
        """多用途应用：按 app + title 匹配"""
        _insert_log(
            provider,
            "2026-07-12T02:00:00+00:00",
            "2026-07-12T03:00:00+00:00",
            3600,
            "browser.exe",
            title="work",
        )
        _insert_log(
            provider,
            "2026-07-12T03:00:00+00:00",
            "2026-07-12T04:00:00+00:00",
            3600,
            "browser.exe",
            title="play",
        )

        result = provider.update_logs_by_app_title(
            app="browser.exe",
            title="work",
            is_multipurpose_app=True,
            category_id="cat-1",
        )

        # 应只更新 1 条（app=browser.exe + title=work）
        assert result == 1

        # 验证：只有 title=work 的记录被更新
        with provider.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT title, category_id FROM user_app_behavior_log WHERE app = 'browser.exe' ORDER BY title"
            )
            rows = cursor.fetchall()
        # sqlite3.Row 需转为 tuple 才能与 tuple 比较
        assert tuple(rows[0]) == ("play", None)  # 未更新
        assert tuple(rows[1]) == ("work", "cat-1")  # 已更新

    def test_multi_purpose_app_without_title_raises(self, provider):
        """多用途应用未提供 title 时抛出 ValueError"""
        with pytest.raises(ValueError, match="多用途应用必须提供 title 参数"):
            provider.update_logs_by_app_title(
                app="browser.exe",
                title=None,
                is_multipurpose_app=True,
                category_id="cat-1",
            )

    def test_goal_id_none_does_not_modify_link_to_goal_id(self, provider):
        """goal_id=None：不修改 link_to_goal_id"""
        _insert_log(
            provider,
            "2026-07-12T02:00:00+00:00",
            "2026-07-12T03:00:00+00:00",
            3600,
            "code.exe",
            link_to_goal_id="goal-original",
        )

        provider.update_logs_by_app_title(
            app="code.exe",
            title=None,
            is_multipurpose_app=False,
            category_id="cat-1",
            goal_id=None,  # 不修改
        )

        goal = _query_single_field(
            provider,
            "link_to_goal_id",
            "user_app_behavior_log",
            "app = 'code.exe'",
            (),
        )
        assert goal == "goal-original"

    def test_goal_id_empty_string_clears_link_to_goal_id(self, provider):
        """goal_id=''：清除 link_to_goal_id（设为 NULL）"""
        _insert_log(
            provider,
            "2026-07-12T02:00:00+00:00",
            "2026-07-12T03:00:00+00:00",
            3600,
            "code.exe",
            link_to_goal_id="goal-original",
        )

        provider.update_logs_by_app_title(
            app="code.exe",
            title=None,
            is_multipurpose_app=False,
            category_id="cat-1",
            goal_id="",  # 清除
        )

        goal = _query_single_field(
            provider,
            "link_to_goal_id",
            "user_app_behavior_log",
            "app = 'code.exe'",
            (),
        )
        assert goal is None

    def test_goal_id_value_sets_link_to_goal_id(self, provider):
        """goal_id='goal-xxx'：设置 link_to_goal_id"""
        _insert_log(
            provider,
            "2026-07-12T02:00:00+00:00",
            "2026-07-12T03:00:00+00:00",
            3600,
            "code.exe",
            link_to_goal_id=None,
        )

        provider.update_logs_by_app_title(
            app="code.exe",
            title=None,
            is_multipurpose_app=False,
            category_id="cat-1",
            goal_id="goal-new",  # 设置
        )

        goal = _query_single_field(
            provider,
            "link_to_goal_id",
            "user_app_behavior_log",
            "app = 'code.exe'",
            (),
        )
        assert goal == "goal-new"

    def test_time_range_filter(self, provider):
        """按时间范围过滤匹配"""
        _insert_log(
            provider,
            "2026-07-12T02:00:00+00:00",
            "2026-07-12T03:00:00+00:00",
            3600,
            "code.exe",
        )
        _insert_log(
            provider,
            "2026-07-13T02:00:00+00:00",
            "2026-07-13T03:00:00+00:00",
            3600,
            "code.exe",
        )

        # 只更新 2026-07-13 之后的
        result = provider.update_logs_by_app_title(
            app="code.exe",
            title=None,
            is_multipurpose_app=False,
            category_id="cat-1",
            start_time="2026-07-13T00:00:00+00:00",
        )

        # 应只更新 1 条（2026-07-13 的那条）
        assert result == 1


# ==================== 8. get_active_time 基线 ====================


class TestGetActiveTime:
    """get_active_time 基线行为"""

    def test_returns_sum_of_duration(self, provider):
        """返回当天所有事件 duration 之和"""
        _insert_log(
            provider,
            "2026-07-12T02:00:00+00:00",
            "2026-07-12T03:00:00+00:00",
            3600,
            "app1.exe",
        )
        _insert_log(
            provider,
            "2026-07-12T03:00:00+00:00",
            "2026-07-12T04:00:00+00:00",
            1800,
            "app2.exe",
        )

        result = provider.get_active_time("2026-07-12")

        assert result == 5400  # 3600 + 1800

    def test_returns_zero_when_no_data(self, provider):
        """无数据返回 0"""
        result = provider.get_active_time("2026-07-12")
        assert result == 0

    def test_excludes_other_dates(self, provider):
        """只统计指定日期的数据"""
        # 本地 2026-07-12 (UTC 02:00)
        _insert_log(
            provider,
            "2026-07-12T02:00:00+00:00",
            "2026-07-12T03:00:00+00:00",
            3600,
            "app1.exe",
        )
        # 本地 2026-07-13 (UTC 2026-07-13 02:00)
        _insert_log(
            provider,
            "2026-07-13T02:00:00+00:00",
            "2026-07-13T03:00:00+00:00",
            7200,
            "app2.exe",
        )

        result = provider.get_active_time("2026-07-12")

        # 只算 2026-07-12 的（本地日期），3600
        assert result == 3600

    def test_cross_timezone_event_counted_in_local_date(self, provider):
        """跨时区事件应计入本地日期

        UTC 2026-07-11T20:00 = 本地 2026-07-12 04:00
        查询本地日期 2026-07-12 时应包含此事件。
        """
        _insert_log(
            provider,
            "2026-07-11T20:00:00+00:00",  # UTC 20:00 = 本地 2026-07-12 04:00
            "2026-07-11T21:00:00+00:00",
            3600,
            "cross_tz.exe",
        )

        result = provider.get_active_time("2026-07-12")

        assert result == 3600


# ==================== 9. get_top_applications 基线 ====================


class TestGetTopApplications:
    """get_top_applications 基线行为"""

    def test_returns_top_n_apps_by_duration(self, provider):
        """返回 Top N 应用，按 duration 降序"""
        _insert_log(
            provider,
            "2026-07-12T02:00:00+00:00",
            "2026-07-12T03:00:00+00:00",
            3600,
            "app1.exe",
        )
        _insert_log(
            provider,
            "2026-07-12T03:00:00+00:00",
            "2026-07-12T04:00:00+00:00",
            7200,
            "app2.exe",
        )
        _insert_log(
            provider,
            "2026-07-12T04:00:00+00:00",
            "2026-07-12T05:00:00+00:00",
            1800,
            "app3.exe",
        )

        result = provider.get_top_applications("2026-07-12", 2)

        assert len(result) == 2
        assert result[0]["name"] == "app2.exe"
        assert result[0]["duration"] == 7200
        assert result[1]["name"] == "app1.exe"
        assert result[1]["duration"] == 3600

    def test_aggregates_same_app(self, provider):
        """同一应用的多个事件应聚合"""
        _insert_log(
            provider,
            "2026-07-12T02:00:00+00:00",
            "2026-07-12T03:00:00+00:00",
            3600,
            "app1.exe",
        )
        _insert_log(
            provider,
            "2026-07-12T03:00:00+00:00",
            "2026-07-12T04:00:00+00:00",
            1800,
            "app1.exe",
        )

        result = provider.get_top_applications("2026-07-12", 10)

        assert len(result) == 1
        assert result[0]["name"] == "app1.exe"
        assert result[0]["duration"] == 5400  # 3600 + 1800

    def test_empty_when_no_data(self, provider):
        """无数据返回空列表"""
        result = provider.get_top_applications("2026-07-12", 10)
        assert result == []

    def test_respects_top_n_limit(self, provider):
        """top_n 限制返回数量"""
        for i in range(5):
            _insert_log(
                provider,
                f"2026-07-12T0{i}:00:00+00:00",
                f"2026-07-12T0{i+1}:00:00+00:00",
                3600,
                f"app{i}.exe",
            )

        result = provider.get_top_applications("2026-07-12", 3)

        assert len(result) == 3


# ==================== 10. get_top_title 基线 ====================


class TestGetTopTitle:
    """get_top_title 基线行为"""

    def test_returns_top_n_titles_by_duration(self, provider):
        """返回 Top N 标题，按 duration 降序"""
        _insert_log(
            provider,
            "2026-07-12T02:00:00+00:00",
            "2026-07-12T03:00:00+00:00",
            3600,
            "app1.exe",
            title="title1",
        )
        _insert_log(
            provider,
            "2026-07-12T03:00:00+00:00",
            "2026-07-12T04:00:00+00:00",
            7200,
            "app2.exe",
            title="title2",
        )

        result = provider.get_top_title("2026-07-12", 2)

        assert len(result) == 2
        assert result[0]["name"] == "title2"
        assert result[0]["duration"] == 7200
        assert result[1]["name"] == "title1"
        assert result[1]["duration"] == 3600

    def test_aggregates_same_title(self, provider):
        """同一标题的多个事件应聚合（即使 app 不同）"""
        _insert_log(
            provider,
            "2026-07-12T02:00:00+00:00",
            "2026-07-12T03:00:00+00:00",
            3600,
            "app1.exe",
            title="same_title",
        )
        _insert_log(
            provider,
            "2026-07-12T03:00:00+00:00",
            "2026-07-12T04:00:00+00:00",
            1800,
            "app2.exe",
            title="same_title",
        )

        result = provider.get_top_title("2026-07-12", 10)

        assert len(result) == 1
        assert result[0]["name"] == "same_title"
        assert result[0]["duration"] == 5400  # 3600 + 1800

    def test_empty_when_no_data(self, provider):
        """无数据返回空列表"""
        result = provider.get_top_title("2026-07-12", 10)
        assert result == []
