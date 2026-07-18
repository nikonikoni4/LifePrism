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

    def test_sync_client_stores_main_event_loop(
        self, initialized_db, sync_repository, mock_event_loop
    ):
        """SyncClient 应保存 main_event_loop 引用"""
        from lifeprism.sync.sync_client import SyncClient

        client = SyncClient(
            db_manager=initialized_db,
            sync_repository=sync_repository,
            main_event_loop=mock_event_loop,
        )
        assert client._main_event_loop is mock_event_loop

    def test_bus_bridge_calls_run_coroutine_threadsafe(
        self,
        sync_client,
        initialized_db,
        clean_conflict_test_dir,
        clean_file_sync_state,
        clean_sync_conflict_dir,
    ):
        """_resolve_conflicts 应通过 run_coroutine_threadsafe 调用 bus.send

        Issue 4 新流程：diff3 产生冲突 → LLM 串行处理 → bus.send 桥接
        """
        from lifeprism.config.settings_manager import settings

        # Arrange: 创建冲突三方内容（diff3 会产生 1 个冲突块）
        base = "line1\nline2\nline3\n"
        ours = "line1\nOURS\nline3\n"
        theirs = "line1\nTHEIRS\nline3\n"

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/2026-07-14.md"
        local_file = test_base / "diary" / "2026-07-14.md"
        local_file.write_text(ours, encoding="utf-8")

        # 预计算 LLM JSON 响应（基于 diff3 冲突块）
        llm_response, parent_hash = _make_conflict_llm_outbound_response(
            base, ours, theirs, replacement="MERGED"
        )

        mock_future = MagicMock()
        mock_future.result.return_value = llm_response

        with (
            patch.object(sync_client, "_fetch_remote_file_content", return_value=theirs),
            patch.object(sync_client, "_fetch_remote_base_content", return_value=base),
            patch(
                "lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe",
                return_value=mock_future,
            ) as mock_rcts,
        ):
            # Act
            sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: 调用了 run_coroutine_threadsafe
        mock_rcts.assert_called_once()
        # 第二个参数是事件循环
        assert mock_rcts.call_args[0][1] is sync_client._main_event_loop

    def test_bus_bridge_waits_with_timeout_600(
        self,
        sync_client,
        initialized_db,
        clean_conflict_test_dir,
        clean_file_sync_state,
        clean_sync_conflict_dir,
    ):
        """future.result 应以 timeout=600 等待 AI 合并完成

        Issue 4 新流程：LLM 调用通过 bus.send，future.result(timeout=600) 等待响应
        """
        from lifeprism.config.settings_manager import settings

        base = "line1\nline2\nline3\n"
        ours = "line1\nOURS\nline3\n"
        theirs = "line1\nTHEIRS\nline3\n"

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/2026-07-14.md"
        local_file = test_base / "diary" / "2026-07-14.md"
        local_file.write_text(ours, encoding="utf-8")

        llm_response, parent_hash = _make_conflict_llm_outbound_response(
            base, ours, theirs, replacement="MERGED"
        )

        mock_future = MagicMock()
        mock_future.result.return_value = llm_response

        with (
            patch.object(sync_client, "_fetch_remote_file_content", return_value=theirs),
            patch.object(sync_client, "_fetch_remote_base_content", return_value=base),
            patch(
                "lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe",
                return_value=mock_future,
            ),
        ):
            sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
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
        self,
        sync_client,
        initialized_db,
        clean_conflict_test_dir,
        clean_file_sync_state,
        clean_sync_conflict_dir,
    ):
        """成功合并后应同时备份本地与云端两个版本到 sync_conflict/{timestamp}/

        修复旧实现仅备份 local_content 的 bug（PRD 决策 19，
        ADR-2026-07-17-conflict-failure-policy.md）。

        Issue 4 新流程：diff3 + LLM JSON 替换后备份双方原始版本
        """
        from lifeprism.config.settings_manager import settings

        # Arrange: 冲突三方内容
        base = "line1\nline2\nline3\n"
        ours = "line1\nOURS\nline3\n"
        theirs = "line1\nTHEIRS\nline3\n"

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/2026-07-14.md"
        local_file = test_base / "diary" / "2026-07-14.md"
        local_file.write_text(ours, encoding="utf-8")

        llm_response, _ = _make_conflict_llm_outbound_response(
            base, ours, theirs, replacement="MERGED"
        )

        mock_future = MagicMock()
        mock_future.result.return_value = llm_response

        with (
            patch.object(sync_client, "_fetch_remote_file_content", return_value=theirs),
            patch.object(sync_client, "_fetch_remote_base_content", return_value=base),
            patch(
                "lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe",
                return_value=mock_future,
            ),
        ):
            sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: sync_conflict 目录下同时存在 .local.md 与 .remote.md 备份
        sync_conflict_dir = settings.lifeprism_data_path / "sync_conflict"
        assert sync_conflict_dir.exists(), "sync_conflict 备份目录应存在"

        local_backup_files = list(sync_conflict_dir.rglob("*.local.md"))
        remote_backup_files = list(sync_conflict_dir.rglob("*.remote.md"))
        assert len(local_backup_files) == 1, "应存在 1 个 .local.md 本地版本备份"
        assert len(remote_backup_files) == 1, "应存在 1 个 .remote.md 云端版本备份"

        # 内容校验：备份的是冲突前的原始 ours/theirs 内容
        assert local_backup_files[0].read_text(encoding="utf-8") == ours
        assert remote_backup_files[0].read_text(encoding="utf-8") == theirs

    def test_resolve_conflicts_writes_merged_content(
        self,
        sync_client,
        initialized_db,
        clean_conflict_test_dir,
        clean_file_sync_state,
        clean_sync_conflict_dir,
    ):
        """成功合并后本地文件应被覆盖为合并后内容

        Issue 4 新流程：LLM 返回 JSON 替换指令，程序执行替换后写入文件
        """
        from lifeprism.config.settings_manager import settings

        base = "line1\nline2\nline3\n"
        ours = "line1\nOURS\nline3\n"
        theirs = "line1\nTHEIRS\nline3\n"

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/2026-07-14.md"
        local_file = test_base / "diary" / "2026-07-14.md"
        local_file.write_text(ours, encoding="utf-8")

        replacement = "MERGED"
        llm_response, _ = _make_conflict_llm_outbound_response(
            base, ours, theirs, replacement=replacement
        )

        mock_future = MagicMock()
        mock_future.result.return_value = llm_response

        # 预期最终内容：冲突块被替换为 replacement
        expected_final = f"line1\n{replacement}\nline3\n"

        with (
            patch.object(sync_client, "_fetch_remote_file_content", return_value=theirs),
            patch.object(sync_client, "_fetch_remote_base_content", return_value=base),
            patch(
                "lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe",
                return_value=mock_future,
            ),
        ):
            sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: 本地文件已被合并内容覆盖
        assert local_file.read_text(encoding="utf-8") == expected_final

    def test_resolve_conflicts_updates_current_hash(
        self,
        sync_client,
        initialized_db,
        clean_conflict_test_dir,
        clean_file_sync_state,
        clean_sync_conflict_dir,
    ):
        """成功合并后 file_sync_state.current_hash 应为 compute_file_hash(merged_content)

        Issue 4 新流程：current_hash = 合并后最终内容的 hash
        """
        from lifeprism.config.settings_manager import settings
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        base = "line1\nline2\nline3\n"
        ours = "line1\nOURS\nline3\n"
        theirs = "line1\nTHEIRS\nline3\n"

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/2026-07-14.md"
        local_file = test_base / "diary" / "2026-07-14.md"
        local_file.write_text(ours, encoding="utf-8")

        replacement = "MERGED"
        llm_response, _ = _make_conflict_llm_outbound_response(
            base, ours, theirs, replacement=replacement
        )

        mock_future = MagicMock()
        mock_future.result.return_value = llm_response

        expected_final = f"line1\n{replacement}\nline3\n"
        expected_hash = compute_file_hash(expected_final.encode("utf-8"))

        with (
            patch.object(sync_client, "_fetch_remote_file_content", return_value=theirs),
            patch.object(sync_client, "_fetch_remote_base_content", return_value=base),
            patch(
                "lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe",
                return_value=mock_future,
            ),
        ):
            sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: current_hash 已更新为合并后最终内容的 hash
        provider = FileSyncStateProvider(db_manager=initialized_db)
        state = provider.get_state(rel_path)
        assert state is not None, "file_sync_state 记录应存在"
        assert state["current_hash"] == expected_hash

    def test_resolve_conflicts_preserves_parent_hash(
        self,
        sync_client,
        initialized_db,
        clean_conflict_test_dir,
        clean_file_sync_state,
        clean_sync_conflict_dir,
    ):
        """成功合并后 file_sync_state.parent_hash 应保持不变

        Issue 4 新流程：parent_hash 由后续 verify_and_advance_parent 推进，
        冲突解决阶段保持不变
        """
        from lifeprism.config.settings_manager import settings
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        base = "line1\nline2\nline3\n"
        ours = "line1\nOURS\nline3\n"
        theirs = "line1\nTHEIRS\nline3\n"

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/2026-07-14.md"
        local_file = test_base / "diary" / "2026-07-14.md"
        local_file.write_text(ours, encoding="utf-8")

        # 预设 file_sync_state 记录，parent_hash = base 内容的 hash
        provider = FileSyncStateProvider(db_manager=initialized_db)
        parent_hash = compute_file_hash(base.encode("utf-8"))
        provider.upsert_state(
            file_path=rel_path,
            parent_hash=parent_hash,
            current_hash=compute_file_hash(ours.encode("utf-8")),
        )

        llm_response, _ = _make_conflict_llm_outbound_response(
            base, ours, theirs, replacement="MERGED"
        )

        mock_future = MagicMock()
        mock_future.result.return_value = llm_response

        with (
            patch.object(sync_client, "_fetch_remote_file_content", return_value=theirs),
            patch.object(sync_client, "_fetch_remote_base_content", return_value=base),
            patch(
                "lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe",
                return_value=mock_future,
            ),
        ):
            sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: parent_hash 保持不变
        state = provider.get_state(rel_path)
        assert state is not None
        assert state["parent_hash"] == parent_hash

    def test_resolve_conflicts_returns_resolved_paths(
        self,
        sync_client,
        initialized_db,
        clean_conflict_test_dir,
        clean_file_sync_state,
        clean_sync_conflict_dir,
    ):
        """_resolve_conflicts 应返回成功合并的文件路径列表

        Issue 4 新流程：成功解决冲突的文件路径出现在返回列表中
        """
        from lifeprism.config.settings_manager import settings

        base = "line1\nline2\nline3\n"
        ours = "line1\nOURS\nline3\n"
        theirs = "line1\nTHEIRS\nline3\n"

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/2026-07-14.md"
        local_file = test_base / "diary" / "2026-07-14.md"
        local_file.write_text(ours, encoding="utf-8")

        llm_response, _ = _make_conflict_llm_outbound_response(
            base, ours, theirs, replacement="MERGED"
        )

        mock_future = MagicMock()
        mock_future.result.return_value = llm_response

        with (
            patch.object(sync_client, "_fetch_remote_file_content", return_value=theirs),
            patch.object(sync_client, "_fetch_remote_base_content", return_value=base),
            patch(
                "lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe",
                return_value=mock_future,
            ),
        ):
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
        self,
        sync_client,
        initialized_db,
        clean_conflict_test_dir,
        clean_file_sync_state,
        clean_sync_conflict_dir,
    ):
        """文件级 TimeoutError 时本地版本应保留不变

        Issue 4 新流程：LLM 调用超时被 resolve_conflict_blocks 内部捕获并重试降级，
        不会传播到文件级。文件级 TimeoutError 只能来自 _fetch_remote_base_content
        等非 LLM 路径（如备份目录读取超时）→ 文件级异常处理 →
        不写入、不备份、不更新 state
        """
        from lifeprism.config.settings_manager import settings

        base = "line1\nline2\nline3\n"
        ours = "line1\nOURS\nline3\n"
        theirs = "line1\nTHEIRS\nline3\n"

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/2026-07-14.md"
        local_file = test_base / "diary" / "2026-07-14.md"
        local_file.write_text(ours, encoding="utf-8")

        # Mock: _fetch_remote_base_content 抛出 TimeoutError（文件级异常）
        with (
            patch.object(sync_client, "_fetch_remote_file_content", return_value=theirs),
            patch.object(
                sync_client,
                "_fetch_remote_base_content",
                side_effect=TimeoutError(),
            ),
            patch(
                "lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe",
            ) as mock_rcts,
        ):
            result = sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: 本地文件内容不变
        assert local_file.read_text(encoding="utf-8") == ours
        # Assert: 不在 resolved_paths 中
        assert result == []
        # Assert: LLM 未被调用（文件级异常在 LLM 之前发生）
        mock_rcts.assert_not_called()
        # Assert: 未创建备份目录
        sync_conflict_dir = settings.lifeprism_data_path / "sync_conflict"
        assert not sync_conflict_dir.exists() or not list(sync_conflict_dir.rglob("2026-07-14.md"))

    def test_empty_merged_content_preserves_local_version(
        self,
        sync_client,
        initialized_db,
        clean_conflict_test_dir,
        clean_file_sync_state,
        clean_sync_conflict_dir,
    ):
        """LLM 返回无效内容（空字符串）→ 重试 3 次失败 → 降级 keep_ours

        Issue 4 新流程：LLM 返回空字符串 → parse_llm_json_response 失败 →
        重试 3 次都失败 → 降级 keep_ours（冲突块替换为 ours 内容）→
        文件写入 ours 内容、hash 更新、路径加入 resolved_paths

        与旧流程差异：旧流程空内容 → 保留本地不写入；新流程 → 降级写入 ours
        """
        from lifeprism.config.settings_manager import settings
        from lifeprism.llm.bus.events import OutboundMessage
        from lifeprism.llm.providers import LLMResponse

        base = "line1\nline2\nline3\n"
        ours = "line1\nOURS\nline3\n"
        theirs = "line1\nTHEIRS\nline3\n"

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/2026-07-14.md"
        local_file = test_base / "diary" / "2026-07-14.md"
        local_file.write_text(ours, encoding="utf-8")

        # Mock LLM 始终返回空字符串（无效 JSON）→ 重试 3 次后降级 keep_ours
        mock_future = MagicMock()
        mock_future.result.return_value = OutboundMessage(
            response=LLMResponse(content=""),
        )

        with (
            patch.object(sync_client, "_fetch_remote_file_content", return_value=theirs),
            patch.object(sync_client, "_fetch_remote_base_content", return_value=base),
            patch(
                "lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe",
                return_value=mock_future,
            ),
        ):
            result = sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: 降级 keep_ours 也算"解决"了冲突，路径在 resolved_paths 中
        assert result == [rel_path]
        # Assert: 本地文件已写入（降级 keep_ours 后冲突块被替换为 ours 内容）
        final_content = local_file.read_text(encoding="utf-8")
        assert "OURS" in final_content  # ours 内容保留
        assert "THEIRS" not in final_content  # 无 theirs 残留
        assert "<<<<<<<" not in final_content  # 无冲突标记残留

    def test_empty_merged_content_preserves_file_sync_state(
        self,
        sync_client,
        initialized_db,
        clean_conflict_test_dir,
        clean_file_sync_state,
        clean_sync_conflict_dir,
    ):
        """LLM 返回无效内容 → 降级 keep_ours → file_sync_state.current_hash 更新为 ours hash

        Issue 4 新流程：降级后文件内容为 ours（冲突块被替换），
        current_hash = compute_file_hash(降级后内容)，parent_hash 不变
        """
        from lifeprism.config.settings_manager import settings
        from lifeprism.llm.bus.events import OutboundMessage
        from lifeprism.llm.providers import LLMResponse
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        base = "line1\nline2\nline3\n"
        ours = "line1\nOURS\nline3\n"
        theirs = "line1\nTHEIRS\nline3\n"

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/2026-07-14.md"
        local_file = test_base / "diary" / "2026-07-14.md"
        local_file.write_text(ours, encoding="utf-8")

        # 预设 file_sync_state
        provider = FileSyncStateProvider(db_manager=initialized_db)
        parent_hash = compute_file_hash(base.encode("utf-8"))
        original_current = compute_file_hash(ours.encode("utf-8"))
        provider.upsert_state(
            file_path=rel_path,
            parent_hash=parent_hash,
            current_hash=original_current,
        )

        # Mock LLM 返回空白字符串（无效 JSON）→ 重试 3 次后降级 keep_ours
        mock_future = MagicMock()
        mock_future.result.return_value = OutboundMessage(
            response=LLMResponse(content="   "),  # 仅空白字符，parse 失败
        )

        with (
            patch.object(sync_client, "_fetch_remote_file_content", return_value=theirs),
            patch.object(sync_client, "_fetch_remote_base_content", return_value=base),
            patch(
                "lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe",
                return_value=mock_future,
            ),
        ):
            sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: file_sync_state 已更新（降级后 current_hash = ours 内容的 hash）
        state = provider.get_state(rel_path)
        assert state is not None
        assert state["parent_hash"] == parent_hash  # parent_hash 不变
        # current_hash = 降级后内容的 hash（ours 内容，冲突块被替换为 ours）
        # 降级 keep_ours 后文件内容仍是 ours（冲突块本就是 ours vs theirs，替换为 ours）
        assert state["current_hash"] == original_current

    def test_generic_exception_preserves_local_version(
        self,
        sync_client,
        initialized_db,
        clean_conflict_test_dir,
        clean_file_sync_state,
        clean_sync_conflict_dir,
    ):
        """文件级 RuntimeError 时本地版本应保留不变

        Issue 4 新流程：LLM 调用异常被 resolve_conflict_blocks 内部捕获并重试降级，
        不会传播到文件级。文件级 RuntimeError 只能来自 _fetch_remote_base_content
        等非 LLM 路径（如备份目录读取失败）→ 文件级异常处理 →
        不写入、不备份、不更新 state
        """
        from lifeprism.config.settings_manager import settings

        base = "line1\nline2\nline3\n"
        ours = "line1\nOURS\nline3\n"
        theirs = "line1\nTHEIRS\nline3\n"

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/2026-07-14.md"
        local_file = test_base / "diary" / "2026-07-14.md"
        local_file.write_text(ours, encoding="utf-8")

        # Mock: _fetch_remote_base_content 抛出 RuntimeError（文件级异常）
        with (
            patch.object(sync_client, "_fetch_remote_file_content", return_value=theirs),
            patch.object(
                sync_client,
                "_fetch_remote_base_content",
                side_effect=RuntimeError("备份目录读取失败"),
            ),
            patch(
                "lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe",
            ) as mock_rcts,
        ):
            result = sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: 本地文件内容不变
        assert local_file.read_text(encoding="utf-8") == ours
        # Assert: 不在 resolved_paths 中
        assert result == []
        # Assert: LLM 未被调用（文件级异常在 LLM 之前发生）
        mock_rcts.assert_not_called()

    def test_fetch_remote_failure_skips_file(
        self,
        sync_client,
        initialized_db,
        clean_conflict_test_dir,
        clean_file_sync_state,
        clean_sync_conflict_dir,
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
        with patch(
            "lifeprism.sync.sync_client.httpx.post", side_effect=httpx.RequestError("网络错误")
        ):
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
        self,
        sync_client,
        initialized_db,
        clean_conflict_test_dir,
        clean_file_sync_state,
        clean_sync_conflict_dir,
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
        self,
        sync_client,
        initialized_db,
        clean_conflict_test_dir,
        clean_file_sync_state,
        clean_sync_conflict_dir,
    ):
        """多个冲突文件中部分失败时，只返回成功的路径

        Issue 4 新流程：文件1 LLM 成功 → resolved；文件2 _fetch_remote_base_content
        抛出 TimeoutError → 文件级异常 → 未 resolved

        说明：LLM 调用异常被 resolve_conflict_blocks 内部捕获并重试降级，
        不会传播到文件级。文件级 TimeoutError 只能来自 _fetch_remote_base_content
        等非 LLM 路径。
        """
        from lifeprism.config.settings_manager import settings

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)

        # 文件1：会成功合并（LLM 返回有效 JSON）
        rel_path1 = "conflict_test/diary/success.md"
        local_file1 = test_base / "diary" / "success.md"
        base1 = "line1\nline2\nline3\n"
        ours1 = "line1\nOURS1\nline3\n"
        theirs1 = "line1\nTHEIRS1\nline3\n"
        local_file1.write_text(ours1, encoding="utf-8")

        # 文件2：会文件级失败（_fetch_remote_base_content 抛出 TimeoutError）
        rel_path2 = "conflict_test/diary/timeout.md"
        local_file2 = test_base / "diary" / "timeout.md"
        base2 = "h1\nh2\nh3\n"
        ours2 = "h1\nOURS2\nh3\n"
        theirs2 = "h1\nTHEIRS2\nh3\n"
        local_file2.write_text(ours2, encoding="utf-8")

        # 预计算文件1的 LLM JSON 响应
        llm_response1, _ = _make_conflict_llm_outbound_response(
            base1, ours1, theirs1, replacement="MERGED1"
        )

        mock_future_success = MagicMock()
        mock_future_success.result.return_value = llm_response1

        with (
            patch.object(
                sync_client,
                "_fetch_remote_file_content",
                side_effect=[theirs1, theirs2],
            ),
            patch.object(
                sync_client,
                "_fetch_remote_base_content",
                side_effect=[base1, TimeoutError()],  # 文件2 文件级异常
            ),
            patch(
                "lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe",
                return_value=mock_future_success,  # 仅文件1调用 LLM
            ),
        ):
            result = sync_client._resolve_conflicts(
                conflict_paths=[rel_path1, rel_path2],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: 只返回成功的路径
        assert result == [rel_path1]
        # Assert: 失败的文件本地内容不变
        assert local_file2.read_text(encoding="utf-8") == ours2


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
        self,
        mock_sync_client,
        initialized_db,
        clean_file_sync_state,
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
        mock_sync_client._pull_files_check.return_value = (
            [
                {
                    "path": conflict_path,
                    "parent_hash": "hash_a",
                    "current_hash": "hash_c",
                }
            ],
            [],
        )

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
        self,
        mock_sync_client,
        initialized_db,
        clean_file_sync_state,
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
        mock_sync_client._pull_files_check.return_value = (
            [
                {
                    "path": conflict_path,
                    "parent_hash": "hash_a",
                    "current_hash": "hash_c",
                }
            ],
            [],
        )
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
        self,
        mock_sync_client,
        initialized_db,
        clean_file_sync_state,
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
        mock_sync_client._pull_files_check.return_value = (
            [
                {
                    "path": conflict_path,
                    "parent_hash": "hash_a",
                    "current_hash": "hash_c",
                }
            ],
            [],
        )
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
        self,
        mock_sync_client,
        initialized_db,
        clean_file_sync_state,
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
        mock_sync_client._pull_files_check.return_value = (
            [
                {
                    "path": push_path,
                    "parent_hash": "hash_a",
                    "current_hash": "hash_a",
                }
            ],
            [],
        )

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
        self,
        mock_sync_client,
        initialized_db,
        clean_file_sync_state,
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
        mock_sync_client._pull_files_check.return_value = (
            [
                {
                    "path": conflict_path,
                    "parent_hash": "hash_a",
                    "current_hash": "hash_c",
                }
            ],
            [],
        )
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
        self,
        mock_sync_client,
        initialized_db,
        clean_file_sync_state,
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
        mock_sync_client._pull_files_check.return_value = (
            [
                {
                    "path": conflict_path,
                    "parent_hash": "hash_a",
                    "current_hash": "hash_c",
                }
            ],
            [],
        )

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
        self,
        mock_sync_client,
        initialized_db,
        clean_file_sync_state,
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
        mock_sync_client._pull_files_check.return_value = (
            [
                {"path": jsonl_path, "parent_hash": "hash_a", "current_hash": "hash_c"},
                {"path": md_path, "parent_hash": "hash_a", "current_hash": "hash_c"},
            ],
            [],
        )
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
        self,
        mock_sync_client,
        initialized_db,
        clean_file_sync_state,
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
        mock_sync_client._pull_files_check.return_value = (
            [
                {"path": jsonl_1, "parent_hash": "hash_a", "current_hash": "hash_c"},
                {"path": jsonl_2, "parent_hash": "hash_a", "current_hash": "hash_c"},
            ],
            [],
        )

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
        self,
        sync_client,
        initialized_db,
        clean_conflict_test_dir,
        clean_file_sync_state,
        clean_sync_conflict_dir,
    ):
        """CONFLICT→AI合并→推送 全流程：本地与云端都修改了同一文件

        Issue 4 新流程：diff3 + LLM JSON 替换 + 推送 + 校验推进
        """
        from lifeprism.config.settings_manager import settings
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        # Arrange: 冲突三方内容
        base = "line1\nline2\nline3\n"
        ours = "line1\nOURS\nline3\n"
        theirs = "line1\nTHEIRS\nline3\n"
        replacement = "MERGED"
        expected_final = f"line1\n{replacement}\nline3\n"
        merged_hash = compute_file_hash(expected_final.encode("utf-8"))

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/test.md"
        local_file = test_base / "diary" / "test.md"
        local_file.write_text(ours, encoding="utf-8")

        # 预设 file_sync_state（parent_hash = base hash，确保 CONFLICT 矩阵触发）
        provider = FileSyncStateProvider(db_manager=initialized_db)
        parent_hash = compute_file_hash(base.encode("utf-8"))
        provider.upsert_state(
            file_path=rel_path,
            parent_hash=parent_hash,
            current_hash="old_hash",  # 会被 _refresh_current_hashes 刷新
        )

        # 预计算 LLM JSON 响应
        llm_response, _ = _make_conflict_llm_outbound_response(
            base, ours, theirs, replacement=replacement
        )

        # Mock HTTP: 不同 URL 返回不同响应
        def mock_http_post(url, json=None, headers=None, timeout=None):
            if "/pull-files/check" in url:
                return _make_mock_response(
                    {
                        "files": [
                            {
                                "path": rel_path,
                                "parent_hash": parent_hash,
                                "current_hash": compute_file_hash(theirs.encode("utf-8")),
                            }
                        ]
                    }
                )
            elif "/push-files" in url:
                return _make_mock_response({"status": "ok"})
            elif "/pull-files/verify" in url:
                # verify 返回合并后内容的 hash（模拟推送后远端已更新）
                return _make_mock_response(
                    {
                        "files": [
                            {
                                "path": rel_path,
                                "current_hash": merged_hash,
                            }
                        ]
                    }
                )
            elif "/pull-files/commit" in url:
                return _make_mock_response({"status": "ok"})
            return _make_mock_response({"status": "unknown"})

        mock_future = MagicMock()
        mock_future.result.return_value = llm_response

        with (
            patch("lifeprism.sync.sync_client.httpx.post", side_effect=mock_http_post),
            patch.object(sync_client, "_fetch_remote_file_content", return_value=theirs),
            patch.object(sync_client, "_fetch_remote_base_content", return_value=base),
            patch(
                "lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe",
                return_value=mock_future,
            ),
        ):
            # Act: 执行全流程
            sync_client._sync_files_full_flow(
                remote_url="http://test:8000",
                api_key="test-key",
                last_sync_time="2026-07-14T00:00:00Z",
                directories=["conflict_test/diary/"],
            )

        # Assert 1: 本地文件已被合并内容覆盖（LLM replacement 替换冲突块后）
        assert local_file.read_text(encoding="utf-8") == expected_final

        # Assert 2: 同时备份本地与云端两个版本（修复旧实现仅备份本地的 bug）
        sync_conflict_dir = settings.lifeprism_data_path / "sync_conflict"
        local_backup_files = list(sync_conflict_dir.rglob("*.local.md"))
        remote_backup_files = list(sync_conflict_dir.rglob("*.remote.md"))
        assert len(local_backup_files) == 1, "应存在 1 个 .local.md 本地版本备份"
        assert len(remote_backup_files) == 1, "应存在 1 个 .remote.md 云端版本备份"
        assert local_backup_files[0].read_text(encoding="utf-8") == ours
        assert remote_backup_files[0].read_text(encoding="utf-8") == theirs

        # Assert 3: file_sync_state.current_hash = compute_file_hash(merged_content)
        state = provider.get_state(rel_path)
        assert state is not None
        assert state["current_hash"] == merged_hash

        # Assert 4: file_sync_state.parent_hash 已推进（verify 成功后 parent_hash = current_hash）
        assert state["parent_hash"] == merged_hash


