"""
功能描述: 简化版云端分类器，整合旧版 cloud_classifier.py 的逻辑
特点：
- 使用 create_ChatTongyiModel 创建模型
- 使用 SystemMessage/HumanMessage 格式
- 输入输出使用 classifyState
- 不区分单用途/多用途，统一一步分类
date: 2025.12.17
"""

import json
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from lifewatch.llm.llm_classify.schemas.classify_shemas import classifyState, LogItem
from lifewatch.llm.llm_classify.utils import (
    create_ChatTongyiModel,
    extract_json_from_response,
    parse_token_usage,
    format_goals_for_prompt,
    format_category_tree_for_prompt
)

MAX_LOG_ITEMS = 15

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ClassifySimple:
    """
    简化版云端分类器
    
    特点：
    - 一步分类流程（模型自带网络搜索能力）
    - 不区分单用途/多用途，统一处理
    """
    
    def __init__(self, goal: list, category_tree: dict):
        """
        初始化分类器
        
        Args:
            goal: 用户目标列表
            category_tree: 分类树字典
        """
        self.goal = goal
        self.category_tree = category_tree
        self.chat_model = create_ChatTongyiModel()
        self.token_usage_list = []  # 记录 token 使用
    
    def classify(self, state: classifyState) -> classifyState:
        """
        对所有 log_items 进行分类
        
        Args:
            state: classifyState 对象，包含 log_items, app_registry
            
        Returns:
            classifyState: 包含 result_items 的状态
        """
        if not state.log_items:
            logger.info("log_items 为空，跳过分类")
            return {"result_items": None}
        
        # 使用类变量
        goal = format_goals_for_prompt(self.goal)
        category_tree = format_category_tree_for_prompt(self.category_tree)
        #print(goal)
        #print(category_tree)
        system_message = SystemMessage(content=f"""
            # 你是一个软件分类专家。你的任务是根据软件名称,描述,将软件进行分类,分类有category和sub_category两级分类。
            # 分类类别
            {category_tree}
            # 用户目标
            {goal}
            # 分类规则
            1. 对于app与goal高度相关的条目,使用goal的分类类别,并关联goal,link_to_goal = goal;否则link_to_goal = null
            2. 对于单用途,依据app_description进行分类,若无法分类,则分类为null
            3. 对于多用途,依据app,app)description和title进行分类
            3. 若category有分类而sub_category无法分类,则sub_category = null
            # 输出格式为json,key为对于数据的id,value为一个list[category,sub_category,link_to_goal]
            {{
                id:[category,sub_category,link_to_goal]
            }}
            示例:
            {{
                "1": ["工作/学习", "编程", "完成LifeWatch-AI项目开发"],
                "2": ["娱乐", "看电视", null]
            }}
            注意：
            - value必须是列表，包含三个元素 [category, sub_category, link_to_goal]
            - 无值时使用 null
            - key必须是id，不是app名称

            """)
        
        all_result_items = []
        
        # 分批处理
        for i in range(0, len(state.log_items), MAX_LOG_ITEMS):
            batch = state.log_items[i:i + MAX_LOG_ITEMS]
            batch_num = i // MAX_LOG_ITEMS + 1
            logger.info(f"classify_simple 处理第 {batch_num} 批，共 {len(batch)} 条记录")
            
            # 构建 compact_data: [id, app_name, app_description, title, is_multipurpose]
            compact_data = []
            for item in batch:
                app_info = state.app_registry.get(item.app)
                compact_data.append([
                    item.id,
                    item.app,
                    app_info.description if app_info else None,
                    item.title,
                    app_info.is_multipurpose if app_info else False
                ])
            
            # Human Message - 留空，用户自行修改
            human_message = HumanMessage(content=f"""
            数据格式：[id, app_name, app_description, title, is_multipurpose]
            {json.dumps(compact_data, ensure_ascii=False)}
            """)
            messages = [system_message, human_message]
            try:
                # 发送请求
                result = self.chat_model.invoke(messages)
                self.token_usage_list.append(parse_token_usage(result))
                
                # 解析 JSON 结果
                clean_content = extract_json_from_response(result.content)
                classification_result = json.loads(clean_content)
                logger.info(f"classify_simple 批次 {batch_num} 成功获取分类结果")
                
                # 更新 log_items
                batch = self._parse_classification_result(batch, classification_result)
                all_result_items.extend(batch)
                
            except Exception as e:
                logger.error(f"classify_simple 批次 {batch_num} 处理出错: {e}")
                # 保留原始数据，不做分类
                all_result_items.extend(batch)
        
        return {"result_items": all_result_items}
    
    def _build_category_tree_text(self, category_tree: dict) -> str:
        """
        构建分类树的文本展示
        """
        if not category_tree:
            return ""
        
        text = "分类选项（主分类 -> 子分类）：\n"
        for main_cat, sub_cats in category_tree.items():
            text += f"- {main_cat}\n"
            if sub_cats:
                for sub_cat in sub_cats:
                    text += f"  - {sub_cat}\n"
        return text
    
    def _parse_classification_result(
        self, 
        log_items: list[LogItem], 
        classification_result: dict
    ) -> list[LogItem]:
        """
        解析分类结果并更新 log_items
        
        Args:
            log_items: 待更新的 LogItem 列表
            classification_result: LLM 返回的分类结果
                格式: {id: [category, sub_category, link_to_goal]}
        
        Returns:
            更新后的 log_items
        """
        # 创建 id -> LogItem 的映射
        id_to_item = {item.id: item for item in log_items}
        
        for id_str, values in classification_result.items():
            try:
                item_id = int(id_str)
                if item_id in id_to_item:
                    item = id_to_item[item_id]
                    if isinstance(values, list) and len(values) >= 2:
                        item.category = values[0]
                        item.sub_category = values[1]
                        if len(values) >= 3:
                            item.link_to_goal = values[2]
            except (ValueError, TypeError) as e:
                logger.warning(f"解析 id={id_str} 的分类结果失败: {e}")
        
        return log_items
    
    def get_total_tokens_usage(self) -> dict:
        """
        获取总 token 使用统计
        """
        total = {
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0,
            'search_count': 0
        }
        for usage in self.token_usage_list:
            total['input_tokens'] += usage.get('input_tokens', 0)
            total['output_tokens'] += usage.get('output_tokens', 0)
            total['total_tokens'] += usage.get('total_tokens', 0)
            total['search_count'] += usage.get('search_count', 0)
        return total


