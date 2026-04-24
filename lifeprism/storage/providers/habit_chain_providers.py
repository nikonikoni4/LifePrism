"""
Habit Chain 模块数据提供者

包含 2 个独立的 Provider：
- HabitChainProvider: habit_chains 表
- HabitChainNodeProvider: habit_chain_nodes 表
"""
from datetime import datetime
from typing import Optional, List, Dict, Any, Set

from lifeprism.storage import LWBaseDataProvider
from lifeprism.storage.providers.common_query_options import QueryOptions
from lifeprism.utils import get_logger, LazySingleton

logger = get_logger(__name__)


# ==================== HabitChainProvider ====================

class HabitChainProvider(LWBaseDataProvider):
    """
    习惯链条数据提供者（对应 habit_chains 表）

    职责：提供 habit_chains 表的所有数据访问接口
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "habit_chains"
    _PRIMARY_KEY = "id"  # INTEGER AUTOINCREMENT
    _DATE_FIELD = None
    _TIME_FIELD = None

    _FILTER_FIELDS: Set[str] = {
        'id', 'name', 'show_in_timeline', 'created_at', 'updated_at'
    }
    _ORDER_FIELDS: Set[str] = {'id', 'name', 'created_at'}
    _SELECT_FIELDS: Set[str] = {
        'id', 'name', 'description', 'show_in_timeline', 'created_at', 'updated_at'
    }
    _UPDATE_FIELDS: Set[str] = {
        'name', 'description', 'show_in_timeline'
    }

    # ==================== 核心方法 ====================

    def create_chain(self, data: Dict[str, Any]) -> int:
        """
        创建习惯链条，返回新记录的自增 ID

        Args:
            data: 链条数据，必填 name，可选 description、show_in_timeline

        Returns:
            新插入记录的 INTEGER 主键
        """
        insert_data = {
            'name': data['name'],
            'description': data.get('description'),
            'show_in_timeline': data.get('show_in_timeline', 0),
        }

        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO habit_chains (name, description, show_in_timeline)
                   VALUES (?, ?, ?)""",
                (
                    insert_data['name'],
                    insert_data['description'],
                    insert_data['show_in_timeline'],
                ),
            )
            chain_id = cursor.lastrowid
            logger.info(f"创建链条成功: {chain_id}")
            return chain_id

    def get_chain_by_id(self, chain_id: int) -> Optional[Dict[str, Any]]:
        """
        按 ID 查询单个链条

        Args:
            chain_id: 链条 ID

        Returns:
            链条数据字典，或 None
        """
        options = QueryOptions(
            filters={'id': chain_id},
            order_by='id',
            order_desc=False
        )
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def get_chains(self, show_in_timeline: Optional[bool] = None) -> List[Dict[str, Any]]:
        """
        获取链条列表，可按 show_in_timeline 过滤

        Args:
            show_in_timeline: True 则只返回 show_in_timeline=1 的链条，None 返回全部

        Returns:
            链条数据字典列表，按 created_at 升序
        """
        options = QueryOptions(
            filters={'show_in_timeline': 1} if show_in_timeline is True else None,
            order_by='created_at',
            order_desc=False
        )
        results, _ = self._generic_query(options)
        return results

    def update_chain(self, chain_id: int, update_data: Dict[str, Any]) -> bool:
        """
        更新链条（PATCH 语义）

        Args:
            chain_id: 链条 ID
            update_data: 要更新的字段字典

        Returns:
            True
        """
        if not update_data:
            return True

        # 白名单验证
        invalid_fields = set(update_data.keys()) - self._UPDATE_FIELDS
        if invalid_fields:
            logger.warning(f"忽略非法更新字段: {invalid_fields}")
            update_data = {k: v for k, v in update_data.items() if k in self._UPDATE_FIELDS}

        if not update_data:
            return True

        return self._generic_update(chain_id, update_data, auto_timestamp=True)

    def delete_chain(self, chain_id: int) -> bool:
        """
        删除链条及其所有节点

        由于 database_manager 未开启外键约束（PRAGMA foreign_keys = ON），
        需要先手动删除子节点，再删除链条

        Args:
            chain_id: 链条 ID

        Returns:
            True
        """
        with self.db.get_connection() as conn:
            conn.execute(
                "DELETE FROM habit_chain_nodes WHERE chain_id = ?", (chain_id,)
            )
            conn.execute(
                "DELETE FROM habit_chains WHERE id = ?", (chain_id,)
            )
        logger.info(f"删除链条 {chain_id} 及其节点成功")
        return True


# ==================== HabitChainNodeProvider ====================

