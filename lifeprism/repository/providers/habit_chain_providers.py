"""
Habit Chain 模块数据提供者

包含 2 个独立的 Provider：
- HabitChainProvider: habit_chains 表
- HabitChainNodeProvider: habit_chain_nodes 表
"""

import sqlite3
from datetime import datetime, timezone
from typing import Any

from lifeprism.repository.base_providers import LWBaseDataProvider
from lifeprism.repository.providers.common_query_options import QueryOptions
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import DataAccessError

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

    _FILTER_FIELDS: set[str] = {"id", "name", "show_in_timeline", "created_at", "updated_at"}
    _ORDER_FIELDS: set[str] = {"id", "name", "created_at"}
    _SELECT_FIELDS: set[str] = {
        "id",
        "name",
        "description",
        "show_in_timeline",
        "created_at",
        "updated_at",
    }
    _UPDATE_FIELDS: set[str] = {"name", "description", "show_in_timeline"}

    # ==================== 核心方法 ====================

    def query_habit_chains(
        self, options: QueryOptions | None = None
    ) -> tuple[list[dict[str, Any]], int]:
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
            records, total = provider.query_habit_chains(options)

            # 分页查询
            options = QueryOptions(page=1, page_size=20)
            records, total = provider.query_habit_chains(options)
        """
        return self._generic_query(options)

    def create_chain(self, data: dict[str, Any]) -> int:
        """
        创建习惯链条，返回新记录的自增 ID

        走 _generic_insert 通道：habit_chains 在 HASH_ID_PREFIXES 中（前缀 hc-），
        _generic_insert 自动生成 hash_id 并写入 created_at/updated_at。

        Args:
            data: 链条数据，必填 name，可选 description、show_in_timeline

        Returns:
            新插入记录的 INTEGER 主键
        """
        insert_data = {
            "name": data["name"],
            "description": data.get("description"),
            "show_in_timeline": data.get("show_in_timeline", 0),
        }

        try:
            chain_id = self._generic_insert(insert_data)
            logger.info("创建链条成功: %s", chain_id)
            return int(chain_id) if chain_id is not None else 0
        except DataAccessError:
            raise
        except sqlite3.Error as e:
            logger.error("创建习惯链失败: error=%s", e)
            raise DataAccessError(f"创建习惯链失败: {e}") from e

    def get_chain_by_id(self, chain_id: int) -> dict[str, Any] | None:
        """
        按 ID 查询单个链条

        Args:
            chain_id: 链条 ID

        Returns:
            链条数据字典，或 None
        """
        options = QueryOptions(filters={"id": chain_id}, order_by="id", order_desc=False)
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def get_chains(self, show_in_timeline: bool | None = None) -> list[dict[str, Any]]:
        """
        获取链条列表，可按 show_in_timeline 过滤

        Args:
            show_in_timeline: True 则只返回 show_in_timeline=1 的链条，None 返回全部

        Returns:
            链条数据字典列表，按 created_at 升序
        """
        options = QueryOptions(
            filters={"show_in_timeline": 1} if show_in_timeline is True else None,
            order_by="created_at",
            order_desc=False,
        )
        results, _ = self._generic_query(options)
        return results

    def update_chain(self, chain_id: int, update_data: dict[str, Any]) -> bool:
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
            logger.warning("忽略非法更新字段: %s", invalid_fields)
            update_data = {k: v for k, v in update_data.items() if k in self._UPDATE_FIELDS}

        if not update_data:
            return True

        return self._generic_update(chain_id, update_data)

    def delete_chain(self, chain_id: int) -> bool:
        """
        删除链条及其所有节点

        走 _generic_* 通道（通道统一）：
        - habit_chain_nodes 走 HabitChainNodeProvider.delete_by_chain_id
          （内部走 _generic_batch_delete）
        - habit_chains 走 self._generic_delete

        注意：habit_chains 和 habit_chain_nodes 当前不在 SYNC_TABLES 中
        （见 docs/known-limitations/habit-chain-tables-not-synced.md），
        所以 _generic_* 不会写墓碑。待 chain_id 改引用 hash_id 恢复同步后，
        走 _generic_* 通道将自动写墓碑，无需再改此处。

        Args:
            chain_id: 链条 ID

        Returns:
            是否成功（链条存在并删除返回 True，不存在返回 False）
        """
        try:
            # 先级联删除所有节点（走 _generic_batch_delete 通道）
            node_provider = HabitChainNodeProvider()
            node_provider.delete_by_chain_id(chain_id)

            # 再删除链条本身（走 _generic_delete 通道）
            success = self._generic_delete(chain_id)
            if success:
                logger.info("删除链条 %s 及其节点成功", chain_id)
            return success
        except DataAccessError:
            raise
        except sqlite3.Error as e:
            logger.error("删除习惯链失败: error=%s", e)
            raise DataAccessError(f"删除习惯链失败: {e}") from e


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

    _FILTER_FIELDS: set[str] = {
        "id",
        "chain_id",
        "habit_id",
        "sort_order",
        "created_at",
        "updated_at",
    }
    _ORDER_FIELDS: set[str] = {"id", "sort_order", "created_at"}
    _SELECT_FIELDS: set[str] = {
        "id",
        "chain_id",
        "sort_order",
        "name",
        "habit_id",
        "trigger_time",
        "created_at",
        "updated_at",
    }
    _UPDATE_FIELDS: set[str] = {"name", "habit_id", "trigger_time", "sort_order"}

    # ==================== 核心方法 ====================

    def query_habit_chain_nodes(
        self, options: QueryOptions | None = None
    ) -> tuple[list[dict[str, Any]], int]:
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
            records, total = provider.query_habit_chain_nodes(options)

            # 分页查询
            options = QueryOptions(page=1, page_size=20)
            records, total = provider.query_habit_chain_nodes(options)
        """
        return self._generic_query(options)

    def create_node(self, data: dict[str, Any]) -> int:
        """
        创建链条节点，返回新记录的自增 ID

        走 _generic_insert 通道：habit_chain_nodes 在 HASH_ID_PREFIXES 中（前缀 hcn-），
        _generic_insert 自动生成 hash_id 并写入 created_at/updated_at。

        Args:
            data: 节点数据，必填 chain_id、sort_order、name，
                  可选 habit_id、trigger_time

        Returns:
            新插入记录的 INTEGER 主键
        """
        insert_data = {
            "chain_id": data["chain_id"],
            "sort_order": data["sort_order"],
            "name": data["name"],
            "habit_id": data.get("habit_id"),
            "trigger_time": data.get("trigger_time"),
        }

        try:
            node_id = self._generic_insert(insert_data)
            logger.info("创建节点成功: %s", node_id)
            return int(node_id) if node_id is not None else 0
        except DataAccessError:
            raise
        except sqlite3.Error as e:
            logger.error("创建习惯链节点失败: error=%s", e)
            raise DataAccessError(f"创建习惯链节点失败: {e}") from e

    def get_nodes_by_chain(self, chain_id: int) -> list[dict[str, Any]]:
        """
        获取指定链条的所有节点，按 sort_order 升序排列

        Args:
            chain_id: 链条 ID

        Returns:
            节点数据字典列表
        """
        options = QueryOptions(
            filters={"chain_id": chain_id}, order_by="sort_order", order_desc=False
        )
        results, _ = self._generic_query(options)
        return results

    def get_node_by_id(self, node_id: int) -> dict[str, Any] | None:
        """
        按 ID 查询单个节点

        Args:
            node_id: 节点 ID

        Returns:
            节点数据字典，或 None
        """
        options = QueryOptions(filters={"id": node_id}, order_by="id", order_desc=False)
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def update_node(self, node_id: int, update_data: dict[str, Any]) -> bool:
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
            logger.warning("忽略非法更新字段: %s", invalid_fields)
            update_data = {k: v for k, v in update_data.items() if k in self._UPDATE_FIELDS}

        if not update_data:
            return True

        return self._generic_update(node_id, update_data)

    def delete_node(self, node_id: int) -> bool:
        """
        删除单个节点

        Args:
            node_id: 节点 ID

        Returns:
            True
        """
        try:
            success = self._generic_delete(node_id)
            if success:
                logger.info("删除节点 %s 成功", node_id)
            return success
        except sqlite3.Error as e:
            logger.error("删除习惯链节点失败: error=%s", e)
            raise DataAccessError(f"删除习惯链节点失败: {e}") from e

    def delete_by_chain_id(self, chain_id: int) -> bool:
        """
        删除指定链条的所有节点（级联清理用）

        走 _generic_batch_delete 通道：habit_chain_nodes 当前不在 SYNC_TABLES 中
        （见 docs/known-limitations/habit-chain-tables-not-synced.md），所以不会写墓碑。
        但仍走 _generic_* 通道保持通道统一，待恢复同步后自动写墓碑。

        实现方式：先查 chain_id 对应的 id 列表，再走 _generic_batch_delete
        （批量 DELETE，AUTOINCREMENT 表不在 SYNC_TABLES 故不写墓碑）。

        Args:
            chain_id: 链条 ID

        Returns:
            True（无节点时也返回 True）
        """
        try:
            # 先查该链条的所有 node id 列表
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT {self._PRIMARY_KEY} FROM {self._TABLE_NAME} WHERE chain_id = ?",
                    (chain_id,),
                )
                node_ids = [row[0] for row in cursor.fetchall()]

            if not node_ids:
                return True

            # 批量删除（_generic_batch_delete 自带事务）
            self._generic_batch_delete(node_ids)
            return True
        except DataAccessError:
            raise
        except sqlite3.Error as e:
            logger.error("按链条ID删除节点失败: error=%s", e)
            raise DataAccessError(f"按链条ID删除节点失败: {e}") from e

    def batch_update_sort_order(self, updates: list[dict[str, Any]]) -> bool:
        """
        批量更新节点排序（逐条 UPDATE）

        Args:
            updates: 列表，每项包含 node_id 和 sort_order

        Returns:
            True
        """
        try:
            now = datetime.now(timezone.utc).isoformat()
            with self.db.get_connection() as conn:
                for item in updates:
                    conn.execute(
                        "UPDATE habit_chain_nodes SET sort_order = ?, updated_at = ? WHERE id = ?",
                        (item["sort_order"], now, item["node_id"]),
                    )
            logger.info("批量更新 %s 个节点排序成功", len(updates))
            return True
        except sqlite3.Error as e:
            logger.error("批量更新排序失败: error=%s", e)
            raise DataAccessError(f"批量更新排序失败: {e}") from e

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
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    """UPDATE habit_chain_nodes
                       SET sort_order = sort_order + 1
                       WHERE chain_id = ? AND sort_order >= ?""",
                    (chain_id, after_order),
                )
            return True
        except sqlite3.Error as e:
            logger.error("递增排序失败: error=%s", e)
            raise DataAccessError(f"递增排序失败: {e}") from e

    def unlink_habit_from_nodes(self, habit_id: str) -> bool:
        """
        将所有关联该习惯的节点的 habit_id 置为 NULL

        Args:
            habit_id: 习惯 ID（TEXT 类型）

        Returns:
            True
        """
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    "UPDATE habit_chain_nodes SET habit_id = NULL WHERE habit_id = ?",
                    (habit_id,),
                )
            logger.info("解除习惯 %s 与节点的关联", habit_id)
            return True
        except sqlite3.Error as e:
            logger.error("取消关联失败: error=%s", e)
            raise DataAccessError(f"取消关联失败: {e}") from e

    # ==================== 跨表查询 ====================

    def get_anchor_info_by_habit_ids(self, habit_ids: list[str]) -> dict[str, dict[str, Any]]:
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

        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            habit_id, node_name, trigger_time, chain_name = row
            if habit_id not in result:
                result[habit_id] = {
                    "chainName": chain_name,
                    "nodeName": node_name,
                    "triggerTime": trigger_time,
                }
        return result

    def get_nodes_with_habit_names(self, chain_id: int) -> list[dict[str, Any]]:
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
            return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]
