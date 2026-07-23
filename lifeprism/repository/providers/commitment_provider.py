"""
CommitmentProvider - 承诺模块数据访问层

从 server/providers/commitment_provider.py 迁移而来，统一走 _generic_* CRUD 通道。

迁移要点：
- create_commitment 走 _generic_insert(data, id_prefix="cmt-")
- update_commitment 走 _generic_update（自动更新 updated_at 为 ISO 8601 + UTC，
  修复旧实现使用 datetime.now(timezone.utc).isoformat() 与 get_utc_now_iso() 不一致的问题）
- delete_commitment 走 _generic_delete（含写墓碑到 deletion_log）
- 异常处理抛出 DataAccessError（而非静默返回 None/False）

表特征：
- TEXT 主键表（id 格式：cmt-{uuid[:8]}）
- 在 SYNC_TABLES 中（删除时写墓碑，墓碑 record_id = 主键值）
- 不在 HASH_ID_PREFIXES 中（无 hash_id 字段）
- timestamps=True, update_at=True
- 有 LEFT JOIN user_values 查询（保留直接 SQL，不走 _generic_query）
"""

import sqlite3
from typing import Any

from lifeprism.repository.base_providers import LWBaseDataProvider
from lifeprism.utils import LazySingleton, get_logger
from lifeprism.utils.exceptions import DataAccessError

logger = get_logger(__name__)


