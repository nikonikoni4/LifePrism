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

import logging
import sqlite3
from typing import Any

from lifeprism.config.database import TABLE_CONFIGS
from lifeprism.utils.exceptions import DataAccessError

logger = logging.getLogger(__name__)


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

    def _validate_table_name(self, table_name: str) -> None:
        """验证表名在 TABLE_CONFIGS 白名单中

        Args:
            table_name: 表名

        Raises:
            DataAccessError: 表名不在白名单中
        """
        if table_name not in TABLE_CONFIGS:
            raise DataAccessError(
                message=f"无效的表名: {table_name}",
                details={"table": table_name},
            )

    def _validate_columns(self, table_name: str, columns: list[str]) -> None:
        """验证列名在 TABLE_CONFIGS 白名单中

        timestamps 自动添加的 created_at / updated_at 也视为有效列。

        Args:
            table_name: 表名
            columns: 待验证的列名列表

        Raises:
            DataAccessError: 列名不在白名单中
        """
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

    def query_incremental(self, table_name: str, last_sync_time: str) -> list[dict[str, Any]]:
        """增量查询：返回 updated_at > last_sync_time 的记录

        执行 SQL: SELECT * FROM {table} WHERE updated_at > ? ORDER BY updated_at ASC

        Args:
            table_name: 表名
            last_sync_time: 上次同步时间（ISO 8601 字符串）

        Returns:
            记录列表，每条记录为字典

        Raises:
            DataAccessError: 数据库操作失败（表不存在等）
        """
        self._validate_table_name(table_name)

        sql = f"SELECT * FROM {table_name} WHERE updated_at > ? ORDER BY updated_at ASC"
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (last_sync_time,))
                rows = cursor.fetchall()
                column_names = [desc[0] for desc in cursor.description]

            results = [dict(zip(column_names, row, strict=False)) for row in rows]
            logger.debug(
                "增量查询 %s: last_sync_time=%s, 返回 %d 条记录",
                table_name,
                last_sync_time,
                len(results),
            )
            return results
        except sqlite3.Error as e:
            logger.error(
                "增量查询失败: table=%s, last_sync_time=%s, error=%s",
                table_name,
                last_sync_time,
                e,
            )
            raise DataAccessError(
                message=f"增量查询表 {table_name} 失败",
                details={
                    "table": table_name,
                    "last_sync_time": last_sync_time,
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

    # ==================== 写入方法 ====================

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
        except (sqlite3.Error, sqlite3.IntegrityError) as e:
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

    def upsert_rows_with_lww(self, table_name: str, rows: list[dict[str, Any]]) -> int:
        """带 LWW（Last-Write-Wins）冲突解决的批量写入

        对于每行数据，先查询本地是否存在同主键（TEXT PK）或同 UNIQUE 约束
        （AUTOINCREMENT 表）的记录。如果本地记录的 updated_at 大于传入记录的
        updated_at，则跳过该行（本地数据更新）。最后调用 upsert_rows() 写入
        过滤后的行。

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

        filtered_rows: list[dict[str, Any]] = []
        skipped_count = 0

        for row in rows:
            incoming_updated_at = row.get("updated_at")
            if incoming_updated_at is None:
                # 没有 updated_at 字段，无法比较，直接写入
                filtered_rows.append(row)
                continue

            existing_updated_at = self._find_existing_updated_at(table_name, row)

            if existing_updated_at is not None and existing_updated_at > incoming_updated_at:
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

        Args:
            table_name: 表名

        Returns:
            主键字段名，未找到则返回 None
        """
        table_config = TABLE_CONFIGS.get(table_name)
        if table_config is None:
            logger.warning("get_primary_key_field: 表 %s 不在 TABLE_CONFIGS 中", table_name)
            return None

        for col_name, col_config in table_config["columns"].items():
            if "PRIMARY KEY" in col_config.get("constraints", []):
                return col_name

        logger.warning("get_primary_key_field: 表 %s 未找到 PRIMARY KEY 约束", table_name)
        return None

    def get_unique_fields(self, table_name: str) -> list[str] | None:
        """从 TABLE_CONFIGS 的 table_constraints 中解析 UNIQUE 约束字段

        支持两种格式：
        - "UNIQUE(field1, field2)" （无空格）
        - "UNIQUE (field1, field2)" （有空格）

        Args:
            table_name: 表名

        Returns:
            UNIQUE 约束字段列表，无 UNIQUE 约束时返回 None
        """
        table_config = TABLE_CONFIGS.get(table_name, {})
        for constraint in table_config.get("table_constraints", []):
            constraint_stripped = constraint.strip()
            if constraint_stripped.upper().startswith("UNIQUE"):
                open_paren = constraint_stripped.find("(")
                close_paren = constraint_stripped.rfind(")")
                if open_paren != -1 and close_paren != -1:
                    fields_str = constraint_stripped[open_paren + 1 : close_paren]
                    return [f.strip() for f in fields_str.split(",")]
        return None
