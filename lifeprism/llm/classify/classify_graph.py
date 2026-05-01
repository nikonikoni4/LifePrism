"""
功能描述: 多步分类器，替代原 LangGraph 实现
date: 2025.12.17
"""
import asyncio
import json
import logging
from lifeprism.llm.schemas.classify_shemas import classifyState, LogItem
from lifeprism.llm.utils import (
    format_goals_for_prompt,
    format_category_tree_for_prompt,
    format_log_items_table,
    extract_json_from_response,
    parse_classification_result,
    split_by_purpose,
    split_by_duration,
)
from lifeprism.llm.bus import OutboundMessage, bus, InboundMessage,MessageType

MAX_LOG_ITEMS = 10
MAX_TITLE_ITEMS = 5
MAX_RETRIES = 3

logger = logging.getLogger(__name__)


class ClassifyGraph:
    def __init__(self, goal: list, category_tree: dict):
        self.goal = goal
        self.category_tree = category_tree

    async def _titles_then_long_classify(self, state: classifyState, long_items: list[LogItem]) -> list[LogItem]:
        """get_titles -> multi_classify_long 串行链，整体可与其他分支并发"""
        long_items = await self.get_titles(long_items)
        return await self.multi_classify_long(state, long_items)

    async def classify(self, state: classifyState) -> dict:
        if not state.log_items:
            logger.info("log_items 为空，跳过分类")
            return {"result_items": None}

        # node 1: 获取 app 描述（必须先完成，后续分类依赖 description）
        state = await self.get_app_description(state)

        # 按用途/时长分流
        split = split_by_purpose(state)
        single_items = split.get("log_items_for_single", [])
        multi_items = split.get("log_items_for_multi", [])
        duration_split = split_by_duration(multi_items) if multi_items else {}
        short_items = duration_split.get("log_items_for_multi_short") or []
        long_items = duration_split.get("log_items_for_multi_long") or []

        # node 2a/2b: 三条分支无互相依赖，并发执行
        # long 分支内部 get_titles -> multi_classify_long 仍保持串行
        branches = []
        if single_items:
            branches.append(self.single_classify(state, single_items))
        if short_items:
            branches.append(self.multi_classify_short(state, short_items))
        if long_items:
            branches.append(self._titles_then_long_classify(state, long_items))

        results = await asyncio.gather(*branches)
        result_items: list[LogItem] = []
        for r in results:
            result_items.extend(r)

        return {"result_items": result_items}

    async def _fetch_one_description(self, app: str, app_info, system_prompt: str):
        """为单个 app 获取描述，带重试"""
        title_sample = ""
        if not app_info.is_multipurpose and app_info.titles:
            title_sample = app_info.titles[0]
        content = f"软件名称: {app}" + (f"\ntitle 样本: {title_sample}" if title_sample else "")
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                msg = InboundMessage(
                    content=content,
                    type=MessageType.CLASSIFY,
                    extra={"system_prompt": system_prompt},
                )
                result :OutboundMessage = await bus.send(msg)
                result = result.response.content
                if result and result.strip() and result.strip().lower() != "none":
                    app_info.description = result.strip()
                    logger.info(f"获取 {app} 描述成功: {result[:50]}")
                    return
                logger.warning(f"获取 {app} 描述为空（第 {attempt}/{MAX_RETRIES} 次）")
            except Exception as e:
                logger.warning(f"获取 {app} 描述异常（第 {attempt}/{MAX_RETRIES} 次）: {e}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(0.5)
        logger.warning(f"获取 {app} 描述失败，已重试 {MAX_RETRIES} 次，跳过")

    async def get_app_description(self, state: classifyState) -> classifyState:
        """node 1: 并发为没有描述的 app 获取描述"""
        system_prompt = (
            "你是一个软件信息搜索助手。请根据软件名称搜索并简短描述该软件的主要用途（50字以内）。\n"
            "若软件名称附带了 title 样本，可作为辅助判断依据。\n"
            "只输出描述文字，不要输出 JSON 或其他格式。"
        )
        apps_without_desc = [
            (app, app_info)
            for app, app_info in state.app_registry.items()
            if not app_info.description
        ]
        await asyncio.gather(*[
            self._fetch_one_description(app, app_info, system_prompt)
            for app, app_info in apps_without_desc
        ])
        return state

    async def _single_classify_batch(self, batch: list, batch_num: int, system_prompt: str,
                                       app_registry: dict, result_items: list):
        """单用途分类单批次"""
        content = format_log_items_table(
            batch, fields=["id", "app", "title"],
            app_registry=app_registry, group_by_app=True, show_app_description=True
        )
        msg = InboundMessage(
            content=content,
            type=MessageType.CLASSIFY,
            extra={"system_prompt": system_prompt},
        )
        raw :OutboundMessage = await bus.send(msg)
        raw = raw.response.content
        clean = extract_json_from_response(raw)
        if not clean:
            logger.error(f"single_classify 批次 {batch_num} 返回空内容，跳过")
            return
        parse_classification_result(result_items, json.loads(clean), "single_classify")

    async def single_classify(self, state: classifyState, items: list[LogItem]) -> list[LogItem]:
        """node 2a: 单用途 app 并发分类"""
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
3. 若 category 有分类而 sub_category 无法分类，则 sub_category = null
4. 若无法分类，则分类为 null
# 输出格式为 JSON，key 为数据的 id，value 为 [category, sub_category, link_to_goal]
注意：value 必须是列表，包含三个元素；无值时使用 null；key 必须是 id。\
"""
        result_items = list(items)
        batches = [items[i:i + MAX_LOG_ITEMS] for i in range(0, len(items), MAX_LOG_ITEMS)]
        logger.info(f"single_classify 共 {len(items)} 条，分 {len(batches)} 批并发")
        await asyncio.gather(*[
            self._single_classify_batch(batch, i + 1, system_prompt, state.app_registry, result_items)
            for i, batch in enumerate(batches)
        ])
        return result_items

    async def _multi_classify_short_batch(self, batch: list, batch_num: int, system_prompt: str, result_items: list):
        """短时长多用途分类单批次"""
        content = format_log_items_table(batch, fields=["id", "app", "title"])
        msg = InboundMessage(
            content=content,
            type=MessageType.CLASSIFY,
            extra={"system_prompt": system_prompt},
        )
        raw :OutboundMessage = await bus.send(msg)
        raw = raw.response.content
        clean = extract_json_from_response(raw)
        if not clean:
            logger.error(f"multi_classify_short 批次 {batch_num} 返回空内容，跳过")
            return
        parse_classification_result(result_items, json.loads(clean), "multi_classify_short")

    async def multi_classify_short(self, state: classifyState, items: list[LogItem]) -> list[LogItem]:
        """node 2b-short: 短时长多用途并发分类"""
        goal_str = format_goals_for_prompt(self.goal)
        category_str = format_category_tree_for_prompt(self.category_tree)
        system_prompt = f"""\
你是一个用户行为分析专家，依据用户浏览的网页 title 对用户行为进行分类。
# 类别
{category_str}
# 用户目标
{goal_str}
# 分类规则
1. 对于与 goal 高度相关的条目，使用 goal 的分类类别，并关联 goal；否则 link_to_goal = null
2. 类别有两个层级 category -> sub_category，sub_category 要属于 category
3. 若 category 有分类而 sub_category 无法分类，则 sub_category = null
4. 若无法分类，则分类为 null
# 输出格式为 JSON，key 为 id，value 为 [category, sub_category, link_to_goal]\
"""
        result_items = list(items)
        batches = [items[i:i + MAX_LOG_ITEMS] for i in range(0, len(items), MAX_LOG_ITEMS)]
        logger.info(f"multi_classify_short 共 {len(items)} 条，分 {len(batches)} 批并发")
        await asyncio.gather(*[
            self._multi_classify_short_batch(batch, i + 1, system_prompt, result_items)
            for i, batch in enumerate(batches)
        ])
        return result_items

    async def _fetch_one_title(self, item: LogItem, system_prompt: str):
        """为单个条目获取 title 分析"""
        if not item.title:
            return
        try:
            result :OutboundMessage = await bus.send(InboundMessage(
                content=f"搜索并分析 {item.title}",
                type=MessageType.CLASSIFY,
                extra={"system_prompt": system_prompt},
            ))
            item.title_analysis = result.response.content
        except Exception as e:
            logger.warning(f"get_titles 分析 title={item.title!r} 失败: {e}")

    async def get_titles(self, items: list[LogItem]) -> list[LogItem]:
        """node 3: 并发为长时长多用途条目获取 title 分析"""
        system_prompt = (
            "你是一个通过网络搜索分析的助手，依据网络搜索结果和 title 分析用户的活动，"
            "要求结果在30字以内。只输出描述文字（用户活动），不要输出其他内容。"
        )
        await asyncio.gather(*[
            self._fetch_one_title(item, system_prompt)
            for item in items
        ])
        return items

    async def _multi_classify_long_batch(self, batch: list, batch_num: int, system_prompt: str, result_items: list):
        """长时长多用途分类单批次"""
        content = format_log_items_table(batch, fields=["id", "app", "title", "title_analysis"])
        msg = InboundMessage(
            content=content,
            type=MessageType.CLASSIFY,
            extra={"system_prompt": system_prompt},
        )
        raw :OutboundMessage = await bus.send(msg)
        raw = raw.response.content
        clean = extract_json_from_response(raw)
        if not clean:
            logger.error(f"multi_classify_long 批次 {batch_num} 返回空内容，跳过")
            return
        parse_classification_result(result_items, json.loads(clean), "multi_classify_long")

    async def multi_classify_long(self, state: classifyState, items: list[LogItem]) -> list[LogItem]:
        """node 4: 长时长多用途并发分类"""
        goal_str = format_goals_for_prompt(self.goal)
        category_str = format_category_tree_for_prompt(self.category_tree)
        system_prompt = f"""\
你是一个用户行为分类专家。根据网页标题（Title）和标题分析（Title Analysis）对用户行为进行分类。
# 分类类别
{category_str}
# 用户目标
{goal_str}
# 分类规则
1. 对于与 goal 高度相关的条目，使用 goal 的分类类别，并关联 goal，link_to_goal = goal；否则 link_to_goal = null
2. 主要依据 Title Analysis 理解用户活动，结合 Title 进行分类
3. 类别有两个层级 category -> sub_category，sub_category 要属于 category
4. 若 category 有分类而 sub_category 无法分类，则 sub_category = null
5. 若无法分类，则分类为 null
# 输出格式为 JSON，key 为 id，value 为 [category, sub_category, link_to_goal]\
"""
        result_items = list(items)
        batches = [items[i:i + MAX_LOG_ITEMS] for i in range(0, len(items), MAX_LOG_ITEMS)]
        logger.info(f"multi_classify_long 共 {len(items)} 条，分 {len(batches)} 批并发")
        await asyncio.gather(*[
            self._multi_classify_long_batch(batch, i + 1, system_prompt, result_items)
            for i, batch in enumerate(batches)
        ])
        return result_items
