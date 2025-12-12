from lifewatch.llm.llm_classify.schemas.classify_shemas import classifyState,LogItem,Goal,AppInFo,MultiNodeResult
from lifewatch.llm.llm_classify.utils.create_model import create_ChatTongyiModel
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage
from lifewatch.llm.llm_classify.providers.lw_data_providers import lw_data_providers
from lifewatch.llm.llm_classify.utils.format_prompt_utils import format_goals_for_prompt, format_category_tree_for_prompt, format_log_items_for_prompt, format_app_log_items_for_prompt
import json
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# step 0 : 创建模型
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
# def single_classify(state: classifyState) -> classifyState:
#     """
#     单用途app分类
#     """
#     # system message
#     goal = format_goals_for_prompt(state.goal)
#     category_tree = format_category_tree_for_prompt(state.category_tree)
#     print(goal)
#     print(category_tree)
#     system_message = SystemMessage(content=f"""
#         # 你是一个软件分类专家。你的任务是根据软件名称,描述,将软件进行分类,分类有category和sub_category两级分类。
#         # 分类类别
#         {category_tree}
#         # 用户目标
#         {goal}
#         # 分类规则
#         1. 对于app与goal高度相关的条目,使用goal的分类类别,并关联goal,link_to_goal = goal;否则link_to_goal = null
#         2. 对于单用途,依据app_description进行分类,若无法分类,则分类为null
#         3. 若category有分类而sub_category无法分类,则sub_category = null
#         # 输出格式（重要：必须是标准JSON格式）
#         返回一个JSON对象，key是log item的id（整数），value是一个包含category、sub_category、link_to_goal的JSON对象
#         {{
#             <id>: {{
#                 "category": <category值或null>,
#                 "sub_category": <sub_category值或null>,
#                 "link_to_goal": <link_to_goal值或null>
#             }}
#         }}
#         示例：
#         {{
#             "1": {{"category": "工作", "sub_category": "编程", "link_to_goal": "goal1"}},
#         }}
#         """)
#     # 获取单用途的log_item
#     single_purpose_items = [
#         item for item in state.log_items 
#         if not state.app_registry[item.app].is_multipurpose
#     ]
    
#     if not single_purpose_items:
#         logger.info("没有单用途应用需要分类")
#         return state
    
#     # 使用工具函数格式化 log_items
#     app_content = format_app_log_items_for_prompt(single_purpose_items, state.app_registry)
#     print(app_content)
    
#     # 构建 human_message
#     human_message = HumanMessage(content=app_content)
#     messages = [system_message, human_message]
    
#     # 发送请求并解析结果
#     try:
#         results = chat_model.invoke(messages)
    
#         # 提取 token 使用情况
#         token_usage = results.response_metadata.get('token_usage', {})
#         if 'single_classify' not in state.node_token_usage.keys():
#             state.node_token_usage['single_classify'] = token_usage
#         else:
#             for key in token_usage.keys():
#                 state.node_token_usage['single_classify'][key] += token_usage[key]
        
#         # 打印原始响应内容以便调试
#         print("\n=== LLM 原始响应 ===")
#         print(results.content)
#         print("=== 响应结束 ===\n")
        
#         # 解析 JSON 结果
#         classification_result = json.loads(results.content)
#         logger.info(f"single_classify 成功获取分类结果")
        
#         # 按照 id 赋值给 logitem
#         # 创建 id 到 log_item 的映射
#         id_to_item = {item.id: item for item in state.log_items}
#         # 遍历分类结果，更新对应的 log_item
#         for item_id_str, classification in classification_result.items():
#             try:
#                 item_id = int(item_id_str)
#                 if item_id in id_to_item:
#                     # classification 格式: {"category": ..., "sub_category": ..., "link_to_goal": ...}
#                     # 确保 classification 是字典对象
#                     if isinstance(classification, dict):
#                         category = classification.get("category")
#                         sub_category = classification.get("sub_category")
#                         link_to_goal = classification.get("link_to_goal")
#                         # 更新 log_item (JSON中的null会被解析为Python的None)
#                         id_to_item[item_id].category = category
#                         id_to_item[item_id].sub_category = sub_category
#                         id_to_item[item_id].link_to_goal = link_to_goal
                        
#                         logger.debug(f"已更新 log_item {item_id}: category={category}, sub_category={sub_category}, link_to_goal={link_to_goal}")
#                     else:
#                         logger.error(f"分类结果格式错误: item_id={item_id}, classification={classification}, 期望字典对象")
#                 else:
#                     logger.warning(f"分类结果中的 id {item_id} 在 log_items 中不存在")
#             except (ValueError, TypeError) as e:
#                 logger.error(f"解析分类结果时出错: item_id={item_id_str}, classification={classification}, error={e}")
        
#         logger.info(f"single_classify token usage: {state.node_token_usage.get('single_classify', {})}")
        
#     except Exception as e:
#         logger.error(f"single_classify 执行失败, 错误: {e}")
#         return state
    
#     return state

# step 2: 单用途分类
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
        # 输出格式（重要：必须是标准JSON格式）
        返回一个JSON对象，key是log item的id（整数），value是一个字符串，格式为 "category|sub_category|link_to_goal"
        {{
            <id>: "category|sub_category|link_to_goal"
        }}
        
        示例：
        {{
            "1": "工作|编程|goal1",
            "2": "娱乐|null|null"
        }}

        注意：
        - value必须是字符串，使用 | 分隔三个字段
        - 无值时使用 null（字符串形式）
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
        
        # 按照 id 赋值给 logitem
        # 创建 id 到 log_item 的映射
        id_to_item = {item.id: item for item in state.log_items}
        # 遍历分类结果，更新对应的 log_item
        for item_id_str, classification in classification_result.items():
            try:
                item_id = int(item_id_str)
                if item_id in id_to_item:
                    # classification 格式: "category|sub_category|link_to_goal"
                    # 确保 classification 是字符串
                    if isinstance(classification, str):
                        parts = classification.split('|')
                        if len(parts) == 3:
                            category, sub_category, link_to_goal = parts
                            
                            # 将字符串 "null" 转换为 Python 的 None
                            category = None if category == "null" else category
                            sub_category = None if sub_category == "null" else sub_category
                            link_to_goal = None if link_to_goal == "null" else link_to_goal
                            
                            # 更新 log_item
                            id_to_item[item_id].category = category
                            id_to_item[item_id].sub_category = sub_category
                            id_to_item[item_id].link_to_goal = link_to_goal
                            
                            logger.debug(f"已更新 log_item {item_id}: category={category}, sub_category={sub_category}, link_to_goal={link_to_goal}")
                        else:
                            logger.error(f"分类结果格式错误: item_id={item_id}, classification={classification}, 期望3个字段")
                    else:
                        logger.error(f"分类结果格式错误: item_id={item_id}, classification={classification}, 期望字符串")
                else:
                    logger.warning(f"分类结果中的 id {item_id} 在 log_items 中不存在")
            except (ValueError, TypeError) as e:
                logger.error(f"解析分类结果时出错: item_id={item_id_str}, classification={classification}, error={e}")
        
        logger.info(f"single_classify token usage: {state.node_token_usage.get('single_classify', {})}")
        
    except Exception as e:
        logger.error(f"single_classify 执行失败, 错误: {e}")
        return state
    
    return state

# step 3: 多用途分类
# step 3.1 提取title中的实体

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
    state = get_state(hours=48)
    state = get_app_description(state)
    state = single_classify(state)
    # graph = StateGraph(state)
    # graph.add_node("get_app_description",get_app_description)
    # graph.add_node()
    # state = get_app_description(state)
