"""本地同步客户端 - 执行 Pull + Push 双向同步

职责：
- HTTP 通信（httpx）
- Last-Write-Wins 冲突解决
- 不直接执行 SQL，所有数据库操作通过 SyncRepository

参考: .scratch/linux-deployment-discussion/issues-p2/05-sync-client-basic.md
"""

import asyncio
import base64
import gzip
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from lifeprism.sync.constants import (
    DB_PUSH_BATCH_SIZE,
    EXCLUDED_FILENAMES as _EXCLUDED_FILENAMES,
    FILE_BATCH_SIZE,
    FULL_CLEAR_TIMEOUT,
    INITIALIZATION_STATUS_TIMEOUT,
    MARK_INITIALIZED_TIMEOUT,
    PUSH_ENDPOINT_TIMEOUT,
    SYNC_DIRECTORIES,
    SYNC_TABLES,
)
from lifeprism.sync.constants import safe_gzip_decompress
from lifeprism.utils import get_logger

logger = get_logger(__name__)


def _safe_write_file(file_path: Path, content: bytes) -> None:
    """原子写入文件：先写临时文件再 os.replace，防止写入中途崩溃导致文件损坏

    Args:
        file_path: 目标文件路径
        content: 文件内容字节串
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=file_path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
        os.replace(tmp_path, file_path)
    except OSError:
        # 清理临时文件后重新抛出（仅捕获文件操作可能抛出的 OSError，
        # 不使用 except Exception 避免吞掉编程错误）
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


# 向后兼容：重新导出常量，让现有的 `from lifeprism.sync.sync_client import SYNC_TABLES` 仍可工作
# 常量定义已移至 lifeprism.sync.constants（客户端和云端共用）
__all__ = [
    "SyncClient",
    "SYNC_TABLES",
    "SYNC_DIRECTORIES",
    "FILE_BATCH_SIZE",
    "_safe_write_file",
]


class SyncClient:
    """本地同步客户端

    执行 Pull + Push 双向同步，应用 Last-Write-Wins 冲突解决策略。
    不直接执行 SQL，所有数据库操作通过 SyncRepository。

    Attributes:
        db: DatabaseManager 实例
        sync_repository: SyncRepository 实例
    """

    def __init__(self, db_manager, sync_repository, main_event_loop=None):
        """初始化同步客户端

        Args:
            db_manager: DatabaseManager 实例
            sync_repository: SyncRepository 实例
            main_event_loop: 主线程的 asyncio 事件循环引用，
                             用于通过 run_coroutine_threadsafe 桥接 bus.send（冲突解决时需要）
        """
        self.db = db_manager
        self.sync_repository = sync_repository
        # 主线程事件循环引用（用于 bus 桥接）
        self._main_event_loop = main_event_loop
        # 并发控制锁：保护 _is_syncing 的原子 check-then-set
        self._sync_lock = threading.Lock()
        # 并发控制标志：True 表示一次同步正在进行中
        self._is_syncing: bool = False
        # 后台定时同步任务句柄
        self._sync_task = None

    @property
    def is_syncing(self) -> bool:
        """只读属性：当前是否正在同步中"""
        return self._is_syncing

    def try_start_sync(self) -> bool:
        """尝试获取同步锁（原子 check-then-set）。

        成功获取返回 True（已将 _is_syncing 置为 True），
        若已在同步中则返回 False。

        Returns:
            True 表示成功获取同步锁，False 表示已在同步中
        """
        with self._sync_lock:
            if self._is_syncing:
                return False
            self._is_syncing = True
            return True

    def finish_sync(self) -> None:
        """释放同步锁（将 _is_syncing 重置为 False）。"""
        with self._sync_lock:
            self._is_syncing = False

    def start_scheduled_sync(self, interval_seconds: int = 600):
        """启动后台定时同步。

        使用 asyncio.create_task 创建后台任务，循环执行同步。
        该方法不阻塞调用方，需在事件循环中调用。

        Args:
            interval_seconds: 同步间隔（秒），默认 600（10 分钟）

        Returns:
            asyncio.Task: 创建的后台同步任务
        """
        self._sync_task = asyncio.create_task(self._run_sync_loop(interval_seconds))
        return self._sync_task

    async def _run_sync_loop(self, interval_seconds: int):
        """定时同步循环的内部实现。

        循环执行：等待 interval_seconds -> 检查配置 -> 调用 sync_once()。
        - 配置检查：每次执行前重新读取 sync.remote_url，为空则跳过本次
          （不取消整个定时任务，方便用户后续在前端配置 url 后自动开始同步）
        - 并发控制：通过 try_start_sync() 原子地检查并设置同步标志，
          若已在同步中则跳过本次并记录 WARNING
        - 失败重试：sync_once 抛异常时记录 ERROR，下次定时触发时自动重试
        - 使用 try...finally 确保 finish_sync() 在异常时也能被调用

        Args:
            interval_seconds: 同步间隔（秒）
        """
        while True:
            await asyncio.sleep(interval_seconds)
            # 配置检查：未配置 remote_url 时跳过本次（不取消定时任务）
            # 这样用户后续在前端配置 url 后，下次定时自动开始同步，无需重启
            remote_url = self._read_remote_url()
            if not remote_url:
                logger.debug("跳过定时同步：未配置 sync.remote_url")
                continue
            # 并发控制：原子地检查并设置同步标志
            if not self.try_start_sync():
                logger.warning("跳过定时同步（上次同步未完成）")
                continue
            try:
                logger.info("定时同步开始")
                start_time = datetime.now(timezone.utc)
                # 使用 asyncio.to_thread 在独立线程中运行同步方法，避免阻塞事件循环
                await asyncio.to_thread(self.sync_once)
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                logger.info("定时同步完成，耗时 %ss", duration)
            except Exception:
                # 失败重试：记录 ERROR，不终止循环，下次定时触发自动重试
                logger.error("定时同步失败", exc_info=True)
            finally:
                self.finish_sync()

    def _read_remote_url(self) -> str:
        """读取 sync.remote_url 配置（每次调用都从 SettingsManager 内存读取，支持热重载）

        前端通过 PATCH /api/v2/settings 修改 sync_remote_url 后，
        SettingsManager.update 会立即更新内存中的 _config，
        因此此处调用 get_setting 能立即读到新值，无需重启或 reload。

        Returns:
            remote_url 字符串，未配置时返回空字符串
        """
        from lifeprism.config.settings_manager import get_setting

        return get_setting("sync.remote_url") or ""

    def sync_once(self, tables=None, directories=None):
        """执行一次完整同步（动态表对比 → 数据库 Pull -> Push → 文件 Pull -> Push）

        从配置读取 remote_url、api_key、last_sync_time，
        依次执行动态表定义对比（双向建表）、数据库同步、文件同步，
        只有全部成功才更新 last_sync_time。

        Args:
            tables: 同步表列表。None 时走默认流程（动态表对比 + 建表 → 拼接 SYNC_TABLES + 动态表列表）；
                    非 None 时跳过动态表对比，直接用传入的表列表（用于测试场景）。
            directories: 文件同步目录列表，None 则使用默认 SYNC_DIRECTORIES

        Raises:
            ValidationError: sync.remote_url 或 sync_api_key 未配置时抛出
        """
        from lifeprism.config.settings_manager import get_setting, set_setting
        from lifeprism.sync.sync_config import get_sync_api_key
        from lifeprism.utils.exceptions import ValidationError

        remote_url = get_setting("sync.remote_url")
        api_key = get_sync_api_key()
        last_sync_time = get_setting("sync.last_sync_time", "")

        # 防御性检查：未配置 remote_url 或 api_key 时直接抛出业务校验异常，
        # 避免发起 HTTP 请求时因 url 格式错误导致 httpx.UnsupportedProtocol
        if not remote_url:
            raise ValidationError(
                message="sync.remote_url 未配置，请先在前端设置云端地址",
                code="SYNC_REMOTE_URL_NOT_CONFIGURED",
            )
        if not api_key:
            raise ValidationError(
                message="sync_api_key 未配置，请先生成云端配置",
                code="SYNC_API_KEY_NOT_CONFIGURED",
            )

        # ===== 首次同步检测分支 =====
        # 检查云端是否已完成首次同步初始化（标志文件存在）。
        # 未初始化时执行全清覆盖（full-clear + 全量推送），绕过增量同步流程。
        # 参考 ADR: docs/adr/2026-07-17-cloud-init-first-sync-full-clear.md
        if not self._check_cloud_initialized(remote_url, api_key):
            logger.info("云端未初始化，执行首次同步（全清覆盖）...")
            self._full_sync_to_cloud(remote_url, api_key, tables, directories)
            logger.info("首次同步完成")
            return

        if tables is None:
            # 默认场景：动态表对比 + 建表 → 拼接 SYNC_TABLES + 动态表列表
            # 参考 ADR: docs/adr/2026-07-16-dynamic-tables-sync-definition-comparison.md
            dynamic_table_names = self._sync_dynamic_tables_definitions(remote_url, api_key)
            tables = list(set(SYNC_TABLES + dynamic_table_names))
            logger.info(
                "同步表列表: 静态表=%d张, 动态表=%d张, 总计=%d张",
                len(SYNC_TABLES),
                len(tables) - len(SYNC_TABLES),
                len(tables),
            )
        if directories is None:
            directories = SYNC_DIRECTORIES

        # 数据库同步：Pull -> Push，任一步骤失败则不更新 last_sync_time
        self.pull_from_remote(remote_url, api_key, last_sync_time, tables)

        self.push_to_remote(remote_url, api_key, tables)

        # 文件同步：全流程（Phase 1-3，参考 ADR v2.1）
        self._sync_files_full_flow(remote_url, api_key, last_sync_time, directories)

        # 只有全部成功才更新 last_sync_time（使用 ISO 8601 格式，与服务端保持一致）
        current_time = datetime.now(timezone.utc).isoformat()
        set_setting("sync.last_sync_time", current_time)
        logger.info("sync_once: 同步完成，last_sync_time 已更新为 %s", current_time)

    def _check_cloud_initialized(self, remote_url: str, api_key: str) -> bool:
        """检查云端是否已完成首次同步初始化

        通过 GET /api/sync/initialization-status 检查云端标志文件是否存在。
        标志文件由 /mark-initialized 端点创建，存在表示云端已完成首次同步。

        失败时返回 True（假设已初始化），避免网络抖动误触发全清。
        副作用：本次 sync_once 会走增量同步分支（依赖前提 3 保证不产生数据混合）。
        下次 sync_once 时若检测成功且云端确实未初始化（标志文件不存在），
        将返回 False 触发 full-clear。

        Args:
            remote_url: 远程服务器 URL
            api_key: API Key

        Returns:
            True 已初始化（或检查失败时假设已初始化），False 未初始化
        """
        try:
            resp = httpx.get(
                url=f"{remote_url}/api/sync/initialization-status",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=INITIALIZATION_STATUS_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json().get("initialized", False)
        except Exception as e:
            logger.warning(
                "检查云端初始化状态失败，假设已初始化（本次走增量同步）: %s",
                e,
            )
            return True

    def _full_sync_to_cloud(
        self,
        remote_url: str,
        api_key: str,
        tables=None,
        directories=None,
    ) -> None:
        """首次同步：清空云端 + 全量推送数据库和文件 + 标记初始化

        流程：
        1. POST /api/sync/full-clear 清空云端所有同步数据
        2. _initial_push_db 全量推送数据库（含动态表定义对比 + 建表）
        3. _initial_push_files 全量推送文件 + 推进本地 parent_hash
        4. set_setting("sync.last_sync_time", ...) + POST /api/sync/mark-initialized

        顺序说明：先设置 last_sync_time 再 mark-initialized，解决非原子性问题。
        如果 mark-initialized 失败，下次 sync_once 会重新检测（未初始化）并重试。

        Args:
            remote_url: 远程服务器 URL
            api_key: API Key
            tables: 同步表列表（首次同步不使用，保留参数仅为兼容 sync_once 调用签名）
            directories: 文件同步目录列表，None 则使用 SYNC_DIRECTORIES
        """
        from lifeprism.config.settings_manager import set_setting

        # 1. 清空云端
        logger.info("步骤 1/4: 清空云端数据...")
        resp = httpx.post(
            url=f"{remote_url}/api/sync/full-clear",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=FULL_CLEAR_TIMEOUT,
        )
        resp.raise_for_status()
        logger.info("云端清空完成: %s", resp.json())

        # 2. 全量推送数据库
        logger.info("步骤 2/4: 全量推送数据库...")
        self._initial_push_db(remote_url, api_key)

        # 3. 全量推送文件
        logger.info("步骤 3/4: 全量推送文件...")
        self._initial_push_files(remote_url, api_key, directories or SYNC_DIRECTORIES)

        # 4. 更新本地 last_sync_time + 标记云端已初始化
        # 注意：先设置 last_sync_time，再 mark-initialized
        # 这样即使 mark-initialized 失败，下次 sync_once 会重新检测（未初始化）并重试
        # 如果 mark-initialized 成功，last_sync_time 已设置，下次走增量同步
        logger.info("步骤 4/4: 更新 last_sync_time 并标记云端已初始化...")
        current_time = datetime.now(timezone.utc).isoformat()
        set_setting("sync.last_sync_time", current_time)

        resp = httpx.post(
            url=f"{remote_url}/api/sync/mark-initialized",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=MARK_INITIALIZED_TIMEOUT,
        )
        resp.raise_for_status()
        logger.info("云端已标记为已初始化, last_sync_time=%s", current_time)

    def _initial_push_db(self, remote_url: str, api_key: str) -> None:
        """首次同步数据库推送：全量推送所有 SYNC_TABLES 数据

        流程：
        1. 调用 _sync_dynamic_tables_definitions 让云端按本地定义创建 custom_<slug> 表
           （云端 full-clear 后 custom_record_types 为空，会触发 slugs_to_create_remotely）
        2. 构建完整表列表（SYNC_TABLES + 动态表）
        3. 逐表全量推送（用 query_all 避免 NULL updated_at 被过滤）
        4. 动态表失败 continue，静态表失败记录到 failed_tables

        Args:
            remote_url: 远程服务器 URL
            api_key: API Key

        Raises:
            RuntimeError: 静态表推送部分失败时抛出
        """
        # 1. 先处理动态表定义（让云端按本地定义创建 custom_<slug> 表）
        # 云端 full-clear 后 custom_record_types 为空，cloud_slugs = 空集
        # _sync_dynamic_tables_definitions 会触发 slugs_to_create_remotely = 本地所有 slug
        # _rebuild_remote_dynamic_tables 是幂等的（表已存在则 skipped）
        dynamic_table_names = self._sync_dynamic_tables_definitions(remote_url, api_key)

        # 2. 构建完整表列表
        all_tables = list(set(SYNC_TABLES + dynamic_table_names))
        logger.info(
            "首次同步数据库推送: 静态表=%d张, 动态表=%d张, 总计=%d张",
            len(SYNC_TABLES),
            len(all_tables) - len(SYNC_TABLES),
            len(all_tables),
        )

        # 3. 全量推送每个表（用 query_all 获取全量数据，避免 NULL updated_at 被过滤）
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        failed_tables = []
        for table_name in all_tables:
            try:
                offset = 0
                total_pushed = 0
                while True:
                    rows = self.sync_repository.query_all(table_name, offset, DB_PUSH_BATCH_SIZE)
                    if not rows:
                        break
                    # 直接推送这一批（query_all 已分页，无需再切分）
                    resp = httpx.post(
                        url=f"{remote_url}/api/sync/push",
                        headers=headers,
                        json={"changes": {table_name: rows}},
                        timeout=PUSH_ENDPOINT_TIMEOUT,
                    )
                    resp.raise_for_status()
                    total_pushed += len(rows)
                    if len(rows) < DB_PUSH_BATCH_SIZE:
                        break
                    offset += DB_PUSH_BATCH_SIZE
                logger.info("表 %s 全量推送完成: %d 条", table_name, total_pushed)
            except Exception as e:
                # 动态表失败时 continue 而非 raise，避免单张动态表失败中断整个首次同步
                # 静态表失败仍记录到 failed_tables，因为静态表是核心数据
                if self.sync_repository.is_dynamic_table(table_name):
                    logger.warning(
                        "动态表 %s 全量推送失败，跳过（不影响首次同步整体）: %s",
                        table_name,
                        e,
                    )
                else:
                    logger.error("静态表 %s 全量推送失败: %s", table_name, e)
                    failed_tables.append(table_name)

        if failed_tables:
            from lifeprism.utils.exceptions import ExternalServiceError

            raise ExternalServiceError(
                message="首次同步数据库推送部分失败",
                code="INITIAL_PUSH_PARTIAL_FAILED",
                details={"failed_tables": failed_tables},
            )

    def _initial_push_files(
        self,
        remote_url: str,
        api_key: str,
        directories: list[str],
    ) -> None:
        """首次同步文件推送：全量推送所有 SYNC_DIRECTORIES 文件

        关键修复：推送完成后推进本地 parent_hash = current_hash，
        避免下次 sync_once 走矩阵判定时误判为 CONFLICT（Row 3 陷阱）。

        流程：
        1. _refresh_current_hashes 扫描文件并刷新 current_hash（复用其返回值避免重复扫描）
        2. 分批 _push_files 推送（复用现有方法）
        3. _advance_local_parent_after_initial_sync 推进本地 parent_hash

        Args:
            remote_url: 远程服务器 URL
            api_key: API Key
            directories: 文件同步目录列表
        """
        # 1. 刷新 current_hash（同时扫描文件，复用扫描结果避免重复扫描）
        # _refresh_current_hashes 会扫描文件并 upsert state（parent_hash=existing or None, current_hash=计算值）
        # 返回扫描到的文件相对路径列表，供后续 _push_files 和 _advance_local_parent 复用
        file_list = self._refresh_current_hashes(directories)
        if not file_list:
            logger.info("无文件需要推送")
            return

        # 2. 分批推送（复用 _push_files）
        batch_size = FILE_BATCH_SIZE
        total = len(file_list)
        for offset in range(0, total, batch_size):
            batch_paths = file_list[offset : offset + batch_size]
            self._push_files(remote_url, api_key, batch_paths)
            logger.info("文件推送进度: %d/%d", offset + len(batch_paths), total)

        logger.info("文件全量推送完成: %d 个文件", total)

        # 3. 推进本地 parent_hash = current_hash
        # 避免 Row 3 陷阱：首次同步后两端 parent_hash 均为 None，
        # 下次 sync_once 时本地文件被修改会误判为 CONFLICT（而非 PUSH）
        self._advance_local_parent_after_initial_sync(file_list)

    def _advance_local_parent_after_initial_sync(self, paths: list[str]) -> None:
        """首次同步后推进本地 parent_hash = current_hash

        修复 Row 3 陷阱：首次同步后两端 file_sync_state 的 parent_hash 均为 None，
        若不推进 parent_hash，下次 sync_once 时本地文件被修改会走矩阵判定 Row 3
        （双方 parent 均为 None 且内容不同 → CONFLICT），触发不必要的 AI merge。

        推进后：
        - 本地 parent_hash = current_hash（标记"已同步到此版本"）
        - 下次 sync_once 时本地文件未修改 → current_hash 不变 → SKIP（正确）
        - 本地文件被修改 → current_hash 变化 → local_has_parent=True, remote_has_parent=False → Row 5 → PUSH（正确）

        使用批量操作（batch_get_states + batch_upsert_states）避免 N+1 查询。

        Args:
            paths: 首次同步推送的文件相对路径列表
        """
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider

        provider = FileSyncStateProvider(db_manager=self.db)
        if not paths:
            return

        # 批量查询现有状态（单次 DB 查询，避免 N 次 get_state 往返）
        existing_states = provider.batch_get_states(paths)

        # 内存中构建 upsert 列表
        to_upsert = []
        for rel_path in paths:
            state = existing_states.get(rel_path)
            if state and state.get("current_hash"):
                to_upsert.append(
                    {
                        "file_path": rel_path,
                        "parent_hash": state["current_hash"],
                        "current_hash": state["current_hash"],
                    }
                )

        # 批量 upsert（单次事务）
        if to_upsert:
            provider.batch_upsert_states(to_upsert)

        advanced_count = len(to_upsert)
        skipped = len(paths) - advanced_count
        logger.info("首次同步后推进 parent_hash: %d/%d 个文件", advanced_count, len(paths))
        if skipped > 0:
            logger.warning(
                "首次同步后 %d 个文件未推进 parent_hash（state 或 current_hash 为空），"
                "可能触发下次同步 CONFLICT 误判",
                skipped,
            )

    def _sync_dynamic_tables_definitions(self, remote_url: str, api_key: str) -> list[str]:
        """拉取云端动态表定义，本地 slug 对比，触发双向建表

        在 pull 之前执行，确保两端 schema 一致后再同步数据。
        参考 ADR: docs/adr/2026-07-16-dynamic-tables-sync-definition-comparison.md

        流程：
        1. GET /api/sync/dynamic-tables-definitions 拉取云端动态表定义
        2. 本地查询 custom_record_types_full_definitions 拿到本地定义
        3. slug 集合对比：
           - 云端有本地没有 → 本地建表（只执行 DDL，不写 meta，让 pull 统一同步）
           - 本地有云端没有 → 调用 _rebuild_remote_dynamic_tables 让云端建表
        4. 返回动态表名列表（云端 slug ∪ 本地 slug → custom_<slug>）

        Args:
            remote_url: 远程服务器 URL
            api_key: API Key

        Returns:
            动态数据表名列表（如 ["custom_reading_log", ...]），无动态表时返回空列表

        Raises:
            httpx.HTTPStatusError / httpx.RequestError: HTTP 请求失败
        """
        # 1. 拉取云端动态表定义
        try:
            response = httpx.get(
                url=f"{remote_url}/api/sync/dynamic-tables-definitions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                },
                timeout=60.0,
            )
            response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error(
                "_sync_dynamic_tables_definitions: 拉取云端动态表定义失败, remote_url=%s, error=%s",
                remote_url,
                e,
            )
            raise

        cloud_types = response.json().get("types", [])
        cloud_slugs = {t["slug"] for t in cloud_types}
        logger.info(
            "_sync_dynamic_tables_definitions: 云端动态表 slug=%s",
            cloud_slugs,
        )

        # 2. 查询本地动态表定义
        local_types = self.sync_repository.get_custom_record_types_full_definitions()
        local_slugs = {t["slug"] for t in local_types}
        logger.info(
            "_sync_dynamic_tables_definitions: 本地动态表 slug=%s",
            local_slugs,
        )

        # 3. slug 集合对比，触发双向建表
        # 3a. 云端有本地没有 → 本地建表（只执行 DDL，不写 meta）
        slugs_to_create_locally = cloud_slugs - local_slugs
        if slugs_to_create_locally:
            logger.info(
                "_sync_dynamic_tables_definitions: 触发本地建表, slugs=%s",
                slugs_to_create_locally,
            )
            self._create_local_dynamic_tables(slugs_to_create_locally, cloud_types)

        # 3b. 本地有云端没有 → 调用云端 rebuild（全量发送，端点幂等）
        slugs_to_create_remotely = local_slugs - cloud_slugs
        if slugs_to_create_remotely:
            logger.info(
                "_sync_dynamic_tables_definitions: 触发云端建表, slugs=%s",
                slugs_to_create_remotely,
            )
            self._rebuild_remote_dynamic_tables(remote_url, api_key)

        # 4. 返回动态表名列表（云端 slug ∪ 本地 slug → custom_<slug>）
        all_slugs = cloud_slugs | local_slugs
        return [f"custom_{slug}" for slug in all_slugs]

    def _create_local_dynamic_tables(
        self,
        slugs: set[str],
        cloud_types: list[dict[str, Any]],
    ) -> None:
        """本地建表（只执行 DDL，不写 meta 数据）

        将 slug→fields 映射委托给 SyncRepository.create_local_data_tables，
        只创建 custom_<slug> 数据表，不写入 custom_record_types / custom_record_fields。
        meta 数据由后续 pull 统一同步（LWW 逻辑只在一处）。

        Args:
            slugs: 需要本地新建的 slug 集合
            cloud_types: 云端动态表定义列表（含 slug 和 fields）

        Raises:
            DataAccessError: 数据库操作失败
        """
        slug_to_fields = {
            slug: next(
                (t.get("fields", []) for t in cloud_types if t["slug"] == slug),
                [],
            )
            for slug in slugs
        }
        self.sync_repository.create_local_data_tables(slug_to_fields)
        logger.info(
            "_create_local_dynamic_tables: 本地建表完成, slugs=%s",
            slugs,
        )

    def _rebuild_remote_dynamic_tables(self, remote_url: str, api_key: str) -> None:
        """发送本地自定义记录类型定义给云端，触发云端重建动态表

        在 pull 之前，由 _sync_dynamic_tables_definitions 检测到本地有云端没有的 slug 时调用。
        将本地最新的 type + fields 完整定义 POST 到云端 /api/sync/rebuild-dynamic-tables，
        云端根据定义 CREATE TABLE / ALTER TABLE ADD COLUMN / DROP TABLE。
        因为端点幂等（已有表走 skipped），所以全量发送。

        失败则抛异常，不继续后续 pull/push（避免动态表数据写入失败）。

        Args:
            remote_url: 远程服务器 URL
            api_key: API Key

        Raises:
            httpx.HTTPStatusError / httpx.RequestError: HTTP 请求失败
        """
        types = self.sync_repository.get_custom_record_types_full_definitions()
        logger.info(
            "发送动态表重建请求到云端: %d 个类型定义",
            len(types),
        )

        try:
            response = httpx.post(
                url=f"{remote_url}/api/sync/rebuild-dynamic-tables",
                json={"types": types},
                headers={
                    "Authorization": f"Bearer {api_key}",
                },
                timeout=60.0,
            )
            response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error(
                "_rebuild_remote_dynamic_tables: 重建动态表失败, remote_url=%s, error=%s",
                remote_url,
                e,
            )
            raise

        result = response.json()
        rebuilt = result.get("rebuilt", [])
        logger.info(
            "云端动态表重建完成: %s",
            rebuilt,
        )

    def pull_from_remote(self, remote_url, api_key, last_sync_time, tables):
        """拉取云端数据（分批拉取），应用 Last-Write-Wins 冲突解决

        对每张表分批拉取（每批 1000 条），逐批应用 LWW 冲突解决。

        对每条远程记录：
        - 本地不存在 -> 直接写入
        - 本地未修改（updated_at <= last_sync_time）-> 远程覆盖
        - 本地已修改 -> 比较 updated_at，谁更晚谁保留

        Args:
            remote_url: 远程服务器 URL
            api_key: API Key
            last_sync_time: 上次同步时间（ISO 8601 字符串）
            tables: 同步表列表
        """
        batch_size = 1000
        grand_total_rows = 0
        tables_with_data = 0

        for table_name in tables:
            logger.debug("开始拉取表: %s", table_name)
            offset = 0
            total_rows = 0

            pk_field = self.sync_repository.get_primary_key_field(table_name)
            if pk_field is None:
                logger.warning("pull_from_remote: 表 %s 无主键定义，跳过", table_name)
                continue

            while True:
                try:
                    response = httpx.post(
                        url=f"{remote_url}/api/sync/pull",
                        json={
                            "last_sync_time": last_sync_time,
                            "tables": [table_name],
                            "offset": offset,
                            "limit": batch_size,
                        },
                        headers={
                            "Authorization": f"Bearer {api_key}",
                        },
                        timeout=60.0,
                    )
                    response.raise_for_status()
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    logger.error(
                        "pull_from_remote: 拉取表 %s 失败, offset=%d, remote_url=%s, error=%s",
                        table_name,
                        offset,
                        remote_url,
                        e,
                    )
                    raise
                data = response.json()

                rows = data.get("changes", {}).get(table_name, [])
                if not rows:
                    break

                # 应用 Last-Write-Wins 冲突解决
                #
                # 优化：使用 batch_get_existing_updated_at 单连接批量查询，
                # 替代逐条 get_row_by_pk（避免 N+1 查询）。
                #
                # 所有同步表都配置了 update_at: True，都有物理 updated_at 列，
                # 因此都走 LWW 比较分支。has_updated_at 主要用于防御性检查
                # （未来如果新增无 updated_at 的表，会走 else 分支直接全量 upsert）。
                if self.sync_repository.has_updated_at(table_name):
                    # 收集本批所有 pk 值
                    pk_values = [row.get(pk_field) for row in rows]

                    # 批量查询本地已存在记录的 updated_at（单连接，避免 N+1 查询）
                    existing_updated_at_map = self.sync_repository.batch_get_existing_updated_at(
                        table_name, pk_field, pk_values
                    )

                    # 在内存中做 Last-Write-Wins 过滤
                    rows_to_upsert = []
                    for remote_row in rows:
                        pk_value = remote_row.get(pk_field)
                        local_updated_at = existing_updated_at_map.get(pk_value)

                        if local_updated_at is None:
                            # 本地不存在 -> 直接写入
                            rows_to_upsert.append(remote_row)
                        elif str(local_updated_at) <= str(last_sync_time):
                            # 本地未修改（updated_at <= last_sync_time）-> 远程覆盖
                            rows_to_upsert.append(remote_row)
                        elif str(remote_row.get("updated_at", "")) > str(local_updated_at):
                            # 云端更晚 -> 覆盖本地
                            rows_to_upsert.append(remote_row)
                        elif str(remote_row.get("updated_at", "")) == str(local_updated_at):
                            # 时间相同 -> 跳过
                            pass
                        else:
                            # 本地更晚 -> 保留本地（稍后推送）
                            logger.debug(
                                "pull_from_remote: 表 %s 记录 %s 本地更新，保留本地",
                                table_name,
                                pk_value,
                            )
                else:
                    # 表无 updated_at 列，无法做 LWW 检查，直接写入所有记录
                    rows_to_upsert = rows

                if rows_to_upsert:
                    self.sync_repository.upsert_rows(table_name, rows_to_upsert)

                total_rows += len(rows)
                logger.debug(
                    "表 %s 分批拉取: offset=%d, 本批=%d, 累计=%d",
                    table_name,
                    offset,
                    len(rows),
                    total_rows,
                )

                if len(rows) < batch_size:
                    break  # 最后一批

                offset += batch_size

            logger.debug("表 %s 拉取完成, 总计 %d 条记录", table_name, total_rows)

            if total_rows > 0:
                tables_with_data += 1
                grand_total_rows += total_rows

        if grand_total_rows > 0:
            logger.info(
                "pull_from_remote: 全部拉取完成, 共 %d 张表有数据, 总计 %d 条记录",
                tables_with_data,
                grand_total_rows,
            )
        else:
            logger.info("pull_from_remote: 无需要拉取的内容")

    def push_to_remote(self, remote_url, api_key, tables):
        """推送本地增量数据到云端（逐表 + 分批）

        对每张表查询增量记录（updated_at > last_sync_time），
        按 batch_size=1000 切分后逐批 POST 推送，避免单请求 payload 过大导致云端 OOM。

        Args:
            remote_url: 远程服务器 URL
            api_key: API Key
            tables: 同步表列表
        """
        from lifeprism.config.settings_manager import get_setting

        last_sync_time = get_setting("sync.last_sync_time", "")
        batch_size = 1000  # 与 pull_from_remote 保持一致
        total_batches = 0
        total_rows_pushed = 0
        tables_pushed = 0

        for table_name in tables:
            # 跳过无 updated_at 列的表（无法增量查询）
            if not self.sync_repository.has_updated_at(table_name):
                logger.debug(
                    "push_to_remote: 表 %s 无 updated_at 列，跳过增量推送",
                    table_name,
                )
                continue

            rows = self.sync_repository.query_incremental(table_name, last_sync_time)
            if not rows:
                continue

            tables_pushed += 1
            total_rows_pushed += len(rows)

            # 内存切分，逐批推送
            for offset in range(0, len(rows), batch_size):
                chunk = rows[offset : offset + batch_size]
                try:
                    response = httpx.post(
                        url=f"{remote_url}/api/sync/push",
                        json={"changes": {table_name: chunk}},
                        headers={"Authorization": f"Bearer {api_key}"},
                        timeout=60.0,
                    )
                    response.raise_for_status()
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    logger.error(
                        "push_to_remote: 推送失败, table=%s, batch_offset=%d, "
                        "batch_size=%d, remote_url=%s, error=%s",
                        table_name,
                        offset,
                        len(chunk),
                        remote_url,
                        e,
                    )
                    raise

                total_batches += 1
                logger.debug(
                    "push_to_remote: 表 %s 批次推送成功, offset=%d, 行数=%d",
                    table_name,
                    offset,
                    len(chunk),
                )

            logger.debug(
                "push_to_remote: 表 %s 推送完成, 总行数=%d, 批次数=%d",
                table_name,
                len(rows),
                (len(rows) + batch_size - 1) // batch_size,
            )

        if total_batches > 0:
            logger.info(
                "push_to_remote: 全部推送完成, 共 %d 张表, 总行数=%d, 批次数=%d",
                tables_pushed,
                total_rows_pushed,
                total_batches,
            )
        else:
            logger.info("push_to_remote: 无需要推送的内容")

    # ==================== 文件同步全流程（Issue 33） ====================

    def _scan_sync_files(self, directories):
        """扫描同步目录下的所有文件，返回相对路径列表

        遍历 directories 中的路径，递归查找所有文件，
        排除 _EXCLUDED_FILENAMES 中的文件名（如 chat_history.json）。

        Args:
            directories: 文件同步目录列表（相对 lifeprism_data_path）

        Returns:
            list[str]: 文件相对路径列表（使用 / 分隔符）
        """
        from lifeprism.config.settings_manager import settings

        data_path = settings.lifeprism_data_path.resolve()

        files = []
        skipped_blacklist = []
        for dir_rel in directories:
            target = (data_path / dir_rel).resolve()

            if not target.exists():
                logger.debug("_scan_sync_files: 路径不存在，跳过 %s", dir_rel)
                continue

            if target.is_file():
                if target.name in _EXCLUDED_FILENAMES:
                    skipped_blacklist.append(str(target.relative_to(data_path)).replace("\\", "/"))
                    continue
                rel_path = str(target.relative_to(data_path)).replace("\\", "/")
                files.append(rel_path)
            elif target.is_dir():
                for file_path in target.rglob("*"):
                    if not file_path.is_file():
                        continue
                    if file_path.name in _EXCLUDED_FILENAMES:
                        skipped_blacklist.append(
                            str(file_path.relative_to(data_path)).replace("\\", "/")
                        )
                        continue
                    rel_path = str(file_path.relative_to(data_path)).replace("\\", "/")
                    files.append(rel_path)

        if skipped_blacklist:
            logger.info(
                "_scan_sync_files: 黑名单过滤生效，跳过 %d 个文件: %s",
                len(skipped_blacklist),
                skipped_blacklist,
            )
        logger.info("_scan_sync_files: 扫描到 %d 个待同步文件", len(files))
        return files

    def _refresh_current_hashes(self, directories):
        """同步前全量扫描：刷新 file_sync_state 中所有文件的 current_hash

        遍历 directories 下所有文件（排除 chat_history.json），
        实时计算 current_hash 并批量更新 file_sync_state 表。
        新文件 parent_hash = NULL；已存在记录保持 parent_hash 不变。

        参考 ADR v2.1 决策 1：hash 更新逻辑 - 同步前刷新 current_hash。

        Args:
            directories: 文件同步目录列表（相对 lifeprism_data_path）

        Returns:
            list[str]: 扫描到的文件相对路径列表（供调用方复用，避免重复扫描）
        """
        from lifeprism.config.settings_manager import settings
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        data_path = settings.lifeprism_data_path.resolve()
        provider = FileSyncStateProvider(db_manager=self.db)

        rel_paths = self._scan_sync_files(directories)

        # 批量获取现有状态（单次 DB 查询，避免逐文件往返）
        existing_states = provider.batch_get_states(rel_paths)

        # 逐文件计算 hash（CPU 密集，无法批量）
        to_upsert = []
        for rel_path in rel_paths:
            file_path = (data_path / rel_path).resolve()
            content_bytes = file_path.read_bytes()
            new_hash = compute_file_hash(content_bytes)

            existing = existing_states.get(rel_path)
            parent_hash = existing["parent_hash"] if existing else None

            to_upsert.append(
                {
                    "file_path": rel_path,
                    "parent_hash": parent_hash,
                    "current_hash": new_hash,
                }
            )

        # 批量 upsert（单次事务）
        if to_upsert:
            provider.batch_upsert_states(to_upsert)

        logger.debug("_refresh_current_hashes: 刷新 %d 个文件的 current_hash", len(rel_paths))
        return rel_paths

    def _pull_files_check(self, remote_url, api_key, last_sync_time, directories):
        """Phase 1: 快照交换 - 调用 POST /pull-files/check 获取云端文件 hash 状态 + 完整路径清单

        云端按 mtime 过滤变更文件，返回 {path, parent_hash, current_hash} 列表（files），
        同时返回所有非黑名单文件的相对路径列表（all_paths）用于存在性判断。

        all_paths 让本地能区分"云端有但未变更"和"云端不存在"两种情况，
        避免云端缺失文件被错误 SKIP。

        Args:
            remote_url: 远程服务器 URL
            api_key: API Key
            last_sync_time: 上次同步时间（ISO 8601 字符串，空字符串表示首次同步）
            directories: 文件同步目录列表

        Returns:
            tuple[list[dict], list[str]]: (变更文件 hash 状态列表, 云端所有文件相对路径列表)
        """
        try:
            response = httpx.post(
                url=f"{remote_url}/api/sync/pull-files/check",
                json={
                    "last_sync_time": last_sync_time,
                    "directories": directories,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                },
                timeout=60.0,
            )
            response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error(
                "_pull_files_check: 调用 check 失败, remote_url=%s, error=%s",
                remote_url,
                e,
            )
            raise

        data = response.json()
        files = data.get("files", [])
        all_paths = data.get("all_paths", [])
        logger.debug(
            "_pull_files_check: 云端返回 %d 个变更文件, %d 个总文件",
            len(files),
            len(all_paths),
        )
        return files, all_paths

    def _decide_sync_action(
        self,
        local_parent,
        local_current,
        remote_parent,
        remote_current,
    ):
        """Phase 2a: 按 11 态矩阵判定文件同步动作

        参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md v2.1 决策 1

        11 态矩阵:
        | # | L.P | L.C | R.P | R.C | Decision |
        | 1 | NULL | A1 | 不存在 | - | PUSH |
        | 2 | 不存在 | - | NULL | A2 | PULL |
        | 3 | NULL | A1 | NULL | A2 | CONFLICT |
        | 4 | NULL | A1 | A | A | PULL |
        | 5 | A | A | NULL | A2 | PUSH |
        | 6 | A | A | A | A | SKIP |
        | 7 | A | A1 | A | A | PUSH |
        | 8 | A | A | A | A1 | PULL |
        | 9 | A | A1 | A | A2 | CONFLICT |
        | 10 | A1 | A1 | A2 | A2 | CONFLICT |
        | 11 | A | A1 | A2 | A2 | CONFLICT |

        Args:
            local_parent: 本地 parent_hash（None = 从未同步或文件不存在）
            local_current: 本地 current_hash（None = 文件不存在本地）
            remote_parent: 云端 parent_hash（None = 从未同步或文件不存在）
            remote_current: 云端 current_hash（None = 文件不存在云端）

        Returns:
            str: "PULL" / "PUSH" / "CONFLICT" / "SKIP"
        """
        # 文件不存在的一侧：current_hash 为 None
        # Row 2: 本地不存在 → PULL
        if local_current is None:
            return "PULL"

        # Row 1: 云端不存在 → PUSH
        if remote_current is None:
            return "PUSH"

        # 双方都存在：先比较内容
        # 内容相同 → SKIP（覆盖 Row 3/9 的同内容边界场景）
        if local_current == remote_current:
            return "SKIP"

        # 内容不同，检查 parent 状态
        local_has_parent = local_parent is not None
        remote_has_parent = remote_parent is not None

        # Row 3: 双方都从未同步（parent 均为 None），内容不同 → CONFLICT
        if not local_has_parent and not remote_has_parent:
            return "CONFLICT"

        # Row 4: 本地从未同步（parent=None），云端有历史 → PULL
        if not local_has_parent and remote_has_parent:
            return "PULL"

        # Row 5: 本地有历史，云端从未同步（parent=None） → PUSH
        if local_has_parent and not remote_has_parent:
            return "PUSH"

        # 双方都有 parent，检查是否一致
        # Row 10/11: parent 不一致 → CONFLICT
        if local_parent != remote_parent:
            return "CONFLICT"

        # parent 一致，判断哪一方改了
        local_changed = local_current != local_parent
        remote_changed = remote_current != remote_parent

        # Row 7: 仅本地改 → PUSH
        if local_changed and not remote_changed:
            return "PUSH"

        # Row 8: 仅云端改 → PULL
        if not local_changed and remote_changed:
            return "PULL"

        # Row 9: 双方都改且内容不同 → CONFLICT
        if local_changed and remote_changed:
            return "CONFLICT"

        # Row 6: 双方都没改（理论上方内容已相同，已被前面的 SKIP 捕获）
        return "SKIP"

    def _pull_files_fetch(self, remote_url, api_key, paths):
        """Phase 2b: 拉取文件内容 → 写入本地 → 立即更新 current_hash

        调用 POST /pull-files/fetch 获取文件内容（gzip+base64），
        解码解压后写入本地文件，然后立即计算 current_hash 并更新 file_sync_state。

        hash 时效性：写入后实时计算 current_hash，不使用云端返回的 hash 值。

        Args:
            remote_url: 远程服务器 URL
            api_key: API Key
            paths: 需要拉取的文件相对路径列表
        """
        from lifeprism.config.settings_manager import settings
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        if not paths:
            return

        try:
            response = httpx.post(
                url=f"{remote_url}/api/sync/pull-files/fetch",
                json={"paths": paths},
                headers={
                    "Authorization": f"Bearer {api_key}",
                },
                timeout=60.0,
            )
            response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error(
                "_pull_files_fetch: 调用 fetch 失败, remote_url=%s, paths=%d, error=%s",
                remote_url,
                len(paths),
                e,
            )
            raise

        data = response.json()
        files = data.get("files", [])

        data_path = settings.lifeprism_data_path.resolve()
        provider = FileSyncStateProvider(db_manager=self.db)

        for file_item in files:
            rel_path = file_item["path"]
            # ===== 防御性黑名单检查 =====
            if Path(rel_path).name in _EXCLUDED_FILENAMES:
                logger.warning(
                    "_pull_files_fetch: ⚠️ 云端返回了黑名单文件，跳过: %s",
                    rel_path,
                )
                continue

            file_path = (data_path / rel_path).resolve()

            # 路径安全检查
            try:
                file_path.relative_to(data_path)
            except ValueError:
                logger.warning("_pull_files_fetch: 跳过不安全路径 %s", rel_path)
                continue

            # base64 解码 + gzip 解压（带大小限制）
            compressed = base64.b64decode(file_item["content"])
            content_bytes = safe_gzip_decompress(compressed)

            # 原子写入文件
            _safe_write_file(file_path, content_bytes)

            # 立即计算 current_hash（实时计算，不使用云端返回的值）
            new_hash = compute_file_hash(content_bytes)

            # 更新 file_sync_state：保持 parent_hash 不变，更新 current_hash
            existing = provider.get_state(rel_path)
            parent_hash = existing["parent_hash"] if existing else file_item.get("parent_hash")

            provider.upsert_state(
                file_path=rel_path,
                parent_hash=parent_hash,
                current_hash=new_hash,
            )

            logger.debug("_pull_files_fetch: 写入 %s, current_hash=%s", rel_path, new_hash)

        logger.info("_pull_files_fetch: 拉取并写入 %d 个文件", len(files))

    def _push_files(self, remote_url, api_key, paths):
        """Phase 2c: 推送本地文件（含 parent_hash + current_hash）到云端

        读取本地文件内容（gzip+base64 编码），附带 file_sync_state 中的
        parent_hash 和 current_hash，按 FILE_BATCH_SIZE 分批通过 POST /push-files 推送到云端，
        避免单请求 payload 过大导致云端 OOM。

        CONFLICT 文件不由此方法处理（由调用方在矩阵判定阶段跳过，仅记录日志）。

        Args:
            remote_url: 远程服务器 URL
            api_key: API Key
            paths: 需要推送的文件相对路径列表
        """
        from lifeprism.config.settings_manager import settings
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider

        if not paths:
            return

        data_path = settings.lifeprism_data_path.resolve()
        provider = FileSyncStateProvider(db_manager=self.db)

        files_payload = []
        skipped_blacklist_push = []
        for rel_path in paths:
            # ===== 防御性黑名单检查 =====
            if Path(rel_path).name in _EXCLUDED_FILENAMES:
                logger.warning(
                    "_push_files: ⚠️ 检测到黑名单文件进入 PUSH 路径，跳过: %s",
                    rel_path,
                )
                skipped_blacklist_push.append(rel_path)
                continue

            file_path = (data_path / rel_path).resolve()

            if not file_path.is_file():
                logger.warning("_push_files: 文件不存在，跳过 %s", rel_path)
                continue

            # 读取并编码文件内容
            content_bytes = file_path.read_bytes()
            compressed = gzip.compress(content_bytes)
            encoded = base64.b64encode(compressed).decode("ascii")

            # 从 file_sync_state 获取 hash
            state = provider.get_state(rel_path)
            parent_hash = state["parent_hash"] if state else None
            current_hash = state["current_hash"] if state else None

            files_payload.append(
                {
                    "path": rel_path,
                    "content": encoded,
                    "parent_hash": parent_hash,
                    "current_hash": current_hash,
                }
            )

        if not files_payload:
            logger.debug("_push_files: 无文件需要推送")
            return

        # 按 FILE_BATCH_SIZE 分批推送，避免单请求 payload 过大导致云端 OOM
        total_batches = 0
        for offset in range(0, len(files_payload), FILE_BATCH_SIZE):
            chunk = files_payload[offset : offset + FILE_BATCH_SIZE]
            try:
                response = httpx.post(
                    url=f"{remote_url}/api/sync/push-files",
                    json={"files": chunk},
                    headers={
                        "Authorization": f"Bearer {api_key}",
                    },
                    timeout=60.0,
                )
                response.raise_for_status()
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                logger.error(
                    "_push_files: 推送失败, batch_offset=%d, batch_size=%d, "
                    "total_files=%d, remote_url=%s, error=%s",
                    offset,
                    len(chunk),
                    len(files_payload),
                    remote_url,
                    e,
                )
                raise

            total_batches += 1
            logger.debug(
                "_push_files: 批次推送成功, offset=%d, 文件数=%d",
                offset,
                len(chunk),
            )

        logger.info(
            "_push_files: 推送 %d 个文件, 批次数=%d",
            len(files_payload),
            total_batches,
        )

    def _verify_and_advance_parent(self, remote_url, api_key, paths):
        """Phase 3: 一致性校验 + parent_hash 推进

        1. 调用 POST /pull-files/verify 获取云端实时 current_hash
        2. 比较本地 current_hash（file_sync_state）与云端 current_hash
        3. 一致的文件：调用 POST /pull-files/commit 推进云端 parent_hash
        4. 一致的文件：本地 parent_hash = current_hash
        5. 不一致的文件：不推进 parent_hash，下次同步重试

        Args:
            remote_url: 远程服务器 URL
            api_key: API Key
            paths: 需要校验的文件相对路径列表
        """
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider

        if not paths:
            return

        provider = FileSyncStateProvider(db_manager=self.db)

        # Step 1: 调用 verify 获取云端实时 hash
        try:
            response = httpx.post(
                url=f"{remote_url}/api/sync/pull-files/verify",
                json={"paths": paths},
                headers={
                    "Authorization": f"Bearer {api_key}",
                },
                timeout=60.0,
            )
            response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error(
                "_verify_and_advance_parent: verify 失败, remote_url=%s, error=%s",
                remote_url,
                e,
            )
            raise

        cloud_files = response.json().get("files", [])
        cloud_hash_map = {f["path"]: f["current_hash"] for f in cloud_files}

        # Step 2: 比较本地与云端 hash，收集一致的路径
        consistent_paths = []
        for rel_path in paths:
            local_state = provider.get_state(rel_path)
            if local_state is None:
                logger.warning(
                    "_verify_and_advance_parent: 本地无 file_sync_state 记录 %s",
                    rel_path,
                )
                continue

            local_current = local_state["current_hash"]
            cloud_current = cloud_hash_map.get(rel_path)

            if cloud_current is None:
                logger.warning(
                    "_verify_and_advance_parent: 云端 verify 未返回 %s",
                    rel_path,
                )
                continue

            if local_current == cloud_current:
                consistent_paths.append(rel_path)
            else:
                logger.warning(
                    "_verify_and_advance_parent: hash 不一致 %s, local=%s, cloud=%s",
                    rel_path,
                    local_current,
                    cloud_current,
                )

        if not consistent_paths:
            logger.debug("_verify_and_advance_parent: 无一致文件，跳过 commit")
            return

        # Step 3: 调用 commit 推进云端 parent_hash
        try:
            commit_response = httpx.post(
                url=f"{remote_url}/api/sync/pull-files/commit",
                json={"paths": consistent_paths},
                headers={
                    "Authorization": f"Bearer {api_key}",
                },
                timeout=60.0,
            )
            commit_response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error(
                "_verify_and_advance_parent: commit 失败, remote_url=%s, error=%s",
                remote_url,
                e,
            )
            raise

        # Step 4: 推进本地 parent_hash = current_hash
        for rel_path in consistent_paths:
            local_state = provider.get_state(rel_path)
            if local_state:
                provider.upsert_state(
                    file_path=rel_path,
                    parent_hash=local_state["current_hash"],
                    current_hash=local_state["current_hash"],
                )

        logger.info(
            "_verify_and_advance_parent: 校验 %d 个文件, 一致 %d, 推进 parent_hash",
            len(paths),
            len(consistent_paths),
        )

    # ==================== CONFLICT_RESOLVE 冲突解决（Issue 34） ====================

    def _fetch_remote_file_content(self, remote_url, api_key, file_path):
        """获取远端文件内容（不写入本地）

        调用 POST /pull-files/fetch 获取文件内容（gzip+base64），
        解码解压后返回字符串内容，不写入本地文件。

        Args:
            remote_url: 远程服务器 URL
            api_key: API Key
            file_path: 文件相对路径

        Returns:
            str: 解码后的文件内容，获取失败返回 None
        """
        try:
            response = httpx.post(
                url=f"{remote_url}/api/sync/pull-files/fetch",
                json={"paths": [file_path]},
                headers={
                    "Authorization": f"Bearer {api_key}",
                },
                timeout=60.0,
            )
            response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error(
                "_fetch_remote_file_content: 获取远端文件失败 %s, error=%s",
                file_path,
                e,
            )
            return None

        data = response.json()
        files = data.get("files", [])
        if not files:
            logger.warning("_fetch_remote_file_content: 远端无文件内容 %s", file_path)
            return None

        file_item = files[0]
        compressed = base64.b64decode(file_item["content"])
        content_bytes = safe_gzip_decompress(compressed)
        return content_bytes.decode("utf-8")

    def _resolve_conflicts(self, conflict_paths, remote_url, api_key):
        """通过 AI 合并解决 CONFLICT 文件（串行处理）

        对每个 CONFLICT 文件（一次一个发送给 AI）：
        1. 读取本地文件内容
        2. 获取远端文件内容
        3. 构建 CONFLICT_RESOLVE 消息（Markdown 格式）
        4. 通过 run_coroutine_threadsafe 桥接 bus.send 到主线程事件循环
        5. 等待 AI 合并结果（timeout=600）
        6. 处理结果：备份本地版本 → 写入合并内容 → 更新 file_sync_state
        7. 失败/超时：保留本地版本，记录 ERROR 日志

        Args:
            conflict_paths: CONFLICT 文件相对路径列表
            remote_url: 远程服务器 URL
            api_key: API Key

        Returns:
            list[str]: 成功合并的文件路径列表（用于后续 Phase 2c 推送）
        """
        from lifeprism.config.settings_manager import settings
        from lifeprism.llm.bus.events import InboundMessage, MessageType, OutboundMessage
        from lifeprism.llm.bus.queue import bus
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider
        from lifeprism.sync.hash_utils import compute_file_hash

        if not conflict_paths:
            return []

        if self._main_event_loop is None:
            logger.error("_resolve_conflicts: main_event_loop 未设置，跳过冲突解决")
            return []

        data_path = settings.lifeprism_data_path.resolve()
        provider = FileSyncStateProvider(db_manager=self.db)

        resolved_paths = []
        for file_path in conflict_paths:
            try:
                start_time = datetime.now(timezone.utc)

                # 1. 读取本地文件内容
                local_file = (data_path / file_path).resolve()
                if not local_file.is_file():
                    logger.warning("_resolve_conflicts: 本地文件不存在 %s，跳过", file_path)
                    continue
                local_content = local_file.read_text(encoding="utf-8")

                # 2. 获取远端文件内容
                remote_content = self._fetch_remote_file_content(remote_url, api_key, file_path)
                if remote_content is None:
                    logger.error(
                        "_resolve_conflicts: 无法获取远端文件内容 %s，跳过",
                        file_path,
                    )
                    continue

                # 3. 构建 CONFLICT_RESOLVE 消息（Markdown 格式）
                msg = InboundMessage(
                    type=MessageType.CONFLICT_RESOLVE,
                    content=(
                        f"## 文件冲突需要解决\n\n"
                        f"文件路径: {file_path}\n\n"
                        f"### 本地版本\n\n{local_content}\n\n"
                        f"### 云端版本\n\n{remote_content}\n\n"
                        f"### 合并指令\n\n"
                        f"请合并以上两份文档，保留双方的有效信息，生成一份完整的合并文档。"
                    ),
                    extra={
                        "conflict_file_path": file_path,
                        "system_prompt": (
                            "你是文档合并助手。请合并两份 Markdown 文档，"
                            "保留双方的有效信息，移除重复内容，保持文档结构清晰。"
                            "直接输出合并后的文档内容，不要解释。"
                        ),
                    },
                )

                # 4. 通过 run_coroutine_threadsafe 桥接 bus.send 到主线程事件循环
                future = asyncio.run_coroutine_threadsafe(
                    bus.send(msg),
                    self._main_event_loop,
                )

                # 5. 等待 AI 合并结果（timeout=600）
                result: OutboundMessage = future.result(timeout=600)

                # 6. 提取合并后的内容
                merged_content = result.response.content if result.response else ""
                if not merged_content or not merged_content.strip():
                    logger.error(
                        "_resolve_conflicts: AI 返回空内容 %s，保留本地版本",
                        file_path,
                    )
                    continue

                # 6a. 计算合并后内容的 new_hash
                new_hash = compute_file_hash(merged_content.encode("utf-8"))

                # 6b. 冲突备份：将本地版本备份到 sync_conflict/{timestamp}/{file_path}
                timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                backup_path = (data_path / "sync_conflict" / timestamp_str / file_path).resolve()
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                backup_path.write_text(local_content, encoding="utf-8")

                # 6c. 原子写入合并后的内容到本地文件
                _safe_write_file(local_file, merged_content.encode("utf-8"))

                # 6d. 更新 file_sync_state: current_hash = new_hash
                existing = provider.get_state(file_path)
                parent_hash = existing["parent_hash"] if existing else None
                provider.upsert_state(
                    file_path=file_path,
                    parent_hash=parent_hash,
                    current_hash=new_hash,
                )

                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                logger.debug(
                    "_resolve_conflicts: 文件 %s AI 合并完成，耗时 %ss，new_hash=%s",
                    file_path,
                    duration,
                    new_hash,
                )
                resolved_paths.append(file_path)

            except TimeoutError:
                logger.error(
                    "_resolve_conflicts: AI 合并超时 %s，保留本地版本",
                    file_path,
                )
            except Exception as e:
                logger.error(
                    "_resolve_conflicts: AI 合并失败 %s，error=%s",
                    file_path,
                    e,
                    exc_info=True,
                )

        logger.info(
            "_resolve_conflicts: 冲突解决完成，成功 %d/%d",
            len(resolved_paths),
            len(conflict_paths),
        )
        return resolved_paths

    def _sync_files_full_flow(self, remote_url, api_key, last_sync_time, directories):
        """文件同步全流程（Phase 1-3）

        编排完整的文件同步流程：
        1. Pre-sync: 全量扫描刷新本地 current_hash
        2. Phase 1: 快照交换（POST /pull-files/check），获取云端变更文件 hash + 完整路径清单
        3. Phase 2a: 11 态矩阵判定（PULL/PUSH/CONFLICT/SKIP），使用 all_paths 区分云端缺失
        4. Phase 2b: PULL 文件（fetch → write → update current_hash）
        5. Phase 2c-1: CONFLICT → AI 合并解决（Issue 34，串行处理 + bus 桥接）
        6. Phase 2c-2: PUSH 文件（含合并成功的 CONFLICT 文件 + 云端缺失文件）
        7. Phase 3: verify + parent_hash 推进

        使用云端 all_paths（完整文件路径清单）区分两种情况：
        - 云端有文件但未变更（mtime <= last_sync_time）→ SKIP
        - 云端不存在此文件 → PUSH（修复 cloud-missing-files-not-synced bug）

        参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md v2.1

        Args:
            remote_url: 远程服务器 URL
            api_key: API Key
            last_sync_time: 上次同步时间（ISO 8601 字符串，空字符串表示首次同步）
            directories: 文件同步目录列表
        """
        from lifeprism.repository.providers.file_sync_state_provider import FileSyncStateProvider

        provider = FileSyncStateProvider(db_manager=self.db)

        # Pre-sync: 全量扫描刷新本地 current_hash（返回扫描结果供复用，避免重复扫描）
        local_rel_paths = self._refresh_current_hashes(directories)

        # Phase 1: 快照交换（变更文件 hash 状态 + 完整路径清单）
        remote_files, remote_all_paths = self._pull_files_check(
            remote_url, api_key, last_sync_time, directories
        )
        remote_state_map = {f["path"]: f for f in remote_files}
        remote_all_paths_set = set(remote_all_paths)

        # 复用 pre-sync 扫描结果（不重复扫描）
        local_paths_set = set(local_rel_paths)

        # 构建所有文件路径的并集
        all_paths = local_paths_set | set(remote_state_map.keys())

        # ===== 诊断日志：黑名单文件是否进入并集 =====
        blacklist_in_union = [p for p in all_paths if Path(p).name in _EXCLUDED_FILENAMES]
        if blacklist_in_union:
            logger.warning(
                "_sync_files_full_flow: ⚠️ 黑名单文件进入 all_paths 并集 (count=%d): %s",
                len(blacklist_in_union),
                blacklist_in_union,
            )
        else:
            logger.info(
                "_sync_files_full_flow: 黑名单检查通过，all_paths 并集中无黑名单文件 (count=%d)",
                len(all_paths),
            )

        # Phase 2a: 11 态矩阵判定
        pull_paths = []
        push_paths = []
        conflict_paths = []

        for path in all_paths:
            # 获取本地状态
            local_state = provider.get_state(path)
            local_parent = local_state["parent_hash"] if local_state else None
            local_current = local_state["current_hash"] if local_state else None

            # 文件不在本地扫描结果中 → 本地不存在
            if path not in local_paths_set:
                local_current = None

            # 获取远端状态
            remote_state = remote_state_map.get(path)
            remote_parent = remote_state["parent_hash"] if remote_state else None
            remote_current = remote_state["current_hash"] if remote_state else None

            # 文件不在 check 变更列表中 → 用 all_paths 判断是"云端有但未改"还是"云端不存在"
            if remote_state is None:
                if path in remote_all_paths_set:
                    # 云端有文件但未变更 → 用 last-synced 状态（local_parent）作为云端状态
                    # 主备模式下云端未改，云端 current == local_parent
                    remote_parent = local_parent
                    remote_current = local_parent
                else:
                    # 云端没有此文件 → PUSH（修复云端缺失文件被错误 SKIP 的 bug）
                    remote_parent = None
                    remote_current = None

            action = self._decide_sync_action(
                local_parent=local_parent,
                local_current=local_current,
                remote_parent=remote_parent,
                remote_current=remote_current,
            )

            if action == "PULL":
                pull_paths.append(path)
            elif action == "PUSH":
                push_paths.append(path)
            elif action == "CONFLICT":
                conflict_paths.append(path)
            # SKIP: 不操作

        logger.info(
            "_sync_files_full_flow: 矩阵判定完成 PULL=%d, PUSH=%d, CONFLICT=%d, SKIP=%d",
            len(pull_paths),
            len(push_paths),
            len(conflict_paths),
            len(all_paths) - len(pull_paths) - len(push_paths) - len(conflict_paths),
        )

        # Phase 2b: PULL 文件
        if pull_paths:
            self._pull_files_fetch(remote_url, api_key, pull_paths)

        # Phase 2c-1: CONFLICT 分流解决
        # JSONL 走文件级 LWW（直接保留本地版本 PUSH），非 JSONL 走 AI 合并
        # 参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md v2.2 决策 3
        resolved_paths = []
        if conflict_paths:
            # 按文件类型分流
            jsonl_conflicts = [p for p in conflict_paths if p.endswith(".jsonl")]
            non_jsonl_conflicts = [p for p in conflict_paths if not p.endswith(".jsonl")]

            # JSONL 走 LWW：直接保留本地版本，加入 push_paths 覆盖云端
            # 主备模式下（前提 1），发起同步的本地端通常是刚工作的活跃端
            if jsonl_conflicts:
                logger.info(
                    "_sync_files_full_flow: JSONL 冲突走 LWW（保留本地版本）: %d 个: %s",
                    len(jsonl_conflicts),
                    jsonl_conflicts,
                )
                push_paths.extend(jsonl_conflicts)

            # 非 JSONL 文件走 AI 合并（Issue 34）
            if non_jsonl_conflicts:
                logger.info(
                    "_sync_files_full_flow: 非 JSONL 冲突走 AI 合并: %d 个: %s",
                    len(non_jsonl_conflicts),
                    non_jsonl_conflicts,
                )
                resolved_paths = self._resolve_conflicts(
                    non_jsonl_conflicts,
                    remote_url,
                    api_key,
                )
                push_paths.extend(resolved_paths)
                logger.info(
                    "_sync_files_full_flow: 非 JSONL CONFLICT 解决完成，成功 %d/%d",
                    len(resolved_paths),
                    len(non_jsonl_conflicts),
                )
        if push_paths:
            self._push_files(remote_url, api_key, push_paths)

        # Phase 3: verify + parent_hash 推进（包含合并成功的文件）
        verify_paths = pull_paths + push_paths
        if verify_paths:
            self._verify_and_advance_parent(remote_url, api_key, verify_paths)
