"""
BeingProvider - 时间悖论测试数据访问层

从 server/providers/being_provider.py 迁移而来，统一走 _generic_* CRUD 通道。

迁移要点：
- create 走 _generic_insert（AUTOINCREMENT 表，自动生成 tp- 前缀 hash_id）
- update 走 _generic_update(hash_id, data)（按 hash_id 定位记录）
- delete 走 _generic_delete(hash_id)（写墓碑，AUTOINCREMENT 表墓碑 record_id = hash_id）
- 复合键方法（*_by_user_mode_version）先查 hash_id 再调用 _generic_*
- upsert 改用"先查 hash_id 再 update/create"（self.db.upsert 在新 schema 下 INSERT
  路径缺 hash_id 且 UPDATE 路径会改变 hash_id，破坏同步语义）
- get_latest_version 保留原生 SQL（基类无 _generic_max）
- 单例改用 LazySingleton
- 异常处理抛出 DataAccessError（而非静默返回 None/False）

表特征：
- AUTOINCREMENT 表（id INTEGER PRIMARY KEY AUTOINCREMENT）
- _PRIMARY_KEY = "hash_id"（跨端稳定标识，非自增 id）
- 在 SYNC_TABLES 中（删除时写墓碑，墓碑 record_id = hash_id）
- 在 HASH_ID_PREFIXES 中（前缀 "tp-"，_generic_insert 自动生成 hash_id）
- timestamps=True, update_at=True
- 复合唯一键：(user_id, mode, version)
"""

import contextlib
import json
import sqlite3
from typing import Any

from lifeprism.repository.base_providers import LWBaseDataProvider
from lifeprism.utils import LazySingleton, get_logger
from lifeprism.utils.exceptions import DataAccessError

logger = get_logger(__name__)


