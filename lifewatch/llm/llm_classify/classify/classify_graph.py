
from langchain_core.prompts.chat import AIMessagePromptTemplate
from lifewatch.llm.llm_classify.schemas.classify_shemas import classifyState,LogItem,Goal,AppInFo,SearchOutput
from lifewatch.llm.llm_classify.utils.create_model import create_ChatTongyiModel
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage,AIMessage
from lifewatch.llm.llm_classify.providers.lw_data_providers import lw_data_providers
from lifewatch.llm.llm_classify.utils.format_prompt_utils import (
    format_goals_for_prompt, 
    format_category_tree_for_prompt, 
    format_log_items_for_prompt, 
    format_app_log_items_for_prompt,
    data_spliter
    )
import json
import logging
from langgraph.types import Send
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
MAX_LOG_ITEMS = 2
MAX_TITLE_ITEMS = 5
SPLIT_DURATION = 10*60 # 20min

# utils

def split_by_purpose(state: classifyState) -> tuple[classifyState, classifyState]:
    """
    将 classifyState 按单用途和多用途分开
    
    Args:
        state: 原始的 classifyState 对象
        
    Returns:
        tuple[classifyState, classifyState]: (单用途state, 多用途state)
        
    Example:
        single_state, multi_state = split_by_purpose(state)
    """
    # 分离 log_items
    single_purpose_items = []
    multi_purpose_items = []
    
    for item in state.log_items:
        app_info = state.app_registry.get(item.app)
        if app_info and not app_info.is_multipurpose:
            single_purpose_items.append(item)
        else:
            multi_purpose_items.append(item)
    
    # 构建单用途 app_registry
    single_apps = set(item.app for item in single_purpose_items)
    single_app_registry = {
        app: info 
        for app, info in state.app_registry.items() 
        if app in single_apps
    }
    
    # 构建多用途 app_registry
    multi_apps = set(item.app for item in multi_purpose_items)
    multi_app_registry = {
        app: info 
        for app, info in state.app_registry.items() 
        if app in multi_apps
    }
    
    # 创建单用途 state
    single_state = classifyState(
        app_registry=single_app_registry,
        log_items=single_purpose_items,
        goal=state.goal,
        category_tree=state.category_tree,
        node_token_usage=state.node_token_usage.copy()
    )
    
    # 创建多用途 state
    multi_state = classifyState(
        app_registry=multi_app_registry,
        log_items=multi_purpose_items,
        goal=state.goal,
        category_tree=state.category_tree,
        node_token_usage=state.node_token_usage.copy()
    )
    
    logger.info(f"分离完成: 单用途 {len(single_purpose_items)} 条, 多用途 {len(multi_purpose_items)} 条")
    
    return single_state, multi_state

def split_by_duartion(state: classifyState)->tuple[classifyState,classifyState]:
    """
    将 classifyState 按时长分开
    
    Args:
        state: 原始的 classifyState 对象
        
    Returns:
        tuple[classifyState, classifyState]: (短时长state, 长时长state)
        
    Example:
        short_state, long_state = split_by_duartion(state)
    """
    # 分离 log_items
    short_duration_items = []
    long_duration_items = []
    
    for item in state.log_items:
        if item.duration < SPLIT_DURATION:
            short_duration_items.append(item)
        else:
            long_duration_items.append(item)
    
    # 构建短时长 app_registry
    short_apps = set(item.app for item in short_duration_items)
    short_app_registry = {
        app: info 
        for app, info in state.app_registry.items() 
        if app in short_apps
    }
    
    # 构建长时长 app_registry
    long_apps = set(item.app for item in long_duration_items)
    long_app_registry = {
        app: info 
        for app, info in state.app_registry.items() 
        if app in long_apps
    }
    
    # 创建短时长 state
    short_state = classifyState(
        app_registry=short_app_registry,
        log_items=short_duration_items,
        goal=state.goal,
        category_tree=state.category_tree,
        node_token_usage=state.node_token_usage.copy()
    )
    
    # 创建长时长 state
    long_state = classifyState(
        app_registry=long_app_registry,
        log_items=long_duration_items,
        goal=state.goal,
        category_tree=state.category_tree,
        node_token_usage=state.node_token_usage.copy()
    )
    
    logger.info(f"按时长分离完成: 短时长(<{SPLIT_DURATION}s) {len(short_duration_items)} 条, 长时长(>={SPLIT_DURATION}s) {len(long_duration_items)} 条")
    
    return short_state, long_state


