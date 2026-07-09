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
import threading
from datetime import datetime, timezone

import httpx

from lifeprism.utils import get_logger

logger = get_logger(__name__)

# 同步范围：除 window_events 外的所有需要同步的静态表（30 张）
SYNC_TABLES = [
    # 用户输入数据（15张）
    "mood_entries",
    "diary",
    "todo_list",
    "goal",
    "goal_journal",
    "plan_doc",
    "daily_focus",
    "weekly_focus",
    "habits",
    "habit_challenges",
    "habit_checkins",
    "habit_chains",
    "habit_chain_nodes",
    "timeline_custom_block",
    "time_paradoxes",
    # 元数据（8张）
    "category",
    "sub_category",
    "mood_types",
    "mood_impacts",
    "user_values",
    "commitments",
    "custom_record_types",
    "custom_record_fields",
    # Monitor 数据（3张）
    "user_app_behavior_log",
    "behavior_analysis",
    "raw_behavior_analysis",
    # 缓存表（3张）
    "multi_purpose_map_cache",
    "single_purpose_map_cache",
    "category_map_cache",
    # 统计数据（1张）
    "tokens_usage_log",
]

# 文件同步白名单：相对 lifeprism_data_path 的路径
# 目录以 / 结尾，单文件为完整路径
SYNC_DIRECTORIES = [
    "agent/",
    "assets/",
    "channel/wechat/account.json",  # 单文件特殊处理
    "diary/",
    "docs/",
    "external_files/",
    "plan/",
    "prompts/",
    "session/",
    "user/",
    "workflow/",
]


