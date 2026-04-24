"""
Habit Chain Aggregator - 习惯链数据聚合层

聚合 HabitChainProvider, HabitChainNodeProvider
提供习惯链相关的统一数据视图
"""
from typing import Optional, List, Dict, Any
from lifeprism.storage.providers.habit_chain_providers import (
    HabitChainProvider,
    HabitChainNodeProvider,
)
from lifeprism.utils import get_logger, LazySingleton

logger = get_logger(__name__)


class HabitChainAggregator:
    """
    习惯链聚合器

    职责：
    1. 聚合 habit_chains、habit_chain_nodes 两个表的数据（核心价值）
    2. 提供统一的数据访问接口（透传 provider 方法）
    """

    def __init__(self):
        self.chain_provider = HabitChainProvider()
        self.node_provider = HabitChainNodeProvider()

    # ==================== 聚合方法（核心价值）====================

    def get_chain_with_nodes(self, chain_id: int) -> Optional[Dict[str, Any]]:
        """
        获取习惯链详情（包含所有节点）

        Args:
            chain_id: 链条 ID

        Returns:
            包含 chain 和 nodes 的字典，不存在返回 None
        """
        chain = self.chain_provider.get_chain_by_id(chain_id)
        if not chain:
            return None

        # 获取该链条的所有节点（按 sort_order 升序）
        nodes = self.node_provider.get_nodes_by_chain(chain_id)
        chain['nodes'] = nodes

        return chain

    def get_chains_with_nodes(
        self, show_in_timeline: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """
        获取习惯链列表（每个包含节点信息）

        Args:
            show_in_timeline: True 则只返回 show_in_timeline=1 的链条，None 返回全部

        Returns:
            链条列表，每个包含 nodes 字段
        """
        chains = self.chain_provider.get_chains(show_in_timeline)

        # 为每个链条获取节点列表
        for chain in chains:
            nodes = self.node_provider.get_nodes_by_chain(chain['id'])
            chain['nodes'] = nodes

        return chains

    # ==================== HabitChain 核心 CRUD 透传 ====================

    def create_chain(self, data: Dict[str, Any]) -> int:
        """透传：创建习惯链"""
        return self.chain_provider.create_chain(data)

    def update_chain(self, chain_id: int, data: Dict[str, Any]) -> bool:
        """透传：更新习惯链"""
        return self.chain_provider.update_chain(chain_id, data)

    def delete_chain(self, chain_id: int) -> bool:
        """透传：删除习惯链"""
        return self.chain_provider.delete_chain(chain_id)

    def get_chains(self, show_in_timeline: Optional[bool] = None) -> List[Dict[str, Any]]:
        """透传：获取习惯链列表"""
        return self.chain_provider.get_chains(show_in_timeline)

    def get_chain_by_id(self, chain_id: int) -> Optional[Dict[str, Any]]:
        """透传：根据ID获取习惯链"""
        return self.chain_provider.get_chain_by_id(chain_id)

    # ==================== HabitChainNode 核心 CRUD 透传 ====================

    def create_node(self, data: Dict[str, Any]) -> int:
        """透传：创建节点"""
        return self.node_provider.create_node(data)

    def update_node(self, node_id: int, data: Dict[str, Any]) -> bool:
        """透传：更新节点"""
        return self.node_provider.update_node(node_id, data)

    def delete_node(self, node_id: int) -> bool:
        """透传：删除节点"""
        return self.node_provider.delete_node(node_id)

    def get_nodes_by_chain(self, chain_id: int) -> List[Dict[str, Any]]:
        """透传：获取链条的所有节点"""
        return self.node_provider.get_nodes_by_chain(chain_id)

    def get_nodes_with_habit_names(self, chain_id: int) -> List[Dict[str, Any]]:
        """透传：获取链条的所有节点（包含习惯名称）"""
        return self.node_provider.get_nodes_with_habit_names(chain_id)

    def get_node_by_id(self, node_id: int) -> Optional[Dict[str, Any]]:
        """透传：根据ID获取节点"""
        return self.node_provider.get_node_by_id(node_id)

    def increment_sort_order_after(self, chain_id: int, after_order: int) -> bool:
        """透传：增加指定顺序之后的节点排序值"""
        return self.node_provider.increment_sort_order_after(chain_id, after_order)

    def batch_update_sort_order(self, updates: List[Dict[str, Any]]) -> bool:
        """透传：批量更新节点排序"""
        return self.node_provider.batch_update_sort_order(updates)

    def unlink_habit_from_nodes(self, habit_id: str) -> bool:
        """透传：解除习惯与节点的关联"""
        return self.node_provider.unlink_habit_from_nodes(habit_id)

    def get_anchor_info_by_habit_ids(self, habit_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """透传：获取习惯的锚点信息"""
        return self.node_provider.get_anchor_info_by_habit_ids(habit_ids)

    # ==================== 事务性聚合方法 ====================

    def create_chain_with_nodes(
        self, chain_data: Dict[str, Any], nodes_data: List[Dict[str, Any]]
    ) -> int:
        """
        创建习惯链并添加节点

        Args:
            chain_data: 链条数据（必填 name，可选 description、show_in_timeline）
            nodes_data: 节点数据列表（每项必填 sort_order、name，可选 habit_id、trigger_time）

        Returns:
            新创建的 chain_id
        """
        # 创建链条
        chain_id = self.chain_provider.create_chain(chain_data)

        # 创建节点
        for node_data in nodes_data:
            node_data['chain_id'] = chain_id
            self.node_provider.create_node(node_data)

        logger.info(f"创建习惯链 {chain_id}，包含 {len(nodes_data)} 个节点")
        return chain_id

    def delete_chain_with_nodes(self, chain_id: int) -> bool:
        """
        删除习惯链及其所有节点

        Args:
            chain_id: 链条 ID

        Returns:
            True
        """
        # HabitChainProvider.delete_chain 已经处理了级联删除节点
        return self.chain_provider.delete_chain(chain_id)

habit_chain_aggregator = LazySingleton(HabitChainAggregator)
