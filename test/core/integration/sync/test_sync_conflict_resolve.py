"""
SyncClient CONFLICT_RESOLVE 冲突解决测试（Issue 34）

测试 seam:
- Seam 1: bus 桥接（run_coroutine_threadsafe 调用 bus.send）
- Seam 2: AI 合并结果处理（备份+写入+更新hash+更新file_sync_state）
- Seam 3: AI 合并失败/超时处理（保留本地版本）
- Seam 4: 合并结果推送（Phase 2c）

TDD: 严格 red-green 循环
"""

import base64
import gzip
import shutil
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
def clean_conflict_test_dir(initialized_db):
    """为每个测试提供干净的冲突测试目录"""
    from lifeprism.config.settings_manager import settings

    test_dir = settings.lifeprism_data_path / "conflict_test"
    if test_dir.exists():
        shutil.rmtree(test_dir, ignore_errors=True)
    test_dir.mkdir(parents=True, exist_ok=True)
    yield test_dir
    if test_dir.exists():
        shutil.rmtree(test_dir, ignore_errors=True)


@pytest.fixture
def clean_file_sync_state(initialized_db):
    """每个测试前后清理 file_sync_state 表"""
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM file_sync_state")
        conn.commit()
    yield
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM file_sync_state")
        conn.commit()


@pytest.fixture
def clean_sync_conflict_dir(initialized_db):
    """清理 sync_conflict 备份目录"""
    from lifeprism.config.settings_manager import settings

    conflict_dir = settings.lifeprism_data_path / "sync_conflict"
    if conflict_dir.exists():
        shutil.rmtree(conflict_dir, ignore_errors=True)
    yield
    if conflict_dir.exists():
        shutil.rmtree(conflict_dir, ignore_errors=True)


def _make_mock_response(json_data, status_code=200):
    """构建 mock httpx.Response 对象"""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    mock_resp.raise_for_status = MagicMock()
    if status_code >= 400:
        mock_resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return mock_resp


def _encode_file_content(content: str) -> str:
    """gzip+base64 编码文件内容（模拟云端返回格式）"""
    compressed = gzip.compress(content.encode("utf-8"))
    return base64.b64encode(compressed).decode("ascii")


# ==================== Seam 1: bus 桥接（run_coroutine_threadsafe） ====================


