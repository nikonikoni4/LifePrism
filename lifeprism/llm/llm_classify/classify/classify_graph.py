"""
功能描述: 实现分类的langgraph
待实现内容: 分类结果的验证功能
date : 2025.12.17 
"""
# Date: 2025/12/17
from httpcore import __name
from lifeprism.llm.llm_classify.schemas.classify_shemas import classifyState,Goal,AppInFo,classifyStateLogitems,LogItem
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage,AIMessage
from lifeprism.llm.llm_classify.utils import (
    format_goals_for_prompt, 
    format_category_tree_for_prompt,
    format_log_items_table,
    create_ChatTongyiModel,
    split_by_purpose,
    split_by_duration,
    parse_classification_result,
    extract_json_from_response,
    parse_token_usage,
    )
import json
import logging
from langgraph.types import Send,RetryPolicy
from langgraph.store.memory import InMemoryStore
import time
import uuid
MAX_LOG_ITEMS = 15
MAX_TITLE_ITEMS = 5
TEST_FLAG = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ClassifyGraph:
    def __init__(self, goal: list, category_tree: dict):
        """
        初始化分类图
        
        Args:
            goal: 用户目标列表
            category_tree: 分类树字典
        """
        self.goal = goal
        self.category_tree = category_tree
        self.chat_model = create_ChatTongyiModel()
        self.store = InMemoryStore()
        self.bulit_graph()

    def recode_tokens_usage(self,node_name,tokens_usage):
        name_space = ("tokens_usage",node_name)
        self.store.put(name_space,str(uuid.uuid4()),tokens_usage) # 生成str(uuid.uuid4())唯一key，避免值被覆盖
    
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
        
        # 获取所有 tokens_usage 命名空间
        namespaces = self.store.list_namespaces(prefix=("tokens_usage",))
        
        for namespace in namespaces:
            # 搜索该命名空间下的所有记录
            items = self.store.search(namespace)
            for item in items:
                usage = item.value
                total['input_tokens'] += usage.get('input_tokens', 0)
                total['output_tokens'] += usage.get('output_tokens', 0)
                total['total_tokens'] += usage.get('total_tokens', 0)
                total['search_count'] += usage.get('search_count', 0)
        
        return total

    
    def bulit_graph(self):
        
        graph = StateGraph(classifyState)
        graph.add_node("get_app_description",self.get_app_description)
        graph.add_node("single_classify",self.single_classify,retry_policy=RetryPolicy(max_attempts=3))
        graph.add_node("multi_classify",self.multi_classify) # 空节点
        graph.add_node("multi_classify_long",self.multi_classify_long,retry_policy=RetryPolicy(max_attempts=3))  # 长时间多用途分类
        graph.add_node("multi_classify_short",self.multi_classify_short,retry_policy=RetryPolicy(max_attempts=3)) # 短时间多用途分类
        graph.add_node("get_titles",self.get_titles)

        graph.add_edge(START,"get_app_description")
        graph.add_conditional_edges("get_app_description",self.router_by_multi_purpose) # -> single_classify | -> multi_classify
        # 单用途分类
        graph.add_edge("single_classify",END)
        # 多用途分类
        graph.add_conditional_edges("multi_classify",self.router_by_duration_for_multi) # ->multi_classify_short | -> get_titles
        graph.add_edge("multi_classify_short",END)
        graph.add_edge("get_titles","multi_classify_long")
        graph.add_edge("multi_classify_long",END)
        # 短时间分类
        # checkpointer = InMemorySaver()  
        self.app = graph.compile(store=self.store)
    def classify(self, state: classifyState) -> dict:
        """
        执行分类任务的入口方法
        
        Args:
            state: classifyState 对象，包含待分类的数据
            
        Returns:
            dict: 包含 result_items 和 tokens_usage 的字典
        """
        # 执行分类
        output = self._classify_internal(state)
        
        # 获取 token 使用统计
        tokens_usage = self.get_total_tokens_usage()
        print(tokens_usage)
        return {
            "result_items": output.get("result_items"),
            "tokens_usage": tokens_usage
        }
    
    def _classify_internal(self, state: classifyState) -> dict:
        """
        内部分类实现，调用 LangGraph
        
        Args:
            state: classifyState 对象，包含待分类的数据
            
        Returns:
            dict: LangGraph 返回的原始结果
        """
        config = {"configurable": {"thread_id": f"thread-{uuid.uuid4()}"}}
        output = self.app.invoke(state, config)
        return output
    
    # node 1 获取所有app的描述
    def get_app_description(self,state: classifyState) -> classifyState:
        """
        获取所有没有描述的 app 的描述信息（使用 for 循环顺序执行）
        
        Args:
            state: classifyState 对象
            
        Returns:
            classifyState: 更新了 app_registry 的状态
        """
        # 1. 找出所有没有描述的 app
        app_to_search = []
        for app, app_info in state.app_registry.items():
            if app_info.description is None or app_info.description == "":
                # 只有单用途应用才获取 title 样本用于辅助识别
                title_sample = ""
                if not app_info.is_multipurpose and app_info.titles:
                    title_sample = app_info.titles[0]
                app_to_search.append((app, title_sample))
        
        if not app_to_search:
            logger.info("所有 app 都已有描述，跳过搜索")
            return {}
        
        logger.info(f"需要搜索描述的 app: {[app for app, _ in app_to_search]}")
        
        # 2. 顺序搜索每个 app 的描述
        app_descriptions = {}  # app_name -> description
        
        system_message = SystemMessage(content="""
        你是一个软件程序识别专家。
        **任务流程：**
        1. 实时查询该软件最新的描述
        2. 根据搜索结果，结合软件名称和标题样本，生成准确的软件描述
        
        **输出要求：**
        - 基于搜索结果提供软件描述（不超过20词）
        - 如果搜索后仍无法确定是什么软件，返回 None
        """)
        
        MAX_RETRIES = 3
        for app, title in app_to_search:
            success = False
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    # 根据是否有 title 调整 prompt
                    if title:
                        user_message = HumanMessage(content=f"""软件名称:{app},软件标题样本:{title}""")
                    else:
                        user_message = HumanMessage(content=f"""软件名称:{app}""")
                    messages = [system_message, user_message]
                    
                    result = self.chat_model.invoke(messages)
                    self.recode_tokens_usage("app_descriptions", parse_token_usage(result))
                    
                    # 检查结果是否为空
                    if result.content is None or result.content.strip() == "" or result.content.strip().lower() == "none":
                        logger.warning(f"获取 {app} 的描述失败（第 {attempt}/{MAX_RETRIES} 次），结果为空")
                        if attempt < MAX_RETRIES:
                            
                            time.sleep(0.5)  # 重试前等待 1 秒
                        continue
                    
                    # 收到非空结果，立即更新 app_registry
                    if app in state.app_registry:
                        state.app_registry[app].description = result.content
                        logger.info(f"已获取并更新 {app} 的描述: {result.content[:50]}...")
                    success = True
                    break  # 成功获取，跳出重试循环
                    
                except Exception as e:
                    logger.warning(f"获取 {app} 的描述时发生异常（第 {attempt}/{MAX_RETRIES} 次）: {e}")
                    if attempt < MAX_RETRIES:
                        time.sleep(1)
            
            if not success:
                logger.warning(f"获取 {app} 的描述失败，已重试 {MAX_RETRIES} 次，跳过该应用")
        
        # 返回更新后的状态
        return {
            "app_registry": state.app_registry
        }

    # router 1 

    def router_by_multi_purpose(self,state: classifyState):
        """
        软件分类路由,单用途和多用途分开处理
        """
        # 如果没有数据，直接结束
        if not state.log_items:
            logger.info("log_items 为空，跳过分类")
            return END
        
        log_dict = split_by_purpose(state)
        log_items_for_single = log_dict.get("log_items_for_single", [])
        log_items_for_multi = log_dict.get("log_items_for_multi", [])
        
        # 创建中间私有状态
        log_items_state = classifyStateLogitems(
            log_items_for_single=log_items_for_single if log_items_for_single else None,
            log_items_for_multi=log_items_for_multi if log_items_for_multi else None,
            private_app_registry=state.app_registry
        )
        
        send_list = []
        if not log_items_for_single:
            logger.info("log_items_for_single 为空, 无单用途数据")
        else:
            send_list.append(Send("single_classify", log_items_state))
        if not log_items_for_multi:
            logger.info("log_items_for_multi 为空, 无多用途数据")
        else:
            send_list.append(Send("multi_classify", log_items_state))
        
        # 如果没有任何任务要发送，返回 END
        if not send_list:
            logger.info("没有数据需要分类，直接结束")
            return END
        
        return send_list
    
    # node superstape2: 单用途分类 -> result_items

    def single_classify(self,state: classifyStateLogitems) -> classifyState:
        """
        单用途app分类（分批处理，每批最多 MAX_LOG_ITEMS 条）
        """
        # system message
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
            3. 若category有分类而sub_category无法分类,则sub_category = null
            # 输出格式为json,key为对于数据的id,value为一个list[category,sub_category,link_to_goal]
            {{
                id:[category,sub_category,link_to_goal]
            }}
            注意：
            - value必须是列表，包含三个元素 [category, sub_category, link_to_goal]
            - 无值时使用 null
            - key必须是id，不是app名称
            - category 和 sub_category 必须在上述分类类别中选择

            """)
        # 获取单用途的log_item（已经在路由时分好了）
        single_purpose_items = state.log_items_for_single or []
        
        if not single_purpose_items:
            logger.info("没有单用途应用需要分类")
            return {}
        
        # 分批处理
        for i in range(0, len(single_purpose_items), MAX_LOG_ITEMS):
            batch = single_purpose_items[i:i + MAX_LOG_ITEMS]
            batch_num = i // MAX_LOG_ITEMS + 1
            logger.info(f"single_classify 处理第 {batch_num} 批，共 {len(batch)} 条记录")
            
            # 使用工具函数格式化 log_items
            app_content = format_log_items_table(
                batch,
                fields=["id", "app", "title"],
                app_registry=state.private_app_registry,
                group_by_app=True,
                show_app_description=True
            )
            #print(app_content)
            
            # 构建 human_message
            human_message = HumanMessage(content=app_content)
            messages = [system_message, human_message]
            
            # 发送请求并解析结果
            result = self.chat_model.invoke(messages)
            self.recode_tokens_usage("single_classify",parse_token_usage(result))
            # 记录 token 使用到全局列表
            # record_token_usage("single_classify", result)
            
            # 打印原始响应内容以便调试
            #print(f"\n=== LLM 原始响应 (批次 {batch_num}) ===")
            #print(result.content)
            #print("=== 响应结束 ===\n")
            
            # 解析 JSON 结果（先清理可能的代码块标记）
            clean_content = extract_json_from_response(result.content)
            classification_result = json.loads(clean_content)
            logger.info(f"single_classify 批次 {batch_num} 成功获取分类结果")
            
            # 使用通用解析函数更新 log_items
            single_purpose_items = parse_classification_result(single_purpose_items, classification_result, "single_classify")

        
        return {
            "result_items" : single_purpose_items
        }
 
    # node supperstep2 多用途分类(空节点) ->classifyStateLogitems

    def multi_classify(self,state:classifyStateLogitems)->classifyStateLogitems:
        # 空节点，后续接上多分类路由
        # 私有变量传递不能中断传递，而同超步的single_class返回主状态，这里更新不会影响到单应用分支
        return state 
    # router_by_duration_for_multi

    def router_by_duration_for_multi(self, state: classifyStateLogitems):
        """
        多用途应用按时长路由，短时长和长时长分开处理
        """
        log_dict = split_by_duration(state)
        log_items_for_multi_short = log_dict.get("log_items_for_multi_short", None)
        log_items_for_multi_long = log_dict.get("log_items_for_multi_long", None)
        # 更新中间私有状态
        log_items_state = classifyStateLogitems(
            private_app_registry=state.private_app_registry,
            log_items_for_single=state.log_items_for_single,
            log_items_for_multi=state.log_items_for_multi,
            log_items_for_multi_short=log_items_for_multi_short,
            log_items_for_multi_long=log_items_for_multi_long,
        )
        send_list = []
        if log_items_for_multi_short is None:
            logger.info("log_items_for_multi_short is None, 无短时长数据")
        else:
            send_list.append(Send("multi_classify_short", log_items_state))
        if log_items_for_multi_long is None:
            logger.info("log_items_for_multi_long is None, 无长时长数据")
        else:
            send_list.append(Send("get_titles", log_items_state))
        
        return send_list
    # node supperstep 3 :多用途短时长分类->{result_items}

    def multi_classify_short(self,state:classifyStateLogitems) -> classifyState:
        """
        短时长多用途分类（分批处理，每批最多 MAX_LOG_ITEMS 条）
        """
        category_tree = format_category_tree_for_prompt(self.category_tree) # 使用类变量
        goal = format_goals_for_prompt(self.goal)
        
        # system message
        system_message = SystemMessage(content = f"""
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
        注意:
        - value必须是列表，包含三个元素 [category, sub_category, link_to_goal]
        - 无值时使用 null
        - category 和 sub_category 必须在上述分类类别中选择
        """)
        
        if not state.log_items_for_multi_short:
            logger.info("没有短时长多用途应用需要分类")
            return {}
        
        # 分批处理
        for i in range(0, len(state.log_items_for_multi_short), MAX_LOG_ITEMS):
            batch = state.log_items_for_multi_short[i:i + MAX_LOG_ITEMS]
            batch_num = i // MAX_LOG_ITEMS + 1
            logger.info(f"multi_classify_short 处理第 {batch_num} 批，共 {len(batch)} 条记录")
            
            items = format_log_items_table(
                batch,
                fields=["id", "app", "title", "title_analysis"]
            )
            human_message = HumanMessage(content=f"""对下面的数据进行分类:\n{items}
            """)
            messages = [system_message, human_message]
            
            # 发送请求并解析结果
            result = self.chat_model.invoke(messages)
            self.recode_tokens_usage("multi_classify_short",parse_token_usage(result))
            # 记录 token 使用到全局列表
            # record_token_usage("multi_classify_short", result)
            
            # 打印原始响应内容以便调试
            #print(f"\n=== LLM 原始响应 (批次 {batch_num}) ===")
            #print(result.content)
            #print("=== 响应结束 ===\n")
            
            # 解析 JSON 结果（先清理可能的代码块标记）
            clean_content = extract_json_from_response(result.content)
            classification_result = json.loads(clean_content)
            logger.info(f"multi_classify_short 批次 {batch_num} 成功获取分类结果")
            
            # 使用通用解析函数更新 log_items
            log_items_for_multi_short = parse_classification_result(state.log_items_for_multi_short, classification_result, "multi_classify_short")
            
        
        return {
            "result_items" : log_items_for_multi_short
        }

    # node supperstep 3 :获取title_analysis->{title_analysis_results}

    def get_titles(self,state:classifyStateLogitems)->classifyStateLogitems:
        system_message = SystemMessage(content="""
        你是一个通过网络搜索分析的助手,依据网络搜索结果和title分析用户的活动，要求结果在30字以内
        # 输出格式:str 内容为:用户活动
        """)
        for item in state.log_items_for_multi_long:
            if item.title:  # 只添加有title的项
                human_message = HumanMessage(content=f"""搜索并分析{item.title}""")
                message = [system_message, human_message]
                result = self.chat_model.invoke(message)
                self.recode_tokens_usage("get_titles",parse_token_usage(result))
                item.title_analysis = result.content
        return {
            "log_items_for_multi_long" : state.log_items_for_multi_long
        }

    # node supperstep 4 : 多分类长时间 {result_items}

    def multi_classify_long(self,state:classifyStateLogitems)->classifyState:
        """
        长时长多用途分类（分批处理，每批最多 MAX_LOG_ITEMS 条）
        """
        goal = format_goals_for_prompt(self.goal)
        category_tree = format_category_tree_for_prompt(self.category_tree)
        
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

        注意：
        - value必须是列表，包含三个元素 [category, sub_category, link_to_goal]
        - 无值时使用 null
        - key必须是id，不是app名称
        - category 和 sub_category 必须在上述分类类别中选择
        """)
        
        if not state.log_items_for_multi_long:
            logger.info("没有长时长多用途应用需要分类")
            return {}
        
        # 分批处理
        for i in range(0, len(state.log_items_for_multi_long), MAX_LOG_ITEMS):
            batch = state.log_items_for_multi_long[i:i + MAX_LOG_ITEMS]
            batch_num = i // MAX_LOG_ITEMS + 1
            logger.info(f"multi_classify_long 处理第 {batch_num} 批，共 {len(batch)} 条记录")
            
            # 使用工具函数格式化 log_items
            items = format_log_items_table(
                batch,
                fields=["id", "app", "title", "title_analysis"]
            )
            
            human_message = HumanMessage(content=f"""
            请对以下用户行为数据进行分类：
            {items}
            """)
            
            messages = [system_message, human_message]
            
            # 发送请求并解析结果
            result = self.chat_model.invoke(messages)
            self.recode_tokens_usage("multi_classify_long",parse_token_usage(result))
            # 记录 token 使用到全局列表
            # record_token_usage("multi_classify_long", result)
            
            # 打印原始响应内容以便调试
            #print(f"\n=== LLM 原始响应 (批次 {batch_num}) ===")
            #print(result.content)
            #print("=== 响应结束 ===\n")
            
            # 解析 JSON 结果（先清理可能的代码块标记）
            clean_content = extract_json_from_response(result.content)
            classification_result = json.loads(clean_content)
            logger.info(f"multi_classify_long 批次 {batch_num} 成功获取分类结果")
            
            # 使用通用解析函数更新 log_items
            log_items_for_multi_long = parse_classification_result(state.log_items_for_multi_long, classification_result, "multi_classify_long")

        
        return {
            "result_items" : log_items_for_multi_long
        }