# ==================== Seam 6: Issue 4 端到端流程（diff3 + LLM 串行 + 替换） ====================


def _make_llm_json_response(conflict_id, start_marker, end_marker, replacement):
    """构造 LLM JSON 响应字符串（Issue 4 新格式）

    LLM 输出 JSON 格式（PRD 决策 4）：
        {"conflict_id": 1, "start_marker": "...", "end_marker": "...", "replacement": "..."}
    """
    import json

    return json.dumps(
        {
            "conflict_id": conflict_id,
            "start_marker": start_marker,
            "end_marker": end_marker,
            "replacement": replacement,
        },
        ensure_ascii=False,
    )


def _make_conflict_llm_outbound_response(base, ours, theirs, replacement="MERGED"):
    """构造单冲突块的 LLM OutboundMessage 响应（测试辅助函数）

    预计算 diff3 冲突块信息，生成对应的 JSON LLM 响应，
    包装成 OutboundMessage 对象供 mock future.result 返回。

    Args:
        base/ours/theirs: 冲突三方内容
        replacement: LLM 返回的替换内容

    Returns:
        (OutboundMessage, expected_final, expected_hash, parent_hash, block) 元组
    """
    from lifeprism.llm.bus.events import OutboundMessage
    from lifeprism.llm.providers import LLMResponse
    from lifeprism.sync.conflict_resolution import compute_hash_8, parse_conflict_blocks
    from lifeprism.sync.diff3 import merge as diff3_merge
    from lifeprism.sync.hash_utils import compute_file_hash

    local_hash_8 = compute_hash_8(ours)
    remote_hash_8 = compute_hash_8(theirs)
    result = diff3_merge(base, ours, theirs, local_hash_8, remote_hash_8)
    assert result["conflicts"] >= 1, "测试场景应至少产生 1 个冲突块"
    blocks = parse_conflict_blocks(result["merged"])
    block = blocks[0]

    llm_json = _make_llm_json_response(
        conflict_id=block.conflict_id,
        start_marker=block.start_marker,
        end_marker=block.end_marker,
        replacement=replacement,
    )
    response = OutboundMessage(
        response=LLMResponse(content=llm_json),
    )

    parent_hash = compute_file_hash(base.encode("utf-8"))
    return response, parent_hash


