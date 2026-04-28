"""
Todo Aggregator - 任务数据聚合层

聚合 TodoProvider，提供任务相关的统一数据视图和业务逻辑
"""
from typing import Optional, List, Dict, Any, Tuple
from lifeprism.repository.providers.todo_provider import TodoProvider
from lifeprism.repository.providers.common_query_options import QueryOptions
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import DataAccessError

logger = get_logger(__name__)


class TodoAggregator:
    """
    任务聚合器

    职责：
    1. 实现业务逻辑（如 order_index 计算）
    2. 提供统一的数据访问接口（透传 provider 方法）
    """

    def __init__(self):
        self.provider = TodoProvider()

    # ==================== 业务逻辑方法 ====================

    def get_next_order_index(self, date: str) -> int:
        """
        获取指定日期的下一个 order_index

        Args:
            date: 日期（YYYY-MM-DD 格式）

        Returns:
            int: 下一个可用的 order_index

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            with self.provider.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COALESCE(MAX(order_index), -1) + 1 FROM todo_list WHERE date = ?",
                    (date,)
                )
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"获取下一个 order_index 失败 (date={date}): {e}")
            raise DataAccessError(
                message=f"获取下一个 order_index 失败",
                details={"date": date, "error": str(e)}
            ) from e

    def create_todo(self, data: Dict[str, Any]) -> str:
        """
        创建新任务（包含 order_index 计算）

        Args:
            data: 任务数据
                - 可包含 'id'，未提供则自动生成
                - 可包含 'order_index'，未提供则自动计算（按 date 分组）

        Returns:
            str: 新任务 ID

        Raises:
            ValidationError: 数据验证失败
            ConflictError: 记录已存在
            DataAccessError: 数据库操作失败
        """
        # 如果未提供 order_index，自动计算
        if 'order_index' not in data:
            data['order_index'] = self.get_next_order_index(data.get('date'))

        # 调用 provider 创建
        return self.provider.create_todo(data)

    # ==================== 透传 Provider 方法 ====================

    def query_todos(
        self,
        options: Optional[QueryOptions] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """透传：通用查询接口"""
        return self.provider.query_todos(options)

    def get_todos_by_date(
        self,
        date: str,
        include_cross_day: bool = True
    ) -> List[Dict[str, Any]]:
        """透传：获取指定日期的任务列表"""
        return self.provider.get_todos_by_date(date, include_cross_day)

    def get_todo_by_id(self, todo_id: str) -> Optional[Dict[str, Any]]:
        """透传：按 ID 获取单个任务"""
        return self.provider.get_todo_by_id(todo_id)

    def update_todo(self, todo_id: str, data: Dict[str, Any]) -> bool:
        """透传：更新任务"""
        return self.provider.update_todo(todo_id, data)

    def delete_todo(self, todo_id: str) -> bool:
        """透传：删除任务"""
        return self.provider.delete_todo(todo_id)

    def get_todos_for_taskpool(
        self,
        goal_id: Optional[str] = None,
        plan_doc_id: Optional[str] = None,
        state: str = "all"
    ) -> List[Dict[str, Any]]:
        """透传：获取任务池任务"""
        return self.provider.get_todos_for_taskpool(goal_id, plan_doc_id, state)

    def reorder_todos(self, todo_ids: List[str]) -> bool:
        """透传：重排序任务"""
        return self.provider.reorder_todos(todo_ids)

    def batch_update_todos(self, updates: List[Dict[str, Any]]) -> int:
        """透传：批量更新任务"""
        return self.provider.batch_update_todos(updates)

    def get_waid_todos(self) -> List[Dict[str, Any]]:
        """透传：获取待办任务"""

        return self.provider.get_waid_todos()