# router
def router_by_multi_purpose(state: classifyState):
    """
    软件分类路由,单用途和多用途分开处理
    """
    single_state, multi_state = split_by_purpose(state)
    return [
        Send("single_classify", single_state),
        Send("multi_classify", multi_state)
    ]

def router_by_duration_for_multi(state:classifyState):
    """
    多用途应用按时长路由，短时长和长时长分开处理
    """
    short_state, long_state = split_by_duartion(state)
    return [
        Send("multi_classify_short", short_state),
        Send("multi_classify_long", long_state)
    ]

# 通用解析函数
def parse_classification_result(state: classifyState, classification_result: dict, node_name: str) -> classifyState:
    """
    通用的分类结果解析函数
    
    Args:
        state: classifyState 对象
        classification_result: LLM 返回的分类结果，格式为 {id: [category, sub_category, link_to_goal]}
        node_name: 节点名称，用于日志输出
        
    Returns:
        更新后的 classifyState 对象
    """
    # 创建 id 到 log_item 的映射
    id_to_item = {item.id: item for item in state.log_items}
    
    # 遍历分类结果，更新对应的 log_item
    for item_id_str, classification in classification_result.items():
        try:
            item_id = int(item_id_str)
            if item_id in id_to_item:
                # classification 格式: [category, sub_category, link_to_goal]
                if isinstance(classification, list) and len(classification) == 3:
                    category, sub_category, link_to_goal = classification
                    
                    # 将字符串 "null" 或 None 转换为 Python 的 None
                    category = None if (category == "null" or category is None) else category
                    sub_category = None if (sub_category == "null" or sub_category is None) else sub_category
                    link_to_goal = None if (link_to_goal == "null" or link_to_goal is None) else link_to_goal
                    
                    # 更新 log_item
                    id_to_item[item_id].category = category
                    id_to_item[item_id].sub_category = sub_category
                    id_to_item[item_id].link_to_goal = link_to_goal
                    
                    logger.debug(f"[{node_name}] 已更新 log_item {item_id}: category={category}, sub_category={sub_category}, link_to_goal={link_to_goal}")
                else:
                    logger.error(f"[{node_name}] 分类结果格式错误: item_id={item_id}, classification={classification}, 期望列表格式 [category, sub_category, link_to_goal]")
            else:
                logger.warning(f"[{node_name}] 分类结果中的 id {item_id} 在 log_items 中不存在")
        except (ValueError, TypeError) as e:
            logger.error(f"[{node_name}] 解析分类结果时出错: item_id={item_id_str}, classification={classification}, error={e}")
    
    return state

# 创建模型
chat_model = create_ChatTongyiModel()