if __name__ == "__main__":
    from lifewatch.llm.llm_classify.classify.data_loader import (
        get_real_data, 
        filter_by_duration, 
        deduplicate_log_items
    )
    
    def get_state(hours=36) -> tuple:
        state, goals, category_tree = get_real_data(hours=hours)
        state = filter_by_duration(state, min_duration=60)
        state = deduplicate_log_items(state)
        return state, goals, category_tree
    
    # 获取测试数据
    main_state, goals, category_tree = get_state(hours=18)
    
    # 创建分类器并执行
    classifier = ClassifySimple(goal=goals, category_tree=category_tree)
    output = classifier.classify(main_state)
    
    # 打印结果
    if output.get("result_items"):
        result_items = output["result_items"]
        print("\n" + "="*80)
        print("📝 分类结果")
        print("="*80)
        print(f"  共 {len(result_items)} 条记录")
        print("-"*80)
        for item in result_items:
            goal_str = f"🎯 {item.link_to_goal}" if item.link_to_goal else ""
            category_str = f"{item.category or '未分类'}/{item.sub_category or '-'}"
            print(f"  [{item.id}] {item.app:<15} | {category_str:<20} | {item.duration:>5}s | {goal_str}")
            if item.title:
                print(f"        └─ 标题: {item.title[:55]}{'...' if len(item.title) > 55 else ''}")
        print("="*80)
    
    # Token 使用统计
    tokens_usage = classifier.get_total_tokens_usage()
    print("\n" + "="*50)
    print("📊 Token 使用统计")
    print("="*50)
    print(f"  输入 tokens:  {tokens_usage['input_tokens']:,}")
    print(f"  输出 tokens:  {tokens_usage['output_tokens']:,}")
    print(f"  总 tokens:    {tokens_usage['total_tokens']:,}")
    print(f"  搜索次数:     {tokens_usage['search_count']}")
    print("="*50)
