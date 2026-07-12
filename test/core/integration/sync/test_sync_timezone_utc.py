"""
UTC 时区迁移后的同步集成测试

测试 seam:
- Seam 1: LWW 冲突解决在 UTC ISO 8601 格式下正确工作
- Seam 2: 跨时区同步场景（本地 UTC+8、云端 UTC）
- Seam 3: last_sync_time 使用 UTC ISO 格式

参考:
- docs/adr/2026-07-12-migrate-to-utc-timezone.md
- docs/guides/utc-migration-hidden-dependencies.md
- test/core/integration/sync/test_sync_client.py
"""

from datetime import datetime, timedelta, timezone
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
    from lifeprism.repository.base_providers.lw_base_data_provider import LWBaseDataProvider
    from lifeprism.repository.lw_table_manager import LWTableManager

    # 重置 update_at 缓存（确保测试使用最新配置）
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
    """清理同步表数据（测试前后都执行，确保隔离）"""
    sync_tables = [
        "mood_entries",
        "todo_list",
        "goal",
        "diary",
        "timeline_custom_block",
        "user_app_behavior_log",
    ]

    def _clean():
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            for table_name in sync_tables:
                cursor.execute(f"DELETE FROM {table_name}")
            conn.commit()

    _clean()
    yield
    _clean()


# ==================== Helper Functions ====================


def _make_mock_response(json_data, status_code=200):
    """构建 mock httpx.Response 对象"""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    mock_resp.raise_for_status = MagicMock()
    if status_code >= 400:
        mock_resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return mock_resp


def _utc_iso(seconds_offset: int = 0) -> str:
    """生成 UTC ISO 8601 时间戳（带时区标识）

    使用固定基准时间，保证测试可重复。

    Args:
        seconds_offset: 相对于基准时间（2026-07-01 10:00:00 UTC）的秒数偏移

    Returns:
        UTC ISO 8601 格式的时间戳字符串，如 "2026-07-01T10:00:00.000000+00:00"
    """
    base = datetime(2026, 7, 1, 10, 0, 0, tzinfo=timezone.utc)
    return (base + timedelta(seconds=seconds_offset)).isoformat()


def _mock_get_setting_factory(
    remote_url="http://test:8000", last_sync_time="2026-07-01T00:00:00+00:00"
):
    """构建 get_setting 的 mock side_effect"""

    def _mock_get_setting(key, default=None):
        if key == "sync.remote_url":
            return remote_url
        elif key == "sync.last_sync_time":
            return last_sync_time
        return default

    return _mock_get_setting


def _mock_post_factory(pull_data=None, push_success=True):
    """构建 httpx.post 的 mock side_effect，区分 4 种同步请求

    - /pull-files -> {"files": []}
    - /push-files -> {"status": "ok"}
    - /pull -> {"changes": pull_data}
    - /push -> {"success": True} 或 500 错误
    """

    def _mock_post(*args, **kwargs):
        url = kwargs.get("url", "")
        if "/pull-files" in url:
            return _make_mock_response({"files": []})
        elif "/push-files" in url:
            if push_success:
                return _make_mock_response({"status": "ok", "written": 0, "skipped": 0})
            else:
                mock_resp = MagicMock()
                mock_resp.status_code = 500
                mock_resp.raise_for_status.side_effect = Exception("HTTP 500 Push Failed")
                return mock_resp
        elif "/pull" in url:
            resp = _make_mock_response({"changes": pull_data or {}})
            return resp
        elif "/push" in url:
            if push_success:
                return _make_mock_response({"success": True})
            else:
                mock_resp = MagicMock()
                mock_resp.status_code = 500
                mock_resp.raise_for_status.side_effect = Exception("HTTP 500 Push Failed")
                return mock_resp
        return _make_mock_response({})

    return _mock_post


# ==================== Seam 1: LWW 冲突解决在 UTC ISO 8601 格式下正确工作 ====================


