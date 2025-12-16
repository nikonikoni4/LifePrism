"""
LLM 分类图管理器 - 企业级封装

使用 LangGraph 构建的分类流程，包含：
- 单用途应用分类
- 多用途应用分类（短时长/长时长）
- 使用 InMemoryStore 存储 token 使用统计
"""

from lifewatch.llm.llm_classify.schemas.classify_shemas import classifyState, Goal, AppInFo, SearchOutput
from langgraph.graph import StateGraph, START, END
from langgraph.store.memory import InMemoryStore
from langchain_core.messages import SystemMessage, HumanMessage
from lifewatch.llm.llm_classify.utils import (
    format_goals_for_prompt,
    format_category_tree_for_prompt,
    format_log_items_table,
    create_ChatTongyiModel,
    split_by_purpose,
    split_by_duartion,
    parse_classification_result,
    extract_json_from_response,
)
import json
import logging
from langgraph.types import Send, RetryPolicy
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LLMClassify:
    """
    LLM 分类图管理器
    
    使用 LangGraph 构建分类流程，支持：
    - 单用途应用分类
    - 多用途应用分类（短时长/长时长）
    - token 使用统计（使用 InMemoryStore）
    
    Example:
        classifier = LLMClassify()
        result = classifier.run(state)
        token_summary = classifier.get_token_summary()
    """
    
    # 配置常量
    MAX_LOG_ITEMS = 15
    MAX_TITLE_ITEMS = 5
    SPLIT_DURATION = 10 * 60  # 10min
    
    # Token 存储命名空间
    TOKEN_NAMESPACE = ("token_usage",)
    
    def __init__(self):
        """初始化分类器"""
        self.chat_model = create_ChatTongyiModel()
        self.store = InMemoryStore()
        self._app = None
        self._token_counter = 0  # 用于生成唯一 key
        self._build_graph()
    
    def _build_graph(self) -> None:
        """构建 LangGraph 图"""
        graph = StateGraph(classifyState)
        
        # 添加节点（带重试策略的节点直接传入 retry 参数）
        graph.add_node("get_app_description", self._get_app_description)
        graph.add_node("single_classify", self._single_classify, retry=RetryPolicy(max_attempts=3))
        graph.add_node("multi_classify", self._multi_classify)
        graph.add_node("get_titles", self._get_titles)
        graph.add_node("search_title", self._search_title)
        graph.add_node("multi_classify_long", self._multi_classify_long, retry=RetryPolicy(max_attempts=3))
        graph.add_node("multi_classify_short", self._multi_classify_short, retry=RetryPolicy(max_attempts=3))
        
        # 添加边
        graph.add_edge(START, "get_app_description")
        graph.add_conditional_edges("get_app_description", self._router_by_multi_purpose)
        graph.add_edge("single_classify", END)
        graph.add_conditional_edges("multi_classify", self._router_by_duration_for_multi)
        graph.add_edge("multi_classify_short", END)
        graph.add_conditional_edges("get_titles", self._send_title)
        graph.add_edge("search_title", "multi_classify_long")
        graph.add_edge("multi_classify_long", END)
        
        self._app = graph.compile(store=self.store)
    
    def _record_token_usage(self, node_name: str, result: Any) -> None:
        """
        记录 token 使用情况到 InMemoryStore
        
        Args:
            node_name: 节点名称
            result: LLM invoke 返回的结果
        """
        raw_usage = result.response_metadata.get('token_usage', {})
        token_data = {
            'node': node_name,
            'input_tokens': raw_usage.get('input_tokens', 0),
            'output_tokens': raw_usage.get('output_tokens', 0),
            'total_tokens': raw_usage.get('total_tokens', 0),
            'search_count': raw_usage.get('plugins', {}).get('search', {}).get('count', 0)
        }
        
        # 使用递增 key 存储
        self._token_counter += 1
        print(f"  💰 [{node_name}] tokens: {token_data['input_tokens']} in + {token_data['output_tokens']} out = {token_data['total_tokens']} total")
        print(token_data["search_count"])
        self.store.put(
            namespace=self.TOKEN_NAMESPACE,
            key=str(self._token_counter),
            value=token_data
        )
    
    def reset_token_usage(self) -> None:
        """重置 token 使用统计"""
        # 删除所有 token 记录
        items = list(self.store.search(self.TOKEN_NAMESPACE))
        for item in items:
            self.store.delete(namespace=self.TOKEN_NAMESPACE, key=item.key)
        self._token_counter = 0
    
    def get_token_summary(self) -> dict[str, dict]:
        """
        获取 token 使用汇总
        
        Returns:
            按节点汇总的 token 使用统计
        """
        summary = {}
        items = list(self.store.search(self.TOKEN_NAMESPACE))
        
        for item in items:
            data = item.value
            node = data['node']
            if node not in summary:
                summary[node] = {
                    'input_tokens': 0,
                    'output_tokens': 0,
                    'total_tokens': 0,
                    'search_count': 0
                }
            summary[node]['input_tokens'] += data['input_tokens']
            summary[node]['output_tokens'] += data['output_tokens']
            summary[node]['total_tokens'] += data['total_tokens']
            summary[node]['search_count'] += data['search_count']
        
        return summary
    
    def get_token_usage_list(self) -> list[dict]:
        """获取所有 token 使用记录"""
        items = list(self.store.search(self.TOKEN_NAMESPACE))
        return [item.value for item in items]
    
    # ==================== 路由函数 ====================
    
    def _router_by_multi_purpose(self, state: classifyState) -> list[Send]:
        """软件分类路由：单用途和多用途分开处理"""
        single_state, multi_state = split_by_purpose(state)
        print(f"single_state:{single_state}")
        print(f"multi_state:{multi_state}")
        return [
            Send("single_classify", single_state),
            Send("multi_classify", multi_state)
        ]
    
    def _router_by_duration_for_multi(self, state: classifyState) -> list[Send]:
        """多用途应用按时长路由：短时长和长时长分开处理"""
        short_state, long_state = split_by_duartion(state)
        return [
            Send("multi_classify_short", short_state),
            Send("get_titles", long_state)
        ]
    
    def _send_title(self, input: SearchOutput) -> list[Send]:
        """为每个 id-title 对创建一个 Send 任务"""
        return [
            Send("search_title", {"id": item_id, "title": title})
            for item_id, title in input.input_data.items()
        ]
    
    # ==================== 节点函数 ====================
    
    def _get_app_description(self, state: classifyState) -> dict:
        """
        获取所有没有描述的 app 的描述信息
        
        Args:
            state: classifyState 对象
            
        Returns:
            更新了 app_registry 的状态字典
        """
        # 找出所有没有描述的 app
        app_to_search = []
        for app, app_info in state.app_registry.items():
            if app_info.description is None or app_info.description == "":
                title_sample = app_info.titles[0] if app_info.titles else ""
                app_to_search.append((app, title_sample))
        
        if not app_to_search:
            logger.info("所有 app 都已有描述，跳过搜索")
            return {}
        
        logger.info(f"需要搜索描述的 app: {[app for app, _ in app_to_search]}")
        
        # 顺序搜索每个 app 的描述
        app_descriptions = {}
        
        system_message = SystemMessage(content="""
        你是一个软件程序识别专家。你的任务是通过 web 搜索识别软件应用程序，并提供准确、精炼的描述。
        **输入说明：**
        - 输入软件名称或程序名称与窗口title
        **输出要求：**
        - 软件描述(不超过20词):以web搜索为主,title信息为辅
        - 返回软件描述
        - 如果搜索后仍无法确定，返回 None
        """)
        
        for app, title in app_to_search:
            try:
                user_message = HumanMessage(content=f"""软件名称:{app} title:{title}""")
                messages = [system_message, user_message]
                
                result = self.chat_model.invoke(messages)
                self._record_token_usage("get_app_description", result)
                
                app_descriptions[app] = result.content
                logger.info(f"已获取 {app} 的描述: {result.content[:50]}...")
                
            except Exception as e:
                logger.error(f"搜索 {app} 描述失败: {e}")
                app_descriptions[app] = None
        
        # 更新 state.app_registry
        for app_name, description in app_descriptions.items():
            if app_name in state.app_registry:
                state.app_registry[app_name].description = description
        
        return {"app_registry": state.app_registry}
    
    def _single_classify(self, state: classifyState) -> dict:
        """单用途 app 分类（分批处理）"""
        goal = format_goals_for_prompt(state.goal)
        category_tree = format_category_tree_for_prompt(state.category_tree)
        
        system_message = SystemMessage(content=f"""
        # 你是一个软件分类专家。你的任务是根据软件名称,描述,将软件进行分类,分类有category和sub_category两级分类。
        # 分类类别
        {category_tree}
        # 用户目标
        {goal}
        # 分类规则
        1. 对于app与goal高度相关的条目,使用goal的分类类别,并关联goal,link_to_goal = goal;否则link_to_goal = null
        2. 对于单用途,依据app_description进行分类,若无法分类,则分类为null
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
        
        # 获取单用途的 log_item
        single_purpose_items = [
            item for item in state.log_items
            if not state.app_registry[item.app].is_multipurpose
        ]
        
        if not single_purpose_items:
            logger.info("没有单用途应用需要分类")
            return {}
        
        # 分批处理
        for i in range(0, len(single_purpose_items), self.MAX_LOG_ITEMS):
            batch = single_purpose_items[i:i + self.MAX_LOG_ITEMS]
            batch_num = i // self.MAX_LOG_ITEMS + 1
            logger.info(f"single_classify 处理第 {batch_num} 批，共 {len(batch)} 条记录")
            
            app_content = format_log_items_table(
                batch,
                fields=["id", "app", "title"],
                app_registry=state.app_registry,
                group_by_app=True,
                show_app_description=True
            )
            print(f"_single_classify:{app_content}")
            human_message = HumanMessage(content=app_content)
            messages = [system_message, human_message]
            
            results = self.chat_model.invoke(messages)
            self._record_token_usage("single_classify", results)
            
            logger.debug(f"LLM 原始响应 (批次 {batch_num}): {results.content}")
            
            clean_content = extract_json_from_response(results.content)
            classification_result = json.loads(clean_content)
            logger.info(f"single_classify 批次 {batch_num} 成功获取分类结果")
            
            state = parse_classification_result(state, classification_result, "single_classify")
        
        return {"result_items": state.log_items}
    
    def _multi_classify(self, state: classifyState) -> classifyState:
        """多用途分类空节点，后续接上多分类路由"""
        return {}
    
    def _multi_classify_short(self, state: classifyState) -> dict:
        """短时长多用途分类（分批处理）"""
        category_tree = format_category_tree_for_prompt(state.category_tree)
        goal = format_goals_for_prompt(state.goal)
        
        system_message = SystemMessage(content=f"""
        你是一个用户行为分析专家,你需要依据用户的浏览的网页title对用户的行为进行分类
        # 类别:
        {category_tree}
        # 用户目标:
        {goal}
        # 分类规则:
        1. 对于title与goal高度相关的条目,使用goal的分类类别,并关联goal,link_to_goal = goal;否则link_to_goal = null
        2. 提取出title中的网站名称和网站标题,通过这两个要素进行分类
        3. 类别有两个层级category->sub_category,分类结果sub_category要属于category。当没有匹配项时,分类为null
        # 输出格式为json,key为对于数据的id,value为一个list[category,sub_category,link_to_goal]
        {{
            id:[category,sub_category,link_to_goal]
        }}
        示例:
        {{
            "1": ["工作/学习", "编程", "完成LifeWatch-AI项目开发"],
            "2": ["娱乐", "看电视", null]
        }}
        """)
        
        if not state.log_items:
            logger.info("没有短时长多用途应用需要分类")
            return {}
        
        # 分批处理
        for i in range(0, len(state.log_items), self.MAX_LOG_ITEMS):
            batch = state.log_items[i:i + self.MAX_LOG_ITEMS]
            batch_num = i // self.MAX_LOG_ITEMS + 1
            logger.info(f"multi_classify_short 处理第 {batch_num} 批，共 {len(batch)} 条记录")
            
            items = format_log_items_table(
                batch,
                fields=["id", "app", "title", "title_analysis"]
            )
            print(f"_multi_classify_short{items}")
            human_message = HumanMessage(content=f"""对下面的数据进行分类:\n{items}""")
            messages = [system_message, human_message]
            
            result = self.chat_model.invoke(messages)
            self._record_token_usage("multi_classify_short", result)
            
            logger.debug(f"LLM 原始响应 (批次 {batch_num}): {result.content}")
            
            clean_content = extract_json_from_response(result.content)
            classification_result = json.loads(clean_content)
            logger.info(f"multi_classify_short 批次 {batch_num} 成功获取分类结果")
            
            state = parse_classification_result(state, classification_result, "multi_classify_short")
        
        return {"result_items": state.log_items}
    
    def _get_titles(self, state: classifyState) -> dict:
        """获取 title 字典用于并发搜索"""
        title_dict = {}
        for item in state.log_items:
            if item.title:
                title_dict[item.id] = item.title
        return {"input_data": title_dict}
    
    def _search_title(self, input: dict) -> dict:
        """搜索并分析单个 title"""
        item_id = input["id"]
        title = input["title"]
        
        system_message = SystemMessage(content="""
        你是一个通过网络搜索分析的助手,依据网络搜索结果和title分析用户的活动，要求结果在50字以内
        # 输出格式:str 内容为:用户活动
        """)
        human_message = HumanMessage(content=f"""搜索并分析{title}""")
        messages = [system_message, human_message]
        
        try:
            result = self.chat_model.invoke(messages)
            self._record_token_usage("search_title", result)
            
            logger.debug(f"search_title 响应: {result.content}")
            title_analysis_result = result.content
        except Exception as e:
            logger.error(f"search_title {title} 执行失败, 错误: {e}")
            title_analysis_result = None
        
        return {
            "title_analysis_results": [(item_id, title_analysis_result)]
        }
    
    def _multi_classify_long(self, state: classifyState) -> dict:
        """长时长多用途分类（分批处理）"""
        goal = format_goals_for_prompt(state.goal)
        category_tree = format_category_tree_for_prompt(state.category_tree)
        
        system_message = SystemMessage(content=f"""
        你是一个用户行为分类专家。你的任务是根据网页标题(Title)和标题分析(Title Analysis)对用户的行为进行分类。
        
        # 分类类别
        {category_tree}
        
        # 用户目标
        {goal}
        
        # 分类规则
        1. 对于与goal高度相关的条目,使用goal的分类类别,并关联goal,link_to_goal = goal;否则link_to_goal = null
        2. 主要依据Title Analysis来理解用户的活动内容,结合Title进行分类
        3. 类别有两个层级category->sub_category,分类结果sub_category要属于category
        4. 若category有分类而sub_category无法分类,则sub_category = null
        5. 若无法分类,则分类为null
        
        # 输出格式为json,key为数据的id,value为一个list[category,sub_category,link_to_goal]
        {{
            "id":[category,sub_category,link_to_goal]
        }}

        示例：
        {{
            "1": ["工作/学习", "编程", "完成LifeWatch-AI项目开发"],
            "2": ["娱乐", "看电视", null]
        }}
        注意：
        - value必须是列表，包含三个元素 [category, sub_category, link_to_goal]
        - 无值时使用 null
        - key必须是id，不是app名称
        """)
        
        if not state.log_items:
            logger.info("没有长时长多用途应用需要分类")
            return {}
        
        # 从 title_analysis_results 构建 id -> analysis 的映射
        analysis_map = {}
        if state.title_analysis_results:
            for item_id, analysis in state.title_analysis_results:
                analysis_map[item_id] = analysis
        
        # 更新 log_items 的 title_analysis 字段
        for item in state.log_items:
            if item.id in analysis_map:
                item.title_analysis = analysis_map[item.id]
        
        # 分批处理
        for i in range(0, len(state.log_items), self.MAX_LOG_ITEMS):
            batch = state.log_items[i:i + self.MAX_LOG_ITEMS]
            batch_num = i // self.MAX_LOG_ITEMS + 1
            logger.info(f"multi_classify_long 处理第 {batch_num} 批，共 {len(batch)} 条记录")
            
            items = format_log_items_table(
                batch,
                fields=["id", "app", "title", "title_analysis"]
            )
            print(f"multi_classify_long:{items}")
            human_message = HumanMessage(content=f"""
            请对以下用户行为数据进行分类：
            {items}
            """)
            print(f"_multi_classify_long{items}")
            messages = [system_message, human_message]
            
            result = self.chat_model.invoke(messages)
            print(result)
            self._record_token_usage("multi_classify_long", result)
            
            logger.debug(f"LLM 原始响应 (批次 {batch_num}): {result.content}")
            
            clean_content = extract_json_from_response(result.content)
            classification_result = json.loads(clean_content)
            logger.info(f"multi_classify_long 批次 {batch_num} 成功获取分类结果")
            
            state = parse_classification_result(state, classification_result, "multi_classify_long")
        
        return {"result_items": state.log_items}
    
    # ==================== 公共接口 ====================
    
    def run(self, state: classifyState) -> dict:
        """
        执行分类流程
        
        Args:
            state: 初始分类状态
            
        Returns:
            分类结果字典
        """
        self.reset_token_usage()
        config = {"configurable": {"thread_id": "thread-123"}}
        return self._app.invoke(state,config = config)
    
    def print_token_summary(self) -> None:
        """打印 token 使用统计"""
        token_summary = self.get_token_summary()
        if not token_summary:
            print("暂无 token 使用记录")
            return
        
        print("\n【Token 使用统计】")
        total_tokens = 0
        total_search_count = 0
        
        for node_name, usage in token_summary.items():
            print(f"\n  {node_name}:")
            print(f"    - Input Tokens:  {usage.get('input_tokens', 0):,}")
            print(f"    - Output Tokens: {usage.get('output_tokens', 0):,}")
            print(f"    - Total Tokens:  {usage.get('total_tokens', 0):,}")
            print(f"    - Search Count:  {usage.get('search_count', 0)}")
            total_tokens += usage.get('total_tokens', 0)
            total_search_count += usage.get('search_count', 0)
        
        print(f"\n  总计 Token 使用: {total_tokens:,}")
        print(f"  总计搜索次数: {total_search_count}")
        print(f"  API 调用次数: {len(self.get_token_usage_list())}")


# ==================== 测试代码 ====================

if __name__ == "__main__":
    from lifewatch.llm.llm_classify.classify.data_loader import (
        get_real_data,
        filter_by_duration,
        deduplicate_log_items
    )
    
    def get_state(hours: int = 36) -> classifyState:
        state = get_real_data(hours=hours)
        state = filter_by_duration(state, min_duration=60)
        state = deduplicate_log_items(state)
        
        print(f"\n去重后的日志（前10条）:")
        for item in state.log_items[:10]:
            multipurpose = "多用途" if state.app_registry[item.app].is_multipurpose else "单用途"
            print(f"  {item.app} ({multipurpose}) | {item.title} | {item.duration}s")
        
        print(f"\n测试过滤功能（只保留 duration >= 60 秒的记录）:")
        print(f"  - 过滤后 log_items: {len(state.log_items)} 条")
        print(f"  - 过滤后 app_registry: {len(state.app_registry)} 个应用")
        return state
    
    # 初始化分类器
    classifier = LLMClassify()
    
    # 获取测试数据
    state = get_state(hours=8)
    print(state.app_registry)
    input_items_len = len(state.log_items)
    
    # 执行分类
    output = classifier.run(state)
    print(output)
    # 输出结果
    print("\n" + "=" * 80)
    print("分类结果汇总")
    print("=" * 80)
    
    # 输出 token 使用情况
    classifier.print_token_summary()
    
    # 输出分类结果
    if "result_items" in output:
        print("\n【分类结果】")
        print(f"  共分类 {len(output['result_items'])} 条记录\n")
        
        for item in output["result_items"]:
            print(f"  ID: {item.id}")
            print(f"    应用: {item.app}")
            if item.title:
                print(f"    标题: {item.title[:50]}{'...' if len(item.title) > 50 else ''}")
            print(f"    分类: {item.category or 'N/A'} -> {item.sub_category or 'N/A'}")
            print(f"    关联目标: {item.link_to_goal or 'N/A'}")
            print(f"    时长: {item.duration}s")
            print(f"{item.title_analysis}")
            print()
    
    print("=" * 80)
    print(f"输入个数: {input_items_len}")
