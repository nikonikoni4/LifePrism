"""
ValueProvider - 价值模块数据访问层

从 server/providers/value_provider.py 迁移而来，统一走 _generic_* CRUD 通道。

迁移要点：
- create_value 走 _generic_insert(data, id_prefix="val-")（自动生成 val- 前缀 ID + ISO 时间戳）
- update_value 走 _generic_update（自动更新 updated_at 为 ISO 8601 + UTC，
  修复旧实现使用 datetime.now(timezone.utc).isoformat() 与 get_utc_now_iso() 不一致的问题）
- delete_value 走 _generic_delete（含写墓碑到 deletion_log，单表删除不含级联）
- 异常处理抛出 DataAccessError（而非静默返回 None/False）

级联删除重构：
- 原 delete_value_with_cascade 在 Provider 层直接调用 CommitmentProvider，违反 Repository 只做
  CRUD 的原则。新实现 delete_value 只做单表删除，级联协调上移到 value_service：
  - cascade=True：CommitmentProvider.delete_by_value_id + ValueProvider.delete_value
  - cascade=False：CommitmentProvider.null_value_id + ValueProvider.delete_value
- count_commitments_by_value 已迁移到 CommitmentProvider.count_by_value（Slice 03 完成）

表特征：
- TEXT 主键表（id 格式：val-{uuid[:8]}）
- 在 SYNC_TABLES 中（删除时写墓碑，墓碑 record_id = 主键值）
- 不在 HASH_ID_PREFIXES 中（无 hash_id 字段）
- timestamps=True, update_at=True
- keywords 字段有 UNIQUE 约束（重复时 sqlite3.IntegrityError，由 service 层转 ConflictError）
"""

import sqlite3
from typing import Any

from lifeprism.repository.base_providers import LWBaseDataProvider
from lifeprism.utils import LazySingleton, get_logger
from lifeprism.utils.exceptions import DataAccessError

logger = get_logger(__name__)


