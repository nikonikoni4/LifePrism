"""
同步数据仓库 - 封装同步相关的动态多表查询和写入

职责：
- query_incremental(): 增量查询某表 updated_at > last_sync_time 的记录
- upsert_rows(): 批量 INSERT OR REPLACE 写入行
- upsert_rows_with_lww(): 带 LWW 冲突解决的批量写入
- get_primary_key_field(): 从 TABLE_CONFIGS 解析主键字段名
- get_unique_fields(): 从 TABLE_CONFIGS 解析 UNIQUE 约束字段

编码规范：不得在非 repository 的任何位置直接编写 SQL
"""

import sqlite3
from typing import Any

from lifeprism.config.database import TABLE_CONFIGS
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import DataAccessError

logger = get_logger(__name__)


class SyncRepository:
    """同步数据仓库

    封装同步相关的动态多表查询和写入操作。
    不继承 LWBaseDataProvider，因为同步操作是跨表的动态操作，
    不绑定单一 _TABLE_NAME。

    SQLite 限制说明：
    - 使用 ? 作为参数占位符（SQLite 风格）
    - 使用 INSERT OR REPLACE 语义
    - 使用 cursor.rowcount 获取受影响行数

    安全说明：
    - 所有表名和列名通过 TABLE_CONFIGS 白名单校验，防止 SQL 注入
    - AUTOINCREMENT 表的 id 字段在写入时被剥离，防止 sqlite_sequence 污染
    """

    def __init__(self, db_manager=None):
        """初始化同步数据仓库

        Args:
            db_manager: DatabaseManager 实例，None 则使用全局单例
        """
        if db_manager is None:
            from lifeprism.repository import lw_db_manager

            self.db = lw_db_manager
        else:
            self.db = db_manager

    # ==================== 白名单校验 ====================

    def is_dynamic_table(self, table_name: str) -> bool:
        """判断表是否为动态自定义记录表（custom_{slug}）

        动态表由 CustomRecordRepository.create_type() 运行时创建，
        不在 TABLE_CONFIGS 中，但具有固定 schema：
        - id TEXT PRIMARY KEY
        - {field_key} TEXT（用户定义字段）
        - created_at TEXT
        - updated_at TEXT

        custom_record_types 和 custom_record_fields 是静态 meta 表，
        在 TABLE_CONFIGS 中，不会被识别为动态表。

        Args:
            table_name: 表名

        Returns:
            True 如果是动态自定义记录表
        """
        return table_name.startswith("custom_") and table_name not in TABLE_CONFIGS

    # 保留私有别名，向后兼容（内部调用）
    _is_dynamic_table = is_dynamic_table

    def _validate_table_name(self, table_name: str) -> None:
        """验证表名在 TABLE_CONFIGS 白名单中或为动态自定义记录表

        Args:
            table_name: 表名

        Raises:
            DataAccessError: 表名不在白名单中
        """
        if table_name in TABLE_CONFIGS:
            return
        if self._is_dynamic_table(table_name):
            return
        raise DataAccessError(
            message=f"无效的表名: {table_name}",
            details={"table": table_name},
        )

    def _validate_columns(self, table_name: str, columns: list[str]) -> None:
        """验证列名在 TABLE_CONFIGS 白名单中

        timestamps 自动添加的 created_at / updated_at 也视为有效列。
        动态自定义记录表（custom_{slug}）跳过验证，由 SQLite 运行时校验。

        Args:
            table_name: 表名
            columns: 待验证的列名列表

        Raises:
            DataAccessError: 列名不在白名单中
        """
        # 动态表列由运行时 DDL 定义，无法静态验证，跳过
        if self._is_dynamic_table(table_name):
            return
        table_config = TABLE_CONFIGS.get(table_name, {})
        valid_columns = set(table_config.get("columns", {}).keys())
        # timestamps 配置自动添加的列
        if table_config.get("timestamps"):
            valid_columns.add("created_at")
            valid_columns.add("updated_at")
        invalid = set(columns) - valid_columns
        if invalid:
            raise DataAccessError(
                message=f"无效的列名: {invalid}",
                details={"table": table_name, "invalid_columns": list(invalid)},
            )

    def _is_autoincrement_table(self, table_name: str) -> bool:
        """检查表的主键是否为 AUTOINCREMENT

        遍历 columns 配置，查找同时包含 "PRIMARY KEY" 和 "AUTOINCREMENT"
        约束的列。

        Args:
            table_name: 表名

        Returns:
            True 如果表有 AUTOINCREMENT 主键，False 否则
        """
        table_config = TABLE_CONFIGS.get(table_name, {})
        for col_config in table_config.get("columns", {}).values():
            constraints = col_config.get("constraints", [])
            if "PRIMARY KEY" in constraints and "AUTOINCREMENT" in constraints:
                return True
        return False

    # ==================== 查询方法 ====================

    def count_rows(self, table_name: str) -> int:
        """查询表中的记录总数

        执行 SQL: SELECT COUNT(*) FROM {table}

        Args:
            table_name: 表名

        Returns:
            记录总数

        Raises:
            DataAccessError: 数据库操作失败（表不存在等）
        """
        self._validate_table_name(table_name)

        sql = f"SELECT COUNT(*) FROM {table_name}"
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            logger.error(
                "计数查询失败: table=%s, error=%s",
                table_name,
                e,
            )
            raise DataAccessError(
                message=f"计数查询表 {table_name} 失败",
                details={
                    "table": table_name,
                    "error": str(e),
                },
                cause=e,
            ) from e

    def count_rows_batch(self, table_names: list[str]) -> dict[str, int]:
        """批量查询多张表的记录总数，使用单一连接。

        相比逐表调用 count_rows，本方法只获取一次数据库连接，
        在单一事务内执行多次 COUNT(*)，减少连接开销。

        Args:
            table_names: 表名列表

        Returns:
            {table_name: count} 字典

        Raises:
            DataAccessError: 数据库操作失败（表不存在等）
        """
        for table_name in table_names:
            self._validate_table_name(table_name)

        results: dict[str, int] = {}
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                for table_name in table_names:
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    results[table_name] = cursor.fetchone()[0]
            return results
        except sqlite3.Error as e:
            logger.error(
                "批量计数查询失败: tables=%s, error=%s",
                table_names,
                e,
            )
            raise DataAccessError(
                message="批量计数查询失败",
                details={
                    "tables": table_names,
                    "error": str(e),
                },
                cause=e,
            ) from e

    def query_incremental(
        self,
        table_name: str,
        last_sync_time: str,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """增量查询：返回 updated_at > last_sync_time 的记录（支持分页）

        执行 SQL: SELECT * FROM {table} WHERE updated_at > ? ORDER BY updated_at ASC
        当 limit 不为 None 时追加 LIMIT ? OFFSET ? 实现分页。

        Args:
            table_name: 表名
            last_sync_time: 上次同步时间（ISO 8601 字符串）
            offset: 分页偏移量（默认 0）
            limit: 每页记录数（None 表示不分页，返回全部记录）

        Returns:
            记录列表，每条记录为字典

        Raises:
            DataAccessError: 数据库操作失败（表不存在等）
        """
        self._validate_table_name(table_name)

        # 动态表（custom_{slug}）在云端可能尚未创建
        # 先检查表是否存在，不存在则直接返回空列表（避免 SELECT 抛 OperationalError）
        if self._is_dynamic_table(table_name):
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,),
                )
                if cursor.fetchone() is None:
                    logger.warning("增量查询: 动态表 %s 不存在于数据库中，返回空列表", table_name)
                    return []

        sql = f"SELECT * FROM {table_name} WHERE updated_at > ? ORDER BY updated_at ASC"
        params: list[Any] = [last_sync_time]

        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, tuple(params))
                rows = cursor.fetchall()
                column_names = [desc[0] for desc in cursor.description]

            results = [dict(zip(column_names, row, strict=False)) for row in rows]
            logger.debug(
                "增量查询 %s: last_sync_time=%s, offset=%d, limit=%s, 返回 %d 条记录",
                table_name,
                last_sync_time,
                offset,
                limit,
                len(results),
            )
            return results
        except sqlite3.Error as e:
            logger.error(
                "增量查询失败: table=%s, last_sync_time=%s, offset=%d, limit=%s, error=%s",
                table_name,
                last_sync_time,
                offset,
                limit,
                e,
            )
            raise DataAccessError(
                message=f"增量查询表 {table_name} 失败",
                details={
                    "table": table_name,
                    "last_sync_time": last_sync_time,
                    "offset": offset,
                    "limit": limit,
                    "error": str(e),
                },
                cause=e,
            ) from e

    def get_row_by_pk(self, table_name: str, pk_field: str, pk_value: Any) -> dict[str, Any] | None:
        """根据主键查询单条记录

        用于同步冲突解决时获取本地记录的 updated_at。

        Args:
            table_name: 表名
            pk_field: 主键字段名
            pk_value: 主键值

        Returns:
            记录字典，不存在时返回 None

        Raises:
            DataAccessError: 数据库操作失败（表不存在等）
        """
        self._validate_table_name(table_name)
        self._validate_columns(table_name, [pk_field])

        sql = f"SELECT * FROM {table_name} WHERE {pk_field} = ?"
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (pk_value,))
                row = cursor.fetchone()
                if row is None:
                    return None
                column_names = [desc[0] for desc in cursor.description]
            result = dict(zip(column_names, row, strict=False))
            logger.debug(
                "主键查询 %s: pk_field=%s, pk_value=%s, 命中",
                table_name,
                pk_field,
                pk_value,
            )
            return result
        except sqlite3.Error as e:
            logger.error(
                "主键查询失败: table=%s, pk_field=%s, pk_value=%s, error=%s",
                table_name,
                pk_field,
                pk_value,
                e,
            )
            raise DataAccessError(
                message=f"主键查询表 {table_name} 失败",
                details={
                    "table": table_name,
                    "pk_field": pk_field,
                    "pk_value": str(pk_value),
                    "error": str(e),
                },
                cause=e,
            ) from e

    def query_all(
        self,
        table_name: str,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """查询表的全量数据（不带 WHERE 过滤，用于首次同步推送）

        与 query_incremental 的差异：
        - 不带 WHERE updated_at > ? 过滤，返回所有记录（包括 updated_at 为 NULL 的）
        - 复用动态表存在性检查逻辑（custom_<slug> 表不存在时返回空列表）

        Args:
            table_name: 表名
            offset: 分页偏移
            limit: 分页限制

        Returns:
            记录列表

        Raises:
            DataAccessError: 数据库操作失败（静态表不存在等）
        """
        self._validate_table_name(table_name)

        # 动态表（custom_{slug}）在本地可能尚未创建（slug 已删除但 meta 残留等场景）
        # 复用 query_incremental 的存在性检查逻辑，避免抛 OperationalError 中断首次同步
        if self._is_dynamic_table(table_name):
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,),
                )
                if cursor.fetchone() is None:
                    logger.warning("全量查询: 动态表 %s 不存在于数据库中，返回空列表", table_name)
                    return []

        sql = f"SELECT * FROM {table_name}"
        params: list[Any] = []
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        elif offset > 0:
            sql += " LIMIT -1 OFFSET ?"
            params.append(offset)

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, tuple(params))
                column_names = [desc[0] for desc in cursor.description]
                results = [dict(zip(column_names, row, strict=False)) for row in cursor.fetchall()]
            logger.debug(
                "全量查询 %s: offset=%d, limit=%s, 返回 %d 条记录",
                table_name,
                offset,
                limit,
                len(results),
            )
            return results
        except sqlite3.Error as e:
            logger.error(
                "全量查询失败: table=%s, offset=%d, limit=%s, error=%s",
                table_name,
                offset,
                limit,
                e,
            )
            raise DataAccessError(
                message=f"全量查询表 {table_name} 失败",
                details={
                    "table": table_name,
                    "offset": offset,
                    "limit": limit,
                    "error": str(e),
                },
                cause=e,
            ) from e

    # ==================== 写入方法 ====================

    def delete_all_rows(self, table_name: str) -> int:
        """删除指定表的所有行（用于 full-clear 等管理操作）

        执行 SQL: DELETE FROM {table_name}

        单表 DELETE 在 SQLite 中是原子操作（隐式事务）。
        跨表非原子，由调用方负责幂等重试。

        Args:
            table_name: 表名（必须通过白名单校验）

        Returns:
            受影响行数

        Raises:
            DataAccessError: 数据库操作失败（表不存在等）
        """
        self._validate_table_name(table_name)

        sql = f"DELETE FROM {table_name}"
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                conn.commit()
                affected = cursor.rowcount
            logger.info("清空表 %s: 受影响 %d 行", table_name, affected)
            return affected
        except sqlite3.Error as e:
            logger.error("清空表失败: table=%s, error=%s", table_name, e)
            raise DataAccessError(
                message=f"清空表 {table_name} 失败",
                details={"table": table_name, "error": str(e)},
                cause=e,
            ) from e

    def upsert_rows(self, table_name: str, rows: list[dict[str, Any]]) -> int:
        """批量写入：INSERT OR REPLACE

        执行 SQL: INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})

        动态构建列名和占位符。Category A（TEXT 主键）按主键判重，
        Category B/C（AUTOINCREMENT + UNIQUE）按 UNIQUE 约束判重。

        对 AUTOINCREMENT 表，自动从行数据中剥离 id 字段，
        避免污染本地 sqlite_sequence。

        Args:
            table_name: 表名
            rows: 行数据列表，每行为字典（key 为列名）

        Returns:
            受影响的行数

        Raises:
            DataAccessError: 数据库操作失败（表不存在、列不存在、约束冲突等）
        """
        if not rows:
            logger.debug("upsert_rows: rows 为空，跳过写入 table=%s", table_name)
            return 0

        self._validate_table_name(table_name)

        # 验证列名（在剥离 id 之前验证原始传入的列名）
        columns = list(rows[0].keys())
        self._validate_columns(table_name, columns)

        # 对 AUTOINCREMENT 表，从行数据副本中移除 id（避免污染 sqlite_sequence）
        if self._is_autoincrement_table(table_name):
            rows = [{k: v for k, v in row.items() if k != "id"} for row in rows]
            if not rows or not rows[0]:
                logger.debug("upsert_rows: AUTOINCREMENT 表 %s 剥离 id 后无数据", table_name)
                return 0
            columns = list(rows[0].keys())

        # 从第一行提取列名（假设所有行有相同的列结构）
        columns_str = ", ".join(columns)
        placeholders = ", ".join(["?"] * len(columns))
        sql = f"INSERT OR REPLACE INTO {table_name} ({columns_str}) VALUES ({placeholders})"

        # 构建 values 列表
        values_list = [[row.get(col) for col in columns] for row in rows]

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(sql, values_list)
                conn.commit()
                affected = cursor.rowcount

            logger.info(
                "批量写入 %s: 尝试 %d 行, 受影响 %d 行",
                table_name,
                len(rows),
                affected,
            )
            return affected
        except sqlite3.Error as e:
            logger.error(
                "批量写入失败: table=%s, rows=%d, error=%s",
                table_name,
                len(rows),
                e,
            )
            raise DataAccessError(
                message=f"批量写入表 {table_name} 失败",
                details={
                    "table": table_name,
                    "row_count": len(rows),
                    "error": str(e),
                },
                cause=e,
            ) from e

    def batch_get_existing_updated_at(
        self, table_name: str, pk_field: str, pk_values: list[Any]
    ) -> dict[Any, str]:
        """批量查询已存在记录的 updated_at（单字段查找）

        在单连接内通过 IN 子句一次性查询所有主键对应的 updated_at，
        避免 N+1 查询问题。适用于 TEXT 主键表。

        当 pk_values 数量超过 SQLite 参数上限时，自动分块查询。

        Args:
            table_name: 表名
            pk_field: 主键字段名
            pk_values: 主键值列表

        Returns:
            {pk_value: updated_at_string} 映射，不存在的 pk 不在结果中

        Raises:
            DataAccessError: 数据库操作失败
        """
        if not pk_values:
            return {}

        self._validate_table_name(table_name)
        self._validate_columns(table_name, [pk_field])

        # SQLite 参数数量上限保护（默认 999，分块避免超限）
        chunk_size = 500
        result: dict[Any, str] = {}

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                for i in range(0, len(pk_values), chunk_size):
                    chunk = pk_values[i : i + chunk_size]
                    placeholders = ", ".join(["?"] * len(chunk))
                    sql = (
                        f"SELECT {pk_field}, updated_at FROM {table_name} "
                        f"WHERE {pk_field} IN ({placeholders})"
                    )
                    cursor.execute(sql, chunk)
                    for row in cursor.fetchall():
                        result[row[0]] = row[1]
        except sqlite3.Error as e:
            logger.error(
                "批量查询 updated_at 失败: table=%s, pk_field=%s, count=%d, error=%s",
                table_name,
                pk_field,
                len(pk_values),
                e,
            )
            raise DataAccessError(
                message=f"批量查询表 {table_name} 已有记录失败",
                details={
                    "table": table_name,
                    "pk_field": pk_field,
                    "count": len(pk_values),
                    "error": str(e),
                },
                cause=e,
            ) from e

        return result

    def _batch_get_existing_updated_at_by_unique(
        self, table_name: str, unique_fields: list[str], rows: list[dict[str, Any]]
    ) -> dict[tuple, str]:
        """批量查询已存在记录的 updated_at（UNIQUE 多字段查找）

        通过 OR 条件批量查询所有 UNIQUE 约束组合对应的 updated_at，
        避免 N+1 查询问题。适用于 AUTOINCREMENT + UNIQUE 约束表。

        当行数超过 SQLite 参数上限时，自动分块查询。

        Args:
            table_name: 表名
            unique_fields: UNIQUE 约束字段列表
            rows: 行数据列表

        Returns:
            {tuple(unique_values): updated_at_string} 映射

        Raises:
            DataAccessError: 数据库操作失败
        """
        if not rows:
            return {}

        self._validate_table_name(table_name)
        self._validate_columns(table_name, unique_fields)

        field_count = len(unique_fields)
        # SQLite 参数数量上限保护：每行贡献 field_count 个参数
        chunk_size = max(1, 500 // field_count)
        select_fields = ", ".join(unique_fields)
        result: dict[tuple, str] = {}

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                for i in range(0, len(rows), chunk_size):
                    chunk = rows[i : i + chunk_size]
                    or_clauses: list[str] = []
                    params: list[Any] = []
                    for row in chunk:
                        and_clause = " AND ".join(f"{f} = ?" for f in unique_fields)
                        or_clauses.append(f"({and_clause})")
                        params.extend(row.get(f) for f in unique_fields)
                    where_clause = " OR ".join(or_clauses)
                    sql = (
                        f"SELECT {select_fields}, updated_at FROM {table_name} WHERE {where_clause}"
                    )
                    cursor.execute(sql, params)
                    for db_row in cursor.fetchall():
                        key = tuple(db_row[:field_count])
                        result[key] = db_row[field_count]
        except sqlite3.Error as e:
            logger.error(
                "批量查询 updated_at (UNIQUE) 失败: table=%s, unique_fields=%s, count=%d, error=%s",
                table_name,
                unique_fields,
                len(rows),
                e,
            )
            raise DataAccessError(
                message=f"批量查询表 {table_name} 已有记录失败 (UNIQUE)",
                details={
                    "table": table_name,
                    "unique_fields": unique_fields,
                    "count": len(rows),
                    "error": str(e),
                },
                cause=e,
            ) from e

        return result

    def upsert_rows_with_lww(self, table_name: str, rows: list[dict[str, Any]]) -> int:
        """带 LWW（Last-Write-Wins）冲突解决的批量写入

        先批量查询本地已存在记录的 updated_at，在内存中做 LWW 过滤，
        最后调用 upsert_rows() 写入过滤后的行。

        查找策略：
        - AUTOINCREMENT + UNIQUE 约束表：按 UNIQUE 字段组合批量查找
        - TEXT 主键表：按主键字段批量查找

        与旧实现的区别：旧实现逐行调用 _find_existing_updated_at（N+1 查询），
        新实现使用单连接批量查询，大幅减少数据库往返。

        Args:
            table_name: 表名
            rows: 行数据列表，每行为字典（key 为列名）

        Returns:
            受影响的行数

        Raises:
            DataAccessError: 数据库操作失败
        """
        if not rows:
            logger.debug("upsert_rows_with_lww: rows 为空，跳过写入 table=%s", table_name)
            return 0

        self._validate_table_name(table_name)

        unique_fields = self.get_unique_fields(table_name)

        if unique_fields:
            # AUTOINCREMENT + UNIQUE 表：按 UNIQUE 字段组合批量查询
            existing_map = self._batch_get_existing_updated_at_by_unique(
                table_name, unique_fields, rows
            )

            def get_lookup_key(row: dict[str, Any]) -> tuple:
                return tuple(row.get(f) for f in unique_fields)

        else:
            # TEXT 主键表：按主键批量查询
            pk_field = self.get_primary_key_field(table_name)
            if pk_field is None:
                # 无主键且无 UNIQUE 约束，无法做 LWW 检查，直接写入
                logger.warning(
                    "upsert_rows_with_lww: 表 %s 无主键和 UNIQUE 约束，跳过 LWW 检查直接写入",
                    table_name,
                )
                return self.upsert_rows(table_name, rows)

            pk_values = [row.get(pk_field) for row in rows]
            existing_map = self.batch_get_existing_updated_at(table_name, pk_field, pk_values)

            def get_lookup_key(row: dict[str, Any]) -> Any:
                return row.get(pk_field)

        # 在内存中做 LWW 过滤
        filtered_rows: list[dict[str, Any]] = []
        skipped_count = 0

        for row in rows:
            incoming_updated_at = row.get("updated_at")
            if incoming_updated_at is None:
                # 没有 updated_at 字段，无法比较，直接写入
                filtered_rows.append(row)
                continue

            existing_updated_at = existing_map.get(get_lookup_key(row))

            if existing_updated_at is not None and existing_updated_at >= incoming_updated_at:
                # 本地数据更新，跳过该行
                skipped_count += 1
                logger.debug(
                    "LWW 跳过旧数据: table=%s, existing_updated_at=%s, incoming_updated_at=%s",
                    table_name,
                    existing_updated_at,
                    incoming_updated_at,
                )
                continue

            filtered_rows.append(row)

        logger.info(
            "LWW 过滤完成: table=%s, 总计 %d 行, 跳过 %d 行, 写入 %d 行",
            table_name,
            len(rows),
            skipped_count,
            len(filtered_rows),
        )

        if not filtered_rows:
            return 0

        return self.upsert_rows(table_name, filtered_rows)

    def _find_existing_updated_at(self, table_name: str, row: dict[str, Any]) -> str | None:
        """查找本地已有记录的 updated_at

        优先用 UNIQUE 约束字段查找（AUTOINCREMENT 表），
        否则用主键查找（TEXT PK 表）。

        Args:
            table_name: 表名
            row: 行数据

        Returns:
            已有记录的 updated_at 值，不存在时返回 None

        Raises:
            DataAccessError: 数据库操作失败
        """
        # 优先用 UNIQUE 约束字段查找（AUTOINCREMENT 表）
        unique_fields = self.get_unique_fields(table_name)
        if unique_fields:
            where_clause = " AND ".join(f"{f} = ?" for f in unique_fields)
            values = tuple(row.get(f) for f in unique_fields)
        else:
            # 用主键查找（TEXT PK 表）
            pk_field = self.get_primary_key_field(table_name)
            if pk_field is None:
                return None
            where_clause = f"{pk_field} = ?"
            values = (row.get(pk_field),)

        sql = f"SELECT updated_at FROM {table_name} WHERE {where_clause}"
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, values)
                result = cursor.fetchone()
                if result is None:
                    return None
                return result[0]
        except sqlite3.Error as e:
            logger.error(
                "LWW 查找已有记录失败: table=%s, error=%s",
                table_name,
                e,
            )
            raise DataAccessError(
                message=f"LWW 查找表 {table_name} 已有记录失败",
                details={
                    "table": table_name,
                    "error": str(e),
                },
                cause=e,
            ) from e

    # ==================== 元数据解析方法 ====================

    def get_primary_key_field(self, table_name: str) -> str | None:
        """从 TABLE_CONFIGS 解析主键字段名

        遍历 columns 配置，查找 constraints 列表中包含 "PRIMARY KEY" 的列。
        动态自定义记录表（custom_{slug}）的主键固定为 "id"。

        Args:
            table_name: 表名

        Returns:
            主键字段名，未找到则返回 None
        """
        table_config = TABLE_CONFIGS.get(table_name)
        if table_config is None:
            # 动态表 custom_{slug} 的主键固定为 id
            if self._is_dynamic_table(table_name):
                return "id"
            logger.warning("get_primary_key_field: 表 %s 不在 TABLE_CONFIGS 中", table_name)
            return None

        for col_name, col_config in table_config["columns"].items():
            if "PRIMARY KEY" in col_config.get("constraints", []):
                return col_name

        logger.warning("get_primary_key_field: 表 %s 未找到 PRIMARY KEY 约束", table_name)
        return None

    def get_unique_fields(self, table_name: str) -> list[str] | None:
        """从 TABLE_CONFIGS 的 table_constraints 中解析 UNIQUE 约束字段

        查找优先级：
        1. 业务 UNIQUE 约束（table_constraints 中的 UNIQUE(...)）
           —— 必须优先，因为 upsert_rows 的 INSERT OR REPLACE 也按业务 UNIQUE 触发替换，
           LWW 查找键必须与 REPLACE 键一致，否则两设备独立创建相同业务键、不同 hash_id
           的记录时，LWW 查不到匹配放行，REPLACE 删新插旧，较新数据被静默覆盖。
        2. hash_id（仅当表在 HASH_ID_PREFIXES 中且无业务 UNIQUE 约束时）
           —— 用于没有业务 UNIQUE 的 AUTOINCREMENT 表（如 mood_impacts 列级 UNIQUE 无法解析）。

        支持两种 table_constraints 格式：
        - "UNIQUE(field1, field2)" （无空格）
        - "UNIQUE (field1, field2)" （有空格）

        Args:
            table_name: 表名

        Returns:
            UNIQUE 约束字段列表，无 UNIQUE 约束时返回 None
        """
        # 优先：业务 UNIQUE 约束（table_constraints）
        table_config = TABLE_CONFIGS.get(table_name, {})
        for constraint in table_config.get("table_constraints", []):
            constraint_stripped = constraint.strip()
            if constraint_stripped.upper().startswith("UNIQUE"):
                open_paren = constraint_stripped.find("(")
                close_paren = constraint_stripped.rfind(")")
                if open_paren != -1 and close_paren != -1:
                    fields_str = constraint_stripped[open_paren + 1 : close_paren]
                    return [f.strip() for f in fields_str.split(",")]

        # 回退：HASH_ID_PREFIXES 中的表用 hash_id 作去重键
        # 参考 ADR: docs/adr/2026-07-22-hash-id-sync-only-identifier.md
        from lifeprism.sync.constants import HASH_ID_PREFIXES

        if HASH_ID_PREFIXES.get(table_name):
            return ["hash_id"]

        return None

    # ==================== 动态表发现 ====================

    def has_updated_at(self, table_name: str) -> bool:
        """检查表是否配置了 update_at（即是否有 updated_at 列）

        通过 TABLE_CONFIGS 的 update_at 标志判断。
        动态自定义记录表（custom_{slug}）固定包含 updated_at 列。

        Args:
            table_name: 表名

        Returns:
            True 如果表有 updated_at 列，False 否则
        """
        table_config = TABLE_CONFIGS.get(table_name, {})
        if not table_config:
            return bool(self._is_dynamic_table(table_name))
        return bool(table_config.get("update_at", False))

    def get_custom_record_slugs(self) -> list[str]:
        """查询所有自定义记录类型的 slug 列表

        执行 SQL: SELECT slug FROM custom_record_types

        用于同步时动态发现 custom_records_{slug} 表。

        Returns:
            slug 字符串列表，无自定义记录类型时返回空列表

        Raises:
            DataAccessError: 数据库操作失败
        """
        sql = "SELECT slug FROM custom_record_types"
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                rows = cursor.fetchall()

            slugs = [row[0] for row in rows]
            logger.debug(
                "查询自定义记录类型 slug: 返回 %d 条",
                len(slugs),
            )
            return slugs
        except sqlite3.Error as e:
            logger.error(
                "查询自定义记录类型 slug 失败: error=%s",
                e,
            )
            raise DataAccessError(
                message="查询自定义记录类型 slug 失败",
                details={"error": str(e)},
                cause=e,
            ) from e

    def get_custom_record_types_snapshot(self) -> set[tuple[str, str]]:
        """获取本地 custom_record_types 的快照（id, updated_at 集合）

        用于 sync_once 中 pull 前后对比，判断云端 meta 表是否有变更。
        如果 pull 后快照变化，说明云端 custom_record_types 有新增/修改/删除。

        Returns:
            (type_id, updated_at) 元组集合，无记录时返回空集合
        """
        sql = "SELECT id, updated_at FROM custom_record_types"
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                rows = cursor.fetchall()
            return {(row[0], row[1]) for row in rows}
        except sqlite3.Error as e:
            logger.error("获取 custom_record_types 快照失败: error=%s", e)
            raise DataAccessError(
                message="获取 custom_record_types 快照失败",
                details={"error": str(e)},
                cause=e,
            ) from e

    def get_custom_record_types_full_definitions(self) -> list[dict[str, Any]]:
        """查询所有自定义记录类型的完整定义（含字段列表）

        返回每个 type 的 slug 和 fields 列表，用于发送给云端重建动态表。

        Returns:
            类型定义列表，每项格式：{"slug": str, "fields": [{"field_key": str, "field_type": str}]}
            无自定义记录类型时返回空列表

        Raises:
            DataAccessError: 数据库操作失败
        """
        sql_types = "SELECT id, slug FROM custom_record_types"
        sql_fields = (
            "SELECT field_key, field_type FROM custom_record_fields "
            "WHERE type_id = ? ORDER BY sort_order ASC"
        )
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql_types)
                types_rows = cursor.fetchall()

                result = []
                for type_id, slug in types_rows:
                    cursor.execute(sql_fields, (type_id,))
                    fields_rows = cursor.fetchall()
                    fields = [{"field_key": r[0], "field_type": r[1]} for r in fields_rows]
                    result.append({"slug": slug, "fields": fields})

            logger.debug(
                "查询自定义记录类型完整定义: 返回 %d 条",
                len(result),
            )
            return result
        except sqlite3.Error as e:
            logger.error(
                "查询自定义记录类型完整定义失败: error=%s",
                e,
            )
            raise DataAccessError(
                message="查询自定义记录类型完整定义失败",
                details={"error": str(e)},
                cause=e,
            ) from e

    def create_local_data_tables(self, slug_to_fields: dict[str, list[dict[str, Any]]]) -> None:
        """本地建表（只执行 DDL，不写 meta 数据）

        接收 slug → fields 映射，复用 CustomRecordRepository.generate_create_table_ddl
        生成 DDL 并执行 CREATE TABLE。不写入 custom_record_types / custom_record_fields，
        meta 数据由后续 pull 统一同步（LWW 逻辑只在一处）。

        所有操作在同一事务中执行，失败则回滚。

        Args:
            slug_to_fields: slug → fields 映射，fields 每项含 field_key / field_type

        Raises:
            DataAccessError: 数据库操作失败
        """
        from lifeprism.repository.aggregators.custom_record_aggregator import (
            CustomRecordRepository,
        )

        if not slug_to_fields:
            return

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                for slug, fields in slug_to_fields.items():
                    data_table = f"custom_{slug}"
                    cursor.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                        (data_table,),
                    )
                    if cursor.fetchone() is not None:
                        logger.info(
                            "本地建表 custom_%s: 表已存在，跳过",
                            slug,
                        )
                        continue
                    ddl = CustomRecordRepository.generate_create_table_ddl(slug, fields)
                    cursor.execute(ddl)
                    logger.info(
                        "本地建表 custom_%s, fields=%d",
                        slug,
                        len(fields),
                    )
        except sqlite3.Error as e:
            logger.error(
                "本地建表失败: slugs=%s, error=%s",
                list(slug_to_fields.keys()),
                e,
            )
            raise DataAccessError(
                message="本地建表失败",
                details={"slugs": list(slug_to_fields.keys()), "error": str(e)},
                cause=e,
            ) from e

    def rebuild_dynamic_tables(self, types: list[dict[str, Any]]) -> list[dict[str, str]]:
        """根据传入的自定义记录类型定义，在云端创建/更新动态表

        对每个传入的 type：
        - 表不存在 → CREATE TABLE（调用 CustomRecordRepository.generate_create_table_ddl）
        - 表存在但字段缺失 → ALTER TABLE ADD COLUMN（只增不删，SQLite 兼容）
        - 表已存在且字段齐全 → skipped

        注意：不删除任何表——删除同步需要独立的 tombstone 机制，不属于本方法的职责范围。

        所有操作在同一事务中执行，失败则回滚。

        Args:
            types: 类型定义列表，每项含 slug 和 fields

        Returns:
            每个 type 的处理结果列表，每项 {"slug": str, "action": "created"|"altered"|"skipped"}

        Raises:
            DataAccessError: 数据库操作失败
        """
        from lifeprism.repository.aggregators.custom_record_aggregator import (
            CustomRecordRepository,
        )

        results: list[dict[str, str]] = []

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # 1. 处理本地传入的 type：CREATE IF NOT EXISTS + ALTER ADD COLUMN
                for t in types:
                    slug = t["slug"]
                    fields = t.get("fields", [])
                    data_table = f"custom_{slug}"

                    # 检查表是否存在
                    cursor.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                        (data_table,),
                    )
                    existing = cursor.fetchone()

                    if existing is None:
                        # 表不存在 → CREATE TABLE
                        ddl = CustomRecordRepository.generate_create_table_ddl(slug, fields)
                        cursor.execute(ddl)
                        results.append({"slug": slug, "action": "created"})
                        logger.info("重建动态表: 创建表 %s", data_table)
                    else:
                        # 表存在 → 检查并 ALTER ADD COLUMN（只增不删）
                        cursor.execute(f"PRAGMA table_info({data_table})")
                        existing_columns = {row[1] for row in cursor.fetchall()}

                        altered = False
                        for f in fields:
                            field_key = f["field_key"]
                            if field_key not in existing_columns:
                                ftype = f.get("field_type", "text")
                                sql_type = CustomRecordRepository._FIELD_TYPE_TO_SQL.get(
                                    ftype, "TEXT"
                                )
                                cursor.execute(
                                    f"ALTER TABLE {data_table} ADD COLUMN {field_key} {sql_type}"
                                )
                                altered = True
                                logger.info(
                                    "重建动态表: %s 新增列 %s (%s)",
                                    data_table,
                                    field_key,
                                    sql_type,
                                )

                        results.append(
                            {"slug": slug, "action": "altered" if altered else "skipped"}
                        )

            logger.info("重建动态表完成: %s", results)
            return results
        except sqlite3.Error as e:
            logger.error("重建动态表失败: error=%s", e)
            raise DataAccessError(
                message="重建动态表失败",
                details={"error": str(e)},
                cause=e,
            ) from e