class TestLwwWithUtcIso8601:
    """Seam 1: LWW 冲突解决在 UTC ISO 8601 格式下正确工作

    验证：当本地和远程的 updated_at 都使用 UTC ISO 8601 格式时，
    LWW 字符串比较能正确判断新旧关系。

    背景：迁移前本地使用 naive 本地时间（如 "2026-07-01 18:00:00"），
    远程使用 UTC ISO 8601（如 "2026-07-01T10:00:00+00:00"），
    字符串比较错误。迁移后两者统一为 UTC ISO 8601，比较正确。
    """

    def test_lww_keeps_local_when_local_newer_with_utc_iso(
        self, sync_repository, initialized_db, clean_tables
    ):
        """LWW: 本地更新（UTC ISO）→ 保留本地，跳过远程旧数据"""
        # Arrange: 本地记录 updated_at = UTC 10:00
        local_updated_at = _utc_iso(0)
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO todo_list (id, content, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    "todo-utc-lww-001",
                    "本地新内容",
                    "completed",
                    local_updated_at,
                    local_updated_at,
                ),
            )
            conn.commit()

        # Act: 远程推送更旧的数据（updated_at = UTC 09:00，比本地早 1 小时）
        remote_row = {
            "id": "todo-utc-lww-001",
            "content": "远程旧内容",
            "state": "pool",
            "created_at": _utc_iso(-3600),
            "updated_at": _utc_iso(-3600),
        }
        affected = sync_repository.upsert_rows_with_lww("todo_list", [remote_row])

        # Assert: 旧数据被跳过
        assert affected == 0
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content, state FROM todo_list WHERE id = ?", ("todo-utc-lww-001",)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "本地新内容"
            assert row[1] == "completed"

    def test_lww_overwrites_local_when_remote_newer_with_utc_iso(
        self, sync_repository, initialized_db, clean_tables
    ):
        """LWW: 远程更新（UTC ISO）→ 远程覆盖本地旧数据"""
        # Arrange: 本地记录 updated_at = UTC 10:00
        local_updated_at = _utc_iso(0)
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO todo_list (id, content, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("todo-utc-lww-002", "本地旧内容", "pool", local_updated_at, local_updated_at),
            )
            conn.commit()

        # Act: 远程推送更新的数据（updated_at = UTC 11:00，比本地晚 1 小时）
        remote_row = {
            "id": "todo-utc-lww-002",
            "content": "远程新内容",
            "state": "completed",
            "created_at": _utc_iso(0),
            "updated_at": _utc_iso(3600),
        }
        affected = sync_repository.upsert_rows_with_lww("todo_list", [remote_row])

        # Assert: 新数据被写入
        assert affected == 1
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content, state FROM todo_list WHERE id = ?", ("todo-utc-lww-002",)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "远程新内容"
            assert row[1] == "completed"

    def test_lww_string_comparison_is_correct_for_utc_iso(self):
        """LWW: UTC ISO 8601 字符串比较与时间顺序一致

        验证：ISO 8601 格式的字符串字典序与时间顺序一致，
        这是 LWW 字符串比较正确性的基础。
        """
        earlier = _utc_iso(0)  # "2026-07-01T10:00:00.000000+00:00"
        later = _utc_iso(3600)  # "2026-07-01T11:00:00.000000+00:00"

        # 字符串比较应与时间顺序一致
        assert earlier < later
        assert later > earlier

    def test_lww_resolves_correctly_in_pull_from_remote_with_utc_iso(
        self, sync_client, initialized_db, clean_tables
    ):
        """LWW: pull_from_remote 在 UTC ISO 8601 格式下正确解决冲突

        场景：本地已修改（updated_at > last_sync_time），远程也修改了
        验证：比较 UTC ISO 8601 格式的 updated_at，谁更晚谁保留
        """
        # Arrange: 本地已修改记录（updated_at > last_sync_time）
        local_updated_at = _utc_iso(3600)  # UTC 11:00
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO todo_list (id, content, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    "todo-pull-lww-001",
                    "本地修改内容",
                    "scheduled",
                    _utc_iso(0),
                    local_updated_at,
                ),
            )
            conn.commit()

        # 远程记录 updated_at = UTC 12:00（比本地更晚）
        remote_row = {
            "id": "todo-pull-lww-001",
            "content": "远程更新内容",
            "state": "completed",
            "created_at": _utc_iso(0),
            "updated_at": _utc_iso(7200),  # UTC 12:00，比本地 11:00 更晚
        }
        mock_response = _make_mock_response({"changes": {"todo_list": [remote_row]}})

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=mock_response):
            # last_sync_time = UTC 10:00，本地 updated_at = UTC 11:00 > last_sync_time → 本地已修改
            # 远程 updated_at = UTC 12:00 > 本地 UTC 11:00 → 远程覆盖本地
            sync_client.pull_from_remote(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time=_utc_iso(0),
                tables=["todo_list"],
            )

        # Assert: 本地被远程覆盖
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content, state FROM todo_list WHERE id = ?", ("todo-pull-lww-001",)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "远程更新内容"
            assert row[1] == "completed"


