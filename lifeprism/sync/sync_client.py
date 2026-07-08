"""本地同步客户端 - 执行 Pull + Push 双向同步

职责：
- HTTP 通信（httpx）
- Last-Write-Wins 冲突解决
- 不直接执行 SQL，所有数据库操作通过 SyncRepository

参考: .scratch/linux-deployment-discussion/issues-p2/05-sync-client-basic.md
"""

import asyncio
import threading
from datetime import datetime

import httpx

from lifeprism.utils import get_logger

logger = get_logger(__name__)

# 同步范围：除 window_events 外的所有需要同步的表
SYNC_TABLES = [
    "mood_entries",
    "diary",
    "todo_list",
    "goal",
    "habits",
    "behavior_analysis",
    "category",
    "sub_category",
    "multi_purpose_map_cache",
    "single_purpose_map_cache",
    "user_app_behavior_log",
    "category_map_cache",
    "timeline_custom_block",
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
                start_time = datetime.now()
                # 使用 asyncio.to_thread 在独立线程中运行同步方法，避免阻塞事件循环
                await asyncio.to_thread(self.sync_once)
                duration = (datetime.now() - start_time).total_seconds()
                logger.info("定时同步完成，耗时 %ss", duration)
            except Exception as e:
                # 失败重试：记录 ERROR，不终止循环，下次定时触发自动重试
                logger.error("定时同步失败: %s", e)
            finally:
                self.finish_sync()

    def sync_once(self, tables=None):
        """执行一次完整同步（Pull -> Push）

        从配置读取 remote_url、api_key、last_sync_time，
        依次执行 pull 和 push，只有全部成功才更新 last_sync_time。

        Args:
            tables: 同步表列表，None 则使用默认 SYNC_TABLES
        """
        from lifeprism.config.settings_manager import get_setting, set_setting
        from lifeprism.sync.sync_config import get_sync_api_key

        remote_url = get_setting("sync.remote_url")
        api_key = get_sync_api_key()
        last_sync_time = get_setting("sync.last_sync_time", "")

        if tables is None:
            tables = SYNC_TABLES

        # Pull -> Push，任一步骤失败则不更新 last_sync_time
        self.pull_from_remote(remote_url, api_key, last_sync_time, tables)
        self.push_to_remote(remote_url, api_key, tables)

        # 只有全部成功才更新 last_sync_time（使用 ISO 8601 格式，与服务端保持一致）
        current_time = datetime.now().isoformat()
        set_setting("sync.last_sync_time", current_time)
        logger.info("sync_once: 同步完成，last_sync_time 已更新为 %s", current_time)

    def pull_from_remote(self, remote_url, api_key, last_sync_time, tables):
        """拉取云端数据，应用 Last-Write-Wins 冲突解决

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
        response = httpx.post(
            url=f"{remote_url}/api/sync/pull",
            json={
                "last_sync_time": last_sync_time,
                "tables": tables,
            },
            headers={
                "Authorization": f"Bearer {api_key}",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

        tables_data = data.get("changes", {})
        for table_name, rows in tables_data.items():
            pk_field = self.sync_repository.get_primary_key_field(table_name)
            if pk_field is None:
                logger.warning("pull_from_remote: 表 %s 无主键定义，跳过", table_name)
                continue

            rows_to_upsert = []
            for remote_row in rows:
                pk_value = remote_row.get(pk_field)
                local_row = self.sync_repository.get_row_by_pk(table_name, pk_field, pk_value)

                if local_row is None:
                    # 本地不存在 -> 直接写入
                    rows_to_upsert.append(remote_row)
                elif str(local_row.get("updated_at", "")) <= str(last_sync_time):
                    # 本地未修改 -> 直接覆盖
                    rows_to_upsert.append(remote_row)
                elif str(remote_row.get("updated_at", "")) > str(local_row.get("updated_at", "")):
                    # 云端更晚 -> 覆盖本地
                    rows_to_upsert.append(remote_row)
                else:
                    # 本地更晚 -> 保留本地（稍后推送）
                    logger.debug(
                        "pull_from_remote: 表 %s 记录 %s 本地更新，保留本地",
                        table_name,
                        pk_value,
                    )

            if rows_to_upsert:
                self.sync_repository.upsert_rows(table_name, rows_to_upsert)
                logger.info(
                    "pull_from_remote: 表 %s 写入 %d 条记录",
                    table_name,
                    len(rows_to_upsert),
                )

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
            rows = self.sync_repository.query_incremental(table_name, last_sync_time)
            if rows:
                tables_data[table_name] = rows

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

        logger.info("push_to_remote: 推送 %d 张表的数据", len(tables_data))