def _compute_diff3_conflict_info(base, ours, theirs):
    """运行 diff3 并返回冲突块信息（测试辅助函数）

    用于在测试中预计算预期的冲突标记，以便构造 mock LLM 响应。
    """
    from lifeprism.sync.conflict_resolution import compute_hash_8, parse_conflict_blocks
    from lifeprism.sync.diff3 import merge

    local_hash_8 = compute_hash_8(ours)
    remote_hash_8 = compute_hash_8(theirs)

    result = merge(base, ours, theirs, local_hash_8, remote_hash_8)
    blocks = parse_conflict_blocks(result["merged"])

    return {
        "merged": result["merged"],
        "blocks": blocks,
        "local_hash_8": local_hash_8,
        "remote_hash_8": remote_hash_8,
        "conflicts": result["conflicts"],
    }


class TestIssue4Diff3LLMSerialFlow:
    """Issue 4 端到端流程：diff3 + LLM 串行 + 替换 + 写入最终文件

    测试新的冲突解决流程（PRD 决策 3-6, 10）：
    1. 读取本地文件 (ours)
    2. 获取远端文件 (theirs)
    3. 获取 base 内容 (parent_hash 对应版本)
    4. 运行 diff3(base, ours, theirs) → 含冲突标记的合并文本
    5. parse_conflict_blocks → 冲突块列表
    6. 串行调用 LLM (每个冲突块一次) → JSON 替换指令
    7. 程序验证 marker + 执行替换
    8. 写入最终文件 + 更新 file_sync_state

    与旧流程的关键差异：
    - 旧流程：LLM 返回整文档合并内容（plain text），易截断
    - 新流程：LLM 返回 JSON 替换指令（仅冲突块），程序执行替换，不会截断
    """

    def test_diff3_produces_conflict_then_llm_resolves(
        self,
        sync_client,
        initialized_db,
        clean_conflict_test_dir,
        clean_file_sync_state,
        clean_sync_conflict_dir,
    ):
        """diff3 产生冲突标记 → LLM 串行替换 → 写入最终文件

        场景：
        - base: "line1\nline2\nline3\n"
        - ours: "line1\nOURS\nline3\n" (本地修改 line2)
        - theirs: "line1\nTHEIRS\nline3\n" (云端修改 line2)
        - diff3 产生 1 个冲突块
        - LLM 返回 JSON 替换指令（replacement="MERGED"）
        - 最终文件: "line1\nMERGED\nline3\n"
        """
        from lifeprism.config.settings_manager import settings
        from lifeprism.llm.bus.events import OutboundMessage
        from lifeprism.llm.providers import LLMResponse
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        # Arrange: 设置 base/ours/theirs
        base = "line1\nline2\nline3\n"
        ours = "line1\nOURS\nline3\n"
        theirs = "line1\nTHEIRS\nline3\n"

        # 预计算预期冲突标记
        info = _compute_diff3_conflict_info(base, ours, theirs)
        assert info["conflicts"] == 1
        block = info["blocks"][0]

        # 创建本地文件 (ours)
        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/test.md"
        local_file = test_base / "diary" / "test.md"
        local_file.write_text(ours, encoding="utf-8")

        # 预设 file_sync_state（parent_hash 存在，表示有 base 版本）
        provider = FileSyncStateProvider(db_manager=initialized_db)
        parent_hash = compute_file_hash(base.encode("utf-8"))
        provider.upsert_state(
            file_path=rel_path,
            parent_hash=parent_hash,
            current_hash=compute_file_hash(ours.encode("utf-8")),
        )

        # Mock LLM 返回 JSON 替换指令
        replacement = "MERGED"
        llm_json = _make_llm_json_response(
            conflict_id=1,
            start_marker=block.start_marker,
            end_marker=block.end_marker,
            replacement=replacement,
        )

        mock_future = MagicMock()
        mock_future.result.return_value = OutboundMessage(
            response=LLMResponse(content=llm_json),
        )

        expected_final = f"line1\n{replacement}\nline3\n"
        expected_hash = compute_file_hash(expected_final.encode("utf-8"))

        with (
            patch.object(sync_client, "_fetch_remote_file_content", return_value=theirs),
            patch.object(sync_client, "_fetch_remote_base_content", return_value=base),
            patch(
                "lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe",
                return_value=mock_future,
            ),
        ):
            result = sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: 返回成功路径
        assert result == [rel_path]

        # Assert: 本地文件已写入合并后内容
        final_content = local_file.read_text(encoding="utf-8")
        assert final_content == expected_final
        # 无冲突标记残留
        assert "<<<<<<<" not in final_content
        assert "=======" not in final_content
        assert ">>>>>>>" not in final_content

        # Assert: file_sync_state 已更新
        state = provider.get_state(rel_path)
        assert state is not None
        assert state["current_hash"] == expected_hash
        assert state["parent_hash"] == parent_hash  # parent_hash 不变

    def test_multiple_conflict_blocks_serial_resolution(
        self,
        sync_client,
        initialized_db,
        clean_conflict_test_dir,
        clean_file_sync_state,
        clean_sync_conflict_dir,
    ):
        """多个冲突块串行处理，每个基于更新后的文件

        场景：
        - base 有 3 个可冲突区域
        - ours 和 theirs 在 3 个区域都做了不同修改
        - diff3 产生 3 个冲突块
        - LLM 串行处理 3 个冲突块，每个返回 JSON 替换指令
        - 最终文件：3 个冲突块都被替换
        """
        from lifeprism.config.settings_manager import settings
        from lifeprism.llm.bus.events import OutboundMessage
        from lifeprism.llm.providers import LLMResponse
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        # Arrange: 3 个冲突区域
        base = "h1\nx1\nh2\nx2\nh3\nx3\nh4\n"
        ours = "h1\nOURS1\nh2\nOURS2\nh3\nOURS3\nh4\n"
        theirs = "h1\nTHEIRS1\nh2\nTHEIRS2\nh3\nTHEIRS3\nh4\n"

        info = _compute_diff3_conflict_info(base, ours, theirs)
        assert info["conflicts"] == 3
        blocks = info["blocks"]

        # 创建本地文件
        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/multi.md"
        local_file = test_base / "diary" / "multi.md"
        local_file.write_text(ours, encoding="utf-8")

        provider = FileSyncStateProvider(db_manager=initialized_db)
        parent_hash = compute_file_hash(base.encode("utf-8"))
        provider.upsert_state(
            file_path=rel_path,
            parent_hash=parent_hash,
            current_hash=compute_file_hash(ours.encode("utf-8")),
        )

        # Mock LLM: 3 次调用，每次返回一个冲突块的 JSON
        replacements = ["MERGED1", "MERGED2", "MERGED3"]
        llm_responses = [
            OutboundMessage(
                response=LLMResponse(
                    content=_make_llm_json_response(
                        conflict_id=block.conflict_id,
                        start_marker=block.start_marker,
                        end_marker=block.end_marker,
                        replacement=replacements[i],
                    )
                )
            )
            for i, block in enumerate(blocks)
        ]

        mock_futures = []
        for resp in llm_responses:
            mf = MagicMock()
            mf.result.return_value = resp
            mock_futures.append(mf)

        expected_final = "h1\nMERGED1\nh2\nMERGED2\nh3\nMERGED3\nh4\n"
        expected_hash = compute_file_hash(expected_final.encode("utf-8"))

        with (
            patch.object(sync_client, "_fetch_remote_file_content", return_value=theirs),
            patch.object(sync_client, "_fetch_remote_base_content", return_value=base),
            patch(
                "lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe",
                side_effect=mock_futures,
            ),
        ):
            result = sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: 返回成功路径
        assert result == [rel_path]

        # Assert: 本地文件已写入合并后内容
        final_content = local_file.read_text(encoding="utf-8")
        assert final_content == expected_final
        assert "<<<<<<<" not in final_content
        assert ">>>>>>>" not in final_content

        # Assert: file_sync_state 已更新
        state = provider.get_state(rel_path)
        assert state is not None
        assert state["current_hash"] == expected_hash

    def test_diff3_no_conflict_writes_merged_directly(
        self,
        sync_client,
        initialized_db,
        clean_conflict_test_dir,
        clean_file_sync_state,
        clean_sync_conflict_dir,
    ):
        """diff3 无冲突时直接写入合并结果（不调用 LLM）

        场景：
        - base: "h1\\nline2\\nh3\\nline4\\nh5\\n"
        - ours: "h1\\nOURS\\nh3\\nline4\\nh5\\n" (本地修改 line2)
        - theirs: "h1\\nline2\\nh3\\nTHEIRS\\nh5\\n" (云端修改 line4)
        - diff3 自动合并成功（双方改不同区域，有 h3/h5 锚点分隔）
        - 不调用 LLM，直接写入合并结果
        """
        from lifeprism.config.settings_manager import settings
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        # Arrange: 双方改不同区域（有锚点分隔）→ diff3 自动合并成功
        base = "h1\nline2\nh3\nline4\nh5\n"
        ours = "h1\nOURS\nh3\nline4\nh5\n"
        theirs = "h1\nline2\nh3\nTHEIRS\nh5\n"

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/no_conflict.md"
        local_file = test_base / "diary" / "no_conflict.md"
        local_file.write_text(ours, encoding="utf-8")

        provider = FileSyncStateProvider(db_manager=initialized_db)
        parent_hash = compute_file_hash(base.encode("utf-8"))
        provider.upsert_state(
            file_path=rel_path,
            parent_hash=parent_hash,
            current_hash=compute_file_hash(ours.encode("utf-8")),
        )

        # diff3 自动合并的预期结果
        expected_final = "h1\nOURS\nh3\nTHEIRS\nh5\n"
        expected_hash = compute_file_hash(expected_final.encode("utf-8"))

        with (
            patch.object(sync_client, "_fetch_remote_file_content", return_value=theirs),
            patch.object(sync_client, "_fetch_remote_base_content", return_value=base),
            patch(
                "lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe"
            ) as mock_rcts,
        ):
            result = sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: 返回成功路径
        assert result == [rel_path]

        # Assert: 本地文件已写入自动合并结果
        final_content = local_file.read_text(encoding="utf-8")
        assert final_content == expected_final

        # Assert: LLM 未被调用（无冲突，不需要 LLM）
        mock_rcts.assert_not_called()

        # Assert: file_sync_state 已更新
        state = provider.get_state(rel_path)
        assert state is not None
        assert state["current_hash"] == expected_hash


