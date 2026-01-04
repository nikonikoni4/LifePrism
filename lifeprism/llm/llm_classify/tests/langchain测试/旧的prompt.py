
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
#         2. 对于单用途,依据app_desc进行分类,若无法分类,则分类为null
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


def multi_classify_node1(state:classifyState) -> classifyState:
    # 获取title
    titles_set = set()
    for log_item in state.log_items:
        titles_set.add(log_item.title)
    print(titles_set)
    
    # system message
    system_message = SystemMessage(content = """
    # 你是一个电脑软件程序标题Title的分析专家,你提取的结果将会作为用户行为分析的依据,你需要按照下面的规则进行对输入的一批titles进行提取
    # title提取规则: 
        1. 若title包含具体的网站名称,则提取网站名称和可能的网站标题作为关键词句
        2. 提取出title中包含的专有名词的句子或标题,尤其是包含未知的专有名词的句子或标题
        2. 每个title都应该提取出至少一个关键词句
    # 依据你的知识库为关键词句增加解释
        1. 判断你的知识库中是否包含该关键词句相关内容,若包含则按照下面规则继续,若不包含给出null
        2. 对于视频网站(Youtube,bilibili,爱奇艺等等)的标题关键词解释:解释应该指向一个具体的语义属性,而不是结构属性
        3. 解释内容应当简单
        **例子**:视频网站的标题'6.皇英絳珠神話_(二)':
            a. 若你不知道什么是皇英絳珠神話,返回null
            b. 坏的回答:
                - 是视频标题中的专有名词，属于特定内容标题。这个回答的是结果属性而不是语义属性
                - 无法确认其语义，返 回null。
            c. 好的回答:
                - 皇英絳珠神話是指的娥皇女英和絳珠仙草的神话
                - null
    # 输出格式:输出一个json
    例如: {
        关键词1 : 关键词1的解释或null, 关键词2 : 关键词2的解释或null
    }
    """)
    human_message = HumanMessage(content=f"""提取下面title中的关键词:{titles_set}
    """)
    message = [system_message,human_message]
    result = chat_model.invoke(message)
    print(result)
    print(result.content)
    message.append(AIMessage(content=result.content))
    # human_message = HumanMessage(content=f"""为什么12.非物讖的婚戀小物_-_關情_涉淫二型这个你不认为他是标题?没有把他添加进来？
    # """)
    # message.append(human_message)
    # result = chat_model.invoke(message)
    # print(result)
    # print(result.content)


你是一个浏览器Title的分析专家,你需要按照下面的步骤进行对输入的一批title进行提取,并分析用户的活动
# title提取: 
    1. 若title中包含网站名称,则web_name = 网站名称,否则web_name=null
    2. 提取title中网页标题web_title
# web_name判断与解释: 
    判断你对于是否了解web_name,若了解给出web_desc(15字以内)
# web_title判断与解释:
    1. 给出你对于这个标题的理解程度评分s(0~100分),规则有不理解的关键词-10分
    1. s>90,给出解释title_desc(15字以内)
    2. s<=90,title_desc=null
# 活动分析
    依据web_name,web_title和解释分析用户的行为活动analysis
# 输出格式：json
    {
        <id>:{
            'web_name' : <web_name>,'web_desc':<web_desc>,'web_title':<web_title>,'title_desc':<title_desc>,'analysis':<analysis>,'s':<s>
        }
    }
    注意:
    - id是输入数据的id
# 提取下面title中的关键词:
{'唐朝诡事录-电视剧全集-完整版视频在线观看-爱奇艺 - 个人 - Microsoft\u200b Edge', '', 'League of Legends (TM) Client', 'LifePrism - Antigravity - Implementation Plan', 'AFFiNE', 'LangGraph 概述 | LangChain 中文文档', 'Google Gemini', 'ActivityWatch', 'Clash for Windows', '快速开始 | LangChain 中文文档', 'Windows 默认锁屏界面', '解释诗句含义 - 豆包 - 豆包', 'WeGame', '唐朝诡事录之西行-电视剧全集-完整版视频在线观看-爱奇艺', '腾讯元宝', '12.非物讖的婚戀小物_-_關情_涉淫二型__哔哩哔哩_bilibili', '智能体 | LangChain 中文文档', 'Next AI Draw.io - AI-Powered Diagram Generator', 'Graph API概述 | LangChain 中 文文档'}

12.非物讖的婚戀小物_-_關情_涉淫二型__哔哩哔哩_bilibili