"""habit_chains 和 habit_chain_nodes 表数据访问层"""
from datetime import datetime
from typing import Optional, List, Dict, Any

from lifeprism.storage import LWBaseDataProvider
from lifeprism.utils import get_logger, LazySingleton

logger = get_logger(__name__)


class HabitChainProvider(LWBaseDataProvider):
    """habit_chains 和 habit_chain_nodes 表的数据访问对象。

    注意：database_manager 未开启 PRAGMA foreign_keys = ON，
    因此 delete_chain 需要先手动删除节点再删除链条。
    """

    # ==================== 链条操作 ====================

    def create_chain(self, data: Dict[str, Any]) -> int:
        """创建习惯链条，返回新记录的自增 ID。

        Args:
            data: 链条数据，必填 name，可选 description、show_in_timeline。

        Returns:
            新插入记录的 INTEGER 主键。
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO habit_chains (name, description, show_in_timeline)
                   VALUES (?, ?, ?)""",
                (
                    data["name"],
                    data.get("description"),
                    data.get("show_in_timeline", 0),
                ),
            )
            return cursor.lastrowid


    def get_chain_by_id(self, chain_id: int) -> Optional[Dict[str, Any]]:
        """按 ID 查询单个链条，不存在返回 None。

        Args:
            chain_id: 链条 ID。

        Returns:
            链条数据字典，或 None。
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM habit_chains WHERE id = ?", (chain_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))

    def get_chains(self, show_in_timeline: Optional[bool] = None) -> List[Dict[str, Any]]:
        """获取链条列表，可按 show_in_timeline 过滤。

        Args:
            show_in_timeline: True 则只返回 show_in_timeline=1 的链条，None 返回全部。

        Returns:
            链条数据字典列表。
        """
        with self.db.get_connection() as conn:
            if show_in_timeline is True:
                cursor = conn.execute(
                    "SELECT * FROM habit_chains WHERE show_in_timeline = 1 ORDER BY created_at ASC"
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM habit_chains ORDER BY created_at ASC"
                )
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def update_chain(self, chain_id: int, update_data: Dict[str, Any]) -> bool:
        """更新链条（PATCH 语义），只更新 allowed_fields 中的字段。

        Args:
            chain_id: 链条 ID。
            update_data: 要更新的字段字典。

        Returns:
            True（始终成功，无记录时也返回 True）。
        """
        allowed_fields = {"name", "description", "show_in_timeline"}
        filtered = {k: v for k, v in update_data.items() if k in allowed_fields}
        if not filtered:
            return True
        filtered["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        set_clause = ", ".join(f"{k} = ?" for k in filtered)
        values = list(filtered.values()) + [chain_id]
        with self.db.get_connection() as conn:
            conn.execute(
                f"UPDATE habit_chains SET {set_clause} WHERE id = ?", values
            )
        return True

    def delete_chain(self, chain_id: int) -> bool:
        """删除链条及其所有节点。

        由于 database_manager 未开启外键约束（PRAGMA foreign_keys = ON），
        需要先手动删除子节点，再删除链条。

        Args:
            chain_id: 链条 ID。

        Returns:
            True。
        """
        with self.db.get_connection() as conn:
            conn.execute(
                "DELETE FROM habit_chain_nodes WHERE chain_id = ?", (chain_id,)
            )
            conn.execute(
                "DELETE FROM habit_chains WHERE id = ?", (chain_id,)
            )
        return True

    # ==================== 节点操作 ====================

    def create_node(self, data: Dict[str, Any]) -> int:
        """创建链条节点，返回新记录的自增 ID。

        Args:
            data: 节点数据，必填 chain_id、sort_order、name，
                  可选 habit_id、trigger_time。

        Returns:
            新插入记录的 INTEGER 主键。
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO habit_chain_nodes
                   (chain_id, sort_order, name, habit_id, trigger_time)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    data["chain_id"],
                    data["sort_order"],
                    data["name"],
                    data.get("habit_id"),
                    data.get("trigger_time"),
                ),
            )
            return cursor.lastrowid


    def get_nodes_by_chain(self, chain_id: int) -> List[Dict[str, Any]]:
        """获取指定链条的所有节点，按 sort_order 升序排列。

        Args:
            chain_id: 链条 ID。

        Returns:
            节点数据字典列表。
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM habit_chain_nodes WHERE chain_id = ? ORDER BY sort_order ASC",
                (chain_id,),
            )
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_node_by_id(self, node_id: int) -> Optional[Dict[str, Any]]:
        """按 ID 查询单个节点，不存在返回 None。

        Args:
            node_id: 节点 ID。

        Returns:
            节点数据字典，或 None。
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM habit_chain_nodes WHERE id = ?", (node_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))

    def update_node(self, node_id: int, update_data: Dict[str, Any]) -> bool:
        """更新节点（PATCH 语义），只更新 allowed_fields 中的字段。

        Args:
            node_id: 节点 ID。
            update_data: 要更新的字段字典。

        Returns:
            True（始终成功，无记录时也返回 True）。
        """
        allowed_fields = {"name", "habit_id", "trigger_time", "sort_order"}
        filtered = {k: v for k, v in update_data.items() if k in allowed_fields}
        if not filtered:
            return True
        filtered["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        set_clause = ", ".join(f"{k} = ?" for k in filtered)
        values = list(filtered.values()) + [node_id]
        with self.db.get_connection() as conn:
            conn.execute(
                f"UPDATE habit_chain_nodes SET {set_clause} WHERE id = ?", values
            )
        return True

    def delete_node(self, node_id: int) -> bool:
        """删除单个节点。

        Args:
            node_id: 节点 ID。

        Returns:
            True。
        """
        with self.db.get_connection() as conn:
            conn.execute(
                "DELETE FROM habit_chain_nodes WHERE id = ?", (node_id,)
            )
        return True

    def batch_update_sort_order(self, updates: List[Dict[str, Any]]) -> bool:
        """批量更新节点排序（逐条 UPDATE）。

        Args:
            updates: 列表，每项包含 node_id 和 sort_order。

        Returns:
            True。
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.db.get_connection() as conn:
            for item in updates:
                conn.execute(
                    "UPDATE habit_chain_nodes SET sort_order = ?, updated_at = ? WHERE id = ?",
                    (item["sort_order"], now, item["node_id"]),
                )
        return True

    def increment_sort_order_after(self, chain_id: int, after_order: int) -> bool:
        """将链条内 sort_order >= after_order 的节点排序值全部加 1。

        用于在指定位置插入新节点前腾出空位。

        Args:
            chain_id: 链条 ID。
            after_order: 起始排序值（含）。

        Returns:
            True。
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
        """将所有关联该习惯的节点的 habit_id 置为 NULL。

        Args:
            habit_id: 习惯 ID（TEXT 类型）。

        Returns:
            True。
        """
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE habit_chain_nodes SET habit_id = NULL WHERE habit_id = ?",
                (habit_id,),
            )
        return True

    # ==================== 跨表查询 ====================

    def get_anchor_info_by_habit_ids(
        self, habit_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """批量查询习惯对应的锚点节点信息。

        同一习惯可能出现在多个节点，取 id 最小（最早创建）的那条记录。
        通过 ORDER BY hcn.id ASC 配合 dict 只写入第一次出现的 habit_id 实现。

        Args:
            habit_ids: 习惯 ID 列表。

        Returns:
            以 habit_id 为 key 的字典，value 包含 chainName、nodeName、triggerTime。
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
        """获取链条节点列表，同时附带关联习惯的名称。

        Args:
            chain_id: 链条 ID。

        Returns:
            节点数据字典列表，每项包含 habit_name 字段（无关联时为 None）。
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


habit_chain_provider = LazySingleton(HabitChainProvider)
