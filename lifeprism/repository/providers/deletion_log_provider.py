"""DeletionLogProvider - 墓碑表数据访问层

职责：为 deletion_log 表提供 CRUD + 增量查询 + source 过滤 + 清理能力。
墓碑不修改，created_at == updated_at，冲突处理用 INSERT OR IGNORE 存在性检查
（本地已有同 (target_table, record_id) 墓碑则跳过，不比较 updated_at）。

参考 ADR: docs/adr/2026-07-22-deletion-log-table.md
参考 ADR: docs/adr/2026-07-22-deletion-sync-tombstone.md 决策 3
参考 PRD: .scratch/deletion-sync-03-tombstone/prd.md
"""

import sqlite3
import uuid
from typing import Any

from lifeprism.repository.base_providers import LWBaseDataProvider
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import DataAccessError, ValidationError

logger = get_logger(__name__)


class DeletionLogProvider(LWBaseDataProvider):
    """墓碑表数据提供者（对应 deletion_log 表）

    元数据驱动通用 CRUD，领域方法支持增量查询、source 过滤、清理、同事务写入。

    source 字段约束：DB 层无 CHECK 约束，由本 Provider 在写入时校验
    source in ('local', 'cloud')，非法值抛 ValidationError。
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "deletion_log"
    _PRIMARY_KEY = "id"
    _DATE_FIELD = None
    _TIME_FIELD = None
    # 与 _write_tombstone 的 INSERT OR IGNORE 语义一致
    # 参考: .scratch/deletion-sync-03-tombstone/issues/01-deletion-log-provider.md（M2）
    _ON_CONFLICT = "ignore"
    _FILTER_FIELDS: set[str] = {"source", "target_table"}
    _ORDER_FIELDS: set[str] = {"created_at", "updated_at"}
    _SELECT_FIELDS: set[str] = {
        "id",
        "target_table",
        "record_id",
        "source",
        "created_at",
        "updated_at",
    }

    _VALID_SOURCES = frozenset({"local", "cloud"})

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    # ==================== 写入方法 ====================

    def create_tombstone(
        self,
        target_table: str,
        record_id: str,
        source: str,
        created_at: str | None = None,
    ) -> str | None:
        """写入墓碑

        id 用 dl- 前缀 + 8 位 hex（通过 _generic_insert(id_prefix='dl-')）。
        created_at 为 None 时用当前 UTC ISO 8601 时间；否则用传入值
        （用于 Pull/Push 写副本时保留原墓碑时间戳，保持两端一致）。
        created_at 传入时 updated_at 同步设为同一值
        （保持墓碑"不修改"语义）。

        冲突处理：_ON_CONFLICT='ignore'，UNIQUE(target_table, record_id) 冲突时
        保留旧墓碑（INSERT OR IGNORE 存在性检查），不刷新 updated_at。

        Args:
            target_table: 被删记录所在表名
            record_id: 被删记录的 hash_id（AUTOINCREMENT 表）或主键（TEXT PK 表）
            source: 来源标识（'local' 本地删除 / 'cloud' 云端传播副本）
            created_at: 显式传入的墓碑时间戳（ISO 8601 + UTC），None 则用当前时间

        Returns:
            新墓碑的 id，冲突时返回 None（INSERT OR IGNORE 语义）

        Raises:
            ValidationError: source 不是 local/cloud 之一
            DataAccessError: 数据库操作失败
        """
        if source not in self._VALID_SOURCES:
            raise ValidationError(
                message=f"source 必须是 local/cloud 之一，实际值: {source}",
                code="INVALID_SOURCE",
                details={"source": source, "valid_sources": sorted(self._VALID_SOURCES)},
            )

        from lifeprism.utils.time_utils import get_utc_now_iso

        timestamp = created_at if created_at is not None else get_utc_now_iso()
        return self._generic_insert(
            data={
                "target_table": target_table,
                "record_id": record_id,
                "source": source,
                # 显式传入 created_at 和 updated_at（保持 == ，墓碑不修改语义）
                # _generic_insert 检测到字段已在 data 中不会自动覆盖
                "created_at": timestamp,
                "updated_at": timestamp,
            },
            id_prefix="dl-",
        )

    def write_tombstone_with_cursor(
        self,
        cursor: sqlite3.Cursor,
        target_table: str,
        record_id: str,
        source: str = "local",
    ) -> None:
        """在同事务内写墓碑（供 Aggregator 调用保证事务边界）

        接受外部 cursor 参数，在同一事务内执行 INSERT OR IGNORE INTO deletion_log。
        供 Aggregator（如 CustomRecordAggregator.delete_entry）调用，确保墓碑写入
        与业务 DELETE 在同一事务内，失败则一起回滚。

        SQL 封装在此方法中（INSERT OR IGNORE INTO deletion_log），符合 Repository Pattern
        （SQL 不暴露到 Aggregator 层）。

        Args:
            cursor: 外部事务的数据库游标
            target_table: 被删记录所在表名
            record_id: 被删记录的 hash_id 或主键
            source: 来源标识（默认 'local'）

        Raises:
            ValidationError: source 不是 local/cloud 之一
        """
        if source not in self._VALID_SOURCES:
            raise ValidationError(
                message=f"source 必须是 local/cloud 之一，实际值: {source}",
                code="INVALID_SOURCE",
                details={"source": source, "valid_sources": sorted(self._VALID_SOURCES)},
            )

        from lifeprism.utils.time_utils import get_utc_now_iso

        tombstone_id = f"dl-{uuid.uuid4().hex[:8]}"
        now_iso = get_utc_now_iso()
        cursor.execute(
            "INSERT OR IGNORE INTO deletion_log "
            "(id, target_table, record_id, source, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (tombstone_id, target_table, record_id, source, now_iso, now_iso),
        )

    # ==================== 查询方法 ====================

    def get_tombstone_with_cursor(
        self,
        cursor: sqlite3.Cursor,
        target_table: str,
        record_id: str,
    ) -> dict[str, Any] | None:
        """按 target_table + record_id 查询墓碑（cursor 版本，供事务内存在性检查）

        与 get_tombstone 功能相同，但接受外部 cursor 参数，在同一事务内执行查询。
        供 _pull_deletion_log 事务内存在性检查使用，确保查询与 DELETE/副本写入在同一事务。

        SQL 封装在此方法中（SELECT FROM deletion_log），符合 Repository Pattern。

        Args:
            cursor: 外部事务的数据库游标
            target_table: 被删记录所在表名
            record_id: 被删记录的 hash_id 或主键

        Returns:
            墓碑字典，不存在时返回 None
        """
        sql = (
            f"SELECT {', '.join(sorted(self._SELECT_FIELDS))} "
            f"FROM {self._TABLE_NAME} "
            f"WHERE target_table = ? AND record_id = ?"
        )
        cursor.execute(sql, (target_table, record_id))
        row = cursor.fetchone()
        if row is None:
            return None
        column_names = [desc[0] for desc in cursor.description]
        return dict(zip(column_names, row, strict=False))

    def create_tombstone_with_cursor(
        self,
        cursor: sqlite3.Cursor,
        target_table: str,
        record_id: str,
        source: str,
        created_at: str | None = None,
    ) -> None:
        """写入墓碑（cursor 版本，供事务内写副本）

        与 create_tombstone 功能相同，但接受外部 cursor 参数，在同一事务内执行写入。
        供 _pull_deletion_log 事务内写本地副本使用，确保 DELETE 与副本写入在同一事务。

        保留原 created_at（Pull/Push 写副本时保持两端一致）。
        updated_at = created_at（墓碑不修改语义）。
        冲突处理：INSERT OR IGNORE 存在性检查，UNIQUE 冲突时保留旧墓碑。

        SQL 封装在此方法中（INSERT OR IGNORE INTO deletion_log），符合 Repository Pattern。

        Args:
            cursor: 外部事务的数据库游标
            target_table: 被删记录所在表名
            record_id: 被删记录的 hash_id 或主键
            source: 来源标识（'local' 本地删除 / 'cloud' 云端传播副本）
            created_at: 显式传入的墓碑时间戳，None 则用当前时间

        Raises:
            ValidationError: source 不是 local/cloud 之一
        """
        if source not in self._VALID_SOURCES:
            raise ValidationError(
                message=f"source 必须是 local/cloud 之一，实际值: {source}",
                code="INVALID_SOURCE",
                details={"source": source, "valid_sources": sorted(self._VALID_SOURCES)},
            )

        from lifeprism.utils.time_utils import get_utc_now_iso

        timestamp = created_at if created_at is not None else get_utc_now_iso()
        tombstone_id = f"dl-{uuid.uuid4().hex[:8]}"
        cursor.execute(
            "INSERT OR IGNORE INTO deletion_log "
            "(id, target_table, record_id, source, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (tombstone_id, target_table, record_id, source, timestamp, timestamp),
        )

    def get_tombstones_since(
        self,
        last_sync_time: str,
        source: str | None = None,
    ) -> list[dict[str, Any]]:
        """按 created_at > last_sync_time 增量查询墓碑，可选按 source 过滤

        Args:
            last_sync_time: 上次同步时间（ISO 8601 字符串，空字符串表示全量）
            source: 可选 source 过滤（'local' 或 'cloud'）

        Returns:
            墓碑记录列表，按 created_at 升序排列

        Raises:
            ValidationError: source 不是 local/cloud 之一
            DataAccessError: 数据库操作失败
        """
        if source is not None and source not in self._VALID_SOURCES:
            raise ValidationError(
                message=f"source 必须是 local/cloud 之一，实际值: {source}",
                code="INVALID_SOURCE",
                details={"source": source, "valid_sources": sorted(self._VALID_SOURCES)},
            )

        # 直接构建 SQL（_generic_query 不支持 > 比较）
        # 参数化查询 + 表名通过 _validate_table_name 校验，防 SQL 注入
        self._validate_table_name()

        if source is not None:
            sql = (
                f"SELECT {', '.join(sorted(self._SELECT_FIELDS))} "
                f"FROM {self._TABLE_NAME} "
                f"WHERE created_at > ? AND source = ? "
                f"ORDER BY created_at ASC"
            )
            params: tuple[Any, ...] = (last_sync_time, source)
        else:
            sql = (
                f"SELECT {', '.join(sorted(self._SELECT_FIELDS))} "
                f"FROM {self._TABLE_NAME} "
                f"WHERE created_at > ? "
                f"ORDER BY created_at ASC"
            )
            params = (last_sync_time,)

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                column_names = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
            results = [dict(zip(column_names, row, strict=False)) for row in rows]
            logger.debug(
                "增量查询墓碑: last_sync_time=%s, source=%s, 返回 %d 条",
                last_sync_time,
                source,
                len(results),
            )
            return results
        except sqlite3.Error as e:
            logger.error(
                "增量查询墓碑失败: last_sync_time=%s, source=%s, error=%s",
                last_sync_time,
                source,
                e,
            )
            raise DataAccessError(
                message="增量查询 deletion_log 失败",
                details={
                    "last_sync_time": last_sync_time,
                    "source": source,
                    "error": str(e),
                },
                cause=e,
            ) from e

    def get_tombstone(
        self,
        target_table: str,
        record_id: str,
    ) -> dict[str, Any] | None:
        """按 target_table + record_id 查询墓碑（用于存在性检查）

        UNIQUE(target_table, record_id) 约束保证至多返回一条记录。

        Args:
            target_table: 被删记录所在表名
            record_id: 被删记录的 hash_id 或主键

        Returns:
            墓碑字典，不存在时返回 None

        Raises:
            DataAccessError: 数据库操作失败
        """
        self._validate_table_name()

        sql = (
            f"SELECT {', '.join(sorted(self._SELECT_FIELDS))} "
            f"FROM {self._TABLE_NAME} "
            f"WHERE target_table = ? AND record_id = ?"
        )
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (target_table, record_id))
                row = cursor.fetchone()
                if row is None:
                    return None
                column_names = [desc[0] for desc in cursor.description]
            result = dict(zip(column_names, row, strict=False))
            logger.debug(
                "查询墓碑: target_table=%s, record_id=%s, 命中",
                target_table,
                record_id,
            )
            return result
        except sqlite3.Error as e:
            logger.error(
                "查询墓碑失败: target_table=%s, record_id=%s, error=%s",
                target_table,
                record_id,
                e,
            )
            raise DataAccessError(
                message="查询 deletion_log 墓碑失败",
                details={
                    "target_table": target_table,
                    "record_id": str(record_id),
                    "error": str(e),
                },
                cause=e,
            ) from e

    # ==================== 清理方法 ====================

    def cleanup_before(self, last_sync_time: str) -> int:
        """清理 created_at <= last_sync_time 的墓碑记录

        激进清理策略——本项目是严格两节点（本地↔云端），不存在多设备清理
        导致删除丢失的风险。同步成功后调用，用旧 last_sync_time（同步前的值）。

        清理是同步成功后的内部操作，不写墓碑（墓碑表自身清理不记录到 deletion_log）。

        在单个事务内执行 DELETE，失败则回滚。

        Args:
            last_sync_time: 同步前的时间戳，清理 created_at <= 此值的记录

        Returns:
            被清理的记录数

        Raises:
            DataAccessError: 数据库操作失败
        """
        self._validate_table_name()

        sql = f"DELETE FROM {self._TABLE_NAME} WHERE created_at <= ?"
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (last_sync_time,))
                affected = cursor.rowcount
                conn.commit()
            logger.info(
                "清理墓碑: last_sync_time<=%s, 清理 %d 条",
                last_sync_time,
                affected,
            )
            return affected
        except sqlite3.Error as e:
            logger.error(
                "清理墓碑失败: last_sync_time=%s, error=%s",
                last_sync_time,
                e,
            )
            raise DataAccessError(
                message="清理 deletion_log 失败",
                details={
                    "last_sync_time": last_sync_time,
                    "error": str(e),
                },
                cause=e,
            ) from e