class SyncClient:
    """本地同步客户端

    执行 Pull + Push 双向同步，应用 Last-Write-Wins 冲突解决策略。
    不直接执行 SQL，所有数据库操作通过 SyncRepository。

    Attributes:
        db: DatabaseManager 实例
        sync_repository: SyncRepository 实例
    """

    def __init__(self, db_manager, sync_repository):
        """初始化同步客户端

        Args:
            db_manager: DatabaseManager 实例
            sync_repository: SyncRepository 实例
        """
        self.db = db_manager
        self.sync_repository = sync_repository
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

        循环执行：等待 interval_seconds -> 调用 sync_once()。
        - 并发控制：通过 try_start_sync() 原子地检查并设置同步标志，
          若已在同步中则跳过本次并记录 WARNING
        - 失败重试：sync_once 抛异常时记录 ERROR，下次定时触发时自动重试
        - 使用 try...finally 确保 finish_sync() 在异常时也能被调用

        Args:
            interval_seconds: 同步间隔（秒）
        """
        while True:
            await asyncio.sleep(interval_seconds)
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

    def get_all_sync_tables(self) -> list[str]:
        """获取所有需要同步的表（包括动态表）

        以静态 SYNC_TABLES 白名单为基础，运行时查询 custom_record_types
        获取 slug 列表，追加 custom_{slug} 动态表。

        Returns:
            所有需要同步的表名列表（静态表 + 动态表）
        """
        tables = SYNC_TABLES.copy()
        slugs = self.sync_repository.get_custom_record_slugs()
        for slug in slugs:
            tables.append(f"custom_{slug}")
        logger.info(
            "同步表列表: 静态表=%d张, 动态表=%d张, 总计=%d张",
            len(SYNC_TABLES),
            len(tables) - len(SYNC_TABLES),
            len(tables),
        )
        return tables

    def sync_once(self, tables=None, directories=None):
        """执行一次完整同步（数据库 Pull -> Push + 文件 Pull -> Push）

        从配置读取 remote_url、api_key、last_sync_time，
        依次执行数据库同步和文件同步，只有全部成功才更新 last_sync_time。

        Args:
            tables: 同步表列表，None 则使用 get_all_sync_tables()（包含动态表）
            directories: 文件同步目录列表，None 则使用默认 SYNC_DIRECTORIES
        """
        from lifeprism.config.settings_manager import get_setting, set_setting
        from lifeprism.sync.sync_config import get_sync_api_key

        remote_url = get_setting("sync.remote_url")
        api_key = get_sync_api_key()
        last_sync_time = get_setting("sync.last_sync_time", "")

        if tables is None:
            tables = self.get_all_sync_tables()
        if directories is None:
            directories = SYNC_DIRECTORIES

        # 数据库同步：Pull -> Push，任一步骤失败则不更新 last_sync_time
        self.pull_from_remote(remote_url, api_key, last_sync_time, tables)
        self.push_to_remote(remote_url, api_key, tables)

        # 文件同步：Pull -> Push
        self.pull_files_from_remote(remote_url, api_key, last_sync_time, directories)
        self.push_files_to_remote(remote_url, api_key, last_sync_time, directories)

        # 只有全部成功才更新 last_sync_time（使用 ISO 8601 格式，与服务端保持一致）
        current_time = datetime.now(timezone.utc).isoformat()
        set_setting("sync.last_sync_time", current_time)
        logger.info("sync_once: 同步完成，last_sync_time 已更新为 %s", current_time)

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

        for table_name in tables:
            logger.info("开始拉取表: %s", table_name)
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
                # 兼容：部分表（mood_types / user_values / habit_checkins /
                # raw_behavior_analysis / custom_record_fields）无物理 updated_at
                # 列，无法做 LWW 比较。原实现中 get_row_by_pk 返回的行不含
                # updated_at 键，local_row.get("updated_at", "") 为 ""，
                # str("") <= str(last_sync_time) 恒为 True，即始终覆盖。
                # 此处对无 updated_at 列的表直接全量 upsert，保持等价。
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

            logger.info("表 %s 拉取完成, 总计 %d 条记录", table_name, total_rows)

    def push_to_remote(self, remote_url, api_key, tables):
        """推送本地增量数据到云端

        使用 query_incremental 获取本地变更（updated_at > last_sync_time），
        通过 HTTP POST 推送到远程。

        Args:
            remote_url: 远程服务器 URL
            api_key: API Key
            tables: 同步表列表
        """
        from lifeprism.config.settings_manager import get_setting

        last_sync_time = get_setting("sync.last_sync_time", "")

        tables_data = {}
        for table_name in tables:
            # 跳过无 updated_at 列的表（无法增量查询）
            if not self.sync_repository.has_updated_at(table_name):
                logger.debug(
                    "push_to_remote: 表 %s 无 updated_at 列，跳过增量推送",
                    table_name,
                )
                continue
            rows = self.sync_repository.query_incremental(table_name, last_sync_time)
            if rows:
                tables_data[table_name] = rows

        try:
            response = httpx.post(
                url=f"{remote_url}/api/sync/push",
                json={
                    "changes": tables_data,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                },
                timeout=60.0,
            )
            response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error(
                "push_to_remote: 推送失败, tables=%s, remote_url=%s, error=%s",
                list(tables_data.keys()),
                remote_url,
                e,
            )
            raise

        logger.info("push_to_remote: 推送 %d 张表的数据", len(tables_data))

    # ==================== 文件同步 ====================

    def pull_files_from_remote(self, remote_url, api_key, last_sync_time, directories):
        """从云端拉取增量文件并写入本地

        调用 POST /api/sync/pull-files 获取云端变更文件，
        对每个文件应用 LWW 冲突解决后写入本地。

        Args:
            remote_url: 远程服务器 URL
            api_key: API Key
            last_sync_time: 上次同步时间（ISO 8601 字符串）
            directories: 文件同步目录列表
        """
        try:
            response = httpx.post(
                url=f"{remote_url}/api/sync/pull-files",
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
                "pull_files_from_remote: 拉取文件失败, remote_url=%s, directories=%s, error=%s",
                remote_url,
                directories,
                e,
            )
            raise
        data = response.json()

        files = data.get("files", [])
        written = 0
        skipped = 0
        for file_item in files:
            if self._write_file(file_item):
                written += 1
            else:
                skipped += 1

        logger.info(
            "pull_files_from_remote: 拉取 %d 个文件, 写入 %d, 跳过 %d",
            len(files),
            written,
            skipped,
        )

    def push_files_to_remote(self, remote_url, api_key, last_sync_time, directories):
        """推送本地变更文件到云端

        收集本地变更文件（mtime > last_sync_time），
        通过 POST /api/sync/push-files 推送到远程。

        Args:
            remote_url: 远程服务器 URL
            api_key: API Key
            last_sync_time: 上次同步时间（ISO 8601 字符串）
            directories: 文件同步目录列表
        """
        files = self._collect_changed_files(last_sync_time, directories)

        try:
            response = httpx.post(
                url=f"{remote_url}/api/sync/push-files",
                json={
                    "files": files,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                },
                timeout=60.0,
            )
            response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error(
                "push_files_to_remote: 推送文件失败, remote_url=%s, files=%d, error=%s",
                remote_url,
                len(files),
                e,
            )
            raise

        logger.info("push_files_to_remote: 推送 %d 个文件", len(files))

    def _collect_changed_files(self, last_sync_time, directories):
        """收集本地变更文件（gzip 压缩 + base64 编码）

        遍历 directories 中的路径，找到 mtime > last_sync_time 的文件，
        读取内容并编码后返回。

        单文件路径（如 channel/wechat/account.json）直接检查；
        目录路径递归遍历（rglob）。

        Args:
            last_sync_time: 上次同步时间（ISO 8601 字符串）
            directories: 文件同步目录/文件列表（相对 lifeprism_data_path）

        Returns:
            list[dict]: 变更文件列表，每项包含 path、content、mtime
        """
        from lifeprism.config.settings_manager import settings

        data_path = settings.lifeprism_data_path.resolve()

        if last_sync_time:
            last_sync_dt = datetime.fromisoformat(last_sync_time)
        else:
            # 首次同步：同步所有文件
            last_sync_dt = datetime(1970, 1, 1, tzinfo=timezone.utc)

        files = []
        for dir_rel in directories:
            target = (data_path / dir_rel).resolve()

            if not target.exists():
                logger.debug("_collect_changed_files: 路径不存在，跳过 %s", dir_rel)
                continue

            if target.is_file():
                # 单文件特殊处理
                if self._should_sync_file(target, last_sync_dt):
                    files.append(self._encode_file(target, data_path))
            elif target.is_dir():
                # 目录递归遍历
                for file_path in target.rglob("*"):
                    if file_path.is_file() and self._should_sync_file(file_path, last_sync_dt):
                        files.append(self._encode_file(file_path, data_path))

        return files

    def _should_sync_file(self, file_path, last_sync_dt):
        """判断文件是否需要同步（mtime > last_sync_time）

        Args:
            file_path: 文件绝对路径
            last_sync_dt: 上次同步时间（datetime 对象）

        Returns:
            bool: 文件 mtime 大于 last_sync_time 时返回 True
        """
        file_mtime = file_path.stat().st_mtime
        return file_mtime > last_sync_dt.timestamp()

    def _encode_file(self, file_path, data_path):
        """编码文件（gzip 压缩 + base64 编码）

        Args:
            file_path: 文件绝对路径
            data_path: 数据根目录（用于计算相对路径）

        Returns:
            dict: 包含 path（相对路径）、content（编码内容）、mtime（ISO 8601）
        """
        content_bytes = file_path.read_bytes()
        compressed = gzip.compress(content_bytes)
        encoded = base64.b64encode(compressed).decode("ascii")
        rel_path = str(file_path.relative_to(data_path)).replace("\\", "/")
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc).isoformat()
        return {
            "path": rel_path,
            "content": encoded,
            "mtime": mtime,
        }

    def _write_file(self, file_item):
        """写入文件（LWW 冲突解决 + 解码解压 + 设置 mtime）

        对比本地文件 mtime 与远程 mtime：
        - 本地更新（mtime > remote）-> 跳过
        - 远程更新或本地不存在 -> 解码解压写入并设置 mtime

        Args:
            file_item: dict，包含 path、content、mtime

        Returns:
            bool: True 表示已写入，False 表示跳过（本地更新）
        """
        from lifeprism.config.settings_manager import settings

        data_path = settings.lifeprism_data_path.resolve()
        file_path = (data_path / file_item["path"]).resolve()

        # 路径安全检查：防止路径遍历攻击（与服务端 _is_path_safe 对称）
        try:
            file_path.relative_to(data_path)
        except ValueError:
            logger.warning("_write_file: 跳过不安全路径 %s", file_item["path"])
            return False

        remote_mtime_dt = datetime.fromisoformat(file_item["mtime"])
        remote_mtime_ts = remote_mtime_dt.timestamp()

        # LWW 冲突解决：本地文件更新时跳过
        if file_path.exists():
            local_mtime_ts = file_path.stat().st_mtime
            if local_mtime_ts > remote_mtime_ts:
                logger.debug(
                    "_write_file: 本地更新，跳过 %s",
                    file_item["path"],
                )
                return False

        # base64 解码 + gzip 解压
        compressed = base64.b64decode(file_item["content"])
        content_bytes = gzip.decompress(compressed)

        # 自动创建父目录
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # 写入文件
        file_path.write_bytes(content_bytes)

        # 设置 mtime
        os.utime(file_path, (remote_mtime_ts, remote_mtime_ts))

        return True
