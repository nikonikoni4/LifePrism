"""
功能描述: 简化版分类器，一步分类
date: 2025.12.17
"""
import asyncio
import json
import logging
from lifeprism.llm.schemas.classify_shemas import classifyState
from lifeprism.llm.utils import (
    extract_json_from_response,
    parse_classification_result,
    format_goals_for_prompt,
    format_category_tree_for_prompt,
)
from lifeprism.llm.bus import OutboundMessage, bus, InboundMessage,MessageType

MAX_LOG_ITEMS = 15

logger = logging.getLogger(__name__)


class ClassifySimple:
    def __init__(self, goal: list, category_tree: dict):
        self.goal = goal
        self.category_tree = category_tree

    async def _classify_batch(self, batch: list, batch_num: int, system_prompt: str,
                               app_registry: dict, result_items: list):
        """单批次分类"""
        compact_data = [
            [
                item.id,
                item.app,
                app_registry[item.app].description if item.app in app_registry else None,
                item.title,
                app_registry[item.app].is_multipurpose if item.app in app_registry else False,
            ]
            for item in batch
        ]
        user_content = f"数据格式：[id, app_name, app_description, title, is_multipurpose]\n{json.dumps(compact_data, ensure_ascii=False)}"
        msg = InboundMessage(
            content=user_content,
            type=MessageType.CLASSIFY,
            extra={"system_prompt": system_prompt},
        )
        raw :OutboundMessage = await bus.send(msg)
        raw = raw.response.content
        clean = extract_json_from_response(raw)
        if not clean:
            logger.error("classify_simple 批次 %s 返回空内容，跳过", batch_num)
            return
        parse_classification_result(result_items, json.loads(clean), "classify_simple")

    async def classify(self, state: classifyState) -> dict:
        if not state.log_items:
            logger.info("log_items 为空，跳过分类")
            return {"result_items": None, "tokens_usage": {}}

        goal_str = format_goals_for_prompt(self.goal)
        category_str = format_category_tree_for_prompt(self.category_tree)

        system_prompt = f"""\
你是一个软件分类专家。你的任务是根据软件名称、描述，将软件进行分类，分类有 category 和 sub_category 两级分类。
# 分类类别
{category_str}
# 用户目标
{goal_str}
# 分类规则
1. 对于 app 与 goal 高度相关的条目，使用 goal 的分类类别，并关联 goal，link_to_goal = goal；否则 link_to_goal = null
2. 对于单用途，依据 app_description 进行分类；若无法分类则为 null
3. 对于多用途，依据 app、app_description 和 title 进行分类
4. 若 category 有分类而 sub_category 无法分类，则 sub_category = null
# 输出格式为 JSON，key 为数据的 id，value 为 [category, sub_category, link_to_goal]
{{
    "id": ["category", "sub_category", "link_to_goal"]
}}
注意：value 必须是列表，包含三个元素；无值时使用 null；key 必须是 id。\
"""
        all_result_items = list(state.log_items)
        batches = [state.log_items[i:i + MAX_LOG_ITEMS] for i in range(0, len(state.log_items), MAX_LOG_ITEMS)]
        logger.info("classify_simple 共 %s 条，分 %s 批并发", len(state.log_items), len(batches))
        await asyncio.gather(*[
            self._classify_batch(batch, i + 1, system_prompt, state.app_registry, all_result_items)
            for i, batch in enumerate(batches)
        ])
        return {"result_items": all_result_items}
