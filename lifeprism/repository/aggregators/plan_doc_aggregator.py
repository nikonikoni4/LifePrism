"""
PlanDoc Aggregator - 计划书数据聚合层

聚合 PlanDocProvider，提供计划书相关的统一数据视图和业务逻辑
"""
from typing import Optional, List, Dict, Any, Tuple
from lifeprism.repository.providers.plan_doc_provider import PlanDocProvider
from lifeprism.repository.providers.common_query_options import QueryOptions
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import DataAccessError

logger = get_logger(__name__)


class PlanDocAggregator:
    """
    计划书聚合器

    职责：
    1. 实现业务逻辑（如 order_index 计算）
    2. 提供统一的数据访问接口（透传 provider 方法）
    """

    def __init__(self):
        self.provider = PlanDocProvider()

    # ==================== 业务逻辑方法 ====================

    def get_next_order_index(self, goal_id: str) -> int:
        """
        获取指定目标的下一个 order_index

        Args:
            goal_id: 目标 ID

        Returns:
            int: 下一个可用的 order_index

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            with self.provider.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COALESCE(MAX(order_index), -1) + 1 FROM plan_doc WHERE goal_id = ?",
                    (goal_id,)
                )
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error("获取下一个 order_index 失败: goal_id=%s, error=%s", goal_id, e)
            raise DataAccessError(
                message=f"获取下一个 order_index 失败",
                details={"goal_id": goal_id, "error": str(e)}
            ) from e

    def create_plan_doc(self, data: Dict[str, Any]) -> Optional[str]:
        """
        创建新计划书（包含 order_index 计算）

        Args:
            data: 计划书数据
                - 必须包含 'id'（作为主键）
                - 可包含 'order_index'，未提供则自动计算（按 goal_id 分组）

        Returns:
            Optional[str]: 新计划书 ID，失败返回 None

        Raises:
            ValidationError: 数据验证失败
            ConflictError: 主键冲突
            DataAccessError: 数据库访问失败
        """
        # 如果未提供 order_index，自动计算
        if 'order_index' not in data:
            data['order_index'] = self.get_next_order_index(data.get('goal_id'))

        # 调用 provider 创建
        return self.provider.create_plan_doc(data)

    # ==================== 透传 Provider 方法 ====================

    def query_plan_docs(
        self,
        options: Optional[QueryOptions] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """透传：通用查询接口"""
        return self.provider.query_plan_docs(options)

    def get_all_plan_docs(self) -> List[Dict[str, Any]]:
        """透传：获取所有计划书"""
        return self.provider.get_all_plan_docs()

    def get_plan_docs_by_goal(self, goal_id: str) -> List[Dict[str, Any]]:
        """透传：获取指定目标的所有计划书"""
        return self.provider.get_plan_docs_by_goal(goal_id)

    def get_plan_doc_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """透传：按 ID 获取单个计划书"""
        return self.provider.get_plan_doc_by_id(doc_id)

    def update_plan_doc(self, doc_id: str, data: Dict[str, Any]) -> bool:
        """透传：更新计划书"""
        return self.provider.update_plan_doc(doc_id, data)

    def delete_plan_doc(self, doc_id: str) -> bool:
        """透传：删除计划书"""
        return self.provider.delete_plan_doc(doc_id)

    def rename_plan_doc(self, old_id: str, new_id: str) -> bool:
        """透传：重命名计划书"""
        return self.provider.rename_plan_doc(old_id, new_id)
