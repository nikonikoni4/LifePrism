"""
Custom Record Aggregator - 自定义记录数据聚合层

独立实现，不继承 LWBaseDataProvider（动态表名运行时才确定，无法套用静态元数据模式）。
内部直接使用 lw_db_manager 执行参数化 SQL。

Meta 表驱动：custom_record_types + custom_record_fields 定义动态数据表的结构，
数据表（custom_<slug>）由 meta 表定义驱动 DDL 动态创建。
"""

import re
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from lifeprism.repository.exceptions import DuplicateEntityError, EntityNotFoundError
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import DataAccessError, ValidationError

logger = get_logger(__name__)


class CustomRecordRepository:
    """
    自定义记录数据访问层

    职责：
    1. 类型管理：创建/列出/获取/删除自定义记录类型（meta 表 + DDL）
    2. 记录管理：录入/查询/删除自定义记录条目（动态数据表）
    3. 校验：slug/field_key 格式与唯一性校验
    """

    # ==================== 常量 ====================

    _TYPE_ID_PREFIX = "crt-"
    _FIELD_ID_PREFIX = "crf-"
    _ENTRY_ID_PREFIX = "cre-"
    _DATA_TABLE_PREFIX = "custom_"

    _SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
    _FIELD_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

    def __init__(self, db_manager=None):
        if db_manager is None:
            from lifeprism.repository import lw_db_manager

            db_manager = lw_db_manager
        self.db = db_manager

    # ==================== 类型管理 ====================

    def create_type(
        self,
        name: str,
        slug: str,
        fields: list[dict[str, Any]],
        description: str | None = None,
    ) -> str:
        """
        创建自定义记录类型

        Args:
            name: 类型显示名（如"体育活动"）
            slug: 语义化标识，用作表名后缀（如 "sport" → 表 "custom_sport"）
            fields: 字段定义列表，每项含 field_name / field_key / field_type
            description: 类型描述（可选）

        Returns:
            str: 新创建的 type_id

        Raises:
            ValidationError: slug/field_key 格式错误或 fields 为空
            DuplicateEntityError: slug 已存在
            DataAccessError: 数据库操作失败
        """
        # 校验 slug 格式
        if not self._SLUG_PATTERN.match(slug):
            raise ValidationError(
                message=f"slug 格式无效: {slug}（要求 ^[a-z][a-z0-9_]*$）",
                code="INVALID_SLUG_FORMAT",
                details={"slug": slug},
            )

        # 校验 fields 非空
        if not fields:
            raise ValidationError(
                message="fields 不能为空，至少需要 1 个字段",
                code="EMPTY_FIELDS",
            )

        # 校验每个 field_key 格式
        for f in fields:
            if not self._FIELD_KEY_PATTERN.match(f["field_key"]):
                raise ValidationError(
                    message=f"field_key 格式无效: {f['field_key']}（要求 ^[a-z][a-z0-9_]*$）",
                    code="INVALID_FIELD_KEY_FORMAT",
                    details={"field_key": f["field_key"]},
                )

        # 校验 field_key 同类型内唯一
        seen_keys = set()
        for f in fields:
            if f["field_key"] in seen_keys:
                raise ValidationError(
                    message=f"field_key 重复: {f['field_key']}",
                    code="DUPLICATE_FIELD_KEY",
                    details={"field_key": f["field_key"]},
                )
            seen_keys.add(f["field_key"])

        # 检查 slug 唯一性（check-then-insert，UNIQUE 约束兜底）
        existing = self._query_one("SELECT id FROM custom_record_types WHERE slug = ?", (slug,))
        if existing:
            raise DuplicateEntityError(
                entity_type="CustomRecordType",
                entity_id=slug,
                conflict_field="slug",
            )

        # 生成 ID
        type_id = f"{self._TYPE_ID_PREFIX}{uuid.uuid4().hex[:8]}"
        data_table = f"{self._DATA_TABLE_PREFIX}{slug}"

        # 事务：meta 写入 + DDL
        now = datetime.now(timezone.utc).isoformat()
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # 1. 写入 custom_record_types
                cursor.execute(
                    "INSERT INTO custom_record_types (id, name, slug, description, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (type_id, name, slug, description or "", now, now),
                )

                # 2. 写入 custom_record_fields
                for idx, f in enumerate(fields):
                    field_id = f"{self._FIELD_ID_PREFIX}{uuid.uuid4().hex[:8]}"
                    cursor.execute(
                        "INSERT INTO custom_record_fields "
                        "(id, type_id, field_name, field_key, field_type, sort_order, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            field_id,
                            type_id,
                            f["field_name"],
                            f["field_key"],
                            f.get("field_type", "text"),
                            f.get("sort_order", idx),
                            now,
                        ),
                    )

                # 3. DDL: 创建数据表
                column_defs = ["id TEXT PRIMARY KEY"]
                for f in fields:
                    column_defs.append(f"{f['field_key']} TEXT")
                column_defs.append("created_at TEXT")
                column_defs.append("updated_at TEXT")

                ddl = f"CREATE TABLE {data_table} ({', '.join(column_defs)})"
                cursor.execute(ddl)

                logger.info(
                    "创建自定义记录类型成功: type_id=%s, name=%s, slug=%s, table=%s",
                    type_id,
                    name,
                    slug,
                    data_table,
                )
                return type_id

        except sqlite3.IntegrityError as e:
            # UNIQUE 约束兜底（check-then-insert 的并发兜底）
            logger.warning(
                "创建自定义记录类型 slug 冲突(UNIQUE 兜底): name=%s, slug=%s", name, slug
            )
            raise DuplicateEntityError(
                entity_type="CustomRecordType",
                entity_id=slug,
                conflict_field="slug",
            ) from e
        except sqlite3.Error as e:
            logger.error("创建自定义记录类型失败: name=%s, slug=%s, error=%s", name, slug, e)
            raise DataAccessError(
                message="创建自定义记录类型失败",
                details={"name": name, "slug": slug, "error": str(e)},
                cause=e,
            ) from e

    # ==================== 内部辅助方法 ====================

    def _query_one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        """查询单条记录，返回字典或 None"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            row = cursor.fetchone()
            if row is None:
                return None
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row, strict=True))

    def _query_all(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """查询多条记录，返回字典列表"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            if not rows:
                return []
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in rows]

    def _get_fields_by_type_id(self, type_id: str) -> list[dict[str, Any]]:
        """按 type_id 获取字段定义列表（按 sort_order 排序）"""
        return self._query_all(
            "SELECT id, field_name, field_key, field_type, sort_order, display_role "
            "FROM custom_record_fields WHERE type_id = ? ORDER BY sort_order ASC",
            (type_id,),
        )

    # ==================== 类型查询 ====================

    def list_types(self) -> list[dict[str, Any]]:
        """
        列出所有自定义记录类型（含 fields）

        Returns:
            List[Dict]: 类型列表，每项含 id/name/slug/description/fields
        """
        try:
            types = self._query_all(
                "SELECT id, name, slug, description, card_template, icon, accent_color, created_at, updated_at "
                "FROM custom_record_types ORDER BY created_at ASC"
            )
            for t in types:
                t["fields"] = self._get_fields_by_type_id(t["id"])
            return types
        except sqlite3.Error as e:
            logger.error("列出自定义记录类型失败: %s", e)
            raise DataAccessError(
                message="列出自定义记录类型失败",
                details={"error": str(e)},
                cause=e,
            ) from e

    def get_type_by_id(self, type_id: str) -> dict[str, Any] | None:
        """
        按 ID 获取类型详情（含 fields）

        Args:
            type_id: 类型 ID

        Returns:
            Optional[Dict]: 类型详情，不存在返回 None
        """
        try:
            t = self._query_one(
                "SELECT id, name, slug, description, card_template, icon, accent_color, created_at, updated_at "
                "FROM custom_record_types WHERE id = ?",
                (type_id,),
            )
            if t is None:
                return None
            t["fields"] = self._get_fields_by_type_id(type_id)
            return t
        except sqlite3.Error as e:
            logger.error("获取自定义记录类型失败: type_id=%s, error=%s", type_id, e)
            raise DataAccessError(
                message="获取自定义记录类型失败",
                details={"type_id": type_id, "error": str(e)},
                cause=e,
            ) from e

    def get_type_fields(self, type_id: str) -> list[dict[str, Any]]:
        """
        按 type_id 获取字段定义列表

        Args:
            type_id: 类型 ID

        Returns:
            List[Dict]: 字段定义列表
        """
        return self._get_fields_by_type_id(type_id)

    def delete_type(self, type_id: str) -> bool:
        """
        硬删类型：DROP 数据表 + 删除 meta 记录（同事务）

        Args:
            type_id: 类型 ID

        Returns:
            bool: 是否成功

        Raises:
            EntityNotFoundError: 类型不存在
            DataAccessError: 数据库操作失败
        """
        # 查询类型是否存在 + 获取 slug（用于 DROP 表名）
        t = self._query_one("SELECT slug FROM custom_record_types WHERE id = ?", (type_id,))
        if t is None:
            raise EntityNotFoundError(entity_type="CustomRecordType", entity_id=type_id)

        data_table = f"{self._DATA_TABLE_PREFIX}{t['slug']}"

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                # 1. DROP 数据表
                cursor.execute(f"DROP TABLE IF EXISTS {data_table}")
                # 2. 删除 custom_record_fields 记录
                cursor.execute("DELETE FROM custom_record_fields WHERE type_id = ?", (type_id,))
                # 3. 删除 custom_record_types 记录
                cursor.execute("DELETE FROM custom_record_types WHERE id = ?", (type_id,))
                logger.info("删除自定义记录类型成功: type_id=%s, table=%s", type_id, data_table)
                return True
        except sqlite3.Error as e:
            logger.error("删除自定义记录类型失败: type_id=%s, error=%s", type_id, e)
            raise DataAccessError(
                message="删除自定义记录类型失败",
                details={"type_id": type_id, "error": str(e)},
                cause=e,
            ) from e

    # ==================== 记录管理 ====================

    def _get_type_and_table(self, type_id: str) -> tuple[dict[str, Any], str]:
        """按 type_id 获取类型元信息 + 数据表名。类型不存在抛 EntityNotFoundError。"""
        t = self._query_one(
            "SELECT id, name, slug FROM custom_record_types WHERE id = ?",
            (type_id,),
        )
        if t is None:
            raise EntityNotFoundError(entity_type="CustomRecordType", entity_id=type_id)
        data_table = f"{self._DATA_TABLE_PREFIX}{t['slug']}"
        return t, data_table

    def create_entry(self, type_id: str, data: dict[str, Any]) -> str:
        """
        录入一条记录到 custom_<slug> 表

        Args:
            type_id: 类型 ID
            data: 字段值字典 {field_key: value}，允许为空字典（插入全 NULL 行）
                  缺失字段存为 NULL，field_key 错误抛 ValidationError

        Returns:
            str: 新创建的 entry_id

        Raises:
            EntityNotFoundError: 类型不存在
            ValidationError: data 含未知 field_key（details 含 valid_fields）
            DataAccessError: 数据库操作失败
        """
        _, data_table = self._get_type_and_table(type_id)
        fields = self._get_fields_by_type_id(type_id)
        valid_keys = {f["field_key"] for f in fields}

        # 校验 data 的 key 是否都在 valid_keys 中
        invalid_keys = set(data.keys()) - valid_keys
        if invalid_keys:
            valid_fields = [
                {"field_key": f["field_key"], "field_name": f["field_name"]} for f in fields
            ]
            raise ValidationError(
                message=f"字段不存在: {','.join(sorted(invalid_keys))}",
                code="INVALID_FIELD_KEY",
                details={
                    "invalid_keys": sorted(invalid_keys),
                    "valid_fields": valid_fields,
                },
            )

        # 生成 entry_id
        entry_id = f"{self._ENTRY_ID_PREFIX}{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()

        # 构造 INSERT：只插入 data 中出现的字段 + id/created_at/updated_at
        columns = ["id", "created_at", "updated_at"]
        placeholders = ["?", "?", "?"]
        values: list[Any] = [entry_id, now, now]
        for key in data:
            columns.append(key)
            placeholders.append("?")
            values.append(data[key])

        sql = f"INSERT INTO {data_table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, tuple(values))
                logger.info(
                    "录入自定义记录成功: type_id=%s, entry_id=%s, table=%s",
                    type_id,
                    entry_id,
                    data_table,
                )
                return entry_id
        except sqlite3.Error as e:
            logger.error("录入自定义记录失败: type_id=%s, error=%s", type_id, e)
            raise DataAccessError(
                message="录入自定义记录失败",
                details={"type_id": type_id, "error": str(e)},
                cause=e,
            ) from e

    def query_entries(
        self,
        type_id: str,
        date_range: tuple[str | None, str | None] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        按日期范围分页查询记录（date_range 过滤 created_at，按 created_at DESC 排序）

        Args:
            type_id: 类型 ID
            date_range: (start, end) 元组，任一侧可为 None 表示不加约束；None 整体不筛选
            page: 页码，从 1 开始
            page_size: 每页条数

        Returns:
            tuple: (记录列表, 总记录数)

        Raises:
            EntityNotFoundError: 类型不存在
            DataAccessError: 数据库操作失败
        """
        _, data_table = self._get_type_and_table(type_id)

        where_clauses: list[str] = []
        params: list[Any] = []
        if date_range:
            start, end = date_range
            if start:
                where_clauses.append("created_at >= ?")
                params.append(start)
            if end:
                where_clauses.append("created_at <= ?")
                params.append(end)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        offset = (page - 1) * page_size

        # COUNT 查询获取总记录数
        count_sql = f"SELECT COUNT(*) FROM {data_table} {where_sql}"
        # 数据查询
        data_sql = (
            f"SELECT * FROM {data_table} {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        )
        data_params = list(params) + [page_size, offset]

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(count_sql, tuple(params))
                total_count = cursor.fetchone()[0]
                cursor.execute(data_sql, tuple(data_params))
                rows = [dict(row) for row in cursor.fetchall()]
            return rows, total_count
        except sqlite3.Error as e:
            logger.error("查询自定义记录失败: type_id=%s, error=%s", type_id, e)
            raise DataAccessError(
                message="查询自定义记录失败",
                details={"type_id": type_id, "error": str(e)},
                cause=e,
            ) from e

    def get_entry(self, type_id: str, entry_id: str) -> dict[str, Any] | None:
        """
        获取单条记录

        Args:
            type_id: 类型 ID
            entry_id: 记录 ID

        Returns:
            Optional[Dict]: 记录字典，不存在返回 None

        Raises:
            EntityNotFoundError: 类型不存在
            DataAccessError: 数据库操作失败
        """
        _, data_table = self._get_type_and_table(type_id)
        try:
            return self._query_one(
                f"SELECT * FROM {data_table} WHERE id = ?",
                (entry_id,),
            )
        except sqlite3.Error as e:
            logger.error(
                "获取自定义记录失败: type_id=%s, entry_id=%s, error=%s",
                type_id,
                entry_id,
                e,
            )
            raise DataAccessError(
                message="获取自定义记录失败",
                details={"type_id": type_id, "entry_id": entry_id, "error": str(e)},
                cause=e,
            ) from e

    def delete_entry(self, type_id: str, entry_id: str) -> bool:
        """
        删除单条记录

        Args:
            type_id: 类型 ID
            entry_id: 记录 ID

        Returns:
            bool: 是否成功

        Raises:
            EntityNotFoundError: 类型不存在 / 记录不存在
            DataAccessError: 数据库操作失败
        """
        _, data_table = self._get_type_and_table(type_id)
        deleted = False
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"DELETE FROM {data_table} WHERE id = ?",
                    (entry_id,),
                )
                deleted = cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(
                "删除自定义记录失败: type_id=%s, entry_id=%s, error=%s",
                type_id,
                entry_id,
                e,
            )
            raise DataAccessError(
                message="删除自定义记录失败",
                details={"type_id": type_id, "entry_id": entry_id, "error": str(e)},
                cause=e,
            ) from e

        # 在 with 块外抛出，避免连接以未 commit/rollback 状态归还池
        if not deleted:
            raise EntityNotFoundError(entity_type="CustomRecordEntry", entity_id=entry_id)
        logger.info(
            "删除自定义记录成功: type_id=%s, entry_id=%s",
            type_id,
            entry_id,
        )
        return True

    # ==================== 配置更新 (Slice 6) ====================

    def update_type_config(
        self,
        type_id: str,
        card_template: str | None = None,
        icon: str | None = None,
        accent_color: str | None = None,
    ) -> bool:
        """
        更新类型展示配置（card_template/icon/accent_color）

        Args:
            type_id: 类型 ID
            card_template: 卡片模板（clean|paper|minimal|bold|metric），None 表示不更新
            icon: 图标名，None 表示不更新
            accent_color: 强调色，None 表示不更新

        Returns:
            bool: 是否成功

        Raises:
            EntityNotFoundError: 类型不存在
            DataAccessError: 数据库操作失败
        """
        set_clauses: list[str] = []
        params: list[Any] = []
        if card_template is not None:
            set_clauses.append("card_template = ?")
            params.append(card_template)
        if icon is not None:
            set_clauses.append("icon = ?")
            params.append(icon)
        if accent_color is not None:
            set_clauses.append("accent_color = ?")
            params.append(accent_color)

        if not set_clauses:
            # 没有需要更新的字段
            return True

        # 始终更新 updated_at
        set_clauses.append("updated_at = ?")
        now = datetime.now(timezone.utc).isoformat()
        params.append(now)

        params.append(type_id)
        sql = f"UPDATE custom_record_types SET {', '.join(set_clauses)} WHERE id = ?"

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, tuple(params))
                updated = cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error("更新类型配置失败: type_id=%s, error=%s", type_id, e)
            raise DataAccessError(
                message="更新类型配置失败",
                details={"type_id": type_id, "error": str(e)},
                cause=e,
            ) from e

        if not updated:
            raise EntityNotFoundError(entity_type="CustomRecordType", entity_id=type_id)
        logger.info("更新类型配置成功: type_id=%s", type_id)
        return True

    def update_field_role(
        self,
        type_id: str,
        field_id: str,
        display_role: str,
    ) -> bool:
        """
        更新字段展示角色（display_role）

        Args:
            type_id: 类型 ID
            field_id: 字段 ID
            display_role: 展示角色（auto|title|main|chip|hidden）

        Returns:
            bool: 是否成功

        Raises:
            EntityNotFoundError: 字段不存在
            DataAccessError: 数据库操作失败
        """
        sql = "UPDATE custom_record_fields SET display_role = ? WHERE id = ? AND type_id = ?"
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (display_role, field_id, type_id))
                updated = cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(
                "更新字段角色失败: type_id=%s, field_id=%s, error=%s",
                type_id,
                field_id,
                e,
            )
            raise DataAccessError(
                message="更新字段角色失败",
                details={"type_id": type_id, "field_id": field_id, "error": str(e)},
                cause=e,
            ) from e

        if not updated:
            raise EntityNotFoundError(entity_type="CustomRecordField", entity_id=field_id)
        logger.info(
            "更新字段角色成功: type_id=%s, field_id=%s, display_role=%s",
            type_id,
            field_id,
            display_role,
        )
        return True
