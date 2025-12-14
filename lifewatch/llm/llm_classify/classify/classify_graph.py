from lifewatch.llm.llm_classify.schemas.classify_shemas import classifyState,Goal,AppInFo,SearchOutput
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
    )
    
    # 创建多用途 state
    multi_state = classifyState(
        app_registry=multi_app_registry,
        log_items=multi_purpose_items,
        goal=state.goal,
        category_tree=state.category_tree,
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
    )
    # 创建长时长 state
    long_state = classifyState(
        app_registry=long_app_registry,
        log_items=long_duration_items,
        goal=state.goal,
        category_tree=state.category_tree,
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
        Send("get_titles", long_state)
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
def get_app_description(state: classifyState) -> classifyState:
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
            # 获取一个 title 样本用于辅助识别
            title_sample = app_info.titles[0] if app_info.titles else ""
            app_to_search.append((app, title_sample))
    
    if not app_to_search:
        logger.info("所有 app 都已有描述，跳过搜索")
        return state
    
    logger.info(f"需要搜索描述的 app: {[app for app, _ in app_to_search]}")
    
    # 2. 顺序搜索每个 app 的描述
    app_descriptions = {}  # app_name -> description
    token_usage = {
        'input_tokens': 0,
        'output_tokens': 0,
        'total_tokens': 0,
        'search_count': 0
    }
    
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
            
            result = chat_model.invoke(messages)
            
            # 提取描述
            app_descriptions[app] = result.content
            
            # 累计 token 使用
            return_tokens = result.response_metadata.get('token_usage', {})
            print(return_tokens)
            token_usage['input_tokens'] += return_tokens.get('input_tokens', 0)
            token_usage['output_tokens'] += return_tokens.get('output_tokens', 0)
            token_usage['total_tokens'] += return_tokens.get('total_tokens', 0)
            # 提取 search_count
            plugins = return_tokens.get('plugins', {})
            search_info = plugins.get('search', {})
            token_usage['search_count'] += search_info.get('count', 0)
            
            logger.info(f"已获取 {app} 的描述: {result.content[:50]}...")
            
        except Exception as e:
            logger.error(f"搜索 {app} 描述失败: {e}")
            app_descriptions[app] = None
    
    
    # 3. 直接更新 state.app_registry
    for app_name, description in app_descriptions.items():
        if app_name in state.app_registry:
            state.app_registry[app_name].description = description
    
    # 返回更新后的状态
    return {
        "node_token_usage": {"get_app_description": token_usage},
        "app_registry": state.app_registry
    }




# step 2: 单用途分类
def single_classify(state: classifyState) -> classifyState:
    """
    单用途app分类（分批处理，每批最多 MAX_LOG_ITEMS 条）
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
    
    # 初始化 token 统计
    total_token_usage = {
        'input_tokens': 0,
        'output_tokens': 0,
        'total_tokens': 0,
        'search_count': 0
    }
    
    # 分批处理
    for i in range(0, len(single_purpose_items), MAX_LOG_ITEMS):
        batch = single_purpose_items[i:i + MAX_LOG_ITEMS]
        batch_num = i // MAX_LOG_ITEMS + 1
        logger.info(f"single_classify 处理第 {batch_num} 批，共 {len(batch)} 条记录")
        
        # 使用工具函数格式化 log_items
        app_content = format_app_log_items_for_prompt(batch, state.app_registry)
        print(app_content)
        
        # 构建 human_message
        human_message = HumanMessage(content=app_content)
        messages = [system_message, human_message]
        
        # 发送请求并解析结果
        try:
            results = chat_model.invoke(messages)
        
            # 提取 token 使用情况
            raw_token_usage = results.response_metadata.get('token_usage', {})
            total_token_usage['input_tokens'] += raw_token_usage.get('input_tokens', 0)
            total_token_usage['output_tokens'] += raw_token_usage.get('output_tokens', 0)
            total_token_usage['total_tokens'] += raw_token_usage.get('total_tokens', 0)
            total_token_usage['search_count'] += raw_token_usage.get('plugins', {}).get('search', {}).get('count', 0)
            
            # 打印原始响应内容以便调试
            print(f"\n=== LLM 原始响应 (批次 {batch_num}) ===")
            print(results.content)
            print("=== 响应结束 ===\n")
            
            # 解析 JSON 结果
            classification_result = json.loads(results.content)
            logger.info(f"single_classify 批次 {batch_num} 成功获取分类结果")
            
            # 使用通用解析函数更新 state
            state = parse_classification_result(state, classification_result, "single_classify")
            
        except Exception as e:
            logger.error(f"single_classify 批次 {batch_num} 执行失败, 错误: {e}")
            continue
    
    state.node_token_usage['single_classify'] = total_token_usage
    logger.info(f"single_classify token usage: {total_token_usage}")
    
    return {
        "result_items" : state.log_items,
        "node_token_usage":{"single_classify": total_token_usage}
    }

# step 3: 多用途分类
def multi_classify(state:classifyState)->classifyState:
    # 空节点，后续接上多分类路由
    return {
        
    }
# step 3.1 短时长分类
def multi_classify_short(state:classifyState) -> classifyState:
    """
    短时长多用途分类（分批处理，每批最多 MAX_LOG_ITEMS 条）
    """
    category_tree = format_category_tree_for_prompt(state.category_tree)
    goal = format_goals_for_prompt(state.goal)
    
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
    
    if not state.log_items:
        logger.info("没有短时长多用途应用需要分类")
        return state
    
    # 初始化 token 统计
    total_token_usage = {
        'input_tokens': 0,
        'output_tokens': 0,
        'total_tokens': 0,
        'search_count': 0
    }
    
    # 分批处理
    for i in range(0, len(state.log_items), MAX_LOG_ITEMS):
        batch = state.log_items[i:i + MAX_LOG_ITEMS]
        batch_num = i // MAX_LOG_ITEMS + 1
        logger.info(f"multi_classify_short 处理第 {batch_num} 批，共 {len(batch)} 条记录")
        
        items = format_app_log_items_for_prompt(batch, state.app_registry)
        human_message = HumanMessage(content=f"""对下面的数据进行分类:{items}
        """)
        messages = [system_message, human_message]
        
        # 发送请求并解析结果
        try:
            result = chat_model.invoke(messages)
            
            # 提取 token 使用情况
            raw_token_usage = result.response_metadata.get('token_usage', {})
            total_token_usage['input_tokens'] += raw_token_usage.get('input_tokens', 0)
            total_token_usage['output_tokens'] += raw_token_usage.get('output_tokens', 0)
            total_token_usage['total_tokens'] += raw_token_usage.get('total_tokens', 0)
            total_token_usage['search_count'] += raw_token_usage.get('plugins', {}).get('search', {}).get('count', 0)
            
            # 打印原始响应内容以便调试
            print(f"\n=== LLM 原始响应 (批次 {batch_num}) ===")
            print(result.content)
            print("=== 响应结束 ===\n")
            
            # 解析 JSON 结果
            classification_result = json.loads(result.content)
            logger.info(f"multi_classify_short 批次 {batch_num} 成功获取分类结果")
            
            # 使用通用解析函数更新 state
            state = parse_classification_result(state, classification_result, "multi_classify_short")
            
        except Exception as e:
            logger.error(f"multi_classify_short 批次 {batch_num} 执行失败, 错误: {e}")
            continue
    
    state.node_token_usage['multi_classify_short'] = total_token_usage
    logger.info(f"multi_classify_short token usage: {total_token_usage}")
    
    return {
        "result_items" : state.log_items,
        "node_token_usage":{"multi_classify_short": total_token_usage}
    }

# step 3.2 长时长分类
# step 3.2.1 搜索title，并总结title活动
# 由于一次请求只能进行一次搜索，所以需要进行并发
def get_titles(state:classifyState) -> SearchOutput:
    # 生成title字典，key为id，value为title
    title_dict = {}
    for item in state.log_items:
        if item.title:  # 只添加有title的项
            title_dict[item.id] = item.title
    return {
        "input_data": title_dict,
    }

def send_title(input: SearchOutput):
    # 为每个 id-title 对创建一个 Send 任务
    return [
        Send("search_title", {"id": item_id, "title": title}) 
        for item_id, title in input.input_data.items()
    ]

def search_title(input: dict) -> SearchOutput:
    """搜索并分析单个title
    
    Args:
        input: 包含 'id' 和 'title' 的字典
    
    Returns:
        SearchOutput: 包含该id的分析结果
    """
    item_id = input["id"]
    title = input["title"]
    
    system_message = SystemMessage(content="""
    你是一个通过网络搜索分析的助手,依据网络搜索结果和title分析用户的活动，要求结果在50字以内
    # 输出格式:str 内容为:用户活动
    """)
    human_message = HumanMessage(content=f"""搜索并分析{title}""")
    message = [system_message, human_message]
   
    try:
        result = chat_model.invoke(message)
        # 打印原始响应内容以便调试
        print("\n=== LLM 原始响应 ===")
        print(f"title:{result.content}")
        print("=== 响应结束 ===\n")
    except Exception as e:
        logger.error(f"search_title 执行失败, 错误: {e}")
        return state
    # 提取 token 使用情况 (只获取 input_tokens, output_tokens, total_tokens)
    raw_token_usage = result.response_metadata.get('token_usage', {})
    token_usage = {
        'input_tokens': raw_token_usage.get('input_tokens', 0),
        'output_tokens': raw_token_usage.get('output_tokens', 0),
        'total_tokens': raw_token_usage.get('total_tokens', 0),
        'search_count': raw_token_usage.get('plugins', {}).get('search', {}).get('count', 0)
    }
    return {
        "title_analysis": {item_id: result.content},
        "search_tokens": [token_usage]
    }

# step 3.2.2 汇总数据
def merge_searchoutput_to_classifystate(output: SearchOutput) -> classifyState:
    """将搜索分析结果合并回state
    Args:
        output: SearchOutput 包含 title_analysis 字典 (id -> analysis_result)
    
    Returns:
        classifyState: 更新了 title_analysis 的状态
    """
    print("test---")
    # 计算search_title的tokens消耗
    from collections import Counter
    search_tokens = Counter()
    for d in output.search_tokens:
        search_tokens.update(d)
    search_tokens = dict(search_tokens)
    return {
        "node_token_usage" : {"search_title":search_tokens},
        "log_items" : {
            "update_flag":"title_analysis",
            "update_data":output.title_analysis
        }
    }
    
# step 3.3 进行分类
def multi_classify_long(state:classifyState)->classifyState:
    """
    长时长多用途分类（分批处理，每批最多 MAX_LOG_ITEMS 条）
    """
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
        return state
    
    # 初始化 token 统计
    total_token_usage = {
        'input_tokens': 0,
        'output_tokens': 0,
        'total_tokens': 0,
        'search_count': 0
    }
    
    # 分批处理
    for i in range(0, len(state.log_items), MAX_LOG_ITEMS):
        batch = state.log_items[i:i + MAX_LOG_ITEMS]
        batch_num = i // MAX_LOG_ITEMS + 1
        logger.info(f"multi_classify_long 处理第 {batch_num} 批，共 {len(batch)} 条记录")
        
        # 构建表格头部
        table_lines = []
        table_lines.append("| ID | Title | Title Analysis |")
        table_lines.append("|-----|-------|----------------|")
        
        # 添加每一行数据
        for item in batch:
            # 处理可能的 None 值
            title = item.title or "N/A"
            title_analysis = item.title_analysis or "N/A"
            
            # 转义特殊字符，避免破坏表格格式
            title = title.replace("|", "\\|").replace("\n", " ")
            title_analysis = title_analysis.replace("|", "\\|").replace("\n", " ")
            
            # 限制长度，避免表格过宽
            if len(title) > 50:
                title = title[:47] + "..."
            if len(title_analysis) > 100:
                title_analysis = title_analysis[:97] + "..."
            
            table_lines.append(f"| {item.id} | {title} | {title_analysis} |")
        
        # 合并为完整的表格字符串
        log_items_table = "\n".join(table_lines)
        
        human_message = HumanMessage(content=f"""
        请对以下用户行为数据进行分类：
        {log_items_table}
        """)
        
        messages = [system_message, human_message]
        
        # 发送请求并解析结果
        try:
            result = chat_model.invoke(messages)
            
            # 提取 token 使用情况
            raw_token_usage = result.response_metadata.get('token_usage', {})
            total_token_usage['input_tokens'] += raw_token_usage.get('input_tokens', 0)
            total_token_usage['output_tokens'] += raw_token_usage.get('output_tokens', 0)
            total_token_usage['total_tokens'] += raw_token_usage.get('total_tokens', 0)
            total_token_usage['search_count'] += raw_token_usage.get('plugins', {}).get('search', {}).get('count', 0)
            
            # 打印原始响应内容以便调试
            print(f"\n=== LLM 原始响应 (批次 {batch_num}) ===")
            print(result.content)
            print("=== 响应结束 ===\n")
            
            # 解析 JSON 结果
            classification_result = json.loads(result.content)
            logger.info(f"multi_classify_long 批次 {batch_num} 成功获取分类结果")
            
            # 使用通用解析函数更新 state
            state = parse_classification_result(state, classification_result, "multi_classify_long")
            
        except Exception as e:
            logger.error(f"multi_classify_long 批次 {batch_num} 执行失败, 错误: {e}")
            continue
    
    state.node_token_usage['multi_classify_long'] = total_token_usage
    logger.info(f"multi_classify_long token usage: {total_token_usage}")
    
    return {
        "result_items" : state.log_items,
        "node_token_usage":{"multi_classify_long": total_token_usage}
    }





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
    input_items_len = len(state.log_items)
    graph = StateGraph(classifyState)
    graph.add_node("get_app_description",get_app_description)
    graph.add_node("single_classify",single_classify)
    graph.add_node("multi_classify",multi_classify) # 空节点
    graph.add_node("get_titles",get_titles) # 获取title
    graph.add_node("search_title",search_title) # 多并发查询title
    graph.add_node("merge_searchoutput_to_classifystate",merge_searchoutput_to_classifystate) # 合并查询数据
    graph.add_node("multi_classify_long",multi_classify_long)  # 长时间多用途分类
    graph.add_node("multi_classify_short",multi_classify_short) # 短时间多用途分类
    
    graph.add_edge(START,"get_app_description")
    graph.add_conditional_edges("get_app_description",router_by_multi_purpose) # -> single_classify | -> multi_classify
    # 单用途分类
    graph.add_edge("single_classify",END)
    # 多用途分类
    graph.add_conditional_edges("multi_classify",router_by_duration_for_multi) # ->multi_classify_short | -> get_titles
    # 短时间分类
    graph.add_edge("multi_classify_short",END)
    # 长时间分类
    graph.add_conditional_edges("get_titles",send_title) # 并发搜索
    graph.add_edge("search_title","merge_searchoutput_to_classifystate") # 合并数据
    graph.add_edge("merge_searchoutput_to_classifystate","multi_classify_long") # 分类
    graph.add_edge("multi_classify_long",END)
    app = graph.compile()
    output = app.invoke(state)
    # 格式化输出结果
    print("\n" + "="*80)
    print("分类结果汇总")
    print("="*80)
    print(output)
    # 输出 token 使用情况
    if "node_token_usage" in output:
        print("\n【Token 使用统计】")
        total_tokens = 0
        total_search_count = 0
        for node_name, usage in output["node_token_usage"].items():
            print(f"\n  {node_name}:")
            print(f"    - Input Tokens:  {usage.get('input_tokens', 0):,}")
            print(f"    - Output Tokens: {usage.get('output_tokens', 0):,}")
            print(f"    - Total Tokens:  {usage.get('total_tokens', 0):,}")
            print(f"    - Search Count:  {usage.get('search_count', 0)}")
            total_tokens += usage.get('total_tokens', 0)
            total_search_count += usage.get('search_count', 0)
        print(f"\n  总计 Token 使用: {total_tokens:,}")
        print(f"  总计搜索次数: {total_search_count}")
    
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
            print()
    
    print("="*80)
    print(f"输入个数:{input_items_len}")
    # 同时保存完整的 JSON 输出到文件（可选）
    # with open("classification_output.json", "w", encoding="utf-8") as f:
    #     json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    # 测试merge_searchoutput_to_classifystate
    # 构建测试流程: get_titles -> search_title (并发) -> merge_searchoutput_to_classifystate
    # s,m = split_by_purpose(state)
    # s,l = split_by_duartion(m)
    # state = l
    # print(l)
    # graph.add_edge(START, "get_titles")
    # graph.add_conditional_edges("get_titles", send_title)  # 并发搜索
    # graph.add_edge("search_title", "merge_searchoutput_to_classifystate")  # 合并数据
    # graph.add_edge("merge_searchoutput_to_classifystate", END)
    
    # # 编译并运行
    # app = graph.compile()
    # output = app.invoke(state)
    
    # print(output)




