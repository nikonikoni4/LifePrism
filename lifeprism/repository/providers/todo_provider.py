"""
Todo 数据提供者（重构版）
提供 todo_list 表的数据库操作（支持多层级 parent_id 关系）
"""

import sqlite3
import uuid
from typing import Any

from lifeprism.repository.base_providers import LWBaseDataProvider
from lifeprism.repository.providers.common_query_options import QueryOptions
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import ConflictError, DataAccessError, ValidationError
from lifeprism.utils.time_utils import get_utc_now_iso

logger = get_logger(__name__)


def generate_todo_id() -> str:
    """生成 todo ID，格式：t-{uuid[:8]}"""
    return f"t-{uuid.uuid4().hex[:8]}"


class TodoProvider(LWBaseDataProvider):
    """
    Todo 数据提供者

    职责：提供 todo_list 表的所有数据访问接口
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "todo_list"
    _PRIMARY_KEY = "id"
    _DATE_FIELD = "date"
    _TIME_FIELD = None
    _ON_CONFLICT = "abort"  # todo 不应该有重复 ID，冲突时应该报错

    # 白名单字段集合（用于防止 SQL 注入）
    _FILTER_FIELDS: set[str] = {
        "id",
        "content",
        "state",
        "link_to_goal_id",
        "date",
        "expected_finished_at",
        "actual_finished_at",
        "cross_day",
        "folder_id",
        "parent_id",
        "plan_doc_id",
        "waid_order",
        "created_at",
        "updated_at",
    }
    _ORDER_FIELDS: set[str] = {
        "id",
        "order_index",
        "pool_order_index",
        "created_at",
        "waid_order",
        "date",
    }
    _SELECT_FIELDS: set[str] = {
        "id",
        "order_index",
        "pool_order_index",
        "content",
        "color",
        "state",
        "link_to_goal_id",
        "date",
        "expected_finished_at",
        "actual_finished_at",
        "cross_day",
        "folder_id",
        "parent_id",
        "plan_doc_id",
        "delay_days",
        "delay_reason",
        "waid_order",
        "created_at",
        "updated_at",
    }
    _UPDATE_FIELDS: set[str] = {
        "content",
        "color",
        "state",
        "link_to_goal_id",
        "date",
        "expected_finished_at",
        "actual_finished_at",
        "cross_day",
        "pool_order_index",
        "folder_id",
        "order_index",
        "parent_id",
        "plan_doc_id",
        "delay_days",
        "delay_reason",
        "waid_order",
    }

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    # ==================== 核心方法（使用通用方法） ====================

    def query_todos(self, options: QueryOptions | None = None) -> tuple[list[dict[str, Any]], int]:
        """
        通用查询接口（使用基类方法）

        Args:
            options: 查询选项
                - 支持 date_range: 日期范围查询（基于 date 字段）
                - 支持 filters: 字段过滤
                - 支持 order_by/order_desc: 排序
                - 支持 page/page_size: 分页

        Returns:
            (记录列表, 总记录数)

        Examples:
            # 查询日期范围
            options = QueryOptions(date_range=("2026-04-01", "2026-04-30"))
            todos, total = provider.query_todos(options)

            # 查询特定状态
            options = QueryOptions(filters={'state': 'active'})
            todos, total = provider.query_todos(options)
        """
        return self._generic_query(options)

    def get_todos_by_date(self, date: str, include_cross_day: bool = True) -> list[dict[str, Any]]:
        """
        获取指定日期的任务列表

        Args:
            date: 日期（YYYY-MM-DD 格式）
            include_cross_day: 是否包含跨天未完成任务

        Returns:
            List[Dict]: 任务列表（可能为空）

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                if include_cross_day:
                    # 获取当天任务 + 跨天未完成任务
                    sql = """
                    SELECT * FROM todo_list
                    WHERE date = ?
                       OR (cross_day = 1 AND state = 'active' AND date < ?)
                    ORDER BY order_index ASC
                    """
                    cursor.execute(sql, (date, date))
                else:
                    # 仅获取当天任务
                    sql = """
                    SELECT * FROM todo_list
                    WHERE date = ?
                    ORDER BY order_index ASC
                    """
                    cursor.execute(sql, (date,))

                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()

                return [dict(zip(columns, row, strict=False)) for row in rows]

        except sqlite3.Error as e:
            logger.error("获取任务列表失败 (date=%s): %s", date, e)
            raise DataAccessError(
                message="获取任务列表失败", details={"date": date, "error": str(e)}
            ) from e

    def get_todo_by_id(self, todo_id: str) -> dict[str, Any] | None:
        """
        按 ID 获取单个任务

        Args:
            todo_id: 任务 ID

        Returns:
            Optional[Dict]: 任务数据，不存在返回 None
        """
        options = QueryOptions(filters={self._PRIMARY_KEY: todo_id}, order_by="id")
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def create_todo(self, data: dict[str, Any]) -> str:
        """
        创建新任务

        Args:
            data: 任务数据
                - 可包含 'id'，未提供则自动生成
                - 必须包含 'order_index'（由聚合层计算）

        Returns:
            str: 新任务 ID

        Raises:
            ValidationError: 数据验证失败（如缺少 order_index）
            ConflictError: 记录已存在
            DataAccessError: 数据库操作失败
        """
        try:
            # 验证必填字段
            if "order_index" not in data:
                raise ValidationError("order_index is required")

            # 生成 ID（如果未提供）
            if "id" not in data:
                data["id"] = generate_todo_id()

            # 白名单验证
            allowed_fields = {
                "id",
                "order_index",
                "pool_order_index",
                "content",
                "color",
                "state",
                "link_to_goal_id",
                "date",
                "expected_finished_at",
                "actual_finished_at",
                "cross_day",
                "folder_id",
                "parent_id",
                "plan_doc_id",
                "delay_days",
                "delay_reason",
                "waid_order",
            }
            invalid_fields = set(data.keys()) - allowed_fields
            if invalid_fields:
                raise ValidationError(f"Invalid insert fields: {invalid_fields}")

            # 使用 _generic_insert
            todo_id = self._generic_insert(data, on_conflict=self._ON_CONFLICT)
            logger.info("创建任务成功，ID: %s", todo_id)
            return todo_id

        except ValidationError:
            raise
        except sqlite3.Error as e:
            logger.error("创建任务失败: %s", e)
            raise DataAccessError(message="创建任务失败", details={"error": str(e)}) from e

    def update_todo(self, todo_id: str, data: dict[str, Any]) -> bool:
        """
        更新任务

        Args:
            todo_id: 任务 ID
            data: 要更新的字段

        Returns:
            bool: 是否成功

        Raises:
            ValidationError: 字段验证失败
            DataAccessError: 数据库操作失败
        """
        if not data:
            return True

        try:
            # 白名单验证
            invalid_fields = set(data.keys()) - self._UPDATE_FIELDS
            if invalid_fields:
                raise ValidationError(f"Invalid update fields: {invalid_fields}")

            # 预处理 cross_day 布尔值为整数
            if "cross_day" in data:
                data["cross_day"] = 1 if data["cross_day"] else 0

            # 使用 _generic_update 自动处理 updated_at
            success = self._generic_update(todo_id, data)

            if success:
                logger.info("更新任务 %s 成功", todo_id)
            return success

        except ValidationError:
            raise
        except sqlite3.Error as e:
            logger.error("更新任务 %s 失败: %s", todo_id, e)
            raise DataAccessError(
                message="更新任务失败", details={"todo_id": todo_id, "error": str(e)}
            ) from e

    def delete_todo(self, todo_id: str) -> bool:
        """
        删除任务

        Args:
            todo_id: 任务 ID

        Returns:
            bool: 是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            success = self._generic_delete(todo_id)
            if success:
                logger.info("删除任务 %s 成功", todo_id)
            return success
        except sqlite3.Error as e:
            logger.error("删除任务 %s 失败: %s", todo_id, e)
            raise DataAccessError(
                message="删除任务失败", details={"todo_id": todo_id, "error": str(e)}
            ) from e

    def delete_todo_cascade(self, todo_id: str) -> int:
        """
        级联删除任务及其所有子任务（todo_list 中的 parent_id 关系）

        Args:
            todo_id: 任务 ID

        Returns:
            int: 删除的总任务数（包括子任务）

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # 递归获取所有子任务 ID
                def get_all_descendant_ids(parent_id: str) -> list[str]:
                    cursor.execute("SELECT id FROM todo_list WHERE parent_id = ?", (parent_id,))
                    child_ids = [row[0] for row in cursor.fetchall()]
                    all_ids = list(child_ids)
                    for child_id in child_ids:
                        all_ids.extend(get_all_descendant_ids(child_id))
                    return all_ids

                # 获取所有要删除的 ID（包括自身）
                all_ids = get_all_descendant_ids(todo_id)
                all_ids.append(todo_id)

                # 从叶子节点开始删除（反向顺序）
                deleted_count = 0
                for tid in reversed(all_ids):
                    cursor.execute("DELETE FROM todo_list WHERE id = ?", (tid,))
                    if cursor.rowcount > 0:
                        deleted_count += 1

                logger.info("级联删除任务 %s 成功，共删除 %s 个任务", todo_id, deleted_count)
                return deleted_count

        except sqlite3.Error as e:
            logger.error("级联删除任务 %s 失败: %s", todo_id, e)
            raise DataAccessError(
                message="级联删除任务失败", details={"todo_id": todo_id, "error": str(e)}
            ) from e

    def get_child_todos(self, parent_id: str) -> list[dict[str, Any]]:
        """
        获取直接子任务列表

        Args:
            parent_id: 父任务 ID

        Returns:
            List[Dict]: 子任务列表（可能为空）

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            options = QueryOptions(
                filters={"parent_id": parent_id}, order_by="pool_order_index", order_desc=False
            )
            results, _ = self._generic_query(options)
            return results
        except sqlite3.Error as e:
            logger.error("获取子任务列表失败 (parent_id=%s): %s", parent_id, e)
            raise DataAccessError(
                message="获取子任务列表失败", details={"parent_id": parent_id, "error": str(e)}
            ) from e

    def batch_delete_todos(self, todo_ids: list[str]) -> int:
        """
        批量删除任务（不级联删除子任务）

        Args:
            todo_ids: 任务 ID 列表

        Returns:
            int: 成功删除的数量

        Raises:
            DataAccessError: 数据库操作失败
        """
        if not todo_ids:
            return 0

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                deleted_count = 0
                for todo_id in todo_ids:
                    cursor.execute("DELETE FROM todo_list WHERE id = ?", (todo_id,))
                    if cursor.rowcount > 0:
                        deleted_count += 1

                logger.info("批量删除 %s 个任务成功", deleted_count)
                return deleted_count

        except sqlite3.Error as e:
            logger.error("批量删除任务失败: %s", e)
            raise DataAccessError(
                message="批量删除任务失败", details={"count": len(todo_ids), "error": str(e)}
            ) from e

    def reorder_todos(self, todo_ids: list[str]) -> bool:
        """
        批量更新任务排序

        Args:
            todo_ids: 任务 ID 列表（按新顺序排列）

        Returns:
            bool: 是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                now_iso = get_utc_now_iso()
                for index, todo_id in enumerate(todo_ids):
                    cursor.execute(
                        "UPDATE todo_list SET order_index = ?, updated_at = ? WHERE id = ?",
                        (index, now_iso, todo_id),
                    )

                logger.info("重排序 %s 个任务成功", len(todo_ids))
                return True

        except sqlite3.Error as e:
            logger.error("重排序任务失败: %s", e)
            raise DataAccessError(
                message="重排序任务失败", details={"count": len(todo_ids), "error": str(e)}
            ) from e

    # ==================== Task Pool 操作 ====================

    def get_todos_by_state(self, state: str) -> list[dict[str, Any]]:
        """
        根据状态获取任务列表

        Args:
            state: 任务状态 ('active', 'completed', 'inactive')

        Returns:
            List[Dict]: 任务列表（可能为空）

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            # 对于 inactive 状态（任务池），按 pool_order_index 排序
            if state == "inactive":
                options = QueryOptions(
                    filters={"state": state}, order_by="pool_order_index", order_desc=False
                )
            else:
                options = QueryOptions(
                    filters={"state": state}, order_by="order_index", order_desc=False
                )

            results, _ = self._generic_query(options)
            return results

        except sqlite3.Error as e:
            logger.error("获取任务列表失败 (state=%s): %s", state, e)
            raise DataAccessError(
                message="获取任务列表失败", details={"state": state, "error": str(e)}
            ) from e

    def reorder_pool_todos(self, todo_ids: list[str]) -> bool:
        """
        批量更新任务池排序 (pool_order_index)

        Args:
            todo_ids: 任务 ID 列表（按新顺序排列）

        Returns:
            bool: 是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                now_iso = get_utc_now_iso()
                for index, todo_id in enumerate(todo_ids):
                    cursor.execute(
                        "UPDATE todo_list SET pool_order_index = ?, updated_at = ? WHERE id = ?",
                        (index, now_iso, todo_id),
                    )

                logger.info("重排序任务池 %s 个任务成功", len(todo_ids))
                return True

        except sqlite3.Error as e:
            logger.error("重排序任务池失败: %s", e)
            raise DataAccessError(
                message="重排序任务池失败", details={"count": len(todo_ids), "error": str(e)}
            ) from e

    def move_todo_to_folder(self, todo_id: str, folder_id: int | None) -> bool:
        """
        移动任务到指定文件夹

        Args:
            todo_id: 任务 ID
            folder_id: 目标文件夹 ID（None 表示移到根级别）

        Returns:
            bool: 是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            return self._generic_update(todo_id, {"folder_id": folder_id})
        except sqlite3.Error as e:
            logger.error("移动任务失败 (todo_id=%s): %s", todo_id, e)
            raise DataAccessError(
                message="移动任务失败",
                details={"todo_id": todo_id, "folder_id": folder_id, "error": str(e)},
            ) from e

    # ==================== 任务池查询 ====================

    def get_todos_for_taskpool(
        self,
        goal_id: str | None = None,
        plan_doc_id: str | None = None,
        state: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        获取任务池任务（支持筛选）

        Args:
            goal_id: 按目标筛选
            plan_doc_id: 按计划书筛选
            state: 按状态筛选（pool/scheduled/completed/all）

        Returns:
            List[Dict]: 任务列表（扁平结构，前端通过 parent_id 构建树，可能为空）

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            filters = {}

            if state and state != "all":
                filters["state"] = state

            if goal_id:
                filters["link_to_goal_id"] = goal_id

            if plan_doc_id:
                filters["plan_doc_id"] = plan_doc_id

            options = QueryOptions(
                filters=filters if filters else None, order_by="pool_order_index", order_desc=False
            )

            results, _ = self._generic_query(options)
            return results

        except sqlite3.Error as e:
            logger.error("获取任务池任务失败: %s", e)
            raise DataAccessError(
                message="获取任务池任务失败",
                details={
                    "goal_id": goal_id,
                    "plan_doc_id": plan_doc_id,
                    "state": state,
                    "error": str(e),
                },
            ) from e

    def get_todos_by_plan_doc(self, plan_doc_id: str) -> list[dict[str, Any]]:
        """
        获取指定计划书关联的所有任务

        Args:
            plan_doc_id: 计划书 ID

        Returns:
            List[Dict]: 任务列表（可能为空）

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            options = QueryOptions(
                filters={"plan_doc_id": plan_doc_id}, order_by="pool_order_index", order_desc=False
            )
            results, _ = self._generic_query(options)
            return results
        except sqlite3.Error as e:
            logger.error("获取计划书任务失败 (plan_doc=%s): %s", plan_doc_id, e)
            raise DataAccessError(
                message="获取计划书任务失败", details={"plan_doc_id": plan_doc_id, "error": str(e)}
            ) from e

    def batch_create_todos(self, todos: list[dict[str, Any]]) -> list[str]:
        """
        批量创建任务

        Args:
            todos: 任务数据列表（可包含 'id'，未提供则自动生成）

        Returns:
            List[str]: 新创建的任务 ID 列表

        Raises:
            ConflictError: 记录已存在
            DataAccessError: 数据库操作失败
        """
        new_ids = []
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                now_iso = get_utc_now_iso()
                for data in todos:
                    todo_id = data.get("id") or generate_todo_id()
                    columns = [
                        "id",
                        "order_index",
                        "pool_order_index",
                        "content",
                        "color",
                        "state",
                        "link_to_goal_id",
                        "date",
                        "expected_finished_at",
                        "actual_finished_at",
                        "cross_day",
                        "parent_id",
                        "plan_doc_id",
                        "delay_days",
                        "delay_reason",
                        "created_at",
                        "updated_at",
                    ]
                    values = [
                        todo_id,
                        data.get("order_index", 0),
                        data.get("pool_order_index", 0),
                        data.get("content"),
                        data.get("color", "#FFFFFF"),
                        data.get("state", "pool"),
                        data.get("link_to_goal_id"),
                        data.get("date"),
                        data.get("expected_finished_at"),
                        data.get("actual_finished_at"),
                        1 if data.get("cross_day") else 0,
                        data.get("parent_id"),
                        data.get("plan_doc_id"),
                        data.get("delay_days"),
                        data.get("delay_reason"),
                        now_iso,
                        now_iso,
                    ]

                    placeholders = ", ".join(["?" for _ in columns])
                    columns_str = ", ".join(columns)

                    cursor.execute(
                        f"INSERT INTO todo_list ({columns_str}) VALUES ({placeholders})", values
                    )
                    new_ids.append(todo_id)

                logger.info("批量创建 %s 个任务成功", len(new_ids))
                return new_ids

        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint" in str(e):
                raise ConflictError("任务已存在") from e
            raise DataAccessError("数据完整性错误") from e
        except sqlite3.Error as e:
            logger.error("批量创建任务失败: %s", e)
            raise DataAccessError(
                message="批量创建任务失败",
                details={"count": len(todos), "created": len(new_ids), "error": str(e)},
            ) from e

    def batch_update_todos(self, updates: list[dict[str, Any]]) -> int:
        """
        批量更新任务

        Args:
            updates: 更新数据列表，每项必须包含 'id' 字段

        Returns:
            int: 成功更新的数量

        Raises:
            ValidationError: 字段验证失败
            DataAccessError: 数据库操作失败
        """
        updated_count = 0
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                now_iso = get_utc_now_iso()
                for data in updates:
                    todo_id = data.get("id")
                    if not todo_id:
                        continue

                    set_clauses = []
                    values = []
                    for key, value in data.items():
                        if key in self._UPDATE_FIELDS:
                            set_clauses.append(f"{key} = ?")
                            if key == "cross_day":
                                values.append(1 if value else 0)
                            else:
                                values.append(value)

                    if not set_clauses:
                        continue

                    # 自动写入 updated_at（ISO 8601 + UTC）
                    set_clauses.append("updated_at = ?")
                    values.append(now_iso)

                    values.append(todo_id)
                    sql = f"UPDATE todo_list SET {', '.join(set_clauses)} WHERE id = ?"

                    cursor.execute(sql, values)
                    if cursor.rowcount > 0:
                        updated_count += 1

                logger.info("批量更新 %s 个任务成功", updated_count)
                return updated_count

        except sqlite3.Error as e:
            logger.error("批量更新任务失败: %s", e)
            raise DataAccessError(
                message="批量更新任务失败",
                details={"count": len(updates), "updated": updated_count, "error": str(e)},
            ) from e

    # ==================== WAID 浮窗操作 ====================

    def get_waid_todos(self) -> list[dict[str, Any]]:
        """
        获取所有 waid_order IS NOT NULL 的 todo，按 waid_order ASC 排序

        Returns:
            List[Dict]: WAID todo 列表（可能为空）

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM todo_list WHERE waid_order IS NOT NULL ORDER BY waid_order ASC"
                )
                rows = cursor.fetchall()
                if not rows:
                    return []
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row, strict=False)) for row in rows]
        except sqlite3.Error as e:
            logger.error("获取 WAID todo 列表失败: %s", e)
            raise DataAccessError(
                message="获取 WAID todo 列表失败", details={"error": str(e)}
            ) from e

    def batch_update_waid_order(self, todo_ids: list[str]) -> bool:
        """
        批量设置 waid_order，按数组索引顺序赋值 0,1,2...

        Args:
            todo_ids: todo ID 列表，索引即为新的 waid_order 值

        Returns:
            bool: 是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                now_iso = get_utc_now_iso()
                for idx, tid in enumerate(todo_ids):
                    cursor.execute(
                        "UPDATE todo_list SET waid_order = ?, updated_at = ? WHERE id = ?",
                        (idx, now_iso, tid),
                    )
                logger.info("批量更新 WAID 排序成功，共 %s 个", len(todo_ids))
                return True
        except sqlite3.Error as e:
            logger.error("批量更新 WAID 排序失败: %s", e)
            raise DataAccessError(
                message="批量更新 WAID 排序失败", details={"count": len(todo_ids), "error": str(e)}
            ) from e

    def clear_waid_order(self, todo_id: str) -> bool:
        """
        将指定 todo 的 waid_order 设为 NULL（从浮窗移除）

        Args:
            todo_id: 任务 ID

        Returns:
            bool: 是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            return self._generic_update(todo_id, {"waid_order": None})
        except sqlite3.Error as e:
            logger.error("清除 WAID 排序失败 (todo_id=%s): %s", todo_id, e)
            raise DataAccessError(
                message="清除 WAID 排序失败", details={"todo_id": todo_id, "error": str(e)}
            ) from e