if __name__ == "__main__":
    # 简易测试用例
    print("=== 开始运行简易测试用例 ===")
    
    # 1. 定义测试数据

    
    mock_category_tree = {
        "学习": ["编程", "阅读"],
        "娱乐": ["视频", "游戏", "社交"],
        "工作": ["会议", "文档"]
    }

    # 2. 构造应用注册表 (AppInfo)
    # 模拟已知应用，部分带有描述，部分没有（测试描述生成暂不涉及，这里模拟已有描述以加快测试）
    mock_app_registry = {
        "Code.exe": AppInFo(
            description="Visual Studio Code - 代码编辑器", 
            is_multipurpose=False,
            titles=["main.py - Visual Studio Code"]
        ),
        "Chrome.exe": AppInFo(
            description="Google Chrome - 网页浏览器", 
            is_multipurpose=True, # 多用途应用，需要根据Title分析
            titles=[]
        ),
        "WeChat.exe": AppInFo(
            description="微信 - 社交软件", 
            is_multipurpose=False,
            titles=["微信"]
        )
    }

    # 3. 构造日志条目 (LogItem)
    mock_log_items = [
        # 单用途：编程 -> 预期：学习/编程
        LogItem(id=1, app="Code.exe", duration=1200, title="classify_graph.py - LifePrism"),
        # 多用途：学习/编程 -> 预期：学习/阅读 或 学习/编程
        LogItem(id=2, app="Chrome.exe", duration=300, title="LangGraph Documentation - Google Chrome"),
        # 多用途：娱乐/视频 -> 预期：娱乐/视频
        LogItem(id=3, app="Chrome.exe", duration=600, title="Bilibili - 搞笑视频 - Google Chrome"),
        # 单用途：娱乐/社交 -> 预期：娱乐/社交
        LogItem(id=4, app="WeChat.exe", duration=100, title="微信")
    ]

    # 4. 初始化状态
    initial_state = classifyState(
        app_registry=mock_app_registry,
        log_items=mock_log_items
    )
 
    # 5. 初始化图并运行
    try:
        classifier = ClassifyGraph([],category_tree=mock_category_tree)
        config = {"configurable": {"thread_id": "test-thread-simple-001"}}
        
        print("正在调用分类工作流...")
        output = classifier.app.invoke(initial_state, config)

        # 6. 输出结果
        print("\n" + "="*60)
        print("📝 测试分类结果")
        print("="*60)
        
        if "result_items" in output and output["result_items"]:
            result_items = output["result_items"]
            # 按ID排序
            result_items.sort(key=lambda x: x.id)
            
            for item in result_items:
                category_info = f"{item.category or 'None'}/{item.sub_category or 'None'}"
                goal_link = f" (关联目标: {item.link_to_goal})" if item.link_to_goal else ""
                print(f"[ID:{item.id}] App: {item.app}")
                print(f"      Title: {item.title}")
                print(f"      结果: {category_info}{goal_link}")
                if item.title_analysis:
                    print(f"      分析: {item.title_analysis}")
                print("-" * 60)
        else:
            print("❌ 未返回 result_items，请检查执行日志。")

        # 7. Token 统计
        print("\nToken Usage:", classifier.get_total_tokens_usage())

    except Exception as e:
        print(f"❌ 测试运行出错: {e}")
        import traceback
        traceback.print_exc()