class BeingProvider(LWBaseDataProvider):
    """Being 模块数据提供者

    职责：提供 time_paradoxes 表的 CRUD 操作，统一走 _generic_* 通道。

    AUTOINCREMENT 表特殊性：
    - id 是自增主键，但 _PRIMARY_KEY 设为 "hash_id"（跨端稳定标识）
    - create 走 _generic_insert，自动生成 tp- 前缀的 hash_id
    - delete 走 _generic_delete，墓碑 record_id = hash_id（非自增 id）
    - 复合键方法（*_by_user_mode_version）先查 hash_id 再调用 _generic_*
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "time_paradoxes"
    _PRIMARY_KEY = "hash_id"  # AUTOINCREMENT 表用 hash_id 作为跨端稳定标识
    _ON_CONFLICT = "abort"  # 不应有重复 (user_id, mode, version)，冲突时抛异常

    _FILTER_FIELDS: set[str] = {"user_id", "mode", "version"}
    _ORDER_FIELDS: set[str] = {"version", "created_at", "updated_at"}
    _SELECT_FIELDS: set[str] = {
        "id",
        "hash_id",
        "user_id",
        "version",
        "mode",
        "content",
        "ai_abstract",
        "created_at",
        "updated_at",
    }
    # 允许更新的字段（不含 id/hash_id 主键，不含 created_at/updated_at 系统字段）
    _UPDATE_FIELDS: set[str] = {"content", "ai_abstract"}

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    # ==================== 查询操作 ====================

    def get_by_id(self, hash_id: str) -> dict[str, Any] | None:
        """按 hash_id 获取单条记录

        Args:
            hash_id: 记录的 hash_id（tp- 前缀，跨端稳定标识）

        Returns:
            记录数据，不存在返回 None（这是正常行为不是错误）

        Raises:
            DataAccessError: 数据库操作失败（而非静默返回 None）
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT * FROM {self._TABLE_NAME} WHERE {self._PRIMARY_KEY} = ?",
                    (hash_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                columns = [desc[0] for desc in cursor.description]
                result = dict(zip(columns, row, strict=False))
                return self._deserialize_content(result)
        except sqlite3.Error as e:
            logger.error("获取记录失败: hash_id=%s, error=%s", hash_id, e)
            raise DataAccessError(
                message="获取记录失败",
                details={"hash_id": hash_id, "error": str(e)},
                cause=e,
            ) from e

    def get_by_user_mode_version(
        self, user_id: int, mode: str, version: int
    ) -> dict[str, Any] | None:
        """按用户ID、模式、版本号获取记录（唯一组合）

        Args:
            user_id: 用户 ID
            mode: 模式 (past/present/future)
            version: 版本号

        Returns:
            记录数据，不存在返回 None（这是正常行为不是错误）

        Raises:
            DataAccessError: 数据库操作失败（而非静默返回 None）
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT * FROM {self._TABLE_NAME} "
                    "WHERE user_id = ? AND mode = ? AND version = ?",
                    (user_id, mode, version),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                columns = [desc[0] for desc in cursor.description]
                result = dict(zip(columns, row, strict=False))
                return self._deserialize_content(result)
        except sqlite3.Error as e:
            logger.error(
                "获取记录失败: user_id=%s, mode=%s, version=%s, error=%s",
                user_id,
                mode,
                version,
                e,
            )
            raise DataAccessError(
                message="获取记录失败",
                details={
                    "user_id": user_id,
                    "mode": mode,
                    "version": version,
                    "error": str(e),
                },
                cause=e,
            ) from e

    def get_all_by_user_mode(self, user_id: int, mode: str) -> list[dict[str, Any]]:
        """获取用户某模式下的所有版本记录

        Args:
            user_id: 用户 ID
            mode: 模式 (past/present/future)

        Returns:
            记录列表，按版本号降序排列（无匹配返回空列表，这是正常行为不是错误）

        Raises:
            DataAccessError: 数据库操作失败（而非静默返回空列表）
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT * FROM {self._TABLE_NAME} "
                    "WHERE user_id = ? AND mode = ? "
                    "ORDER BY version DESC",
                    (user_id, mode),
                )
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                results = [dict(zip(columns, row, strict=False)) for row in rows]
                return [self._deserialize_content(r) for r in results]
        except sqlite3.Error as e:
            logger.error("获取记录列表失败: user_id=%s, mode=%s, error=%s", user_id, mode, e)
            raise DataAccessError(
                message="获取记录列表失败",
                details={"user_id": user_id, "mode": mode, "error": str(e)},
                cause=e,
            ) from e

    def get_latest_version(self, user_id: int, mode: str) -> int:
        """获取用户某模式下的最新版本号

        保留原生 SQL（基类无 _generic_max）。

        Args:
            user_id: 用户 ID
            mode: 模式 (past/present/future)

        Returns:
            最新版本号，如果没有记录返回 0

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT MAX(version) FROM {self._TABLE_NAME} WHERE user_id = ? AND mode = ?",
                    (user_id, mode),
                )
                result = cursor.fetchone()
                return result[0] if result[0] is not None else 0
        except sqlite3.Error as e:
            logger.error("获取最新版本号失败: user_id=%s, mode=%s, error=%s", user_id, mode, e)
            raise DataAccessError(
                message="获取最新版本号失败",
                details={"user_id": user_id, "mode": mode, "error": str(e)},
                cause=e,
            ) from e

    def get_latest_record(self, user_id: int, mode: str) -> dict[str, Any] | None:
        """获取用户某模式下的最新版本记录

        Args:
            user_id: 用户 ID
            mode: 模式 (past/present/future)

        Returns:
            最新记录，不存在返回 None（这是正常行为不是错误）

        Raises:
            DataAccessError: 数据库操作失败（而非静默返回 None）
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT * FROM {self._TABLE_NAME} "
                    "WHERE user_id = ? AND mode = ? "
                    "ORDER BY version DESC LIMIT 1",
                    (user_id, mode),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                columns = [desc[0] for desc in cursor.description]
                result = dict(zip(columns, row, strict=False))
                return self._deserialize_content(result)
        except sqlite3.Error as e:
            logger.error("获取最新记录失败: user_id=%s, mode=%s, error=%s", user_id, mode, e)
            raise DataAccessError(
                message="获取最新记录失败",
                details={"user_id": user_id, "mode": mode, "error": str(e)},
                cause=e,
            ) from e

    # ==================== 创建操作 ====================

    def create(self, data: dict[str, Any]) -> str:
        """创建新记录（走 _generic_insert 通道）

        _generic_insert 对 AUTOINCREMENT 表（在 HASH_ID_PREFIXES 中）自动处理：
        - 生成 tp- 前缀的 hash_id（12 位 hex，共 15 字符）
        - 写入 created_at/updated_at（ISO 8601 + UTC，time_paradoxes 配置
          timestamps=True 和 update_at=True）
        - 走 _ON_CONFLICT = "abort" 策略（UNIQUE(user_id,mode,version) 冲突时抛异常）

        Args:
            data: 记录数据，应包含 user_id, mode, version, content

        Returns:
            新记录的 hash_id（跨端稳定标识，格式：tp-{12 位 hex}）

        Raises:
            DataAccessError: 数据库操作失败（如 UNIQUE 冲突、NOT NULL 约束失败等）
        """
        # 序列化 content 字段（dict → JSON 字符串）
        insert_data = self._serialize_content(data)
        # _generic_insert 自动生成 hash_id（HASH_ID_PREFIXES["time_paradoxes"] = "tp-"）
        # 并自动写入 created_at/updated_at（time_paradoxes 配置 timestamps=True, update_at=True）
        self._generic_insert(insert_data)
        # _generic_insert 把生成的 hash_id 写入 insert_data 字典
        hash_id = insert_data["hash_id"]
        logger.info("创建 Being 记录成功，hash_id: %s", hash_id)
        return hash_id

    def create_new_version(
        self, user_id: int, mode: str, content: dict[str, Any], ai_abstract: str = None
    ) -> dict[str, Any] | None:
        """创建新版本（自动递增版本号）

        Args:
            user_id: 用户 ID
            mode: 模式 (past/present/future)
            content: 测试内容
            ai_abstract: AI 总结（可选）

        Returns:
            创建的记录，失败返回 None

        Raises:
            DataAccessError: 数据库操作失败
        """
        # 获取最新版本号并递增
        latest_version = self.get_latest_version(user_id, mode)
        new_version = latest_version + 1

        data = {
            "user_id": user_id,
            "mode": mode,
            "version": new_version,
            "content": content,
            "ai_abstract": ai_abstract,
        }

        hash_id = self.create(data)
        return self.get_by_id(hash_id)

    # ==================== 更新操作 ====================

    def update(self, hash_id: str, data: dict[str, Any]) -> bool:
        """更新记录（走 _generic_update 通道）

        _generic_update 自动处理：
        - 按 _PRIMARY_KEY = "hash_id" 定位记录
        - 更新 updated_at（ISO 8601 + UTC，time_paradoxes 配置 update_at=True）
        - 走 _UPDATE_FIELDS 白名单验证（无效字段抛 ValueError）
        - 空数据返回 True（无操作）

        Args:
            hash_id: 记录的 hash_id（tp- 前缀，跨端稳定标识）
            data: 要更新的字段

        Returns:
            是否成功（记录不存在时返回 False）

        Raises:
            ValueError: 字段不在 _UPDATE_FIELDS 白名单中
            DataAccessError: 数据库操作失败
        """
        update_data = self._serialize_content(data)
        success = self._generic_update(hash_id, update_data)
        if success:
            logger.info("更新 Being 记录成功，hash_id: %s", hash_id)
        return success

    def update_by_user_mode_version(
        self, user_id: int, mode: str, version: int, data: dict[str, Any]
    ) -> bool:
        """按用户ID、模式、版本号更新记录

        复合键方法：先查 hash_id 再调用 _generic_update。
        1. 按 (user_id, mode, version) 查询获取 hash_id
        2. 用 hash_id 调用 _generic_update（自动更新 updated_at）

        Args:
            user_id: 用户 ID
            mode: 模式 (past/present/future)
            version: 版本号
            data: 要更新的字段

        Returns:
            是否成功（记录不存在时返回 False）

        Raises:
            ValueError: 字段不在 _UPDATE_FIELDS 白名单中
            DataAccessError: 数据库操作失败
        """
        # 先查 hash_id（复合键 → 主键）
        record = self.get_by_user_mode_version(user_id, mode, version)
        if record is None:
            return False

        hash_id = record["hash_id"]
        return self.update(hash_id, data)

    def upsert(
        self,
        user_id: int,
        mode: str,
        version: int,
        content: dict[str, Any],
        ai_abstract: str = None,
    ) -> bool:
        """UPSERT 操作（存在则更新，不存在则插入）

        采用"先查 hash_id 再调用 _generic_*"方案（与其它复合键方法一致）：
        1. 按 (user_id, mode, version) 查询记录
        2. 存在 → 调用 update(hash_id, data)（走 _generic_update，保留原 hash_id）
        3. 不存在 → 调用 create(data)（走 _generic_insert，自动生成 tp- 前缀 hash_id）

        此方案替代 self.db.upsert，因为新 schema（hash_id NOT NULL UNIQUE）下
        self.db.upsert 的 INSERT 路径缺少 hash_id 会失败，且 UPDATE 路径会改变
        现有记录的 hash_id（破坏同步语义）。改用 _generic_* 通道保证 hash_id 不可变。

        已知限制（竞态条件）：
        此 read-then-write 方案非原子操作。在并发场景下，两个请求可能同时查到记录不存在，
        都执行 INSERT，导致 UNIQUE(user_id, mode, version) 约束冲突。
        实际影响低（单用户操作，同一 mode+version 并发概率极低），触发时抛出
        DataAccessError，不会数据损坏。如需原子操作，可改为 try/except 捕获
         sqlite3.IntegrityError 后重试 UPDATE。

        Args:
            user_id: 用户 ID
            mode: 模式 (past/present/future)
            version: 版本号
            content: 测试内容
            ai_abstract: AI 总结（可选）

        Returns:
            是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        data = {
            "user_id": user_id,
            "mode": mode,
            "version": version,
            "content": content,
            "ai_abstract": ai_abstract,
        }

        # 先查 hash_id（复合键 → 主键）
        existing = self.get_by_user_mode_version(user_id, mode, version)
        if existing is not None:
            # UPDATE 路径：走 _generic_update，保留原 hash_id
            # 仅传递可更新字段（content, ai_abstract），复合键字段不可变
            update_data = {k: v for k, v in data.items() if k in self._UPDATE_FIELDS}
            return self.update(existing["hash_id"], update_data)

        # INSERT 路径：走 _generic_insert，自动生成 tp- 前缀 hash_id
        self.create(data)
        logger.info(
            "UPSERT Being 记录成功（新建）: user_id=%s, mode=%s, version=%s",
            user_id,
            mode,
            version,
        )
        return True

    # ==================== 删除操作 ====================

    def delete(self, hash_id: str) -> bool:
        """删除记录（走 _generic_delete 通道）

        _generic_delete 对 SYNC_TABLES 中的 AUTOINCREMENT 表自动处理：
        - 删除 time_paradoxes 表中的记录
        - 写墓碑到 deletion_log（time_paradoxes 在 SYNC_TABLES 中）
        - 墓碑 record_id = hash_id（AUTOINCREMENT 表用 hash_id 而非自增 id）
        - 墓碑 source = "local"
        - 墓碑与 DELETE 在同一事务（DELETE 失败时墓碑回滚）

        Args:
            hash_id: 记录的 hash_id（tp- 前缀，跨端稳定标识）

        Returns:
            是否成功（记录不存在时返回 False）

        Raises:
            DataAccessError: 数据库操作失败
        """
        success = self._generic_delete(hash_id)
        if success:
            logger.info("删除 Being 记录成功，hash_id: %s", hash_id)
        return success

    def delete_by_user_mode_version(self, user_id: int, mode: str, version: int) -> bool:
        """按用户ID、模式、版本号删除记录

        复合键方法：先查 hash_id 再调用 _generic_delete。
        1. 按 (user_id, mode, version) 查询获取 hash_id
        2. 用 hash_id 调用 _generic_delete（自动写墓碑，record_id = hash_id）

        Args:
            user_id: 用户 ID
            mode: 模式 (past/present/future)
            version: 版本号

        Returns:
            是否成功（记录不存在时返回 False）

        Raises:
            DataAccessError: 数据库操作失败
        """
        # 先查 hash_id（复合键 → 主键）
        record = self.get_by_user_mode_version(user_id, mode, version)
        if record is None:
            return False

        hash_id = record["hash_id"]
        return self.delete(hash_id)

    # ==================== 辅助方法 ====================

    def _serialize_content(self, data: dict[str, Any]) -> dict[str, Any]:
        """序列化 content 字段为 JSON 字符串"""
        result = data.copy()
        if "content" in result and isinstance(result["content"], dict):
            result["content"] = json.dumps(result["content"], ensure_ascii=False)
        return result

    def _deserialize_content(self, data: dict[str, Any]) -> dict[str, Any]:
        """反序列化 content 字段为 Python 对象"""
        result = data.copy()
        if "content" in result and isinstance(result["content"], str):
            with contextlib.suppress(json.JSONDecodeError):
                result["content"] = json.loads(result["content"])
        return result


# 创建全局单例（改用 LazySingleton，延迟实例化）
being_provider = LazySingleton(BeingProvider)
