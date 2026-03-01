"""
habit_chain_service.py
链式习惯业务逻辑。
"""
from typing import Optional, List

from lifeprism.server.providers.habit_chain_provider import habit_chain_provider
from lifeprism.server.providers.habit_checkin_provider import habit_checkin_provider
from lifeprism.server.schemas.habit_schemas import (
    CreateChainRequest, UpdateChainRequest,
    CreateNodeRequest, UpdateNodeRequest,
    ReorderNodesRequest,
    ChainNodeObject, ChainListItem, ChainDetailResponse,
    ChainListResponse, TimelineResponse, TimelineChainItem, TimelineNodeItem,
)
from lifeprism.utils import get_logger, LazySingleton
from lifeprism.utils.exceptions import NotFoundError, ValidationError

logger = get_logger(__name__)


class HabitChainService:

    # ─── 链 CRUD ───

    def get_chains(self, show_in_timeline: Optional[bool]) -> ChainListResponse:
        chains = habit_chain_provider.get_chains(show_in_timeline)
        items = []
        for c in chains:
            nodes = habit_chain_provider.get_nodes_with_habit_names(c["id"])
            items.append(self._build_chain_item(c, nodes))
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

        # 1. 抽取批量节点时间更新
        trigger_times = update_data.pop("triggerTimes", None)

        # 2. 如果请求中包含了时间更新，去获取当前节点并与将更新的时间合并（模拟内存态）
        nodes = habit_chain_provider.get_nodes_by_chain(chain_id)
        if trigger_times is not None:
            # 建立 nodeId 到 triggerTime 的映射
            tt_map = {item["nodeId"]: item["triggerTime"] for item in trigger_times}
            for n in nodes:
                if n["id"] in tt_map:
                    n["trigger_time"] = tt_map[n["id"]]

        # 3. 业务校验: 判断最终是否要在 Timeline 中展示
        is_showing_in_timeline = update_data.get("showInTimeline", bool(chain.get("show_in_timeline", False)))

        if is_showing_in_timeline:
            if not nodes:
                raise ValidationError("链中没有节点，无法加入 Timeline")
            first = sorted(nodes, key=lambda n: n["sort_order"])[0]
            if not first.get("trigger_time"):
                raise ValidationError("第一个节点必须设置触发时间才能加入 Timeline")

        # 转换 camelCase -> snake_case，以匹配 provider 的 allowed_fields
        if "showInTimeline" in update_data:
            update_data["show_in_timeline"] = update_data.pop("showInTimeline")

        # 更新链条的配置
        if update_data:
            habit_chain_provider.update_chain(chain_id, update_data)
            
        # 逐个更新节点的时间
        if trigger_times is not None:
            for item in trigger_times:
                habit_chain_provider.update_node(item["nodeId"], {"trigger_time": item["triggerTime"]})

        return self.get_chain_detail(chain_id)

    def delete_chain(self, chain_id: int) -> None:
        self._get_chain_or_404(chain_id)
        habit_chain_provider.delete_chain(chain_id)

    # ─── 节点操作 ───

    def create_node(self, chain_id: int, req: CreateNodeRequest) -> dict:
        existing = habit_chain_provider.get_nodes_by_chain(chain_id)
        if req.insertAfterNodeId is not None:
            after_node = next(
                (n for n in existing if n["id"] == req.insertAfterNodeId), None
            )
            sort_order = (after_node["sort_order"] + 1) if after_node else len(existing) + 1
            habit_chain_provider.increment_sort_order_after(chain_id, sort_order)
        else:
            sort_order = len(existing) + 1

        data = req.model_dump(exclude_unset=True)
        # 转换 camelCase -> snake_case for provider
        if "habitId" in data:
            data["habit_id"] = data.pop("habitId")
        if "triggerTime" in data:
            data["trigger_time"] = data.pop("triggerTime")
        data.pop("insertAfterNodeId", None)
        data["chain_id"] = chain_id
        data["sort_order"] = sort_order

        node_id = habit_chain_provider.create_node(data)
        return habit_chain_provider.get_node_by_id(node_id)

    def update_node(self, node_id: int, req: UpdateNodeRequest) -> dict:
        self._get_node_or_404(node_id)
        update_data = req.model_dump(exclude_unset=True)
        # 转换 camelCase -> snake_case
        if "habitId" in update_data:
            update_data["habit_id"] = update_data.pop("habitId")
        if "triggerTime" in update_data:
            update_data["trigger_time"] = update_data.pop("triggerTime")
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
        updates = [
            {"node_id": item.nodeId, "sort_order": item.sortOrder}
            for item in req.items
        ]
        habit_chain_provider.batch_update_sort_order(updates)

    # ─── Timeline ───

    def get_timeline(self) -> TimelineResponse:
        chains = habit_chain_provider.get_chains(show_in_timeline=True)
        chain_items = []
        for c in chains:
            nodes = habit_chain_provider.get_nodes_with_habit_names(c["id"])
            habit_ids = [n["habit_id"] for n in nodes if n.get("habit_id")]
            today_map = (
                habit_checkin_provider.get_today_checkins(habit_ids)
                if habit_ids
                else {}
            )
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
            chain_items.append(
                TimelineChainItem(id=c["id"], name=c["name"], nodes=node_items)
            )
        return TimelineResponse(chains=chain_items)

    # ─── 私有辅助 ───

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
