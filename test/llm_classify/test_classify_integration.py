"""
集成测试：使用真实数据测试 LLM 分类流程
测试范围：24小时内的真实 ActivityWatch 数据
"""
import asyncio
import logging
from datetime import datetime, timedelta

from lifeprism.processors.data_clean import clean_activitywatch_data
from lifeprism.server.providers import server_lw_data_provider, goal_provider
from lifeprism.llm.schemas import Goal as LLMGoal
from lifeprism.llm.classify.main_classify import LLMClassify
from lifeprism.llm.agent.loop import AgentLoop
from lifeprism.llm.channel.manager import channel_manager
from lifeprism.utils import get_logger

logger = get_logger(__name__, logging.DEBUG)


def build_classify_inputs():
    """
    获取分类所需的数据：classify_state, goals_for_llm, category_tree
    逻辑与 DataProcessingService._classify_apps 保持一致
    """
    # 时间范围：过去 24 小时
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=24)

    # 获取 ActivityWatch 数据并清洗
    category_map_cache_df = server_lw_data_provider.load_category_map_cache_V2()
    _filtered_data, classify_state = clean_activitywatch_data(
        start_time=start_time,
        end_time=end_time,
        category_map_cache_df=category_map_cache_df,
    )

    logger.info(f"待分类条目数: {len(classify_state.log_items) if classify_state.log_items else 0}")

    # 获取分类树
    category = server_lw_data_provider.load_categories()
    sub_category = server_lw_data_provider.load_sub_categories()

    import pandas as pd
    if sub_category is None:
        sub_category = pd.DataFrame(columns=['category_id', 'name', 'state'])
    category_tree = {}
    if category is not None and not category.empty:
        for _, cat in category.iterrows():
            if cat.get('state', 1) == 0:
                continue
            sub_mask = sub_category['category_id'] == cat['id']
            if 'state' in sub_category.columns:
                sub_mask = sub_mask & (sub_category['state'].fillna(1) == 1)
            category_tree[cat['name']] = sub_category[sub_mask]['name'].tolist()

    # 构建 goals
    goals_for_llm = []
    for g in goal_provider.get_active_goals_for_classify():
        cat_name = None
        sub_cat_name = None
        if g.get('link_to_category_id'):
            cat_row = category[category['id'] == g['link_to_category_id']]
            if not cat_row.empty:
                cat_name = cat_row.iloc[0]['name']
        if g.get('link_to_sub_category_id'):
            sub_row = sub_category[sub_category['id'] == g['link_to_sub_category_id']]
            if not sub_row.empty:
                sub_cat_name = sub_row.iloc[0]['name']
        goals_for_llm.append(LLMGoal(goal=g['name'], category=cat_name, sub_category=sub_cat_name))

    return classify_state, goals_for_llm, category_tree

def print_result(result, classify_mode: str):
    """打印分类结果"""
    if not result or not result.get('result_items'):
        logger.warning(f"[{classify_mode}] 分类结果为空")
        return
    items = result['result_items']
    print(f"\n{'='*80}")
    print(f"[{classify_mode}] 分类结果，共 {len(items)} 条")
    print('='*80)
    for item in items:
        goal_str = f" -> {item.link_to_goal}" if item.link_to_goal else ""
        cat_str = f"{item.category or '未分类'}/{item.sub_category or '-'}"
        print(f"  [{item.id:>3}] {item.app:<20} | {cat_str:<25} | {item.duration:>5}s{goal_str}")
        if item.title:
            print(f"         title: {item.title[:60]}")
    print('='*80)


async def run_test(classify_mode: str):
    """运行单次分类测试"""
    logger.info(f"\n开始集成测试: classify_mode={classify_mode}")

    # 启动 AgentLoop
    agent = AgentLoop()
    loop_task = asyncio.create_task(agent.loop())

    try:
        classify_state, goals_for_llm, category_tree = build_classify_inputs()

        if not classify_state.log_items:
            logger.warning("过去24小时内无待分类数据，测试结束")
            return

        logger.info(f"待分类: {len(classify_state.log_items)} 条，category_tree: {list(category_tree.keys())}")

        classifier = LLMClassify(
            classify_mode=classify_mode,
            goal=goals_for_llm,
            category_tree=category_tree,
        )

        result = await classifier.classify(classify_state)
        print_result(result, classify_mode)

    finally:
        loop_task.cancel()
        await channel_manager.close()
        try:
            await loop_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "classify_simple"
    print(f"运行分类集成测试，模式: {mode}")
    print("可用模式: classify_simple | classify_graph")
    asyncio.run(run_test(mode))
