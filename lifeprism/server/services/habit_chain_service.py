"""
habit_chain_service.py
Chain business logic.
"""
from datetime import datetime
from typing import Optional, List

from lifeprism.server.providers.habit_chain_provider import habit_chain_provider
from lifeprism.server.providers.habit_checkin_provider import habit_checkin_provider
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

    # --- Chain CRUD ---

    def get_chains(self, show_in_timeline: Optional[bool]) -> ChainListResponse:
        chains = habit_chain_provider.get_chains(show_in_timeline)
        items = []
        for chain in chains:
            nodes = habit_chain_provider.get_nodes_with_habit_names(chain["id"])
            items.append(self._build_chain_item(chain, nodes))
        return ChainListResponse(chains=items)

    def get_chain_detail(self, chain_id: int) -> ChainDetailResponse:
        chain = self._get_chain_or_404(chain_id)
        nodes = habit_chain_provider.get_nodes_with_habit_names(chain_id)
        return ChainDetailResponse(**self._build_chain_item(chain, nodes).model_dump())

    def create_chain(self, req: CreateChainRequest) -> ChainDetailResponse:
        data = req.model_dump(exclude_unset=True)
        chain_id = habit_chain_provider.create_chain(data)
        return self.get_chain_detail(chain_id)

    def update_chain(self, chain_id: int, req: UpdateChainRequest) -> ChainDetailResponse:
        chain = self._get_chain_or_404(chain_id)
        update_data = req.model_dump(exclude_unset=True)

        trigger_times = update_data.pop("triggerTimes", None)

        nodes = habit_chain_provider.get_nodes_by_chain(chain_id)
        if trigger_times is not None:
            trigger_time_map = {item["nodeId"]: item["triggerTime"] for item in trigger_times}
            for node in nodes:
                if node["id"] in trigger_time_map:
                    node["trigger_time"] = trigger_time_map[node["id"]]

        is_showing_in_timeline = update_data.get("showInTimeline", bool(chain.get("show_in_timeline", False)))
        self._validate_chain_timeline_rules(nodes, is_showing_in_timeline)

        if "showInTimeline" in update_data:
            update_data["show_in_timeline"] = update_data.pop("showInTimeline")

        if update_data:
            habit_chain_provider.update_chain(chain_id, update_data)

        if trigger_times is not None:
            for item in trigger_times:
                habit_chain_provider.update_node(item["nodeId"], {"trigger_time": item["triggerTime"]})

        return self.get_chain_detail(chain_id)

    def delete_chain(self, chain_id: int) -> None:
        self._get_chain_or_404(chain_id)
        habit_chain_provider.delete_chain(chain_id)

    # --- Node operations ---

    def create_node(self, chain_id: int, req: CreateNodeRequest) -> dict:
        chain = habit_chain_provider.get_chain_by_id(chain_id)
        existing = habit_chain_provider.get_nodes_by_chain(chain_id)

        if req.insertAfterNodeId is not None:
            after_node = next((n for n in existing if n["id"] == req.insertAfterNodeId), None)
            sort_order = (after_node["sort_order"] + 1) if after_node else len(existing) + 1
        else:
            sort_order = len(existing) + 1

        data = req.model_dump(exclude_unset=True)
        if "habitId" in data:
            data["habit_id"] = data.pop("habitId")
        if "triggerTime" in data:
            data["trigger_time"] = data.pop("triggerTime")
        data.pop("insertAfterNodeId", None)
        data["chain_id"] = chain_id
        data["sort_order"] = sort_order

        if bool(chain and chain.get("show_in_timeline", False)):
            simulated_nodes = [dict(node) for node in existing]
            if req.insertAfterNodeId is not None:
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
            self._validate_chain_timeline_rules(simulated_nodes, True)

        if req.insertAfterNodeId is not None:
            habit_chain_provider.increment_sort_order_after(chain_id, sort_order)

        node_id = habit_chain_provider.create_node(data)
        return habit_chain_provider.get_node_by_id(node_id)

    def update_node(self, node_id: int, req: UpdateNodeRequest) -> dict:
        node = self._get_node_or_404(node_id)
        chain_id = node["chain_id"]
        chain = habit_chain_provider.get_chain_by_id(chain_id)

        update_data = req.model_dump(exclude_unset=True)
        if "habitId" in update_data:
            update_data["habit_id"] = update_data.pop("habitId")
        if "triggerTime" in update_data:
            update_data["trigger_time"] = update_data.pop("triggerTime")

        if bool(chain and chain.get("show_in_timeline", False)):
            simulated_nodes = [dict(item) for item in habit_chain_provider.get_nodes_by_chain(chain_id)]
            for item in simulated_nodes:
                if item["id"] == node_id and "trigger_time" in update_data:
                    item["trigger_time"] = update_data["trigger_time"]
            self._validate_chain_timeline_rules(simulated_nodes, True)

        habit_chain_provider.update_node(node_id, update_data)
        return habit_chain_provider.get_node_by_id(node_id)

    def delete_node(self, node_id: int) -> None:
        node = self._get_node_or_404(node_id)
        chain_id = node["chain_id"]
        habit_chain_provider.delete_node(node_id)
        remaining = habit_chain_provider.get_nodes_by_chain(chain_id)
        sorted_nodes = sorted(remaining, key=lambda n: n["sort_order"])
        updates = [
            {"node_id": n["id"], "sort_order": i + 1}
            for i, n in enumerate(sorted_nodes)
        ]
        if updates:
            habit_chain_provider.batch_update_sort_order(updates)

    def reorder_nodes(self, chain_id: int, req: ReorderNodesRequest) -> None:
        existing = habit_chain_provider.get_nodes_by_chain(chain_id)
        existing_ids = {n["id"] for n in existing}
        request_ids = {item.nodeId for item in req.items}
        if existing_ids != request_ids:
            raise ValidationError(
                f"节点 ID 集合不匹配：期望 {existing_ids}，实际 {request_ids}"
            )

        updates = [{"node_id": item.nodeId, "sort_order": item.sortOrder} for item in req.items]

        chain = habit_chain_provider.get_chain_by_id(chain_id)
        if bool(chain and chain.get("show_in_timeline", False)):
            order_map = {item.nodeId: item.sortOrder for item in req.items}
            simulated_nodes = []
            for node in existing:
                copied = dict(node)
                copied["sort_order"] = order_map[node["id"]]
                simulated_nodes.append(copied)
            self._validate_chain_timeline_rules(simulated_nodes, True)

        habit_chain_provider.batch_update_sort_order(updates)

    # --- Timeline ---

    def get_timeline(self) -> TimelineResponse:
        chains = habit_chain_provider.get_chains(show_in_timeline=True)
        chain_items = []
        for chain in chains:
            nodes = habit_chain_provider.get_nodes_with_habit_names(chain["id"])
            habit_ids = [n["habit_id"] for n in nodes if n.get("habit_id")]
            today_map = habit_checkin_provider.get_today_checkins(habit_ids) if habit_ids else {}
            node_items = [
                TimelineNodeItem(
                    id=n["id"],
                    name=n["name"],
                    habitId=n.get("habit_id"),
                    habitName=n.get("habit_name"),
                    triggerTime=n.get("trigger_time"),
                    sortOrder=n["sort_order"],
                    todayCheckedIn=today_map.get(n.get("habit_id"), False),
                )
                for n in sorted(nodes, key=lambda x: x["sort_order"])
            ]
            chain_items.append(TimelineChainItem(id=chain["id"], name=chain["name"], nodes=node_items))
        return TimelineResponse(chains=chain_items)

    # --- helpers ---

    def _parse_time_to_minutes(self, time_value: Optional[str]) -> Optional[int]:
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
            raise ValidationError(f"{self._MSG_INVALID_TIME}: {time_value}")

        try:
            normalized = value.replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalized)
            return dt.hour * 60 + dt.minute
        except ValueError as exc:
            raise ValidationError(f"{self._MSG_INVALID_TIME}: {time_value}") from exc

    def _validate_chain_timeline_rules(self, nodes: List[dict], is_showing_in_timeline: bool) -> None:
        if not is_showing_in_timeline:
            return

        if not nodes:
            raise ValidationError(self._MSG_NO_NODES)

        sorted_nodes = sorted(nodes, key=lambda n: n["sort_order"])
        first_minutes = self._parse_time_to_minutes(sorted_nodes[0].get("trigger_time"))
        if first_minutes is None:
            raise ValidationError(self._MSG_FIRST_NODE_NEEDS_TIME)

        last_minutes = first_minutes
        for node in sorted_nodes[1:]:
            current_minutes = self._parse_time_to_minutes(node.get("trigger_time"))
            if current_minutes is None:
                continue
            if current_minutes < last_minutes:
                raise ValidationError(self._MSG_INVALID_ORDER)
            last_minutes = current_minutes

    def _get_chain_or_404(self, chain_id: int) -> dict:
        chain = habit_chain_provider.get_chain_by_id(chain_id)
        if not chain:
            raise NotFoundError(f"Chain {chain_id} not found")
        return chain

    def _get_node_or_404(self, node_id: int) -> dict:
        node = habit_chain_provider.get_node_by_id(node_id)
        if not node:
            raise NotFoundError(f"Node {node_id} not found")
        return node

    def _build_chain_item(self, chain: dict, nodes: list) -> ChainListItem:
        node_objs = [
            ChainNodeObject(
                id=n["id"],
                name=n["name"],
                habitId=n.get("habit_id"),
                habitName=n.get("habit_name"),
                triggerTime=n.get("trigger_time"),
                sortOrder=n["sort_order"],
            )
            for n in sorted(nodes, key=lambda x: x["sort_order"])
        ]
        return ChainListItem(
            id=chain["id"],
            name=chain["name"],
            description=chain.get("description"),
            showInTimeline=bool(chain.get("show_in_timeline")),
            nodes=node_objs,
        )


habit_chain_service = LazySingleton(HabitChainService)