# ==================== Seam 2: 跨时区同步场景（本地 UTC+8、云端 UTC）====================


class TestCrossTimezoneSync:
    """Seam 2: 跨时区同步场景

    验证：迁移后，无论本地机器时区如何（如 UTC+8），
    本地和云端都使用 datetime.now(timezone.utc).isoformat() 生成时间戳，
    格式一致，LWW 比较正确。

    背景：迁移前本地用 datetime.now()（naive 本地时间），云端用 datetime.now(timezone.utc)，
    导致同一时刻生成的时间戳字符串不同，LWW 比较错误。
    """

    def test_cross_timezone_sync_both_use_utc_iso(
        self, sync_client, initialized_db, clean_tables
    ):
        """跨时区同步：本地 UTC+8 和云端 UTC 都生成 UTC ISO 8601，LWW 正确"""
        # 模拟：本地机器在 UTC+8，但迁移后使用 datetime.now(timezone.utc)
        # 此时本地时间 18:00 (UTC+8) = UTC 10:00
        # 本地生成的 updated_at = "2026-07-01T10:00:00+00:00" (UTC ISO)
        local_utc_iso = _utc_iso(0)  # UTC 10:00

        # 模拟：云端机器在 UTC，使用 datetime.now(timezone.utc)
        # 云端生成的 updated_at = "2026-07-01T11:00:00+00:00" (UTC ISO，1 小时后)
        remote_utc_iso = _utc_iso(3600)  # UTC 11:00

        # Arrange: 本地插入记录
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO todo_list (id, content, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    "todo-cross-tz-001",
                    "本地内容",
                    "pool",
                    local_utc_iso,
                    local_utc_iso,
                ),
            )
            conn.commit()

        # 远程推送更新记录
        remote_row = {
            "id": "todo-cross-tz-001",
            "content": "远程更新内容",
            "state": "completed",
            "created_at": local_utc_iso,
            "updated_at": remote_utc_iso,  # 比本地晚 1 小时
        }
        mock_response = _make_mock_response({"changes": {"todo_list": [remote_row]}})

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=mock_response):
            # last_sync_time = UTC 09:00，本地 updated_at = UTC 10:00 > last_sync_time → 本地已修改
            # 远程 updated_at = UTC 11:00 > 本地 UTC 10:00 → 远程覆盖
            sync_client.pull_from_remote(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time=_utc_iso(-3600),  # UTC 09:00
                tables=["todo_list"],
            )

        # Assert: 远程覆盖本地（因为远程 UTC 11:00 > 本地 UTC 10:00）
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content, state FROM todo_list WHERE id = ?", ("todo-cross-tz-001",)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "远程更新内容"
            assert row[1] == "completed"

    def test_cross_timezone_sync_no_false_duplicate_push(
        self, sync_client, initialized_db, clean_tables
    ):
        """跨时区同步：迁移后不会因时区差异导致每次同步都推送全部数据

        背景：迁移前，本地 updated_at 是 naive 本地时间 "2026-07-01 18:00:00"，
        last_sync_time 是 UTC ISO "2026-07-01T10:00:00+00:00"，
        字符串比较 "2026-07-01 18:00:00" > "2026-07-01T10:00:00+00:00" 恒为 True
        （因为 '1' < '2' 在第二位字符位置），导致每次 push 都推送全部数据。

        迁移后，两者都是 UTC ISO 格式，比较正确，不会重复推送。
        """
        # Arrange: 本地记录 updated_at = UTC 10:00 (迁移后格式)
        local_updated_at = _utc_iso(0)  # "2026-07-01T10:00:00.000000+00:00"
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO todo_list (id, content, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    "todo-no-dup-001",
                    "本地内容",
                    "pool",
                    local_updated_at,
                    local_updated_at,
                ),
            )
            conn.commit()

        # last_sync_time = UTC 10:00 (与本地 updated_at 相同)
        # 迁移后：str(local_updated_at) <= str(last_sync_time) → 本地未修改 → 不推送
        mock_response = _make_mock_response({"success": True})

        with (
            patch(
                "lifeprism.sync.sync_client.httpx.post", return_value=mock_response
            ) as mock_post,
            patch(
                "lifeprism.config.settings_manager.get_setting",
                return_value=local_updated_at,  # last_sync_time = UTC 10:00
            ),
        ):
            sync_client.push_to_remote(
                remote_url="http://test:8000",
                api_key="test-key",
                tables=["todo_list"],
            )

        # Assert: 不应推送该记录（因为 updated_at <= last_sync_time）
        tables_data = mock_post.call_args.kwargs["json"]["changes"]
        assert "todo_list" not in tables_data or len(tables_data.get("todo_list", [])) == 0

    def test_cross_timezone_sync_local_newer_keeps_local(
        self, sync_client, initialized_db, clean_tables
    ):
        """跨时区同步：本地更晚（UTC ISO）→ 保留本地，不拉取远程旧数据"""
        # Arrange: 本地 updated_at = UTC 12:00 (较晚)
        local_updated_at = _utc_iso(7200)  # UTC 12:00
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO todo_list (id, content, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    "todo-cross-tz-002",
                    "本地新内容",
                    "scheduled",
                    _utc_iso(0),
                    local_updated_at,
                ),
            )
            conn.commit()

        # 远程 updated_at = UTC 11:00 (较早)
        remote_row = {
            "id": "todo-cross-tz-002",
            "content": "远程旧内容",
            "state": "pool",
            "created_at": _utc_iso(0),
            "updated_at": _utc_iso(3600),  # UTC 11:00，比本地 12:00 早
        }
        mock_response = _make_mock_response({"changes": {"todo_list": [remote_row]}})

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=mock_response):
            # last_sync_time = UTC 10:00，本地 updated_at = UTC 12:00 > last_sync_time → 本地已修改
            # 远程 updated_at = UTC 11:00 < 本地 UTC 12:00 → 保留本地
            sync_client.pull_from_remote(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time=_utc_iso(0),  # UTC 10:00
                tables=["todo_list"],
            )

        # Assert: 本地保留
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content, state FROM todo_list WHERE id = ?", ("todo-cross-tz-002",)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "本地新内容"
            assert row[1] == "scheduled"


