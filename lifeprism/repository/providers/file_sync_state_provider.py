"""
FileSyncStateProvider - 文件同步状态数据访问层

职责：提供 file_sync_state 表的纯 CRUD 接口（get_state / get_all_states / upsert_state / delete_state）
不包含 hash 计算、11 状态矩阵判定、parent_hash 推进等同步业务逻辑。

参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md v2.1 决策 1（per-file version tracking）
"""

from typing import Any

from lifeprism.repository.base_providers import LWBaseDataProvider
from lifeprism.repository.providers.common_query_options import QueryOptions


class FileSyncStateProvider(LWBaseDataProvider):
    """
    文件同步状态数据提供者（对应 file_sync_state 表）

    职责：提供 file_sync_state 表的纯 CRUD 接口。
    不包含 hash 计算、矩阵判定等同步业务逻辑。
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "file_sync_state"
    _PRIMARY_KEY = "file_path"
    _DATE_FIELD = None
    _TIME_FIELD = None
    _ON_CONFLICT = "replace"  # file_path 冲突时替换（upsert 语义）

    # 白名单字段集合（用于防止 SQL 注入）
    _FILTER_FIELDS: set[str] = {"file_path", "parent_hash", "current_hash", "updated_at"}
    _ORDER_FIELDS: set[str] = {"file_path", "updated_at"}
    _SELECT_FIELDS: set[str] = {
        "file_path",
        "parent_hash",
        "current_hash",
        "updated_at",
    }
    _UPDATE_FIELDS: set[str] = {
        "parent_hash",
        "current_hash",
        "updated_at",
    }

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    # ==================== 纯 CRUD 方法 ====================

    def get_state(self, file_path: str) -> dict[str, Any] | None:
        """
        查询单条文件同步状态

        Args:
            file_path: 相对 lifeprism_data_path 的路径（如 user/user.md）

        Returns:
            包含 parent_hash + current_hash 的字典，不存在返回 None
        """
        options = QueryOptions(filters={"file_path": file_path})
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def get_all_states(self, directory: str) -> list[dict[str, Any]]:
        """
        查询指定目录下所有文件的同步状态

        使用 LIKE 前缀匹配，directory 参数会规范化为以 / 结尾，
        避免 "user" 误匹配 "user_backup/" 等同级目录。

        Args:
            directory: 目录路径（如 "user/" 或 "user"）

        Returns:
            文件状态字典列表，每项包含 file_path + parent_hash + current_hash + updated_at
        """
        # 规范化：确保目录以 / 结尾，避免 "user" 匹配 "user_backup/"
        if directory and not directory.endswith("/"):
            directory = directory + "/"
        pattern = directory + "%"

        sql = (
            f"SELECT file_path, parent_hash, current_hash, updated_at "
            f"FROM {self._TABLE_NAME} WHERE file_path LIKE ?"
        )
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (pattern,))
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
        return [dict(zip(columns, row, strict=False)) for row in rows]

    def batch_get_states(self, file_paths: list[str]) -> dict[str, dict[str, Any]]:
        """批量查询多个文件的同步状态

        单次 DB 查询获取所有指定文件的状态，避免逐文件 DB 往返。

        Args:
            file_paths: 文件相对路径列表

        Returns:
            {file_path: state_dict} 映射，不存在的文件不在结果中
        """
        if not file_paths:
            return {}
        placeholders = ",".join("?" * len(file_paths))
        sql = (
            f"SELECT file_path, parent_hash, current_hash, updated_at "
            f"FROM {self._TABLE_NAME} WHERE file_path IN ({placeholders})"
        )
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, file_paths)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
        return {row[0]: dict(zip(columns, row, strict=False)) for row in rows}

    def batch_upsert_states(self, states: list[dict[str, Any]]) -> None:
        """批量插入或更新文件同步状态

        在单次事务中执行所有 upsert，减少 DB 往返次数。

        Args:
            states: 状态字典列表，每项包含 file_path、parent_hash、current_hash
        """
        if not states:
            return
        from lifeprism.utils.time_utils import get_utc_now_iso

        now = get_utc_now_iso()
        sql = (
            f"INSERT OR REPLACE INTO {self._TABLE_NAME} "
            f"(file_path, parent_hash, current_hash, updated_at) "
            f"VALUES (?, ?, ?, ?)"
        )
        rows = [(s["file_path"], s["parent_hash"], s["current_hash"], now) for s in states]
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(sql, rows)
            conn.commit()

    def upsert_state(
        self,
        file_path: str,
        parent_hash: str | None,
        current_hash: str | None,
    ) -> bool:
        """
        插入或更新文件同步状态

        基于 file_path 主键执行 INSERT OR REPLACE。
        updated_at 由本方法自动设置为当前 UTC ISO 8601 时间戳。

        Args:
            file_path: 相对 lifeprism_data_path 的路径
            parent_hash: 上次同步成功时的 hash（NULL = 从未同步）
            current_hash: 当前文件内容的 hash

        Returns:
            是否成功
        """
        from lifeprism.utils.time_utils import get_utc_now_iso

        data = {
            "file_path": file_path,
            "parent_hash": parent_hash,
            "current_hash": current_hash,
            "updated_at": get_utc_now_iso(),
        }
        self._generic_insert(data, on_conflict="replace")
        return True

    def delete_state(self, file_path: str) -> bool:
        """
        删除文件同步状态记录

        Args:
            file_path: 相对 lifeprism_data_path 的路径

        Returns:
            是否成功（记录不存在时返回 False）
        """
        return self._generic_delete(file_path)