# ==================== Seam 7: Issue 4 重试与降级策略 ====================


class TestIssue4RetryAndDegradation:
    """Issue 4 重试与降级策略

    PRD 决策 6, 10:
    - 单个冲突块重试 3 次失败 → 降级 keep_ours（保留本地版本）
    - 整个文件失败（如 diff3 异常）→ 回退 LWW（保留本地 + 备份云端）
    """

    def test_single_block_retry_3_times_then_degrade_to_keep_ours(
        self,
        sync_client,
        initialized_db,
        clean_conflict_test_dir,
        clean_file_sync_state,
        clean_sync_conflict_dir,
    ):
        """单个冲突块重试 3 次都失败 → 降级 keep_ours（保留 ours 内容）"""
        from lifeprism.config.settings_manager import settings
        from lifeprism.llm.bus.events import OutboundMessage
        from lifeprism.llm.providers import LLMResponse
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        base = "line1\nline2\nline3\n"
        ours = "line1\nOURS\nline3\n"
        theirs = "line1\nTHEIRS\nline3\n"

        info = _compute_diff3_conflict_info(base, ours, theirs)
        assert info["conflicts"] == 1

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/retry.md"
        local_file = test_base / "diary" / "retry.md"
        local_file.write_text(ours, encoding="utf-8")

        provider = FileSyncStateProvider(db_manager=initialized_db)
        parent_hash = compute_file_hash(base.encode("utf-8"))
        provider.upsert_state(
            file_path=rel_path,
            parent_hash=parent_hash,
            current_hash=compute_file_hash(ours.encode("utf-8")),
        )

        # Mock LLM: 3 次都返回无效 JSON → 重试 3 次后降级 keep_ours
        mock_future = MagicMock()
        mock_future.result.return_value = OutboundMessage(
            response=LLMResponse(content="always invalid json"),
        )

        with (
            patch.object(sync_client, "_fetch_remote_file_content", return_value=theirs),
            patch.object(sync_client, "_fetch_remote_base_content", return_value=base),
            patch(
                "lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe",
                return_value=mock_future,
            ),
        ):
            result = sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: 仍然返回成功路径（降级 keep_ours 也算"解决"了冲突）
        assert result == [rel_path]

        # Assert: 本地文件保留 ours 内容（降级 keep_ours）
        final_content = local_file.read_text(encoding="utf-8")
        assert "OURS" in final_content
        assert "THEIRS" not in final_content
        # 无冲突标记残留（降级后冲突块被替换为 ours 内容）
        assert "<<<<<<<" not in final_content
        assert ">>>>>>>" not in final_content

        # Assert: file_sync_state 已更新（current_hash = ours 的 hash）
        state = provider.get_state(rel_path)
        assert state is not None
        assert state["current_hash"] == compute_file_hash(ours.encode("utf-8"))

    def test_whole_file_failure_falls_back_to_lww(
        self,
        sync_client,
        initialized_db,
        clean_conflict_test_dir,
        clean_file_sync_state,
        clean_sync_conflict_dir,
    ):
        """整个文件失败（如获取 base 内容失败）→ 回退 LWW（保留本地 + 备份云端）

        PRD 决策 10：整个文件失败时回退到 LWW（保留本地 + 备份云端到 sync_conflict/）
        """
        from lifeprism.config.settings_manager import settings
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        base = "line1\nline2\nline3\n"
        ours = "line1\nOURS\nline3\n"
        theirs = "line1\nTHEIRS\nline3\n"

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/lww.md"
        local_file = test_base / "diary" / "lww.md"
        local_file.write_text(ours, encoding="utf-8")

        provider = FileSyncStateProvider(db_manager=initialized_db)
        parent_hash = compute_file_hash(base.encode("utf-8"))
        original_current = compute_file_hash(ours.encode("utf-8"))
        provider.upsert_state(
            file_path=rel_path,
            parent_hash=parent_hash,
            current_hash=original_current,
        )

        # Mock: base 内容获取失败 → 整个文件失败 → LWW 回退
        with (
            patch.object(sync_client, "_fetch_remote_file_content", return_value=theirs),
            patch.object(sync_client, "_fetch_remote_base_content", return_value=None),
            patch(
                "lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe"
            ) as mock_rcts,
        ):
            result = sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: LWW 回退后仍返回成功路径（本地版本"赢"，需推送）
        assert result == [rel_path]

        # Assert: 本地文件保留原 ours 内容（LWW = 本地赢）
        final_content = local_file.read_text(encoding="utf-8")
        assert final_content == ours

        # Assert: LLM 未被调用（LWW 回退，不走 diff3 + LLM 流程）
        mock_rcts.assert_not_called()

        # Assert: 已备份云端版本到 sync_conflict/
        sync_conflict_dir = settings.lifeprism_data_path / "sync_conflict"
        assert sync_conflict_dir.exists()
        remote_backup_files = list(sync_conflict_dir.rglob("*.remote.md"))
        assert len(remote_backup_files) == 1
        assert remote_backup_files[0].read_text(encoding="utf-8") == theirs

        # Assert: file_sync_state.current_hash 保持为 ours 的 hash（LWW 本地赢）
        state = provider.get_state(rel_path)
        assert state is not None
        assert state["current_hash"] == original_current

    def test_partial_block_failure_does_not_interrupt_other_blocks(
        self,
        sync_client,
        initialized_db,
        clean_conflict_test_dir,
        clean_file_sync_state,
        clean_sync_conflict_dir,
    ):
        """单个冲突块失败不中断其他冲突块处理

        场景：
        - 2 个冲突块
        - 块 1：LLM 始终返回无效 JSON → 3 次重试失败 → 降级 keep_ours
        - 块 2：LLM 返回有效 JSON → 替换成功
        - 最终：块 1 保留 ours 内容，块 2 被替换
        """
        from lifeprism.config.settings_manager import settings
        from lifeprism.llm.bus.events import OutboundMessage
        from lifeprism.llm.providers import LLMResponse
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        base = "h1\nx1\nh2\nx2\nh3\n"
        ours = "h1\nOURS1\nh2\nOURS2\nh3\n"
        theirs = "h1\nTHEIRS1\nh2\nTHEIRS2\nh3\n"

        info = _compute_diff3_conflict_info(base, ours, theirs)
        assert info["conflicts"] == 2
        blocks = info["blocks"]

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/partial.md"
        local_file = test_base / "diary" / "partial.md"
        local_file.write_text(ours, encoding="utf-8")

        provider = FileSyncStateProvider(db_manager=initialized_db)
        parent_hash = compute_file_hash(base.encode("utf-8"))
        provider.upsert_state(
            file_path=rel_path,
            parent_hash=parent_hash,
            current_hash=compute_file_hash(ours.encode("utf-8")),
        )

        # Mock LLM:
        # - 前 3 次调用（块 1 重试 3 次）：返回无效 JSON
        # - 第 4 次调用（块 2）：返回有效 JSON
        invalid_resp = OutboundMessage(
            response=LLMResponse(content="always invalid"),
        )
        valid_resp = OutboundMessage(
            response=LLMResponse(
                content=_make_llm_json_response(
                    conflict_id=blocks[1].conflict_id,
                    start_marker=blocks[1].start_marker,
                    end_marker=blocks[1].end_marker,
                    replacement="MERGED2",
                )
            )
        )

        mock_futures = [
            MagicMock(result=MagicMock(return_value=invalid_resp)) for _ in range(3)
        ]
        mock_futures.append(MagicMock(result=MagicMock(return_value=valid_resp)))

        with (
            patch.object(sync_client, "_fetch_remote_file_content", return_value=theirs),
            patch.object(sync_client, "_fetch_remote_base_content", return_value=base),
            patch(
                "lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe",
                side_effect=mock_futures,
            ),
        ):
            result = sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: 返回成功路径（降级 + 替换都算"解决"）
        assert result == [rel_path]

        # Assert: 块 1 保留 ours 内容（降级 keep_ours），块 2 被替换
        final_content = local_file.read_text(encoding="utf-8")
        assert "OURS1" in final_content  # 块 1 降级保留
        assert "MERGED2" in final_content  # 块 2 替换成功
        assert "THEIRS" not in final_content  # 无 theirs 内容残留
        assert "<<<<<<<" not in final_content  # 无冲突标记残留
        assert ">>>>>>>" not in final_content


