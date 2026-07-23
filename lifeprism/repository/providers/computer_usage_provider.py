"""
Computer Usage 数据提供者

职责：提供 user_app_behavior_log 表的所有数据访问接口
"""

from typing import Any

from lifeprism.repository.base_providers import LWBaseDataProvider
from lifeprism.repository.exceptions import EntityNotFoundError
from lifeprism.repository.providers.common_query_options import QueryOptions
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import ValidationError

logger = get_logger(__name__)


class ComputerUsageProvider(LWBaseDataProvider):
    """
    Computer Usage 数据提供者

    职责：提供 user_app_behavior_log 表的所有数据访问接口
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "user_app_behavior_log"
    _PRIMARY_KEY = "id"
    _DATE_FIELD = None
    _TIME_FIELD = "start_time"
    _ON_CONFLICT = "replace"

    _FILTER_FIELDS: set[str] = {
        "id",
        "start_time",
        "end_time",
        "duration",
        "app",
        "title",
        "is_multipurpose_app",
        "category_id",
        "sub_category_id",
        "link_to_goal_id",
    }
    _ORDER_FIELDS: set[str] = {"id", "start_time", "end_time", "duration"}
    _SELECT_FIELDS: set[str] = {
        "id",
        "start_time",
        "end_time",
        "duration",
        "app",
        "title",
        "is_multipurpose_app",
        "category_id",
        "sub_category_id",
        "link_to_goal_id",
    }
    _UPDATE_FIELDS: set[str] = {
        "start_time",
        "end_time",
        "duration",
        "app",
        "title",
        "is_multipurpose_app",
        "category_id",
        "sub_category_id",
        "link_to_goal_id",
    }

    # ==================== 核心 CRUD 方法 ====================

    def query_computer_usage(
        self, options: QueryOptions | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        """
        通用查询接口

        Args:
            options: 查询选项

        Returns:
            (记录列表, 总记录数)
        """
        return self._generic_query(options)

    def get_computer_usage_by_id(self, record_id: str) -> dict[str, Any] | None:
        """
        根据 ID 获取单条记录

        Args:
            record_id: 记录 ID

        Returns:
            dict | None: 记录或 None
        """
        options = QueryOptions(filters={self._PRIMARY_KEY: record_id})
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def create_computer_usage(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        创建记录

        Args:
            data: 记录数据

        Returns:
            dict: 创建后的完整记录

        Raises:
            ValueError: 字段不合法
        """
        allowed_fields = self._UPDATE_FIELDS | {self._PRIMARY_KEY}
        invalid_fields = set(data.keys()) - allowed_fields
        if invalid_fields:
            raise ValidationError(
                message=f"无效的插入字段: {invalid_fields}",
                code="VALIDATION_FAILED",
                details={"invalid_fields": list(invalid_fields)},
            )

        record_id = self._generic_insert(data)
        if record_id:
            return self.get_computer_usage_by_id(str(record_id)) or {}
        return {}

    def update_computer_usage(self, record_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        """
        更新记录

        Args:
            record_id: 记录 ID
            data: 要更新的字段

        Returns:
            dict | None: 更新后的完整记录或 None
        """
        update_data = {k: v for k, v in data.items() if v is not None}
        if not update_data:
            return self.get_computer_usage_by_id(record_id)

        invalid_fields = set(update_data.keys()) - self._UPDATE_FIELDS
        if invalid_fields:
            raise ValidationError(
                message=f"无效的更新字段: {invalid_fields}",
                code="VALIDATION_FAILED",
                details={"invalid_fields": list(invalid_fields)},
            )

        affected_rows = self._generic_update(record_id, update_data)
        if affected_rows:
            return self.get_computer_usage_by_id(record_id)
        logger.error("更新ComputerUsage失败: record_id=%s, 记录不存在", record_id)
        raise EntityNotFoundError("ComputerUsage", record_id)

    def delete_computer_usage(self, record_id: str) -> bool:
        """
        删除记录

        Args:
            record_id: 记录 ID

        Returns:
            bool: 是否删除成功
        """
        return self._generic_delete(record_id)

    # ==================== 批量操作方法 ====================

    # 允许调用方显式传入的系统字段（不在 _UPDATE_FIELDS 中但合法）
    _SYSTEM_UPDATE_FIELDS: set[str] = {"updated_at"}

    def batch_update_computer_usage(self, record_ids: list[str], data: dict[str, Any]) -> int:
        """
        批量更新记录

        动态构建 SET 子句 + IN 占位符，单次 SQL。不自动更新 updated_at
        （由调用方决定是否传入）。

        Args:
            record_ids: 记录 ID 列表
            data: 要更新的字段（如 {"category_id":..., "sub_category_id":...}）
                None 值会被跳过（不修改该字段）

        Returns:
            int: 受影响行数

        Raises:
            ValidationError: 字段不在白名单内
        """
        if not record_ids:
            return 0

        # 过滤 None 值（与 update_computer_usage 一致：None 表示不修改）
        update_data = {k: v for k, v in data.items() if v is not None}
        if not update_data:
            return 0

        # 白名单校验（允许 _UPDATE_FIELDS + updated_at）
        allowed_fields = self._UPDATE_FIELDS | self._SYSTEM_UPDATE_FIELDS
        invalid_fields = set(update_data.keys()) - allowed_fields
        if invalid_fields:
            raise ValidationError(
                message=f"无效的更新字段: {invalid_fields}",
                code="VALIDATION_FAILED",
                details={"invalid_fields": list(invalid_fields)},
            )

        # 动态构建 SET + IN 子句
        set_clause = ", ".join([f"{key} = ?" for key in update_data])
        placeholders = ", ".join(["?"] * len(record_ids))
        sql = (
            f"UPDATE {self._TABLE_NAME} "
            f"SET {set_clause} "
            f"WHERE {self._PRIMARY_KEY} IN ({placeholders})"
        )
        values = list(update_data.values()) + [str(rid) for rid in record_ids]

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, values)
            conn.commit()
            return cursor.rowcount

    def batch_delete_computer_usage(self, record_ids: list[str]) -> int:
        """
        批量删除记录（走 _generic_batch_delete 写墓碑）

        调用基类 _generic_batch_delete，内部为每条记录写墓碑到 deletion_log +
        批量 DELETE 在同一事务。

        Args:
            record_ids: 记录 ID 列表

        Returns:
            int: 删除行数
        """
        return self._generic_batch_delete(record_ids)

    # ==================== 动态 WHERE 更新方法 ====================

    # 设计权衡说明（code review Issue 1/2/3/5/8）：
    # update_by_filter 是为 update_logs_by_app_title 的动态 WHERE 需求设计的通用方法
    # （支持 app = ? AND title = ? AND start_time >= ? AND start_time <= ?）。
    # update_computer_usage / batch_update_computer_usage 只支持按 ID 更新，无法满足此需求。
    #
    # None 语义差异（Issue 3）：
    # - update_computer_usage：None = 跳过不修改（走 _generic_update 过滤 None）
    # - update_by_filter：None = 清除为 NULL（直接传入 SQL SET field = NULL）
    # 这两种语义在同一类中并存是有意的设计——update_by_filter 用于"清除"语义
    # （前端"选择 -- Select --"场景），update_computer_usage 用于"部分更新"语义。
    # 调用方需根据场景选择正确的方法。
    #
    # 绕过 _generic_update（Issue 5）：
    # update_by_filter 和 batch_update_computer_usage 不经过 _generic_update，
    # 不会自动管理 updated_at。Service 层需显式传入 updated_at 触发 LWW 同步。
    # _SYSTEM_UPDATE_FIELDS = {"updated_at"}（Issue 8）允许 updated_at 通过白名单。
    #
    # where_conditions 支持的操作符后缀（key 以这些后缀结尾时剥除得到字段名）
    _WHERE_OPERATOR_SUFFIXES: tuple[str, ...] = (" >=", " <=", " >", " <", " !=", " IN")

    def update_by_filter(self, set_fields: dict[str, Any], where_conditions: dict[str, Any]) -> int:
        """
        按条件更新记录（动态 WHERE）

        支持操作符后缀（如 "start_time >="）。where_conditions 的 key 必须在
        _FILTER_FIELDS 白名单内（校验时先剥除操作符后缀再比对）。
        set_fields 中 None 值表示清除该字段为 NULL。

        Args:
            set_fields: 要更新的字段（None 值表示清除该字段为 NULL）
            where_conditions: WHERE 条件（如 {"app":..., "start_time >=":...}）

        Returns:
            int: 受影响行数

        Raises:
            ValidationError: set_fields 或 where_conditions 的字段不在白名单内
        """
        if not set_fields:
            return 0

        # 1. 校验 set_fields（允许 _UPDATE_FIELDS + updated_at）
        allowed_set = self._UPDATE_FIELDS | self._SYSTEM_UPDATE_FIELDS
        invalid_set = set(set_fields.keys()) - allowed_set
        if invalid_set:
            raise ValidationError(
                message=f"无效的更新字段: {invalid_set}",
                code="VALIDATION_FAILED",
                details={"invalid_fields": list(invalid_set)},
            )

        # 2. 校验 where_conditions 并构建 WHERE 子句
        where_parts: list[str] = []
        where_params: list[Any] = []
        for key, value in where_conditions.items():
            field_name, op = self._parse_where_key(key)
            if field_name not in self._FILTER_FIELDS:
                raise ValidationError(
                    message=f"无效的筛选字段: {field_name}",
                    code="VALIDATION_FAILED",
                    details={"invalid_field": field_name},
                )
            if value is None:
                where_parts.append(f"{field_name} IS NULL")
            elif op == "IN":
                # IN 子句：value 必须是 list/tuple，展开为 IN (?, ?, ?)
                if not isinstance(value, (list, tuple)):
                    raise ValidationError(
                        message=f"IN 操作符要求 value 为 list 或 tuple，实际类型: {type(value).__name__}",
                        code="VALIDATION_FAILED",
                        details={"field": field_name, "value_type": type(value).__name__},
                    )
                if len(value) == 0:
                    # 空 list：IN () 在 SQLite 中语法错误，用 1=0 保证不匹配任何行
                    where_parts.append("1=0")
                else:
                    placeholders = ", ".join(["?"] * len(value))
                    where_parts.append(f"{field_name} IN ({placeholders})")
                    where_params.extend(value)
            else:
                where_parts.append(f"{field_name} {op} ?")
                where_params.append(value)

        # 3. 构建 SET 子句（None = SET field = NULL，sqlite3 将 None 转为 NULL）
        set_clause = ", ".join([f"{key} = ?" for key in set_fields])
        set_params = list(set_fields.values())

        # 4. 构建 WHERE 子句
        where_clause = " AND ".join(where_parts) if where_parts else "1=1"

        sql = f"UPDATE {self._TABLE_NAME} SET {set_clause} WHERE {where_clause}"
        values = set_params + where_params

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, values)
            conn.commit()
            return cursor.rowcount

    def _parse_where_key(self, key: str) -> tuple[str, str]:
        """解析 where_conditions 的 key，剥除操作符后缀

        Args:
            key: 原始 key（如 "start_time >=" 或 "app"）

        Returns:
            (字段名, 操作符)，如 ("start_time", ">=") 或 ("app", "=")
        """
        for suffix in self._WHERE_OPERATOR_SUFFIXES:
            if key.endswith(suffix):
                return key[: -len(suffix)].strip(), suffix.strip()
        return key, "="

    # ==================== 聚合查询方法 ====================

    def get_total_duration(self, start_utc: str, end_utc: str) -> int:
        """
        获取时间范围内总活跃时长

        Args:
            start_utc: 开始时间（UTC ISO 8601）
            end_utc: 结束时间（UTC ISO 8601）

        Returns:
            int: 总时长（秒），无数据返回 0

        注意：时区转换由 Service 层完成，Provider 只接收 UTC。
        """
        sql = (
            f"SELECT SUM(duration) FROM {self._TABLE_NAME} "
            f"WHERE start_time >= ? AND start_time <= ?"
        )
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (start_utc, end_utc))
            result = cursor.fetchone()[0]
            return int(result) if result is not None else 0

    def get_top_groups_by_duration(
        self, group_field: str, start_utc: str, end_utc: str, top_n: int
    ) -> list[tuple[str, int]]:
        """
        按指定字段分组聚合 Top N

        合并了原 get_top_applications 和 get_top_title，通过 group_field 参数区分。

        Args:
            group_field: 分组字段（如 "app" 或 "title"），必须在 _FILTER_FIELDS 白名单内
            start_utc: 开始时间（UTC ISO 8601）
            end_utc: 结束时间（UTC ISO 8601）
            top_n: 返回前 N 条

        Returns:
            list[tuple[str, int]]: [(name, duration), ...]，按 duration 降序

        Raises:
            ValidationError: group_field 不在 _FILTER_FIELDS 白名单内

        注意：时区转换由 Service 层完成，Provider 只接收 UTC。
        """
        if group_field not in self._FILTER_FIELDS:
            raise ValidationError(
                message=f"无效的分组字段: {group_field}",
                code="VALIDATION_FAILED",
                details={"invalid_field": group_field},
            )

        sql = (
            f"SELECT {group_field}, CAST(SUM(duration) AS INTEGER) "
            f"FROM {self._TABLE_NAME} "
            f"WHERE start_time >= ? AND start_time <= ? "
            f"GROUP BY {group_field} "
            f"ORDER BY CAST(SUM(duration) AS INTEGER) DESC "
            f"LIMIT ?"
        )
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (start_utc, end_utc, top_n))
            return [(row[0], row[1]) for row in cursor.fetchall()]
