"""
Plan Doc 数据提供者（重构版）

职责：提供 plan_doc 表的所有数据访问接口
"""
import sqlite3
from typing import Dict, Any, Optional, List, Tuple, Set
from lifeprism.repository.base_providers import LWBaseDataProvider
from lifeprism.repository.providers.common_query_options import QueryOptions
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import DataAccessError, ConflictError, ValidationError

logger = get_logger(__name__)


class PlanDocProvider(LWBaseDataProvider):
    """
    计划书数据提供者

    职责：提供 plan_doc 表的所有数据访问接口
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "plan_doc"
    _PRIMARY_KEY = "id"
    _DATE_FIELD = None
    _TIME_FIELD = None
    _ON_CONFLICT = "abort"  # 计划书不应该有重复 ID，冲突时应该报错

    # 白名单字段集合（用于防止 SQL 注入）
    _FILTER_FIELDS: Set[str] = {
        'id', 'goal_id', 'status', 'order_index',
        'created_at', 'updated_at'
    }
    _ORDER_FIELDS: Set[str] = {
        'id', 'order_index', 'created_at', 'updated_at'
    }
    _SELECT_FIELDS: Set[str] = {
        'id', 'goal_id', 'content', 'status', 'order_index',
        'created_at', 'updated_at'
    }
    _UPDATE_FIELDS: Set[str] = {
        'status', 'order_index'
    }

    # ==================== 核心 CRUD 方法 ====================

    def query_plan_docs(
        self,
        options: Optional[QueryOptions] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        通用查询接口

        Args:
            options: 查询选项
                - 支持 filters: 字段过滤
                - 支持 order_by/order_desc: 排序
                - 支持 page/page_size: 分页

        Returns:
            (记录列表, 总记录数)

        Examples:
            # 基本查询
            options = QueryOptions(filters={'status': 'active'})
            records, total = provider.query_plan_docs(options)

            # 分页查询
            options = QueryOptions(page=1, page_size=20)
            records, total = provider.query_plan_docs(options)
        """
        return self._generic_query(options)

    def get_all_plan_docs(self) -> List[Dict[str, Any]]:
        """
        获取所有计划书

        Returns:
            List[Dict]: 计划书列表，按排序索引升序排列

        Raises:
            DataAccessError: 数据库访问失败
        """
        try:
            # 使用原生 SQL 保持复杂排序逻辑
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM plan_doc
                    ORDER BY order_index ASC, created_at DESC
                    """
                )

                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()

                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            logger.error("获取所有计划书失败: %s", e)
            raise DataAccessError(f"获取所有计划书失败: {e}") from e

    def get_plan_docs_by_goal(self, goal_id: str) -> List[Dict[str, Any]]:
        """
        获取指定目标的所有计划书

        Args:
            goal_id: 目标 ID

        Returns:
            List[Dict]: 计划书列表，按排序索引升序排列

        Raises:
            DataAccessError: 数据库访问失败
        """
        try:
            # 使用原生 SQL 保持复杂排序逻辑
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM plan_doc
                    WHERE goal_id = ?
                    ORDER BY order_index ASC, created_at DESC
                    """,
                    (goal_id,)
                )

                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()

                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            logger.error("获取目标 %s 的计划书失败: %s", goal_id, e)
            raise DataAccessError(f"获取目标 {goal_id} 的计划书失败: {e}") from e

    def get_plan_doc_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        按 ID 获取单个计划书

        Args:
            doc_id: 计划书 ID (格式: plandoc-xxx)

        Returns:
            Optional[Dict]: 计划书数据，不存在返回 None
        """
        options = QueryOptions(
            filters={self._PRIMARY_KEY: doc_id},
            order_by='id'
        )
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def create_plan_doc(self, data: Dict[str, Any]) -> Optional[str]:
        """
        创建新计划书

        Args:
            data: 计划书数据
                - 必须包含 'id'（作为主键）
                - 必须包含 'order_index'（由聚合层计算）

        Returns:
            Optional[str]: 新计划书 ID，失败返回 None

        Raises:
            ValidationError: 数据验证失败（如 id 或 order_index 为空）
            ConflictError: 主键冲突
            DataAccessError: 数据库访问失败
        """
        try:
            # 验证必填字段
            doc_id = data.get('id', '')
            if not doc_id:
                raise ValidationError("创建计划书失败: id 不能为空")

            if 'order_index' not in data:
                raise ValidationError("创建计划书失败: order_index 不能为空")

            # 白名单验证
            allowed_fields = {'id', 'goal_id', 'status', 'order_index'}
            invalid_fields = set(data.keys()) - allowed_fields
            if invalid_fields:
                raise ValidationError(f"Invalid insert fields: {invalid_fields}")

            # 使用 _generic_insert
            result_id = self._generic_insert(data, on_conflict=self._ON_CONFLICT)
            logger.info("创建计划书成功，ID: %s", doc_id)
            return doc_id

        except ValidationError:
            raise
        except Exception as e:
            logger.error("创建计划书失败: %s", e)
            raise DataAccessError(f"创建计划书失败: {e}") from e

    def update_plan_doc(self, doc_id: str, data: Dict[str, Any]) -> bool:
        """
        更新计划书

        Args:
            doc_id: 计划书 ID (格式: plandoc-xxx)
            data: 要更新的字段

        Returns:
            bool: 是否成功

        Raises:
            ValidationError: 字段验证失败
            DataAccessError: 数据库访问失败
        """
        if not data:
            return True

        try:
            # 白名单验证
            invalid_fields = set(data.keys()) - self._UPDATE_FIELDS
            if invalid_fields:
                raise ValidationError(f"Invalid update fields: {invalid_fields}")

            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                set_clauses = []
                values = []
                for key, value in data.items():
                    if key in self._UPDATE_FIELDS:
                        set_clauses.append(f"{key} = ?")
                        values.append(value)

                if not set_clauses:
                    return True

                # 添加 updated_at
                set_clauses.append("updated_at = datetime('now')")

                values.append(doc_id)
                sql = f"UPDATE plan_doc SET {', '.join(set_clauses)} WHERE id = ?"

                cursor.execute(sql, values)
                success = cursor.rowcount > 0

                if success:
                    logger.info("更新计划书 %s 成功", doc_id)
                return success

        except ValidationError:
            raise
        except Exception as e:
            logger.error("更新计划书 %s 失败: %s", doc_id, e)
            raise DataAccessError(f"更新计划书 {doc_id} 失败: {e}") from e

    def delete_plan_doc(self, doc_id: str) -> bool:
        """
        删除计划书

        Args:
            doc_id: 计划书 ID (格式: plandoc-xxx)

        Returns:
            bool: 是否成功

        Raises:
            DataAccessError: 数据库访问失败
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM plan_doc WHERE id = ?", (doc_id,))

                success = cursor.rowcount > 0
                if success:
                    logger.info("删除计划书 %s 成功", doc_id)
                return success

        except Exception as e:
            logger.error("删除计划书 %s 失败: %s", doc_id, e)
            raise DataAccessError(f"删除计划书 {doc_id} 失败: {e}") from e

    def rename_plan_doc(self, old_id: str, new_id: str) -> bool:
        """
        重命名计划书（修改 ID 并级联更新关联表）

        Args:
            old_id: 旧 ID
            new_id: 新 ID

        Returns:
            bool: 是否成功

        Raises:
            ConflictError: 新 ID 已存在
            DataAccessError: 数据库访问失败
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # 1. 更新 plan_doc 表的主键 ID
                cursor.execute(
                    "UPDATE plan_doc SET id = ?, updated_at = datetime('now') WHERE id = ?",
                    (new_id, old_id)
                )

                if cursor.rowcount == 0:
                    logger.warning("重命名失败: 计划书 %s 不存在", old_id)
                    return False

                # 2. 级联更新 todo_list 表 (Task Pool) 中的引用
                cursor.execute(
                    "UPDATE todo_list SET plan_doc_id = ? WHERE plan_doc_id = ?",
                    (new_id, old_id)
                )

                logger.info("重命名计划书成功: %s -> %s, 关联任务更新数: %s", old_id, new_id, cursor.rowcount)
                return True

        except sqlite3.IntegrityError as e:
            logger.error("重命名计划书 %s -> %s 失败: %s", old_id, new_id, e)
            raise ConflictError(f"重命名计划书失败，新 ID 已存在: {new_id}") from e
        except Exception as e:
            logger.error("重命名计划书 %s -> %s 失败: %s", old_id, new_id, e)
            raise DataAccessError(f"重命名计划书 {old_id} -> {new_id} 失败: {e}") from e