# ==================== Seam 8: Issue 4 behavior.md 场景（安全属性验证） ====================


class TestIssue4BehaviorMdScenario:
    """Issue 4 behavior.md 冲突场景端到端测试

    重现 2026-07-16 behavior.md 被破坏的场景（P0 bug），
    验证新流程的安全属性：
    1. 不会出现 LLM 截断数据（LLM 只能替换冲突块，不能截断整个文件）
    2. 不会出现 WriteFileTool XML 残留（LLM 无工具，只返回 JSON）
    """

    def test_behavior_md_no_truncation(
        self,
        sync_client,
        initialized_db,
        clean_conflict_test_dir,
        clean_file_sync_state,
        clean_sync_conflict_dir,
    ):
        """behavior.md 冲突：LLM 无法截断数据

        场景：
        - behavior.md 是一个长文档（模拟）
        - 本地和云端在中间某处有冲突
        - LLM 返回的 replacement 很短（模拟"截断"行为）
        - 验证：只有冲突块被替换，文件其他部分完整保留

        关键安全属性（PRD 决策 5）：
        - LLM 只能替换冲突块（从 start_marker 到 end_marker）
        - 文件非冲突区域的内容不会被 LLM 触碰
        - 即使 LLM 返回很短的 replacement，也不会截断整个文件
        """
        from lifeprism.config.settings_manager import settings
        from lifeprism.llm.bus.events import OutboundMessage
        from lifeprism.llm.providers import LLMResponse
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        # 构造长文档：50 行头部 + 冲突区域 + 50 行尾部
        head_lines = [f"行为记录 {i}" for i in range(50)]
        tail_lines = [f"行为记录 {50 + i}" for i in range(50)]

        base = "\n".join(head_lines + ["原始行"] + tail_lines) + "\n"
        ours = "\n".join(head_lines + ["本地修改行"] + tail_lines) + "\n"
        theirs = "\n".join(head_lines + ["云端修改行"] + tail_lines) + "\n"

        info = _compute_diff3_conflict_info(base, ours, theirs)
        assert info["conflicts"] == 1
        block = info["blocks"][0]

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "user").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/user/behavior.md"
        local_file = test_base / "user" / "behavior.md"
        local_file.write_text(ours, encoding="utf-8")

        provider = FileSyncStateProvider(db_manager=initialized_db)
        parent_hash = compute_file_hash(base.encode("utf-8"))
        provider.upsert_state(
            file_path=rel_path,
            parent_hash=parent_hash,
            current_hash=compute_file_hash(ours.encode("utf-8")),
        )

        # Mock LLM: 返回很短的 replacement（模拟"截断"行为）
        short_replacement = "短"
        llm_json = _make_llm_json_response(
            conflict_id=1,
            start_marker=block.start_marker,
            end_marker=block.end_marker,
            replacement=short_replacement,
        )

        mock_future = MagicMock()
        mock_future.result.return_value = OutboundMessage(
            response=LLMResponse(content=llm_json),
        )

        with (
            patch.object(sync_client, "_fetch_remote_file_content", return_value=theirs),
            patch.object(sync_client, "_fetch_remote_base_content", return_value=base),
            patch(
                "lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe",
                return_value=mock_future,
            ),
        ):
            result = sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: 返回成功路径
        assert result == [rel_path]

        # Assert: 文件非冲突区域完整保留（关键安全属性）
        final_content = local_file.read_text(encoding="utf-8")
        for i in range(50):
            assert f"行为记录 {i}" in final_content, f"头部第 {i} 行丢失（截断）"
            assert f"行为记录 {50 + i}" in final_content, f"尾部第 {50 + i} 行丢失（截断）"

        # Assert: 冲突块已被替换为短 replacement
        assert short_replacement in final_content
        assert "本地修改行" not in final_content
        assert "云端修改行" not in final_content

        # Assert: 无冲突标记残留
        assert "<<<<<<<" not in final_content
        assert ">>>>>>>" not in final_content

    def test_behavior_md_no_write_file_tool_xml_residue(
        self,
        sync_client,
        initialized_db,
        clean_conflict_test_dir,
        clean_file_sync_state,
        clean_sync_conflict_dir,
    ):
        """behavior.md 冲突：无 WriteFileTool XML 残留

        场景：
        - behavior.md 冲突
        - 验证最终文件不包含任何 XML 工具调用残留

        背景（docs/history-bugs/2026-07-17-write-file-xml-tag-residue-in-doc.md）：
        - 旧流程中 LLM 有 WriteFileTool，可能输出 XML 工具调用残留
        - 新流程 LLM 无工具（tools=[]），只返回 JSON，不可能产生 XML 残留

        关键安全属性（PRD 决策 8 / ADR-1 决策 2）：
        - CONFLICT_RESOLVE 分支 tools=[]
        - LLM 只输出 JSON，程序解析 JSON 后执行替换
        - 最终文件不可能包含 XML 工具调用标签
        """
        from lifeprism.config.settings_manager import settings
        from lifeprism.llm.bus.events import OutboundMessage
        from lifeprism.llm.providers import LLMResponse
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        base = "# behavior\n原始内容\n"
        ours = "# behavior\n本地修改\n"
        theirs = "# behavior\n云端修改\n"

        info = _compute_diff3_conflict_info(base, ours, theirs)
        assert info["conflicts"] == 1
        block = info["blocks"][0]

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "user").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/user/behavior.md"
        local_file = test_base / "user" / "behavior.md"
        local_file.write_text(ours, encoding="utf-8")

        provider = FileSyncStateProvider(db_manager=initialized_db)
        parent_hash = compute_file_hash(base.encode("utf-8"))
        provider.upsert_state(
            file_path=rel_path,
            parent_hash=parent_hash,
            current_hash=compute_file_hash(ours.encode("utf-8")),
        )

        # Mock LLM: 返回正常 JSON（不含任何 XML 标签）
        replacement = "合并后的内容"
        llm_json = _make_llm_json_response(
            conflict_id=1,
            start_marker=block.start_marker,
            end_marker=block.end_marker,
            replacement=replacement,
        )

        mock_future = MagicMock()
        mock_future.result.return_value = OutboundMessage(
            response=LLMResponse(content=llm_json),
        )

        with (
            patch.object(sync_client, "_fetch_remote_file_content", return_value=theirs),
            patch.object(sync_client, "_fetch_remote_base_content", return_value=base),
            patch(
                "lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe",
                return_value=mock_future,
            ),
        ):
            result = sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: 返回成功路径
        assert result == [rel_path]

        # Assert: 最终文件无 XML 工具调用残留
        final_content = local_file.read_text(encoding="utf-8")
        xml_residue_patterns = [
            "<write_file>",
            "</write_file>",
            "<edit_file>",
            "</edit_file>",
            "<read_file>",
            "</read_file>",
            "<file_tree>",
            "</file_tree>",
            "<search_file>",
            "</search_file>",
            "<search_string>",
            "</search_string>",
            "<tool_call>",
            "</tool_call>",
            "<function_call>",
            "</function_call>",
        ]
        for pattern in xml_residue_patterns:
            assert pattern not in final_content, f"发现 XML 工具调用残留: {pattern}"

        # Assert: 无冲突标记残留
        assert "<<<<<<<" not in final_content
        assert ">>>>>>>" not in final_content

        # Assert: 冲突块已被替换
        assert replacement in final_content