# step 1: 获取所有app的描述
def get_app_description(state: classifyState):
    # 1. 判断那些app没有描述
    app_to_web_search = []
    app_titles_map = {}  # 存储每个app对应的titles样本
    for app, app_info in state.app_registry.items():
        if app_info.description == None or app_info.description == "":
            app_to_web_search.append(app)
            # 收集该app的titles信息（如果有的话）
            if app_info.titles:
                app_titles_map[app] = app_info.titles[:2]  # 最多取1个title样本
    # 2. 对未知app进行搜索和总结
    if app_to_web_search:
        # 构建包含titles信息的软件列表描述
        app_info_list = []
        for app in app_to_web_search:
            if app in app_titles_map:
                app_info_list.append(f"{app} (窗口标题示例: {app_titles_map[app]})")
            else:
                app_info_list.append(app)
        
        system_message = SystemMessage(content="""
        你是一个软件程序识别专家。你的任务是通过 web 搜索识别软件应用程序，并提供准确、精炼的描述。
        **输入说明：**
        - 软件列表可能包含窗口标题示例，格式为：软件名 (窗口标题示例: [...])
        - 以web搜索为主,title信息为辅
        **输出要求：**
        - 返回 JSON 对象格式
        - 每个软件用一句话（不超过20字）描述核心功能
        - 描述要准确、专业，突出主要用途
        - 如果搜索后仍无法确定，返回 None
        """)
        user_message = HumanMessage(content=f"""
        请通过 web 搜索识别以下软件应用程序，并用一句简短的话描述每个软件的核心功能和用途。
        参考窗口标题可以帮助你更准确地理解软件用途。
        待识别的软件列表：
        {app_info_list}
        返回格式JSON（注意：key只需要软件名称，不包含标题信息）：
            {{"<软件名称>": "<精炼的功能描述>"}}
        示例：
        输入: ["weixin (窗口标题示例: ['张三', '工作群'])", "vscode"]
        输出: {{"weixin": "腾讯开发的即时通讯和社交平台","vscode": "微软开发的轻量级代码编辑器"}}
        """)
        messages = [system_message, user_message]
        
        # 重试机制
        app_description = None
        max_attempt = 3
        for attempt in range(max_attempt):
            try:
                results = chat_model.invoke(messages)
                
                # 提取 token 使用情况
                token_usage = results.response_metadata.get('token_usage', {})
                # 累加或更新 token usage (这里简单覆盖，或者你可以选择累加)
                if 'get_app_description' not in state.node_token_usage.keys():
                    state.node_token_usage['get_app_description'] = token_usage
                else:
                    for key,_  in token_usage.items():
                        state.node_token_usage['get_app_description'][key] += token_usage[key]
                app_description = json.loads(results.content)
                break # 解析成功，跳出循环
            except Exception as e:
                print(f"get_app_description 输出格式错误 (第 {attempt + 1} 次尝试), 错误: {e}")
                if attempt == max_attempt - 1: # 最后一次尝试也失败
                    print(f"get_app_description token usage: {state.node_token_usage['get_app_description']}")
                    return state

        if not app_description:
            return state

        # 3. 更新app描述
        for app in app_to_web_search:
            desc = app_description.get(app, None)
            if desc:
                # 更新 description，保持 is_multipurpose titles不变
                state.app_registry[app] = AppInFo(
                    description=desc,
                    is_multipurpose=state.app_registry[app].is_multipurpose,
                    titles=state.app_registry[app].titles
                )
        # 更新数据库
        lw_data_providers.update_app_description([
            {"app": app, "app_description": state.app_registry[app].description}
            for app in app_to_web_search
        ])
    print(f"get_app_description 重复次数: {max_attempt}")
    print(f"get_app_description token usage: {state.node_token_usage['get_app_description']}")
    return state



# step 2: 单用途分类
def data_split_for_single_classify(state: classifyState):
    return 

def single_classify(state: classifyState) -> classifyState:
    """
    单用途app分类
    """
    # system message
    goal = format_goals_for_prompt(state.goal)
    category_tree = format_category_tree_for_prompt(state.category_tree)
    print(goal)
    print(category_tree)
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
    # 获取单用途的log_item
    single_purpose_items = [
        item for item in state.log_items 
        if not state.app_registry[item.app].is_multipurpose
    ]
    
    if not single_purpose_items:
        logger.info("没有单用途应用需要分类")
        return state
    
    # 使用工具函数格式化 log_items
    app_content = format_app_log_items_for_prompt(single_purpose_items, state.app_registry)
    print(app_content)
    
    # 构建 human_message
    human_message = HumanMessage(content=app_content)
    messages = [system_message, human_message]
    
    # 发送请求并解析结果
    try:
        results = chat_model.invoke(messages)
    
        # 提取 token 使用情况
        token_usage = results.response_metadata.get('token_usage', {})
        if 'single_classify' not in state.node_token_usage.keys():
            state.node_token_usage['single_classify'] = token_usage
        else:
            for key in token_usage.keys():
                state.node_token_usage['single_classify'][key] += token_usage[key]
        
        # 打印原始响应内容以便调试
        print("\n=== LLM 原始响应 ===")
        print(results.content)
        print("=== 响应结束 ===\n")
        
        # 解析 JSON 结果
        classification_result = json.loads(results.content)
        logger.info(f"single_classify 成功获取分类结果")
        
        # 使用通用解析函数更新 state
        state = parse_classification_result(state, classification_result, "single_classify")
        
        logger.info(f"single_classify token usage: {state.node_token_usage.get('single_classify', {})}")
        
    except Exception as e:
        logger.error(f"single_classify 执行失败, 错误: {e}")
        return state
    
    return state

# step 3: 多用途分类
def multi_classify(state:classifyState)->classifyState:
    # 空节点，后续接上多分类路由
    return classifyState