class HabitChainNodeProvider(LWBaseDataProvider):
    """
    习惯链条节点数据提供者（对应 habit_chain_nodes 表）

    职责：提供 habit_chain_nodes 表的所有数据访问接口
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "habit_chain_nodes"
    _PRIMARY_KEY = "id"  # INTEGER AUTOINCREMENT
    _DATE_FIELD = None
    _TIME_FIELD = None  # trigger_time 不用于范围查询

    _FILTER_FIELDS: Set[str] = {
        'id', 'chain_id', 'habit_id', 'sort_order', 'created_at', 'updated_at'
    }
    _ORDER_FIELDS: Set[str] = {'id', 'sort_order', 'created_at'}
    _SELECT_FIELDS: Set[str] = {
        'id', 'chain_id', 'sort_order', 'name', 'habit_id', 'trigger_time',
        'created_at', 'updated_at'
    }
    _UPDATE_FIELDS: Set[str] = {
        'name', 'habit_id', 'trigger_time', 'sort_order'
    }

    # ==================== 核心方法 ====================

    def create_node(self, data: Dict[str, Any]) -> int:
        """
        创建链条节点，返回新记录的自增 ID

        Args:
            data: 节点数据，必填 chain_id、sort_order、name，
                  可选 habit_id、trigger_time

        Returns:
            新插入记录的 INTEGER 主键
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO habit_chain_nodes
                   (chain_id, sort_order, name, habit_id, trigger_time)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    data['chain_id'],
                    data['sort_order'],
                    data['name'],
                    data.get('habit_id'),
                    data.get('trigger_time'),
                ),
            )
            node_id = cursor.lastrowid
            logger.info(f"创建节点成功: {node_id}")
            return node_id

    def get_nodes_by_chain(self, chain_id: int) -> List[Dict[str, Any]]:
        """
        获取指定链条的所有节点，按 sort_order 升序排列

        Args:
            chain_id: 链条 ID

        Returns:
            节点数据字典列表
        """
        options = QueryOptions(
            filters={'chain_id': chain_id},
            order_by='sort_order',
            order_desc=False
        )
        results, _ = self._generic_query(options)
        return results

    def get_node_by_id(self, node_id: int) -> Optional[Dict[str, Any]]:
        """
        按 ID 查询单个节点

        Args:
            node_id: 节点 ID

        Returns:
            节点数据字典，或 None
        """
        options = QueryOptions(
            filters={'id': node_id},
            order_by='id',
            order_desc=False
        )
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def update_node(self, node_id: int, update_data: Dict[str, Any]) -> bool:
        """
        更新节点（PATCH 语义）

        Args:
            node_id: 节点 ID
            update_data: 要更新的字段字典

        Returns:
            True
        """
        if not update_data:
            return True

        # 白名单验证
        invalid_fields = set(update_data.keys()) - self._UPDATE_FIELDS
        if invalid_fields:
            logger.warning(f"忽略非法更新字段: {invalid_fields}")
            update_data = {k: v for k, v in update_data.items() if k in self._UPDATE_FIELDS}

        if not update_data:
            return True

        return self._generic_update(node_id, update_data, auto_timestamp=True)

    def delete_node(self, node_id: int) -> bool:
        """
        删除单个节点

        Args:
            node_id: 节点 ID

        Returns:
            True
        """
        success = self._generic_delete(node_id)
        if success:
            logger.info(f"删除节点 {node_id} 成功")
        return success

    def batch_update_sort_order(self, updates: List[Dict[str, Any]]) -> bool:
        """
        批量更新节点排序（逐条 UPDATE）

        Args:
            updates: 列表，每项包含 node_id 和 sort_order

        Returns:
            True
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.db.get_connection() as conn:
            for item in updates:
                conn.execute(
                    "UPDATE habit_chain_nodes SET sort_order = ?, updated_at = ? WHERE id = ?",
                    (item["sort_order"], now, item["node_id"]),
                )
        logger.info(f"批量更新 {len(updates)} 个节点排序成功")
        return True

    def increment_sort_order_after(self, chain_id: int, after_order: int) -> bool:
        """
        将链条内 sort_order >= after_order 的节点排序值全部加 1

        用于在指定位置插入新节点前腾出空位

        Args:
            chain_id: 链条 ID
            after_order: 起始排序值（含）

        Returns:
            True
        """
        with self.db.get_connection() as conn:
            conn.execute(
                """UPDATE habit_chain_nodes
                   SET sort_order = sort_order + 1
                   WHERE chain_id = ? AND sort_order >= ?""",
                (chain_id, after_order),
            )
        return True

    def unlink_habit_from_nodes(self, habit_id: str) -> bool:
        """
        将所有关联该习惯的节点的 habit_id 置为 NULL

        Args:
            habit_id: 习惯 ID（TEXT 类型）

        Returns:
            True
        """
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE habit_chain_nodes SET habit_id = NULL WHERE habit_id = ?",
                (habit_id,),
            )
        logger.info(f"解除习惯 {habit_id} 与节点的关联")
        return True

    # ==================== 跨表查询 ====================

    def get_anchor_info_by_habit_ids(
        self, habit_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        批量查询习惯对应的锚点节点信息

        同一习惯可能出现在多个节点，取 id 最小（最早创建）的那条记录

        Args:
            habit_ids: 习惯 ID 列表

        Returns:
            以 habit_id 为 key 的字典，value 包含 chainName、nodeName、triggerTime
        """
        if not habit_ids:
            return {}

        placeholders = ", ".join("?" for _ in habit_ids)
        sql = f"""
            SELECT hcn.habit_id, hcn.name AS node_name, hcn.trigger_time, hc.name AS chain_name
            FROM habit_chain_nodes hcn
            JOIN habit_chains hc ON hcn.chain_id = hc.id
            WHERE hcn.habit_id IN ({placeholders})
            ORDER BY hcn.id ASC
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(sql, habit_ids)
            rows = cursor.fetchall()

        result: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            habit_id, node_name, trigger_time, chain_name = row
            if habit_id not in result:
                result[habit_id] = {
                    "chainName": chain_name,
                    "nodeName": node_name,
                    "triggerTime": trigger_time,
                }
        return result

    def get_nodes_with_habit_names(self, chain_id: int) -> List[Dict[str, Any]]:
        """
        获取链条节点列表，同时附带关联习惯的名称

        Args:
            chain_id: 链条 ID

        Returns:
            节点数据字典列表，每项包含 habit_name 字段（无关联时为 None）
        """
        sql = """
            SELECT hcn.*, h.name AS habit_name
            FROM habit_chain_nodes hcn
            LEFT JOIN habits h ON hcn.habit_id = h.id
            WHERE hcn.chain_id = ?
            ORDER BY hcn.sort_order ASC
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(sql, (chain_id,))
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]