# ==================== Seam 9: Issue 4 备份与 file_sync_state 更新 ====================


class TestIssue4BackupAndStateUpdate:
    """Issue 4 备份与 file_sync_state 更新

    验证新流程在冲突解决后正确执行：
    1. 备份本地与云端版本到 sync_conflict/（PRD 决策 19）
    2. 更新 file_sync_state.current_hash = 合并后内容的 hash
    3. 保持 file_sync_state.parent_hash 不变
    """

    def test_backup_both_local_and_remote_versions(
        self,
        sync_client,
        initialized_db,
        clean_conflict_test_dir,
        clean_file_sync_state,
        clean_sync_conflict_dir,
    ):
        """冲突解决后应同时备份本地与云端版本到 sync_conflict/"""
        from lifeprism.config.settings_manager import settings
        from lifeprism.llm.bus.events import OutboundMessage
        from lifeprism.llm.providers import LLMResponse
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        base = "line1\nline2\nline3\n"
        ours = "line1\nOURS\nline3\n"
        theirs = "line1\nTHEIRS\nline3\n"

        info = _compute_diff3_conflict_info(base, ours, theirs)
        block = info["blocks"][0]

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/backup.md"
        local_file = test_base / "diary" / "backup.md"
        local_file.write_text(ours, encoding="utf-8")

        provider = FileSyncStateProvider(db_manager=initialized_db)
        parent_hash = compute_file_hash(base.encode("utf-8"))
        provider.upsert_state(
            file_path=rel_path,
            parent_hash=parent_hash,
            current_hash=compute_file_hash(ours.encode("utf-8")),
        )

        replacement = "MERGED"
        llm_json = _make_llm_json_response(
            conflict_id=1,
            start_marker=block.start_marker,
            end_marker=block.end_marker,
            replacement=replacement,
        )

        mock_future = MagicMock()
        mock_future.result.return_value = OutboundMessage(
            response=LLMResponse(content=llm_json),
        )

        with (
            patch.object(sync_client, "_fetch_remote_file_content", return_value=theirs),
            patch.object(sync_client, "_fetch_remote_base_content", return_value=base),
            patch(
                "lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe",
                return_value=mock_future,
            ),
        ):
            sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: 同时备份本地与云端版本
        sync_conflict_dir = settings.lifeprism_data_path / "sync_conflict"
        assert sync_conflict_dir.exists()
        local_backup_files = list(sync_conflict_dir.rglob("*.local.md"))
        remote_backup_files = list(sync_conflict_dir.rglob("*.remote.md"))
        assert len(local_backup_files) == 1
        assert len(remote_backup_files) == 1
        assert local_backup_files[0].read_text(encoding="utf-8") == ours
        assert remote_backup_files[0].read_text(encoding="utf-8") == theirs

    def test_file_sync_state_current_hash_updated_to_merged_hash(
        self,
        sync_client,
        initialized_db,
        clean_conflict_test_dir,
        clean_file_sync_state,
        clean_sync_conflict_dir,
    ):
        """冲突解决后 current_hash 应为合并后内容的 hash"""
        from lifeprism.config.settings_manager import settings
        from lifeprism.llm.bus.events import OutboundMessage
        from lifeprism.llm.providers import LLMResponse
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        base = "line1\nline2\nline3\n"
        ours = "line1\nOURS\nline3\n"
        theirs = "line1\nTHEIRS\nline3\n"

        info = _compute_diff3_conflict_info(base, ours, theirs)
        block = info["blocks"][0]

        test_base = settings.lifeprism_data_path / "conflict_test"
        (test_base / "diary").mkdir(parents=True, exist_ok=True)
        rel_path = "conflict_test/diary/state.md"
        local_file = test_base / "diary" / "state.md"
        local_file.write_text(ours, encoding="utf-8")

        provider = FileSyncStateProvider(db_manager=initialized_db)
        parent_hash = compute_file_hash(base.encode("utf-8"))
        provider.upsert_state(
            file_path=rel_path,
            parent_hash=parent_hash,
            current_hash=compute_file_hash(ours.encode("utf-8")),
        )

        replacement = "MERGED"
        llm_json = _make_llm_json_response(
            conflict_id=1,
            start_marker=block.start_marker,
            end_marker=block.end_marker,
            replacement=replacement,
        )

        mock_future = MagicMock()
        mock_future.result.return_value = OutboundMessage(
            response=LLMResponse(content=llm_json),
        )

        expected_final = f"line1\n{replacement}\nline3\n"
        expected_hash = compute_file_hash(expected_final.encode("utf-8"))

        with (
            patch.object(sync_client, "_fetch_remote_file_content", return_value=theirs),
            patch.object(sync_client, "_fetch_remote_base_content", return_value=base),
            patch(
                "lifeprism.sync.sync_client.asyncio.run_coroutine_threadsafe",
                return_value=mock_future,
            ),
        ):
            sync_client._resolve_conflicts(
                conflict_paths=[rel_path],
                remote_url="http://test:8000",
                api_key="test-key",
            )

        # Assert: current_hash 已更新为合并后内容的 hash
        state = provider.get_state(rel_path)
        assert state is not None
        assert state["current_hash"] == expected_hash
        # Assert: parent_hash 保持不变
        assert state["parent_hash"] == parent_hash