# step 3.1 短时长分类
def multi_classify_short(state:classifyState) -> classifyState:
    category_tree = format_category_tree_for_prompt(state.category_tree)
    goal = format_goals_for_prompt(state.goal)
    items = format_app_log_items_for_prompt(state.log_items,state.app_registry) # 后续优化
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
    """)
    human_message = HumanMessage(content=f"""对下面的数据进行分类:{items}
    """)
    message = [system_message,human_message]
    
    # 发送请求并解析结果
    try:
        result = chat_model.invoke(message)
        
        # 提取 token 使用情况
        token_usage = result.response_metadata.get('token_usage', {})
        if 'multi_classify_short' not in state.node_token_usage.keys():
            state.node_token_usage['multi_classify_short'] = token_usage
        else:
            for key in token_usage.keys():
                state.node_token_usage['multi_classify_short'][key] += token_usage[key]
        
        # 打印原始响应内容以便调试
        print("\n=== LLM 原始响应 ===")
        print(result.content)
        print("=== 响应结束 ===\n")
        
        # 解析 JSON 结果
        classification_result = json.loads(result.content)
        logger.info(f"multi_classify_short 成功获取分类结果")
        
        # 使用通用解析函数更新 state
        state = parse_classification_result(state, classification_result, "multi_classify_short")
        
        logger.info(f"multi_classify_short token usage: {state.node_token_usage.get('multi_classify_short', {})}")
        
    except Exception as e:
        logger.error(f"multi_classify_short 执行失败, 错误: {e}")
        return state
    
    return state

# step 3.2 长时长分类
# step 3.2.1 搜索title，并总结title活动
# 由于一次请求只能进行一次搜索，所以需要进行并发
def multi_classify_long(state:classifyState) ->SearchOutput:
    # 生成title，list
    title_set = set()
    for item in state.log_items:
        title_set.add((item.id,item.title))
    return {
        "input_data":list(title_set)
    }

def send_title(input:SearchOutput):
    return [
        Send("search_title",input) for input in input.input_data
    ]

def search_title(input:tuple[int,str])->SearchOutput:
    system_message = SystemMessage(content="""
    你是一个通过网络搜索分析的助手,依据网络搜索结果和title分析用户的活动，要求结果在50字以内
    # 输出格式:str 内容为:用户活动
    """)
    human_message = HumanMessage(content=f"""搜索并分析{input[1]}""")
    message = [system_message,human_message]
    result = chat_model.invoke(message)
    print(result)
    print(result.content)
    return {
        "title_analysis": [(input[0],result.content)]
        }


# step 3.2 使用数据库查询实体

# step 3.3 使用网络搜索查询剩余信息并保存实体

# step 3.4 分析用户的行为，并分类




if __name__ == "__main__":
    from lifewatch.llm.llm_classify.classify.data_loader import get_real_data,filter_by_duration,deduplicate_log_items
    
    def get_state(hours = 36) -> classifyState:
        state = get_real_data(hours=hours)
        state = filter_by_duration(state, min_duration=60)
        state = deduplicate_log_items(state)
        print(f"\n去重后的日志（前10条）:")
        for item in state.log_items[:10]:
            multipurpose = "多用途" if state.app_registry[item.app].is_multipurpose else "单用途"
            print(f"  {item.app} ({multipurpose}) | {item.title} | {item.duration}s")
        
        # 测试过滤功能
        print(f"\n测试过滤功能（只保留 duration >= 60 秒的记录）:")
        print(f"  - 过滤后 log_items: {len(state.log_items)} 条")
        print(f"  - 过滤后 app_registry: {len(state.app_registry)} 个应用")
        return state
    state = get_state(hours=100)
    s,m=split_by_purpose(state)
    ms,ml=split_by_duartion(m)
    graph = StateGraph(classifyState)
    graph.add_node("multi_classify_long",multi_classify_long)
    graph.add_node("search_title",search_title)
    graph.add_edge(START,"multi_classify_long")
    graph.add_conditional_edges("multi_classify_long",send_title)
    graph.add_edge("search_title",END)
    app = graph.compile()
    output = app.invoke(ml)
    print(output)
    # multi_classify_short(ms)

    # multi_classify_node1(state)
    #state = get_app_description(state)
    #state = single_classify(state)
    # graph = StateGraph(state)
    # graph.add_node("get_app_description",get_app_description)
    # graph.add_node()
    # state = get_app_description(state)
