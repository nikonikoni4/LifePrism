"""
habit_chain_service.py
Chain business logic.
"""
from datetime import datetime
from typing import Optional, List

from lifeprism.server.errors.error_codes import (
    CHAIN_NODE_VALIDATION_FAILED,
    CHAIN_NOT_FOUND,
    CHAIN_VALIDATION_FAILED,
    NODE_NOT_FOUND,
    REORDER_VALIDATION_FAILED,
)
from lifeprism.repository import habit_repository, habit_chain_repository
from lifeprism.server.schemas.habit_schemas import (
    CreateChainRequest,
    UpdateChainRequest,
    CreateNodeRequest,
    UpdateNodeRequest,
    ReorderNodesRequest,
    ChainNodeObject,
    ChainListItem,
    ChainDetailResponse,
    ChainListResponse,
    TimelineResponse,
    TimelineChainItem,
    TimelineNodeItem,
)
from lifeprism.utils import get_logger, LazySingleton
from lifeprism.utils.exceptions import NotFoundError, ValidationError

logger = get_logger(__name__)


class HabitChainService:

    _MSG_NO_NODES = "链中没有节点，无法加入 Timeline"
    _MSG_FIRST_NODE_NEEDS_TIME = "第一个节点必须设置触发时间才能加入 Timeline"
    _MSG_INVALID_TIME = "节点触发时间格式非法"
    _MSG_INVALID_ORDER = "节点触发时间顺序不合理：后续节点时间不能早于前序节点"

    # 时间计算常量
    _DEFAULT_INTERVAL_MINUTES = 30  # 默认时长（分钟）
    _MIN_GAP_MINUTES = 10  # 相邻节点最小间距（分钟）

    # --- Chain CRUD ---

    def get_chains(self, show_in_timeline: Optional[bool]) -> ChainListResponse:
        chains = habit_chain_repository.get_chains(show_in_timeline)
        items = []
        for chain in chains:
            nodes = habit_chain_repository.get_nodes_with_habit_names(chain["id"])
            items.append(self._build_chain_item(chain, nodes))
        return ChainListResponse(chains=items)

    def get_chain_detail(self, chain_id: int) -> ChainDetailResponse:
        chain = self._get_chain_or_404(chain_id)
        nodes = habit_chain_repository.get_nodes_with_habit_names(chain_id)
        nodes_with_calculated = self._calculate_node_times(nodes)
        return ChainDetailResponse(**self._build_chain_item(chain, nodes_with_calculated).model_dump())

    def create_chain(self, req: CreateChainRequest) -> ChainDetailResponse:
        data = req.model_dump(exclude_unset=True)
        chain_id = habit_chain_repository.create_chain(data)
        return self.get_chain_detail(chain_id)

    def update_chain(self, chain_id: int, req: UpdateChainRequest) -> ChainDetailResponse:
        chain = self._get_chain_or_404(chain_id)
        update_data = req.model_dump(exclude_unset=True)

        trigger_times = update_data.pop("trigger_times", None)

        nodes = habit_chain_repository.get_nodes_by_chain(chain_id)
        if trigger_times is not None:
            trigger_time_map = {item["node_id"]: item["trigger_time"] for item in trigger_times}
            for node in nodes:
                if node["id"] in trigger_time_map:
                    node["trigger_time"] = trigger_time_map[node["id"]]

        is_showing_in_timeline = update_data.get("show_in_timeline", bool(chain.get("show_in_timeline", False)))
        self._validate_chain_timeline_rules(nodes, is_showing_in_timeline, CHAIN_VALIDATION_FAILED)

        if update_data:
            habit_chain_repository.update_chain(chain_id, update_data)

        if trigger_times is not None:
            for item in trigger_times:
                habit_chain_repository.update_node(item["node_id"], {"trigger_time": item["trigger_time"]})

        return self.get_chain_detail(chain_id)

    def delete_chain(self, chain_id: int) -> None:
        self._get_chain_or_404(chain_id)
        habit_chain_repository.delete_chain(chain_id)

    # --- Node operations ---

    def create_node(self, chain_id: int, req: CreateNodeRequest) -> dict:
        chain = self._get_chain_or_404(chain_id)
        existing = habit_chain_repository.get_nodes_by_chain(chain_id)

        if req.insert_after_node_id is not None:
            after_node = next((n for n in existing if n["id"] == req.insert_after_node_id), None)
            sort_order = (after_node["sort_order"] + 1) if after_node else len(existing) + 1
        else:
            sort_order = len(existing) + 1

        data = req.model_dump(exclude_unset=True)
        data.pop("insert_after_node_id", None)
        data["chain_id"] = chain_id
        data["sort_order"] = sort_order

        if bool(chain and chain.get("show_in_timeline", False)):
            simulated_nodes = [dict(node) for node in existing]
            if req.insert_after_node_id is not None:
                for node in simulated_nodes:
                    if node["sort_order"] >= sort_order:
                        node["sort_order"] += 1
            simulated_nodes.append(
                {
                    "id": -1,
                    "sort_order": sort_order,
                    "trigger_time": data.get("trigger_time"),
                }
            )
            self._validate_chain_timeline_rules(simulated_nodes, True, CHAIN_NODE_VALIDATION_FAILED)

        if req.insert_after_node_id is not None:
            habit_chain_repository.increment_sort_order_after(chain_id, sort_order)

        node_id = habit_chain_repository.create_node(data)
        return habit_chain_repository.get_node_by_id(node_id)

    def update_node(self, node_id: int, req: UpdateNodeRequest) -> dict:
        node = self._get_node_or_404(node_id)
        chain_id = node["chain_id"]
        chain = habit_chain_repository.get_chain_by_id(chain_id)

        update_data = req.model_dump(exclude_unset=True)

        if bool(chain and chain.get("show_in_timeline", False)):
            simulated_nodes = [dict(item) for item in habit_chain_repository.get_nodes_by_chain(chain_id)]
            for item in simulated_nodes:
                if item["id"] == node_id and "trigger_time" in update_data:
                    item["trigger_time"] = update_data["trigger_time"]
            self._validate_chain_timeline_rules(simulated_nodes, True, CHAIN_NODE_VALIDATION_FAILED)

        habit_chain_repository.update_node(node_id, update_data)
        return habit_chain_repository.get_node_by_id(node_id)

    def delete_node(self, node_id: int) -> None:
        node = self._get_node_or_404(node_id)
        chain_id = node["chain_id"]
        habit_chain_repository.delete_node(node_id)
        remaining = habit_chain_repository.get_nodes_by_chain(chain_id)
        sorted_nodes = sorted(remaining, key=lambda n: n["sort_order"])
        updates = [
            {"node_id": n["id"], "sort_order": i + 1}
            for i, n in enumerate(sorted_nodes)
        ]
        if updates:
            habit_chain_repository.batch_update_sort_order(updates)

    def reorder_nodes(self, chain_id: int, req: ReorderNodesRequest) -> None:
        existing = habit_chain_repository.get_nodes_by_chain(chain_id)
        existing_ids = {n["id"] for n in existing}
        request_ids = {item.node_id for item in req.items}
        if existing_ids != request_ids:
            raise ValidationError(
                f"节点 ID 集合不匹配：期望 {existing_ids}，实际 {request_ids}",
                code=REORDER_VALIDATION_FAILED,
            )

        updates = [{"node_id": item.node_id, "sort_order": item.sort_order} for item in req.items]

        chain = habit_chain_repository.get_chain_by_id(chain_id)
        if bool(chain and chain.get("show_in_timeline", False)):
            order_map = {item.node_id: item.sort_order for item in req.items}
            simulated_nodes = []
            for node in existing:
                copied = dict(node)
                copied["sort_order"] = order_map[node["id"]]
                simulated_nodes.append(copied)
            self._validate_chain_timeline_rules(simulated_nodes, True, REORDER_VALIDATION_FAILED)

        habit_chain_repository.batch_update_sort_order(updates)

    # --- Timeline ---

    def get_timeline(self) -> TimelineResponse:
        chains = habit_chain_repository.get_chains(show_in_timeline=True)
        chain_items = []
        for chain in chains:
            nodes = habit_chain_repository.get_nodes_with_habit_names(chain["id"])
            # 计算每个节点的 calculated_time（不存库）
            nodes_with_calculated = self._calculate_node_times(nodes)
            habit_ids = [n["habit_id"] for n in nodes if n.get("habit_id")]
            today_map = habit_repository.get_today_checkins(habit_ids) if habit_ids else {}
            node_items = [
                TimelineNodeItem(
                    id=n["id"],
                    name=n["name"],
                    habit_id=n.get("habit_id"),
                    habit_name=n.get("habit_name"),
                    trigger_time=n.get("trigger_time"),           # 原始值
                    calculated_time=n.get("calculated_time"),     # 计算值
                    sort_order=n["sort_order"],
                    today_checked_in=today_map.get(n.get("habit_id"), False),
                )
                for n in sorted(nodes_with_calculated, key=lambda x: x["sort_order"])
            ]
            chain_items.append(TimelineChainItem(id=chain["id"], name=chain["name"], nodes=node_items))
        return TimelineResponse(chains=chain_items)

    # --- helpers ---

    def _parse_time_to_minutes(self, time_value: Optional[str], error_code: str) -> Optional[int]:
        if time_value is None:
            return None

        value = str(time_value).strip()
        if not value:
            return None

        parts = value.split(":")
        if len(parts) == 2 and all(part.isdigit() for part in parts):
            hour = int(parts[0])
            minute = int(parts[1])
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return hour * 60 + minute
            raise ValidationError(f"{self._MSG_INVALID_TIME}: {time_value}", code=error_code)

        try:
            normalized = value.replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalized)
            return dt.hour * 60 + dt.minute
        except ValueError as exc:
            raise ValidationError(f"{self._MSG_INVALID_TIME}: {time_value}", code=error_code) from exc

    def _calculate_node_times(self, nodes: List[dict]) -> List[dict]:
        """
        计算每个节点的 calculated_time（不存库，仅返回计算结果）

        规则：
        - 显式设置的 trigger_time 保持不变
        - 隐式节点（无 trigger_time）根据规则计算：
          a. 若后续有显式节点，按平均间距分配
          b. 若后续无显式节点，按默认30min递推

        返回的节点中，calculated_time 字段已填充计算结果
        """
        if not nodes:
            return nodes

        sorted_nodes = sorted(nodes, key=lambda n: n["sort_order"])

        # 找出所有锚点（显式设置了 trigger_time 的节点）
        anchors = []
        for i, node in enumerate(sorted_nodes):
            if node.get("trigger_time"):
                minutes = self._parse_time_to_minutes(node["trigger_time"], "INTERNAL_ERROR")
                anchors.append({"index": i, "minutes": minutes, "original_time": node["trigger_time"]})

        # 情况A：没有锚点，所有节点按默认30min递推
        if not anchors:
            current_minutes = 0  # 从0点开始
            for node in sorted_nodes:
                node["calculated_time"] = self._format_minutes_to_time(current_minutes)
                current_minutes += self._DEFAULT_INTERVAL_MINUTES
            return sorted_nodes

        # 情况B：有锚点，处理第一段（第一个锚点之前的节点）
        first_anchor = anchors[0]
        if first_anchor["index"] > 0:
            current_minutes = first_anchor["minutes"] - (first_anchor["index"] * self._DEFAULT_INTERVAL_MINUTES)
            for i in range(first_anchor["index"]):
                sorted_nodes[i]["calculated_time"] = self._format_minutes_to_time(current_minutes)
                current_minutes += self._DEFAULT_INTERVAL_MINUTES

        # 锚点本身的 calculated_time 等于 trigger_time
        for anchor in anchors:
            sorted_nodes[anchor["index"]]["calculated_time"] = anchor["original_time"]

        # 处理锚点之间的节点
        for a in range(len(anchors) - 1):
            curr_anchor = anchors[a]
            next_anchor = anchors[a + 1]
            nodes_between = next_anchor["index"] - curr_anchor["index"] - 1

            if nodes_between == 0:
                # 连续锚点，中间无节点
                pass
            else:
                # 有中间节点，平均分配
                total_minutes = next_anchor["minutes"] - curr_anchor["minutes"]
                interval = total_minutes / (nodes_between + 1)
                for i in range(nodes_between):
                    idx = curr_anchor["index"] + 1 + i
                    sorted_nodes[idx]["calculated_time"] = self._format_minutes_to_time(
                        curr_anchor["minutes"] + int(interval * (i + 1))
                    )

        # 处理最后一个锚点之后的节点
        last_anchor = anchors[-1]
        if last_anchor["index"] < len(sorted_nodes) - 1:
            current_minutes = last_anchor["minutes"] + self._DEFAULT_INTERVAL_MINUTES
            for i in range(last_anchor["index"] + 1, len(sorted_nodes)):
                sorted_nodes[i]["calculated_time"] = self._format_minutes_to_time(current_minutes)
                current_minutes += self._DEFAULT_INTERVAL_MINUTES

        return sorted_nodes

    def _format_minutes_to_time(self, minutes: int) -> str:
        """将分钟数转换为 HH:mm 格式"""
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours:02d}:{mins:02d}"

    def _validate_chain_timeline_rules(
        self, nodes: List[dict], is_showing_in_timeline: bool, error_code: str,
    ) -> None:
        if not is_showing_in_timeline:
            return

        if not nodes:
            raise ValidationError(self._MSG_NO_NODES, code=error_code)

        sorted_nodes = sorted(nodes, key=lambda n: n["sort_order"])
        first_minutes = self._parse_time_to_minutes(sorted_nodes[0].get("trigger_time"), error_code)
        if first_minutes is None:
            raise ValidationError(self._MSG_FIRST_NODE_NEEDS_TIME, code=error_code)

        last_minutes = first_minutes
        for node in sorted_nodes[1:]:
            current_minutes = self._parse_time_to_minutes(node.get("trigger_time"), error_code)
            if current_minutes is None:
                continue
            if current_minutes < last_minutes:
                raise ValidationError(self._MSG_INVALID_ORDER, code=error_code)
            # 新增：检查相邻节点最小间距
            gap = current_minutes - last_minutes
            if gap < self._MIN_GAP_MINUTES:
                prev_time = self._format_minutes_to_time(last_minutes)
                curr_time = self._format_minutes_to_time(current_minutes)
                raise ValidationError(
                    f"节点触发时间间距不足：{prev_time} → {curr_time} 间距{gap}min，要求>={self._MIN_GAP_MINUTES}min",
                    code=error_code
                )
            last_minutes = current_minutes

    def _get_chain_or_404(self, chain_id: int) -> dict:
        chain = habit_chain_repository.get_chain_by_id(chain_id)
        if not chain:
            raise NotFoundError(f"Chain {chain_id} not found", code=CHAIN_NOT_FOUND)
        return chain

    def _get_node_or_404(self, node_id: int) -> dict:
        node = habit_chain_repository.get_node_by_id(node_id)
        if not node:
            raise NotFoundError(f"Node {node_id} not found", code=NODE_NOT_FOUND)
        return node

    def _build_chain_item(self, chain: dict, nodes: list) -> ChainListItem:
        node_objs = [
            ChainNodeObject(
                id=n["id"],
                name=n["name"],
                habit_id=n.get("habit_id"),
                habit_name=n.get("habit_name"),
                trigger_time=n.get("trigger_time"),
                calculated_time=n.get("calculated_time"),
                sort_order=n["sort_order"],
            )
            for n in sorted(nodes, key=lambda x: x["sort_order"])
        ]
        return ChainListItem(
            id=chain["id"],
            name=chain["name"],
            description=chain.get("description"),
            show_in_timeline=bool(chain.get("show_in_timeline")),
            nodes=node_objs,
        )


habit_chain_service = LazySingleton(HabitChainService)