# ==================== Seam 3: last_sync_time 使用 UTC ISO 格式 ====================


class TestLastSyncTimeUtcIso:
    """Seam 3: last_sync_time 使用 UTC ISO 格式

    验证：sync_once() 成功后更新的 last_sync_time 是 UTC ISO 8601 格式，
    包含时区标识（+00:00）。
    """

    def test_sync_once_writes_utc_timezone_identifier(
        self, sync_client, initialized_db, clean_tables
    ):
        """last_sync_time 包含 UTC 时区标识 +00:00"""
        with (
            patch(
                "lifeprism.sync.sync_client.httpx.post",
                side_effect=_mock_post_factory(),
            ),
            patch(
                "lifeprism.config.settings_manager.get_setting",
                side_effect=_mock_get_setting_factory(),
            ),
            patch("lifeprism.sync.sync_config.get_sync_api_key", return_value="test-key"),
            patch("lifeprism.config.settings_manager.set_setting") as mock_set_setting,
        ):
            sync_client.sync_once(tables=["todo_list"])

        mock_set_setting.assert_called_once()
        args = mock_set_setting.call_args
        assert args.args[0] == "sync.last_sync_time"
        last_sync_time = args.args[1]
        # UTC ISO 8601 格式包含 +00:00 时区标识
        assert "+00:00" in last_sync_time, (
            f"last_sync_time 应为 UTC ISO 8601 格式（包含 +00:00），实际: {last_sync_time}"
        )

    def test_sync_once_last_sync_time_is_parseable_as_utc(
        self, sync_client, initialized_db, clean_tables
    ):
        """last_sync_time 可被解析为 UTC aware datetime"""
        with (
            patch(
                "lifeprism.sync.sync_client.httpx.post",
                side_effect=_mock_post_factory(),
            ),
            patch(
                "lifeprism.config.settings_manager.get_setting",
                side_effect=_mock_get_setting_factory(),
            ),
            patch("lifeprism.sync.sync_config.get_sync_api_key", return_value="test-key"),
            patch("lifeprism.config.settings_manager.set_setting") as mock_set_setting,
        ):
            sync_client.sync_once(tables=["todo_list"])

        args = mock_set_setting.call_args
        last_sync_time = args.args[1]

        # 解析为 datetime 对象
        parsed = datetime.fromisoformat(last_sync_time)
        # 验证是 aware datetime（tzinfo 不为 None）
        assert parsed.tzinfo is not None, (
            f"last_sync_time 解析后应为 aware datetime，实际 tzinfo=None: {last_sync_time}"
        )
        # 验证时区是 UTC（utcoffset 为 0）
        assert parsed.utcoffset() == timedelta(0), (
            f"last_sync_time 时区应为 UTC（utcoffset=0），实际: {parsed.utcoffset()}"
        )