class TestBusBridge:
    """Seam 1: SyncClient 通过 run_coroutine_threadsafe 桥接 bus.send

    SyncClient 在同步线程中通过 asyncio.run_coroutine_threadsafe()
    将 bus.send() 提交到主线程的事件循环。
    """

    def test_sync_client_stores_main_event_loop(self, initialized_db, sync_repository, mock_event_loop):
        """SyncClient 应保存 main_event_loop 引用"""
        from lifeprism.sync.sync_client import SyncClient

        client = SyncClient(
            db_manager=initialized_db,
            sync_repository=sync_repository,
            main_event_loop=mock_event_loop,
        )
        assert client._main_event_loop is mock_event_loop

    def test_bus_bridge_calls_run_coroutine_threadsafe(
        self, sync_client, initialized_db, clean_conflict_test_dir,
        clean_file_sync_state, clean_sync_conflict_dir,
    ):
        """_resolve_conflicts 应通过 run_coroutine_threadsafe 调用 bus.send"""
        from lifeprism.config.settings_manager import settings

        # Arrange: 创建本地冲突文件
        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        local_content = "# 本地日记\n今天心情不错"
        local_file = test_base / "diary" / "2026-07-14.md"
        local_file.write_text(local_content, encoding="utf-8")

        remote_content = "# 云端日记\n今天天气晴朗"
        fetch_response = _make_mock_response({
            "files": [{
                "path": "conflict_test/diary/2026-07-14.md",
                "content": _encode_file_content(remote_content),
                "parent_hash": "old_hash",
                "current_hash": "remote_hash",
            }]
        })

        # Mock bus bridge: run_coroutine_threadsafe 返回 mock future
        from lifeprism.llm.bus.events import OutboundMessage
        from lifeprism.llm.providers import LLMResponse

        mock_future = MagicMock()
        mock_future.result.return_value = OutboundMessage(
            response=LLMResponse(content="# 合并后的日记\n今天心情不错，天气晴朗"),
        )

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=fetch_response), \
             patch("lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe", return_value=mock_future) as mock_rcts:

            # Act
            sync_client._resolve_conflicts(
                conflict_paths=["conflict_test/diary/2026-07-14.md"],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: 调用了 run_coroutine_threadsafe
        mock_rcts.assert_called_once()
        # 第二个参数是事件循环
        assert mock_rcts.call_args[0][1] is sync_client._main_event_loop

    def test_bus_bridge_waits_with_timeout_600(
        self, sync_client, initialized_db, clean_conflict_test_dir,
        clean_file_sync_state, clean_sync_conflict_dir,
    ):
        """future.result 应以 timeout=600 等待 AI 合并完成"""
        from lifeprism.config.settings_manager import settings
        from lifeprism.llm.bus.events import OutboundMessage
        from lifeprism.llm.providers import LLMResponse

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        local_file = test_base / "diary" / "2026-07-14.md"
        local_file.write_text("本地内容", encoding="utf-8")

        fetch_response = _make_mock_response({
            "files": [{
                "path": "conflict_test/diary/2026-07-14.md",
                "content": _encode_file_content("云端内容"),
                "parent_hash": "old_hash",
                "current_hash": "remote_hash",
            }]
        })

        mock_future = MagicMock()
        mock_future.result.return_value = OutboundMessage(
            response=LLMResponse(content="合并后的内容"),
        )

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=fetch_response), \
             patch("lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe", return_value=mock_future):

            sync_client._resolve_conflicts(
                conflict_paths=["conflict_test/diary/2026-07-14.md"],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: future.result 以 timeout=600 调用
        mock_future.result.assert_called_once_with(timeout=600)


# ==================== Seam 2: AI 合并结果处理（备份+写入+更新hash+更新file_sync_state） ====================


class TestMergeResultHandling:
    """Seam 2: _resolve_conflicts 正确处理 AI 合并结果

    成功合并后应：
    1. 备份本地版本到 sync_conflict/{timestamp}/{file_path}
    2. 写入合并内容到本地文件
    3. 更新 file_sync_state.current_hash = compute_file_hash(merged_content)
    4. 保持 file_sync_state.parent_hash 不变
    5. 返回成功合并的文件路径列表
    """

    def test_resolve_conflicts_backs_up_local_version(
        self, sync_client, initialized_db, clean_conflict_test_dir,
        clean_file_sync_state, clean_sync_conflict_dir,
    ):
        """成功合并后应备份本地版本到 sync_conflict/{timestamp}/{file_path}"""
        from lifeprism.config.settings_manager import settings
        from lifeprism.llm.bus.events import OutboundMessage
        from lifeprism.llm.providers import LLMResponse

        # Arrange: 创建本地冲突文件
        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        local_content = "# 本地日记\n今天心情不错"
        rel_path = "conflict_test/diary/2026-07-14.md"
        local_file = test_base / "diary" / "2026-07-14.md"
        local_file.write_text(local_content, encoding="utf-8")

        fetch_response = _make_mock_response({
            "files": [{
                "path": rel_path,
                "content": _encode_file_content("# 云端日记\n今天天气晴朗"),
                "parent_hash": "old_hash",
                "current_hash": "remote_hash",
            }]
        })

        mock_future = MagicMock()
        mock_future.result.return_value = OutboundMessage(
            response=LLMResponse(content="# 合并后的日记\n今天心情不错，天气晴朗"),
        )

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=fetch_response), \
             patch("lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe", return_value=mock_future):

            sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: sync_conflict 目录下存在备份文件，内容为本地原始内容
        sync_conflict_dir = settings.lifeprism_data_path / "sync_conflict"
        assert sync_conflict_dir.exists(), "sync_conflict 备份目录应存在"

        # 遍历 timestamp 子目录查找备份文件
        backup_files = list(sync_conflict_dir.rglob("2026-07-14.md"))
        assert len(backup_files) == 1, "应存在 1 个备份文件"
        assert backup_files[0].read_text(encoding="utf-8") == local_content

    def test_resolve_conflicts_writes_merged_content(
        self, sync_client, initialized_db, clean_conflict_test_dir,
        clean_file_sync_state, clean_sync_conflict_dir,
    ):
        """成功合并后本地文件应被覆盖为合并后内容"""
        from lifeprism.config.settings_manager import settings
        from lifeprism.llm.bus.events import OutboundMessage
        from lifeprism.llm.providers import LLMResponse

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/2026-07-14.md"
        local_file = test_base / "diary" / "2026-07-14.md"
        local_file.write_text("# 本地日记\n今天心情不错", encoding="utf-8")

        merged_content = "# 合并后的日记\n今天心情不错，天气晴朗"
        fetch_response = _make_mock_response({
            "files": [{
                "path": rel_path,
                "content": _encode_file_content("# 云端日记"),
                "parent_hash": "old_hash",
                "current_hash": "remote_hash",
            }]
        })

        mock_future = MagicMock()
        mock_future.result.return_value = OutboundMessage(
            response=LLMResponse(content=merged_content),
        )

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=fetch_response), \
             patch("lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe", return_value=mock_future):

            sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: 本地文件已被合并内容覆盖
        assert local_file.read_text(encoding="utf-8") == merged_content

    def test_resolve_conflicts_updates_current_hash(
        self, sync_client, initialized_db, clean_conflict_test_dir,
        clean_file_sync_state, clean_sync_conflict_dir,
    ):
        """成功合并后 file_sync_state.current_hash 应为 compute_file_hash(merged_content)"""
        from lifeprism.config.settings_manager import settings
        from lifeprism.llm.bus.events import OutboundMessage
        from lifeprism.llm.providers import LLMResponse
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/2026-07-14.md"
        local_file = test_base / "diary" / "2026-07-14.md"
        local_file.write_text("# 本地内容", encoding="utf-8")

        merged_content = "# 合并后的内容\n保留双方信息"
        expected_hash = compute_file_hash(merged_content.encode("utf-8"))

        fetch_response = _make_mock_response({
            "files": [{
                "path": rel_path,
                "content": _encode_file_content("# 云端内容"),
                "parent_hash": "old_hash",
                "current_hash": "remote_hash",
            }]
        })

        mock_future = MagicMock()
        mock_future.result.return_value = OutboundMessage(
            response=LLMResponse(content=merged_content),
        )

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=fetch_response), \
             patch("lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe", return_value=mock_future):

            sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: current_hash 已更新为合并内容的 hash
        provider = FileSyncStateProvider(db_manager=initialized_db)
        state = provider.get_state(rel_path)
        assert state is not None, "file_sync_state 记录应存在"
        assert state["current_hash"] == expected_hash

    def test_resolve_conflicts_preserves_parent_hash(
        self, sync_client, initialized_db, clean_conflict_test_dir,
        clean_file_sync_state, clean_sync_conflict_dir,
    ):
        """成功合并后 file_sync_state.parent_hash 应保持不变"""
        from lifeprism.config.settings_manager import settings
        from lifeprism.llm.bus.events import OutboundMessage
        from lifeprism.llm.providers import LLMResponse
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/2026-07-14.md"
        local_file = test_base / "diary" / "2026-07-14.md"
        local_file.write_text("# 本地内容", encoding="utf-8")

        # 预设 file_sync_state 记录，parent_hash = "original_parent_hash"
        original_parent_hash = "original_parent_hash"
        provider = FileSyncStateProvider(db_manager=initialized_db)
        provider.upsert_state(
            file_path=rel_path,
            parent_hash=original_parent_hash,
            current_hash="old_current_hash",
        )

        fetch_response = _make_mock_response({
            "files": [{
                "path": rel_path,
                "content": _encode_file_content("# 云端内容"),
                "parent_hash": original_parent_hash,
                "current_hash": "remote_hash",
            }]
        })

        mock_future = MagicMock()
        mock_future.result.return_value = OutboundMessage(
            response=LLMResponse(content="# 合并后的内容"),
        )

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=fetch_response), \
             patch("lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe", return_value=mock_future):

            sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: parent_hash 保持不变
        state = provider.get_state(rel_path)
        assert state is not None
        assert state["parent_hash"] == original_parent_hash

    def test_resolve_conflicts_returns_resolved_paths(
        self, sync_client, initialized_db, clean_conflict_test_dir,
        clean_file_sync_state, clean_sync_conflict_dir,
    ):
        """_resolve_conflicts 应返回成功合并的文件路径列表"""
        from lifeprism.config.settings_manager import settings
        from lifeprism.llm.bus.events import OutboundMessage
        from lifeprism.llm.providers import LLMResponse

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/2026-07-14.md"
        local_file = test_base / "diary" / "2026-07-14.md"
        local_file.write_text("# 本地内容", encoding="utf-8")

        fetch_response = _make_mock_response({
            "files": [{
                "path": rel_path,
                "content": _encode_file_content("# 云端内容"),
                "parent_hash": "old_hash",
                "current_hash": "remote_hash",
            }]
        })

        mock_future = MagicMock()
        mock_future.result.return_value = OutboundMessage(
            response=LLMResponse(content="# 合并后的内容"),
        )

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=fetch_response), \
             patch("lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe", return_value=mock_future):

            result = sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: 返回列表包含成功合并的路径
        assert result == [rel_path]


