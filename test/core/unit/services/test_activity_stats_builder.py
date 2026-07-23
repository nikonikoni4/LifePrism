"""
activity_stats_builder 迁移测试（Slice 05）

验证 activity_stats_builder 中 4 个统计方法从 server_lw_data_provider 迁移到
computer_usage_repository 后的行为正确性，以及 3 类业务逻辑（时区转换、
百分比计算、字段映射）上移到 Service 层后的正确性。

被测方法：
1. get_top_app → computer_usage_repository.get_top_groups_by_duration("app", ...)
                 + computer_usage_repository.get_total_duration(...)
2. get_top_title → computer_usage_repository.get_top_groups_by_duration("title", ...)
                   + computer_usage_repository.get_total_duration(...)
3. build_activity_summary → computer_usage_repository.load_user_app_behavior_log(...)
                            + Service 层 Python 聚合（_add_local_date_column + groupby）

依据 issue: .scratch/deletion-sync-02a-statistical/issues/05-activity-stats-builder-migration.md
依据 PRD: .scratch/deletion-sync-02a-statistical/prd.md
"""

import pytest

from lifeprism.server.services import activity_stats_builder

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


def _clear_tables(db, table_names):
    """清理指定表的数据"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        for name in table_names:
            cursor.execute(f"DELETE FROM {name}")
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


# ==================== Fixtures ====================


@pytest.fixture
def stats_fixture(test_data_path):
    """初始化测试环境：创建表 + 清理数据 + 设置时区

    使用模块级 computer_usage_repository 单例（与 activity_stats_builder 相同的实例），
    确保 activity_stats_builder 调用的就是测试中设置的数据。

    时区固定为 Asia/Shanghai（UTC+8），用于跨时区测试用例。
    """
    from lifeprism.config.settings_manager import settings
    from lifeprism.repository import computer_usage_repository

    settings._initialize()
    # 显式设置时区为 Asia/Shanghai，确保跨时区用例可重现
    settings.set("timezone", "Asia/Shanghai", save=False)

    db = computer_usage_repository.computer_usage_provider.db

    # 创建测试所需的表
    _create_user_app_behavior_log(db)
    _create_category_tables(db)

    # 清理旧数据
    _clear_tables(db, ["user_app_behavior_log", "category", "sub_category"])

    yield computer_usage_repository

    # 清理表数据
    _clear_tables(db, ["user_app_behavior_log", "category", "sub_category"])


# ==================== 1. get_top_app 迁移测试 ====================


class TestGetTopApp:
    """get_top_app 迁移后行为测试

    迁移路径：server_lw_data_provider.get_top_applications + get_active_time
              → computer_usage_repository.get_top_groups_by_duration("app", ...)
              + computer_usage_repository.get_total_duration(...)

    业务逻辑上移：
    - 时区转换（build_utc_time_range 上移到 Service 层）
    - 字段映射（tuple 解包替代 dict 访问）
    - 百分比计算（Service 层 int(duration / total * 100)）
    """

    def test_returns_top_apps_with_percentage(self, stats_fixture):
        """返回 Top N 应用，按 duration 降序，含正确百分比

        时区 Asia/Shanghai (UTC+8)：本地 2026-07-12 10:00 = UTC 2026-07-12 02:00
        """
        repo = stats_fixture
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="app1.exe",
        )
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T03:00:00+00:00",
            end_time="2026-07-12T04:00:00+00:00",
            duration=7200,
            app="app2.exe",
        )

        result = activity_stats_builder.get_top_app("2026-07-12", 10)

        assert len(result) == 2
        # 按 duration 降序
        assert result[0].name == "app2.exe"
        assert result[0].duration == 7200
        # 7200 / 10800 * 100 = 66.66... → int = 66
        assert result[0].percentage == 66
        assert result[1].name == "app1.exe"
        assert result[1].duration == 3600
        # 3600 / 10800 * 100 = 33.33... → int = 33
        assert result[1].percentage == 33

    def test_aggregates_same_app(self, stats_fixture):
        """同一应用的多个事件应聚合"""
        repo = stats_fixture
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="app1.exe",
        )
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T03:00:00+00:00",
            end_time="2026-07-12T04:00:00+00:00",
            duration=1800,
            app="app1.exe",
        )

        result = activity_stats_builder.get_top_app("2026-07-12", 10)

        assert len(result) == 1
        assert result[0].name == "app1.exe"
        assert result[0].duration == 5400  # 3600 + 1800
        # 唯一应用，占 100%
        assert result[0].percentage == 100

    def test_empty_when_no_data(self, stats_fixture):
        """无数据返回空列表"""
        result = activity_stats_builder.get_top_app("2026-07-12", 10)
        assert result == []

    def test_respects_top_n_limit(self, stats_fixture):
        """top_n 限制返回数量"""
        repo = stats_fixture
        for i in range(5):
            _insert_log_via_generic_insert(
                repo.computer_usage_provider,
                start_time=f"2026-07-12T0{i + 1}:00:00+00:00",
                end_time=f"2026-07-12T0{i + 2}:00:00+00:00",
                duration=3600,
                app=f"app{i}.exe",
            )

        result = activity_stats_builder.get_top_app("2026-07-12", 3)

        assert len(result) == 3

    def test_zero_total_duration_returns_zero_percentage(self, stats_fixture, monkeypatch):
        """total_duration 为 0 时百分比为 0（避免除零）

        通过 monkeypatch 让 get_total_duration 返回 0，验证除零保护。
        """
        repo = stats_fixture
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="app1.exe",
        )

        # monkeypatch get_total_duration 返回 0，模拟无总时长数据（除零保护）
        monkeypatch.setattr(repo, "get_total_duration", lambda *args, **kwargs: 0)
        result = activity_stats_builder.get_top_app("2026-07-12", 10)
        assert len(result) == 1
        assert result[0].percentage == 0  # total_duration=0 时百分比为 0（除零保护）

    def test_does_not_use_server_lw_data_provider(self, stats_fixture, monkeypatch):
        """验证不通过 server_lw_data_provider 调用（迁移验证）

        如果 activity_stats_builder 仍调用 server_lw_data_provider.get_top_applications
        或 server_lw_data_provider.get_active_time，此测试会因 RuntimeError 而失败。
        """
        from lifeprism.server.providers import server_lw_data_provider

        def _explode(*args, **kwargs):
            raise RuntimeError(
                "server_lw_data_provider.get_top_applications / get_active_time 不应被调用"
            )

        monkeypatch.setattr(server_lw_data_provider, "get_top_applications", _explode)
        monkeypatch.setattr(server_lw_data_provider, "get_active_time", _explode)

        repo = stats_fixture
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="not_via_provider.exe",
        )

        # 如果仍走 server_lw_data_provider，会抛 RuntimeError
        result = activity_stats_builder.get_top_app("2026-07-12", 10)
        assert len(result) == 1
        assert result[0].name == "not_via_provider.exe"


# ==================== 2. get_top_title 迁移测试 ====================


class TestGetTopTitle:
    """get_top_title 迁移后行为测试

    迁移路径：server_lw_data_provider.get_top_title + get_active_time
              → computer_usage_repository.get_top_groups_by_duration("title", ...)
              + computer_usage_repository.get_total_duration(...)

    业务逻辑上移（同 get_top_app）：
    - 时区转换（build_utc_time_range 上移到 Service 层）
    - 字段映射（tuple 解包替代 dict 访问）
    - 百分比计算（Service 层 int(duration / total * 100)）
    """

    def test_returns_top_titles_with_percentage(self, stats_fixture):
        """返回 Top N 标题，按 duration 降序，含正确百分比"""
        repo = stats_fixture
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="app1.exe",
            title="title1",
        )
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T03:00:00+00:00",
            end_time="2026-07-12T04:00:00+00:00",
            duration=7200,
            app="app2.exe",
            title="title2",
        )

        result = activity_stats_builder.get_top_title("2026-07-12", 10)

        assert len(result) == 2
        # 按 duration 降序
        assert result[0].name == "title2"
        assert result[0].duration == 7200
        # 7200 / 10800 * 100 = 66.66... → int = 66
        assert result[0].percentage == 66
        assert result[1].name == "title1"
        assert result[1].duration == 3600
        # 3600 / 10800 * 100 = 33.33... → int = 33
        assert result[1].percentage == 33

    def test_aggregates_same_title_across_apps(self, stats_fixture):
        """同一标题的多个事件应聚合（即使 app 不同）"""
        repo = stats_fixture
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="app1.exe",
            title="same_title",
        )
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T03:00:00+00:00",
            end_time="2026-07-12T04:00:00+00:00",
            duration=1800,
            app="app2.exe",
            title="same_title",
        )

        result = activity_stats_builder.get_top_title("2026-07-12", 10)

        assert len(result) == 1
        assert result[0].name == "same_title"
        assert result[0].duration == 5400  # 3600 + 1800
        # 唯一标题占 100%
        assert result[0].percentage == 100

    def test_empty_when_no_data(self, stats_fixture):
        """无数据返回空列表"""
        result = activity_stats_builder.get_top_title("2026-07-12", 10)
        assert result == []

    def test_respects_top_n_limit(self, stats_fixture):
        """top_n 限制返回数量"""
        repo = stats_fixture
        for i in range(5):
            _insert_log_via_generic_insert(
                repo.computer_usage_provider,
                start_time=f"2026-07-12T0{i + 1}:00:00+00:00",
                end_time=f"2026-07-12T0{i + 2}:00:00+00:00",
                duration=3600,
                app=f"app{i}.exe",
                title=f"title{i}",
            )

        result = activity_stats_builder.get_top_title("2026-07-12", 3)

        assert len(result) == 3

    def test_does_not_use_server_lw_data_provider(self, stats_fixture, monkeypatch):
        """验证不通过 server_lw_data_provider 调用（迁移验证）

        如果 activity_stats_builder 仍调用 server_lw_data_provider.get_top_title
        或 server_lw_data_provider.get_active_time，此测试会因 RuntimeError 而失败。
        """
        from lifeprism.server.providers import server_lw_data_provider

        def _explode(*args, **kwargs):
            raise RuntimeError(
                "server_lw_data_provider.get_top_title / get_active_time 不应被调用"
            )

        monkeypatch.setattr(server_lw_data_provider, "get_top_title", _explode)
        monkeypatch.setattr(server_lw_data_provider, "get_active_time", _explode)

        repo = stats_fixture
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="not_via_provider.exe",
            title="not_via_provider_title",
        )

        # 如果仍走 server_lw_data_provider，会抛 RuntimeError
        result = activity_stats_builder.get_top_title("2026-07-12", 10)
        assert len(result) == 1
        assert result[0].name == "not_via_provider_title"


# ==================== 3. build_activity_summary 迁移测试 ====================


class TestBuildActivitySummary:
    """build_activity_summary 迁移后行为测试

    迁移路径：server_lw_data_provider.get_daily_active_time
              → computer_usage_repository.load_user_app_behavior_log(...)
              + Service 层 Python 聚合（_add_local_date_column + groupby）

    业务逻辑上移：
    - 时区转换：复用 _add_local_date_column（pandas 向量化，等价于原 utc_to_local_display）
    - 百分比计算：Service 层 int(total_duration * 100 / 86400)
    - 分类筛选：Service 层 df[df["category_id"] == category_id]

    依据 PRD "已知风险 1"：迁移时必须保留 Python 层时区分组，
    禁止改用 SQL DATE(start_time) 分组（会按 UTC 日期分组导致跨时区错位）。
    """

    def test_basic_grouping_by_local_date(self, stats_fixture):
        """基本场景：按本地日期分组并计算百分比

        时区 Asia/Shanghai (UTC+8)：本地 2026-07-12 10:00 = UTC 2026-07-12 02:00
        """
        repo = stats_fixture
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="app1.exe",
        )

        result = activity_stats_builder.build_activity_summary(
            "2026-07-12", 0, 0, None, None
        )

        assert len(result.daily_activities) == 1
        assert result.daily_activities[0].date == "2026-07-12"
        # 3600 * 100 / 86400 = 4.166... → int = 4
        assert result.daily_activities[0].active_time_percentage == 4
        # duration = int(percentage * 86400 / 100) = int(4 * 86400 / 100) = 3456
        assert result.daily_activities[0].duration == 3456

    def test_cross_timezone_utc_evening_to_local_next_day(self, stats_fixture):
        """跨时区用例（关键）：UTC 20:00 → 本地次日 04:00，应归属本地次日

        时区 Asia/Shanghai (UTC+8)：
        - UTC 2026-07-11T20:00:00+00:00 = 本地 2026-07-12 04:00:00

        build_activity_summary("2026-07-12", 0, 0, ...) 查询范围：
        - start_utc = local_to_utc_iso("2026-07-12 00:00:00") = "2026-07-11T16:00:00+00:00"
        - end_utc = local_to_utc_iso("2026-07-12 23:59:59") = "2026-07-12T15:59:59+00:00"

        该事件 (UTC 20:00) 落在查询范围内，且经 _add_local_date_column 转换后
        本地日期为 "2026-07-12"，应归属本地 2026-07-12（不是 UTC 日期 2026-07-11）。

        依据 PRD "已知风险 1"：迁移时必须保留 Python 层时区分组（_add_local_date_column），
        禁止改用 SQL DATE(start_time) 分组（会按 UTC 日期分组导致跨时区错位）。

        依据 Slice 01 基线测试 test_cross_timezone_utc_evening_to_local_next_day：
        迁移后此等价用例仍应通过。
        """
        repo = stats_fixture
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-11T20:00:00+00:00",  # UTC 20:00 = 本地 2026-07-12 04:00
            end_time="2026-07-11T21:00:00+00:00",  # UTC 21:00 = 本地 2026-07-12 05:00
            duration=3600,
            app="cross_tz.exe",
        )

        result = activity_stats_builder.build_activity_summary(
            "2026-07-12", 0, 0, None, None
        )

        # 应归属本地 2026-07-12，不是 2026-07-11
        assert len(result.daily_activities) == 1, (
            f"应只有 1 天的数据，实际 {len(result.daily_activities)}: {result.daily_activities}"
        )
        assert result.daily_activities[0].date == "2026-07-12", (
            f"UTC 20:00 的事件应归属本地次日 2026-07-12，"
            f"实际归属 {result.daily_activities[0].date}"
        )
        # 3600 * 100 / 86400 = 4.166... → int = 4
        assert result.daily_activities[0].active_time_percentage == 4

    def test_multi_day_range(self, stats_fixture):
        """多日范围：每天独立分组，缺失日期补 0"""
        repo = stats_fixture
        # Day 1: 本地 2026-07-12 (UTC 2026-07-12 02:00)
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="app1.exe",
        )
        # Day 2: 本地 2026-07-13 (UTC 2026-07-13 02:00)
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-13T02:00:00+00:00",
            end_time="2026-07-13T03:00:00+00:00",
            duration=7200,
            app="app2.exe",
        )

        # 中心日期 2026-07-12，0 历史天数，1 未来天数 → 范围 [2026-07-12, 2026-07-13]
        result = activity_stats_builder.build_activity_summary(
            "2026-07-12", 0, 1, None, None
        )

        assert len(result.daily_activities) == 2
        assert result.daily_activities[0].date == "2026-07-12"
        assert result.daily_activities[0].active_time_percentage == 4  # 3600*100/86400
        assert result.daily_activities[1].date == "2026-07-13"
        assert result.daily_activities[1].active_time_percentage == 8  # 7200*100/86400=8.33→8

    def test_empty_range_returns_zeros(self, stats_fixture):
        """无数据时所有日期补 0（保持完整日期数组）"""
        result = activity_stats_builder.build_activity_summary(
            "2026-07-12", 0, 0, None, None
        )

        assert len(result.daily_activities) == 1
        assert result.daily_activities[0].date == "2026-07-12"
        assert result.daily_activities[0].active_time_percentage == 0
        assert result.daily_activities[0].duration == 0

    def test_missing_day_filled_with_zero(self, stats_fixture):
        """缺失日期补 0（验证完整日期数组构建）"""
        repo = stats_fixture
        # 只在 2026-07-13 插入数据，2026-07-12 应补 0
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-13T02:00:00+00:00",
            end_time="2026-07-13T03:00:00+00:00",
            duration=3600,
            app="app1.exe",
        )

        result = activity_stats_builder.build_activity_summary(
            "2026-07-12", 0, 1, None, None
        )

        assert len(result.daily_activities) == 2
        # 2026-07-12 无数据，补 0
        assert result.daily_activities[0].date == "2026-07-12"
        assert result.daily_activities[0].active_time_percentage == 0
        assert result.daily_activities[0].duration == 0
        # 2026-07-13 有数据
        assert result.daily_activities[1].date == "2026-07-13"
        assert result.daily_activities[1].active_time_percentage == 4

    def test_filters_by_category_id(self, stats_fixture):
        """按 category_id 筛选（Service 层 Python 过滤）"""
        repo = stats_fixture
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="app1.exe",
            category_id="cat-1",
        )
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T03:00:00+00:00",
            end_time="2026-07-12T04:00:00+00:00",
            duration=1800,
            app="app2.exe",
            category_id="cat-2",
        )

        # 查询 cat-1
        result = activity_stats_builder.build_activity_summary(
            "2026-07-12", 0, 0, "cat-1", None
        )

        assert len(result.daily_activities) == 1
        assert result.daily_activities[0].date == "2026-07-12"
        # 只有 cat-1 的 3600 秒
        assert result.daily_activities[0].active_time_percentage == 4  # 3600*100/86400

    def test_filters_by_sub_category_id(self, stats_fixture):
        """按 sub_category_id 筛选（Service 层 Python 过滤）"""
        repo = stats_fixture
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="app1.exe",
            category_id="cat-1",
            sub_category_id="sub-1",
        )
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T03:00:00+00:00",
            end_time="2026-07-12T04:00:00+00:00",
            duration=1800,
            app="app2.exe",
            category_id="cat-1",
            sub_category_id="sub-2",
        )

        result = activity_stats_builder.build_activity_summary(
            "2026-07-12", 0, 0, None, "sub-1"
        )

        assert len(result.daily_activities) == 1
        # 只有 sub-1 的 3600 秒
        assert result.daily_activities[0].active_time_percentage == 4  # 3600*100/86400

    def test_does_not_use_server_lw_data_provider(self, stats_fixture, monkeypatch):
        """验证不通过 server_lw_data_provider 调用（迁移验证）

        如果 activity_stats_builder 仍调用 server_lw_data_provider.get_daily_active_time，
        此测试会因 RuntimeError 而失败。
        """
        from lifeprism.server.providers import server_lw_data_provider

        def _explode(*args, **kwargs):
            raise RuntimeError(
                "server_lw_data_provider.get_daily_active_time 不应被调用"
            )

        monkeypatch.setattr(server_lw_data_provider, "get_daily_active_time", _explode)

        repo = stats_fixture
        _insert_log_via_generic_insert(
            repo.computer_usage_provider,
            start_time="2026-07-12T02:00:00+00:00",
            end_time="2026-07-12T03:00:00+00:00",
            duration=3600,
            app="not_via_provider.exe",
        )

        # 如果仍走 server_lw_data_provider，会抛 RuntimeError
        result = activity_stats_builder.build_activity_summary(
            "2026-07-12", 0, 0, None, None
        )
        assert len(result.daily_activities) == 1
        assert result.daily_activities[0].date == "2026-07-12"
        assert result.daily_activities[0].active_time_percentage == 4