class CommitmentProvider(LWBaseDataProvider):
    """承诺模块数据提供者

    职责：提供 commitments 表的 CRUD 操作，统一走 _generic_* 通道。
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "commitments"
    _PRIMARY_KEY = "id"
    _ON_CONFLICT = "abort"  # 不应有重复 ID，冲突时抛异常

    _FILTER_FIELDS: set[str] = {
        "id",
        "content",
        "value_id",
        "status",
        "created_at",
        "updated_at",
    }
    _ORDER_FIELDS: set[str] = {"status", "created_at", "updated_at"}
    _SELECT_FIELDS: set[str] = {
        "id",
        "content",
        "value_id",
        "status",
        "created_at",
        "updated_at",
    }
    # 允许更新的字段（不含 id 主键，不含 created_at/updated_at 系统字段）
    _UPDATE_FIELDS: set[str] = {"content", "value_id", "status"}

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    # ==================== 查询方法（直接 SQL，保持原 LEFT JOIN 行为）====================

    def get_commitments(
        self, status: str | None = None, value_id: str | None = None
    ) -> list[dict[str, Any]]:
        """获取承诺列表（LEFT JOIN user_values 获取 value_keywords）

        注：使用直接 SQL 而非 _generic_query，因为需要 LEFT JOIN user_values
        获取 value_keywords 字段，并保持原 status 排序 + created_at DESC 双字段排序。

        Args:
            status: 状态筛选，支持逗号分隔多值（如 "active,archived"）
            value_id: 按价值 ID 筛选

        Returns:
            承诺列表（无匹配返回空列表，这是正常行为不是错误）

        Raises:
            DataAccessError: 数据库操作失败（而非静默返回空列表）
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                conditions = []
                params = []

                if status:
                    status_list = [s.strip() for s in status.split(",")]
                    placeholders = ",".join(["?"] * len(status_list))
                    conditions.append(f"c.status IN ({placeholders})")
                    params.extend(status_list)

                if value_id:
                    conditions.append("c.value_id = ?")
                    params.append(value_id)

                where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
                sql = f"""
                    SELECT c.*, v.keywords AS value_keywords
                    FROM commitments c
                    LEFT JOIN user_values v ON c.value_id = v.id
                    {where}
                    ORDER BY
                        CASE c.status WHEN 'active' THEN 0 WHEN 'archived' THEN 1 WHEN 'completed' THEN 2 END,
                        c.created_at DESC
                """
                cursor.execute(sql, params)
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error("获取承诺列表失败: error=%s", e)
            raise DataAccessError(
                message="获取承诺列表失败",
                details={"error": str(e)},
                cause=e,
            ) from e

    def get_commitment_by_id(self, commitment_id: str) -> dict[str, Any] | None:
        """按 ID 获取承诺（LEFT JOIN user_values 获取 value_keywords）

        Args:
            commitment_id: 承诺 ID（格式：cmt-xxx）

        Returns:
            承诺记录；不存在返回 None（这是正常行为不是错误）

        Raises:
            DataAccessError: 数据库操作失败（而非静默返回 None）
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT c.*, v.keywords AS value_keywords
                    FROM commitments c
                    LEFT JOIN user_values v ON c.value_id = v.id
                    WHERE c.id = ?
                """,
                    (commitment_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row, strict=False))
        except sqlite3.Error as e:
            logger.error("获取承诺失败: commitment_id=%s, error=%s", commitment_id, e)
            raise DataAccessError(
                message="获取承诺失败",
                details={"commitment_id": commitment_id, "error": str(e)},
                cause=e,
            ) from e

    def get_commitments_by_value(self, value_id: str) -> list[dict[str, Any]]:
        """获取某价值下的所有承诺（不 JOIN，用于 ValueDetailItem）

        Args:
            value_id: 价值 ID

        Returns:
            承诺列表（无匹配返回空列表，这是正常行为不是错误）

        Raises:
            DataAccessError: 数据库操作失败（而非静默返回空列表）
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, content, status, created_at FROM commitments
                    WHERE value_id = ?
                    ORDER BY
                        CASE status WHEN 'active' THEN 0 WHEN 'archived' THEN 1 WHEN 'completed' THEN 2 END,
                        created_at DESC
                """,
                    (value_id,),
                )
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error("获取价值承诺列表失败: value_id=%s, error=%s", value_id, e)
            raise DataAccessError(
                message="获取价值承诺列表失败",
                details={"value_id": value_id, "error": str(e)},
                cause=e,
            ) from e

    # ==================== 核心方法（使用通用方法） ====================

    def create_commitment(self, data: dict[str, Any]) -> str:
        """创建承诺（走 _generic_insert 通道）

        _generic_insert 自动处理：
        - 生成 cmt- 前缀 ID（8 位 hex）
        - 写入 created_at/updated_at（ISO 8601 + UTC，commitments 配置了 timestamps=True）
        - 走 _ON_CONFLICT = "abort" 策略（重复 ID 抛异常）
        - status 未传时由 DB DEFAULT 'active' 兜底

        Args:
            data: 承诺数据，应包含 content, value_id 等字段

        Returns:
            新承诺 ID（格式：cmt-{8 位 hex}）

        Raises:
            DataAccessError: 数据库操作失败（如重复 ID、外键约束失败等）
        """
        commitment_id = self._generic_insert(data, id_prefix="cmt-")
        logger.info("创建承诺成功，ID: %s", commitment_id)
        return commitment_id

    def update_commitment(self, commitment_id: str, data: dict[str, Any]) -> bool:
        """更新承诺（走 _generic_update 通道）

        _generic_update 自动处理：
        - 更新 updated_at（ISO 8601 + UTC，commitments 配置 update_at=True）
        - 走 _UPDATE_FIELDS 白名单验证（无效字段抛 ValueError）
        - 空数据返回 True（无操作）

        Args:
            commitment_id: 承诺 ID（格式：cmt-xxx）
            data: 要更新的字段

        Returns:
            是否成功（记录不存在时返回 False）

        Raises:
            ValueError: 字段不在 _UPDATE_FIELDS 白名单中
            DataAccessError: 数据库操作失败
        """
        success = self._generic_update(commitment_id, data)
        if success:
            logger.info("更新承诺 %s 成功", commitment_id)
        return success

    def delete_commitment(self, commitment_id: str) -> bool:
        """删除承诺（走 _generic_delete 通道）

        _generic_delete 自动处理：
        - 删除 commitments 表中的记录
        - 写墓碑到 deletion_log（commitments 在 SYNC_TABLES 中）
        - 墓碑 record_id = 主键值（TEXT 主键表，不在 HASH_ID_PREFIXES 中）
        - 墓碑与 DELETE 在同一事务（DELETE 失败时墓碑回滚）

        Args:
            commitment_id: 承诺 ID（格式：cmt-xxx）

        Returns:
            是否成功（记录不存在时返回 False）

        Raises:
            DataAccessError: 数据库操作失败
        """
        success = self._generic_delete(commitment_id)
        if success:
            logger.info("删除承诺 %s 成功", commitment_id)
        return success

    # ==================== 级联方法（供 ValueProvider 删除价值时调用）====================

    def delete_by_value_id(self, value_id: str) -> int:
        """级联删除某价值下所有承诺（走 _generic_batch_delete 通道，含写墓碑）

        先查询该价值下所有承诺的 ID，再走 _generic_batch_delete 批量删除。
        _generic_batch_delete 自动处理：
        - 批量写墓碑到 deletion_log（commitments 在 SYNC_TABLES 中）
        - 批量 DELETE（墓碑与 DELETE 在同一事务）

        Args:
            value_id: 价值 ID

        Returns:
            成功删除的记录数（无匹配返回 0）

        Raises:
            DataAccessError: 数据库操作失败
        """
        # 查询该价值下所有承诺的 ID
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT {self._PRIMARY_KEY} FROM {self._TABLE_NAME} WHERE value_id = ?",
                    (value_id,),
                )
                commitment_ids = [row[0] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error("查询价值 %s 的承诺 ID 失败: error=%s", value_id, e)
            raise DataAccessError(
                message="查询价值承诺 ID 失败",
                details={"value_id": value_id, "error": str(e)},
                cause=e,
            ) from e

        if not commitment_ids:
            return 0

        deleted_count = self._generic_batch_delete(commitment_ids)
        logger.info("级联删除价值 %s 下 %s 条承诺", value_id, deleted_count)
        return deleted_count

    def null_value_id(self, value_id: str) -> int:
        """置空某价值下所有承诺的 value_id（供 ValueProvider 删除价值时"置空关联"使用）

        批量 UPDATE，同时更新 updated_at（ISO 8601 + UTC，因 commitments 配置 update_at=True）。
        与 delete_by_value_id 的区别：此方法只解除关联，不删除承诺记录，不写墓碑。

        Args:
            value_id: 价值 ID

        Returns:
            成功更新的记录数（无匹配返回 0）

        Raises:
            DataAccessError: 数据库操作失败
        """
        from lifeprism.utils.time_utils import get_utc_now_iso

        now_iso = get_utc_now_iso()
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"UPDATE {self._TABLE_NAME} SET value_id = NULL, updated_at = ? "
                    "WHERE value_id = ?",
                    (now_iso, value_id),
                )
                conn.commit()
                updated_count = cursor.rowcount
        except sqlite3.Error as e:
            logger.error("置空价值 %s 的承诺关联失败: error=%s", value_id, e)
            raise DataAccessError(
                message="置空价值承诺关联失败",
                details={"value_id": value_id, "error": str(e)},
                cause=e,
            ) from e

        logger.info("置空价值 %s 下 %s 条承诺的 value_id", value_id, updated_count)
        return updated_count

    def count_by_value(self, value_id: str) -> int:
        """统计某价值下承诺数（从 ValueProvider.count_commitments_by_value 迁移）

        供 ValueProvider 删除价值前询问用户"是否级联删除"时统计关联数。
        只统计 value_id 等于指定值的承诺，不统计 value_id 为 NULL 的承诺。

        Args:
            value_id: 价值 ID

        Returns:
            承诺数（无匹配返回 0）

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT COUNT(*) FROM {self._TABLE_NAME} WHERE value_id = ?",
                    (value_id,),
                )
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            logger.error("统计价值 %s 的承诺数失败: error=%s", value_id, e)
            raise DataAccessError(
                message="统计价值承诺数失败",
                details={"value_id": value_id, "error": str(e)},
                cause=e,
            ) from e


# 创建全局单例
commitment_provider = LazySingleton(CommitmentProvider)