# ==================== Seam 3: AI 合并失败/超时处理（保留本地版本） ====================


class TestMergeFailureHandling:
    """Seam 3: _resolve_conflicts 失败/超时处理

    失败场景应保留本地版本不变：
    1. TimeoutError: future.result 超时
    2. AI 返回空内容
    3. 其他异常
    4. 获取远端文件失败
    5. 本地文件不存在

    所有失败场景：
    - 本地文件内容保持不变
    - 不创建备份
    - file_sync_state 不被更新（parent_hash/current_hash 不变）
    - 失败的路径不在返回的 resolved_paths 列表中
    """

    def test_timeout_preserves_local_version(
        self, sync_client, initialized_db, clean_conflict_test_dir,
        clean_file_sync_state, clean_sync_conflict_dir,
    ):
        """TimeoutError 时本地版本应保留不变"""
        from lifeprism.config.settings_manager import settings

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/2026-07-14.md"
        local_file = test_base / "diary" / "2026-07-14.md"
        local_content = "# 本地日记\n原始内容"
        local_file.write_text(local_content, encoding="utf-8")

        fetch_response = _make_mock_response({
            "files": [{
                "path": rel_path,
                "content": _encode_file_content("# 云端内容"),
                "parent_hash": "old_hash",
                "current_hash": "remote_hash",
            }]
        })

        # Mock future.result 抛出 TimeoutError
        mock_future = MagicMock()
        mock_future.result.side_effect = TimeoutError()

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=fetch_response), \
             patch("lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe", return_value=mock_future):

            result = sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: 本地文件内容不变
        assert local_file.read_text(encoding="utf-8") == local_content
        # Assert: 不在 resolved_paths 中
        assert result == []
        # Assert: 未创建备份目录
        sync_conflict_dir = settings.lifeprism_data_path / "sync_conflict"
        assert not sync_conflict_dir.exists() or not list(sync_conflict_dir.rglob("2026-07-14.md"))

    def test_empty_merged_content_preserves_local_version(
        self, sync_client, initialized_db, clean_conflict_test_dir,
        clean_file_sync_state, clean_sync_conflict_dir,
    ):
        """AI 返回空内容时本地版本应保留不变"""
        from lifeprism.config.settings_manager import settings
        from lifeprism.llm.bus.events import OutboundMessage
        from lifeprism.llm.providers import LLMResponse

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/2026-07-14.md"
        local_file = test_base / "diary" / "2026-07-14.md"
        local_content = "# 本地日记\n原始内容"
        local_file.write_text(local_content, encoding="utf-8")

        fetch_response = _make_mock_response({
            "files": [{
                "path": rel_path,
                "content": _encode_file_content("# 云端内容"),
                "parent_hash": "old_hash",
                "current_hash": "remote_hash",
            }]
        })

        # Mock 返回空内容
        mock_future = MagicMock()
        mock_future.result.return_value = OutboundMessage(
            response=LLMResponse(content=""),
        )

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=fetch_response), \
             patch("lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe", return_value=mock_future):

            result = sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: 本地文件内容不变
        assert local_file.read_text(encoding="utf-8") == local_content
        # Assert: 不在 resolved_paths 中
        assert result == []

    def test_empty_merged_content_preserves_file_sync_state(
        self, sync_client, initialized_db, clean_conflict_test_dir,
        clean_file_sync_state, clean_sync_conflict_dir,
    ):
        """AI 返回空内容时 file_sync_state 不应被更新"""
        from lifeprism.config.settings_manager import settings
        from lifeprism.llm.bus.events import OutboundMessage
        from lifeprism.llm.providers import LLMResponse
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/2026-07-14.md"
        local_file = test_base / "diary" / "2026-07-14.md"
        local_file.write_text("# 本地内容", encoding="utf-8")

        # 预设 file_sync_state
        original_parent = "original_parent"
        original_current = "original_current"
        provider = FileSyncStateProvider(db_manager=initialized_db)
        provider.upsert_state(
            file_path=rel_path,
            parent_hash=original_parent,
            current_hash=original_current,
        )

        fetch_response = _make_mock_response({
            "files": [{
                "path": rel_path,
                "content": _encode_file_content("# 云端内容"),
                "parent_hash": original_parent,
                "current_hash": "remote_hash",
            }]
        })

        mock_future = MagicMock()
        mock_future.result.return_value = OutboundMessage(
            response=LLMResponse(content="   "),  # 仅空白字符也算空
        )

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=fetch_response), \
             patch("lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe", return_value=mock_future):

            sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: file_sync_state 不变
        state = provider.get_state(rel_path)
        assert state is not None
        assert state["parent_hash"] == original_parent
        assert state["current_hash"] == original_current

    def test_generic_exception_preserves_local_version(
        self, sync_client, initialized_db, clean_conflict_test_dir,
        clean_file_sync_state, clean_sync_conflict_dir,
    ):
        """其他异常时本地版本应保留不变"""
        from lifeprism.config.settings_manager import settings

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/2026-07-14.md"
        local_file = test_base / "diary" / "2026-07-14.md"
        local_content = "# 本地日记\n原始内容"
        local_file.write_text(local_content, encoding="utf-8")

        fetch_response = _make_mock_response({
            "files": [{
                "path": rel_path,
                "content": _encode_file_content("# 云端内容"),
                "parent_hash": "old_hash",
                "current_hash": "remote_hash",
            }]
        })

        # Mock future.result 抛出通用异常
        mock_future = MagicMock()
        mock_future.result.side_effect = RuntimeError("LLM 服务不可用")

        with patch("lifeprism.sync.sync_client.httpx.post", return_value=fetch_response), \
             patch("lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe", return_value=mock_future):

            result = sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: 本地文件内容不变
        assert local_file.read_text(encoding="utf-8") == local_content
        # Assert: 不在 resolved_paths 中
        assert result == []

    def test_fetch_remote_failure_skips_file(
        self, sync_client, initialized_db, clean_conflict_test_dir,
        clean_file_sync_state, clean_sync_conflict_dir,
    ):
        """获取远端文件失败时应跳过该文件"""
        from lifeprism.config.settings_manager import settings

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/2026-07-14.md"
        local_file = test_base / "diary" / "2026-07-14.md"
        local_content = "# 本地日记\n原始内容"
        local_file.write_text(local_content, encoding="utf-8")

        # Mock httpx.post 抛出异常（获取远端失败）
        with patch("lifeprism.sync.sync_client.httpx.post", side_effect=httpx.RequestError("网络错误")):

            result = sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: 本地文件内容不变
        assert local_file.read_text(encoding="utf-8") == local_content
        # Assert: 不在 resolved_paths 中
        assert result == []

    def test_missing_local_file_skips(
        self, sync_client, initialized_db, clean_conflict_test_dir,
        clean_file_sync_state, clean_sync_conflict_dir,
    ):
        """本地文件不存在时应跳过该文件"""
        rel_path = "conflict_test/diary/nonexistent.md"

        # 不创建本地文件
        result = sync_client._resolve_conflicts(
            conflict_paths=[rel_path],
            remote_url="http://test:8000",
            api_key="test-key",
        )

        # Assert: 不在 resolved_paths 中
        assert result == []

    def test_partial_failure_returns_only_successful(
        self, sync_client, initialized_db, clean_conflict_test_dir,
        clean_file_sync_state, clean_sync_conflict_dir,
    ):
        """多个冲突文件中部分失败时，只返回成功的路径"""
        from lifeprism.config.settings_manager import settings
        from lifeprism.llm.bus.events import OutboundMessage
        from lifeprism.llm.providers import LLMResponse

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)

        # 文件1：会成功合并
        rel_path1 = "conflict_test/diary/success.md"
        local_file1 = test_base / "diary" / "success.md"
        local_file1.write_text("# 本地内容1", encoding="utf-8")

        # 文件2：会超时失败
        rel_path2 = "conflict_test/diary/timeout.md"
        local_file2 = test_base / "diary" / "timeout.md"
        local_content2 = "# 本地内容2\n原始"
        local_file2.write_text(local_content2, encoding="utf-8")

        # Mock: 第一次调用返回成功，第二次调用抛出 TimeoutError
        fetch_response = _make_mock_response({
            "files": [{
                "path": rel_path1,
                "content": _encode_file_content("# 云端内容1"),
                "parent_hash": "old_hash1",
                "current_hash": "remote_hash1",
            }]
        })
        fetch_response2 = _make_mock_response({
            "files": [{
                "path": rel_path2,
                "content": _encode_file_content("# 云端内容2"),
                "parent_hash": "old_hash2",
                "current_hash": "remote_hash2",
            }]
        })

        mock_future_success = MagicMock()
        mock_future_success.result.return_value = OutboundMessage(
            response=LLMResponse(content="# 合并后内容1"),
        )
        mock_future_timeout = MagicMock()
        mock_future_timeout.result.side_effect = TimeoutError()

        with patch("lifeprism.sync.sync_client.httpx.post", side_effect=[fetch_response, fetch_response2]), \
             patch("lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe",
                   side_effect=[mock_future_success, mock_future_timeout]):

            result = sync_client._resolve_conflicts(
                conflict_paths=[rel_path1, rel_path2],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: 只返回成功的路径
        assert result == [rel_path1]
        # Assert: 失败的文件本地内容不变
        assert local_file2.read_text(encoding="utf-8") == local_content2


# ==================== Seam 4: _sync_files_full_flow 集成（CONFLICT→AI合并→Phase 2c推送） ====================


class TestFullFlowConflictIntegration:
    """Seam 4: _sync_files_full_flow 集成 CONFLICT 解决流程

    _sync_files_full_flow 应在检测到 CONFLICT 文件后：
    1. 调用 _resolve_conflicts 进行 AI 合并
    2. 将成功合并的文件加入 push_paths（Phase 2c 推送）
    3. 将成功合并的文件加入 verify_paths（Phase 3 校验）
    """

    @pytest.fixture
    def mock_sync_client(self, sync_client):
        """创建内部方法均已 mock 的 SyncClient"""
        # Mock 所有子方法，便于隔离测试 _sync_files_full_flow 的编排逻辑
        sync_client._refresh_current_hashes = MagicMock()
        sync_client._pull_files_check = MagicMock(return_value=([], []))
        sync_client._pull_files_fetch = MagicMock()
        sync_client._push_files = MagicMock()
        sync_client._verify_and_advance_parent = MagicMock()
        sync_client._resolve_conflicts = MagicMock(return_value=[])
        sync_client._scan_sync_files = MagicMock(return_value=[])
        return sync_client

    def test_full_flow_calls_resolve_conflicts_for_conflict_files(
        self, mock_sync_client, initialized_db, clean_file_sync_state,
    ):
        """_sync_files_full_flow 应为 CONFLICT 文件调用 _resolve_conflicts"""
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider

        # Arrange: 设置矩阵判定为 CONFLICT
        # local: parent=A, current=B; remote: parent=A, current=C → CONFLICT (Row 9)
        conflict_path = "diary/conflict.md"
        provider = FileSyncStateProvider(db_manager=initialized_db)
        provider.upsert_state(
            file_path=conflict_path,
            parent_hash="hash_a",
            current_hash="hash_b",
        )

        mock_sync_client._refresh_current_hashes.return_value = [conflict_path]
        mock_sync_client._pull_files_check.return_value = ([{
            "path": conflict_path,
            "parent_hash": "hash_a",
            "current_hash": "hash_c",
        }], [])

        # Act
        mock_sync_client._sync_files_full_flow(
            remote_url="http://test:8000",
            api_key="test-key",
            last_sync_time="2026-07-14T00:00:00Z",
            directories=["diary/"],
        )

        # Assert: 调用了 _resolve_conflicts
        mock_sync_client._resolve_conflicts.assert_called_once()
        call_args = mock_sync_client._resolve_conflicts.call_args
        assert conflict_path in call_args[0][0]  # conflict_paths 位置参数
        assert call_args[0][1] == "http://test:8000"  # remote_url
        assert call_args[0][2] == "test-key"  # api_key

    def test_full_flow_pushes_resolved_files(
        self, mock_sync_client, initialized_db, clean_file_sync_state,
    ):
        """_sync_files_full_flow 应将合并成功的文件加入 push_paths 推送"""
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider

        # Arrange: 一个 CONFLICT 文件，_resolve_conflicts 返回成功
        conflict_path = "diary/conflict.md"
        provider = FileSyncStateProvider(db_manager=initialized_db)
        provider.upsert_state(
            file_path=conflict_path,
            parent_hash="hash_a",
            current_hash="hash_b",
        )

        mock_sync_client._refresh_current_hashes.return_value = [conflict_path]
        mock_sync_client._pull_files_check.return_value = ([{
            "path": conflict_path,
            "parent_hash": "hash_a",
            "current_hash": "hash_c",
        }], [])
        mock_sync_client._resolve_conflicts.return_value = [conflict_path]

        # Act
        mock_sync_client._sync_files_full_flow(
            remote_url="http://test:8000",
            api_key="test-key",
            last_sync_time="2026-07-14T00:00:00Z",
            directories=["diary/"],
        )

        # Assert: _push_files 被调用且包含 resolved path
        mock_sync_client._push_files.assert_called_once()
        push_paths = mock_sync_client._push_files.call_args[0][2]
        assert conflict_path in push_paths

    def test_full_flow_verifies_resolved_files(
        self, mock_sync_client, initialized_db, clean_file_sync_state,
    ):
        """_sync_files_full_flow 应将合并成功的文件加入 verify_paths 校验"""
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider

        conflict_path = "diary/conflict.md"
        provider = FileSyncStateProvider(db_manager=initialized_db)
        provider.upsert_state(
            file_path=conflict_path,
            parent_hash="hash_a",
            current_hash="hash_b",
        )

        mock_sync_client._refresh_current_hashes.return_value = [conflict_path]
        mock_sync_client._pull_files_check.return_value = ([{
            "path": conflict_path,
            "parent_hash": "hash_a",
            "current_hash": "hash_c",
        }], [])
        mock_sync_client._resolve_conflicts.return_value = [conflict_path]

        # Act
        mock_sync_client._sync_files_full_flow(
            remote_url="http://test:8000",
            api_key="test-key",
            last_sync_time="2026-07-14T00:00:00Z",
            directories=["diary/"],
        )

        # Assert: _verify_and_advance_parent 被调用且包含 resolved path
        mock_sync_client._verify_and_advance_parent.assert_called_once()
        verify_paths = mock_sync_client._verify_and_advance_parent.call_args[0][2]
        assert conflict_path in verify_paths

    def test_full_flow_skips_resolve_when_no_conflicts(
        self, mock_sync_client, initialized_db, clean_file_sync_state,
    ):
        """无 CONFLICT 文件时不应调用 _resolve_conflicts"""
        # Arrange: 一个 PUSH 文件（本地有改，云端未改）
        push_path = "diary/push.md"
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        provider = FileSyncStateProvider(db_manager=initialized_db)
        provider.upsert_state(
            file_path=push_path,
            parent_hash="hash_a",
            current_hash="hash_b",  # 本地改了
        )

        mock_sync_client._refresh_current_hashes.return_value = [push_path]
        # 云端有 parent 但 current=parent（未改）→ PUSH (Row 7)
        mock_sync_client._pull_files_check.return_value = ([{
            "path": push_path,
            "parent_hash": "hash_a",
            "current_hash": "hash_a",
        }], [])

        # Act
        mock_sync_client._sync_files_full_flow(
            remote_url="http://test:8000",
            api_key="test-key",
            last_sync_time="2026-07-14T00:00:00Z",
            directories=["diary/"],
        )

        # Assert: 未调用 _resolve_conflicts
        mock_sync_client._resolve_conflicts.assert_not_called()

    def test_full_flow_does_not_push_failed_resolutions(
        self, mock_sync_client, initialized_db, clean_file_sync_state,
    ):
        """合并失败的文件不应被推送"""
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider

        conflict_path = "diary/conflict.md"
        provider = FileSyncStateProvider(db_manager=initialized_db)
        provider.upsert_state(
            file_path=conflict_path,
            parent_hash="hash_a",
            current_hash="hash_b",
        )

        mock_sync_client._refresh_current_hashes.return_value = [conflict_path]
        mock_sync_client._pull_files_check.return_value = ([{
            "path": conflict_path,
            "parent_hash": "hash_a",
            "current_hash": "hash_c",
        }], [])
        # _resolve_conflicts 返回空列表（全部失败）
        mock_sync_client._resolve_conflicts.return_value = []

        # Act
        mock_sync_client._sync_files_full_flow(
            remote_url="http://test:8000",
            api_key="test-key",
            last_sync_time="2026-07-14T00:00:00Z",
            directories=["diary/"],
        )

        # Assert: _push_files 未被调用（无文件需推送）
        mock_sync_client._push_files.assert_not_called()

    def test_full_flow_jsonl_conflict_goes_lww_not_ai_merge(
        self, mock_sync_client, initialized_db, clean_file_sync_state,
    ):
        """JSONL CONFLICT 文件应走 LWW（直接 push），不调用 _resolve_conflicts"""
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider

        # Arrange: 设置 JSONL 文件为 CONFLICT
        conflict_path = "session/test.jsonl"
        provider = FileSyncStateProvider(db_manager=initialized_db)
        provider.upsert_state(
            file_path=conflict_path,
            parent_hash="hash_a",
            current_hash="hash_b",
        )

        mock_sync_client._refresh_current_hashes.return_value = [conflict_path]
        mock_sync_client._pull_files_check.return_value = ([{
            "path": conflict_path,
            "parent_hash": "hash_a",
            "current_hash": "hash_c",
        }], [])

        # Act
        mock_sync_client._sync_files_full_flow(
            remote_url="http://test:8000",
            api_key="test-key",
            last_sync_time="2026-07-14T00:00:00Z",
            directories=["session/"],
        )

        # Assert: _resolve_conflicts 未被调用（JSONL 走 LWW）
        mock_sync_client._resolve_conflicts.assert_not_called()
        # Assert: _push_files 被调用且包含 JSONL 路径
        mock_sync_client._push_files.assert_called_once()
        push_paths = mock_sync_client._push_files.call_args[0][2]
        assert conflict_path in push_paths

    def test_full_flow_mixed_conflicts_split_correctly(
        self, mock_sync_client, initialized_db, clean_file_sync_state,
    ):
        """混合冲突时 JSONL 走 LWW，MD 走 AI 合并，两条路径互不干扰"""
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider

        # Arrange: 一个 JSONL 和一个 MD 同时 CONFLICT
        jsonl_path = "session/test.jsonl"
        md_path = "diary/conflict.md"
        provider = FileSyncStateProvider(db_manager=initialized_db)
        for path in [jsonl_path, md_path]:
            provider.upsert_state(
                file_path=path,
                parent_hash="hash_a",
                current_hash="hash_b",
            )

        mock_sync_client._refresh_current_hashes.return_value = [jsonl_path, md_path]
        mock_sync_client._pull_files_check.return_value = ([
            {"path": jsonl_path, "parent_hash": "hash_a", "current_hash": "hash_c"},
            {"path": md_path, "parent_hash": "hash_a", "current_hash": "hash_c"},
        ], [])
        mock_sync_client._resolve_conflicts.return_value = [md_path]

        # Act
        mock_sync_client._sync_files_full_flow(
            remote_url="http://test:8000",
            api_key="test-key",
            last_sync_time="2026-07-14T00:00:00Z",
            directories=["session/", "diary/"],
        )

        # Assert: _resolve_conflicts 被调用且只包含 MD 路径
        mock_sync_client._resolve_conflicts.assert_called_once()
        resolve_args = mock_sync_client._resolve_conflicts.call_args[0][0]
        assert md_path in resolve_args
        assert jsonl_path not in resolve_args

        # Assert: _push_files 被调用且同时包含 JSONL 和 MD 路径
        mock_sync_client._push_files.assert_called_once()
        push_paths = mock_sync_client._push_files.call_args[0][2]
        assert jsonl_path in push_paths
        assert md_path in push_paths

    def test_full_flow_jsonl_only_conflicts_call_push_directly(
        self, mock_sync_client, initialized_db, clean_file_sync_state,
    ):
        """仅 JSONL 冲突时应直接 push，不调用 _resolve_conflicts 和备份"""
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider

        # Arrange: 两个 JSONL 文件 CONFLICT
        jsonl_1 = "session/chat.jsonl"
        jsonl_2 = "session/memory.jsonl"
        provider = FileSyncStateProvider(db_manager=initialized_db)
        for path in [jsonl_1, jsonl_2]:
            provider.upsert_state(
                file_path=path,
                parent_hash="hash_a",
                current_hash="hash_b",
            )

        mock_sync_client._refresh_current_hashes.return_value = [jsonl_1, jsonl_2]
        mock_sync_client._pull_files_check.return_value = ([
            {"path": jsonl_1, "parent_hash": "hash_a", "current_hash": "hash_c"},
            {"path": jsonl_2, "parent_hash": "hash_a", "current_hash": "hash_c"},
        ], [])

        # Act
        mock_sync_client._sync_files_full_flow(
            remote_url="http://test:8000",
            api_key="test-key",
            last_sync_time="2026-07-14T00:00:00Z",
            directories=["session/"],
        )

        # Assert: _resolve_conflicts 未被调用
        mock_sync_client._resolve_conflicts.assert_not_called()
        # Assert: _push_files 被调用且包含全部 JSONL 路径
        mock_sync_client._push_files.assert_called_once()
        push_paths = mock_sync_client._push_files.call_args[0][2]
        assert jsonl_1 in push_paths
        assert jsonl_2 in push_paths
        # Assert: verify 也被调用且包含 JSONL 路径
        mock_sync_client._verify_and_advance_parent.assert_called_once()
        verify_paths = mock_sync_client._verify_and_advance_parent.call_args[0][2]
        assert jsonl_1 in verify_paths
        assert jsonl_2 in verify_paths


# ==================== Seam 5: 全流程集成测试（CONFLICT→AI合并→推送→校验） ====================


class TestFullFlowEndToEnd:
    """Seam 5: CONFLICT→AI合并→推送→校验 全流程端到端测试

    使用真实的 _sync_files_full_flow（不 mock 子方法），
    仅 mock HTTP 层（httpx.post）和 bus 桥接（run_coroutine_threadsafe），
    验证完整流程：CONFLICT 检测 → AI 合并 → 备份 → 写入 → 更新 hash → 推送 → 校验推进
    """

    def test_conflict_to_merge_to_push_full_flow(
        self, sync_client, initialized_db, clean_conflict_test_dir,
        clean_file_sync_state, clean_sync_conflict_dir,
    ):
        """CONFLICT→AI合并→推送 全流程：本地与云端都修改了同一文件"""
        from lifeprism.config.settings_manager import settings
        from lifeprism.llm.bus.events import OutboundMessage
        from lifeprism.llm.providers import LLMResponse
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        # Arrange: 创建本地文件
        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/test.md"
        local_file = test_base / "diary" / "test.md"
        local_content = "# 本地日记\n今天心情不错"
        local_file.write_text(local_content, encoding="utf-8")

        # 预设 file_sync_state（parent_hash = "parent_hash"，current_hash 会被 _refresh_current_hashes 刷新）
        provider = FileSyncStateProvider(db_manager=initialized_db)
        provider.upsert_state(
            file_path=rel_path,
            parent_hash="parent_hash",  # 虚假 parent hash，确保 local_changed=True
            current_hash="old_hash",
        )

        remote_content = "# 云端日记\n今天天气晴朗"
        merged_content = "# 合并后的日记\n今天心情不错，天气晴朗"
        merged_hash = compute_file_hash(merged_content.encode("utf-8"))

        # Mock HTTP: 不同 URL 返回不同响应
        def mock_http_post(url, json=None, headers=None, timeout=None):
            if "/pull-files/check" in url:
                return _make_mock_response({
                    "files": [{
                        "path": rel_path,
                        "parent_hash": "parent_hash",
                        "current_hash": "remote_hash",
                    }]
                })
            elif "/pull-files/fetch" in url:
                return _make_mock_response({
                    "files": [{
                        "path": rel_path,
                        "content": _encode_file_content(remote_content),
                        "parent_hash": "parent_hash",
                        "current_hash": "remote_hash",
                    }]
                })
            elif "/push-files" in url:
                return _make_mock_response({"status": "ok"})
            elif "/pull-files/verify" in url:
                # verify 返回合并后内容的 hash（模拟推送后远端已更新）
                return _make_mock_response({
                    "files": [{
                        "path": rel_path,
                        "current_hash": merged_hash,
                    }]
                })
            elif "/pull-files/commit" in url:
                return _make_mock_response({"status": "ok"})
            return _make_mock_response({"status": "unknown"})

        mock_future = MagicMock()
        mock_future.result.return_value = OutboundMessage(
            response=LLMResponse(content=merged_content),
        )

        with patch("lifeprism.sync.sync_client.httpx.post", side_effect=mock_http_post), \
             patch("lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe", return_value=mock_future):

            # Act: 执行全流程
            sync_client._sync_files_full_flow(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-14T00:00:00Z",
                directories=["conflict_test/diary/"],
            )

        # Assert 1: 本地文件已被合并内容覆盖
        assert local_file.read_text(encoding="utf-8") == merged_content

        # Assert 2: 备份文件存在且内容为原始本地内容
        sync_conflict_dir = settings.lifeprism_data_path / "sync_conflict"
        backup_files = list(sync_conflict_dir.rglob("test.md"))
        assert len(backup_files) == 1
        assert backup_files[0].read_text(encoding="utf-8") == local_content

        # Assert 3: file_sync_state.current_hash = compute_file_hash(merged_content)
        state = provider.get_state(rel_path)
        assert state is not None
        assert state["current_hash"] == merged_hash

        # Assert 4: file_sync_state.parent_hash 已推进（verify 成功后 parent_hash = current_hash）
        assert state["parent_hash"] == merged_hash
