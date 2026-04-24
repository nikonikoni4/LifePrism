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

    职责：聚合 habit_chains 和 habit_chain_nodes 两个表的数据
    """

    def __init__(self):
        self.chain_provider = HabitChainProvider()
        self.node_provider = HabitChainNodeProvider()

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


# ==================== 导出单例 ====================

habit_chain_aggregator = LazySingleton(HabitChainAggregator)