class ValueProvider(LWBaseDataProvider):
    """价值模块数据提供者

    职责：提供 user_values 表的 CRUD 操作，统一走 _generic_* 通道。

    级联协调不属于 Provider 层职责，已上移到 value_service：
    - cascade=True：service 调用 CommitmentProvider.delete_by_value_id + ValueProvider.delete_value
    - cascade=False：service 调用 CommitmentProvider.null_value_id + ValueProvider.delete_value
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "user_values"
    _PRIMARY_KEY = "id"
    _ON_CONFLICT = "abort"  # 不应有重复 ID，冲突时抛异常（防止默认 replace 覆盖已有记录）

    _FILTER_FIELDS: set[str] = {
        "id",
        "keywords",
        "sort_order",
        "created_at",
        "updated_at",
    }
    _ORDER_FIELDS: set[str] = {"sort_order", "created_at", "updated_at"}
    _SELECT_FIELDS: set[str] = {
        "id",
        "keywords",
        "content_positive",
        "content_negative",
        "sort_order",
        "created_at",
        "updated_at",
    }
    # 允许更新的字段（不含 id 主键，不含 created_at/updated_at 系统字段）
    _UPDATE_FIELDS: set[str] = {"keywords", "content_positive", "content_negative", "sort_order"}

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    # ==================== 查询方法（直接 SQL，保持原 ORDER BY 行为）====================

    def get_values(self) -> list[dict[str, Any]]:
        """获取所有价值（按 sort_order DESC, created_at DESC 排序）

        注：使用直接 SQL 而非 _generic_query，因为 _generic_query 仅支持单字段排序，
        而原实现需要 sort_order DESC, created_at DESC 双字段排序以保持行为等价。

        Returns:
            价值列表（无匹配返回空列表，这是正常行为不是错误）

        Raises:
            DataAccessError: 数据库操作失败（而非静默返回空列表）
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT * FROM {self._TABLE_NAME} ORDER BY sort_order DESC, created_at DESC"
                )
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error("获取价值列表失败: error=%s", e)
            raise DataAccessError(
                message="获取价值列表失败",
                details={"error": str(e)},
                cause=e,
            ) from e

    def get_value_by_id(self, value_id: str) -> dict[str, Any] | None:
        """按 ID 获取价值

        Args:
            value_id: 价值 ID（格式：val-xxx）

        Returns:
            价值记录；不存在返回 None（这是正常行为不是错误）

        Raises:
            DataAccessError: 数据库操作失败（而非静默返回 None）
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT * FROM {self._TABLE_NAME} WHERE {self._PRIMARY_KEY} = ?",
                    (value_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row, strict=False))
        except sqlite3.Error as e:
            logger.error("获取价值失败: value_id=%s, error=%s", value_id, e)
            raise DataAccessError(
                message="获取价值失败",
                details={"value_id": value_id, "error": str(e)},
                cause=e,
            ) from e

    # ==================== 核心方法（使用通用方法） ====================

    def create_value(self, data: dict[str, Any]) -> str:
        """创建价值（走 _generic_insert 通道）

        _generic_insert 自动处理：
        - 生成 val- 前缀 ID（8 位 hex）
        - 写入 created_at/updated_at（ISO 8601 + UTC，user_values 配置了 timestamps=True）
        - 走 _ON_CONFLICT = "abort" 策略（重复 ID 抛异常）
        - keywords UNIQUE 冲突时抛 sqlite3.IntegrityError（由 service 层转 ConflictError）

        Args:
            data: 价值数据，应包含 keywords 字段

        Returns:
            新价值 ID（格式：val-{8 位 hex}）

        Raises:
            sqlite3.IntegrityError: keywords UNIQUE 冲突（由 service 层捕获转 ConflictError）
            DataAccessError: 其他数据库操作失败
        """
        value_id = self._generic_insert(data, id_prefix="val-")
        logger.info("创建价值成功，ID: %s", value_id)
        return value_id

    def update_value(self, value_id: str, data: dict[str, Any]) -> bool:
        """更新价值（走 _generic_update 通道）

        _generic_update 自动处理：
        - 更新 updated_at（ISO 8601 + UTC，user_values 配置 update_at=True）
        - 走 _UPDATE_FIELDS 白名单验证（无效字段抛 ValueError）
        - 空数据返回 True（无操作）

        修复点：旧实现使用 datetime.now(timezone.utc).isoformat() 与新插入时的
        get_utc_now_iso() 不一致，新实现统一用 _generic_update，时间戳由 get_utc_now_iso() 生成。

        Args:
            value_id: 价值 ID（格式：val-xxx）
            data: 要更新的字段

        Returns:
            是否成功（记录不存在时返回 False）

        Raises:
            ValueError: 字段不在 _UPDATE_FIELDS 白名单中
            DataAccessError: 数据库操作失败
        """
        success = self._generic_update(value_id, data)
        if success:
            logger.info("更新价值 %s 成功", value_id)
        return success

    def delete_value(self, value_id: str) -> bool:
        """删除价值（走 _generic_delete 通道，单表删除，不含级联）

        _generic_delete 自动处理：
        - 删除 user_values 表中的记录
        - 写墓碑到 deletion_log（user_values 在 SYNC_TABLES 中）
        - 墓碑 record_id = 主键值（TEXT 主键表，不在 HASH_ID_PREFIXES 中）
        - 墓碑 source = "local"
        - 墓碑与 DELETE 在同一事务（DELETE 失败时墓碑回滚）

        重构点：原 delete_value_with_cascade 在 Provider 层直接调用 CommitmentProvider，
        违反 Repository 只做 CRUD 的原则。新实现 delete_value 只做单表删除，
        级联协调上移到 value_service。

        Args:
            value_id: 价值 ID（格式：val-xxx）

        Returns:
            是否成功（记录不存在时返回 False）

        Raises:
            DataAccessError: 数据库操作失败
        """
        success = self._generic_delete(value_id)
        if success:
            logger.info("删除价值 %s 成功", value_id)
        return success


# 创建全局单例
value_provider = LazySingleton(ValueProvider)
