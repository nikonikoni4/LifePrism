from lifewatch.llm.langchain_test.creat_model import create_ChatTongyiModel 
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage
import json
from lifewatch.llm.langchain_test.utils import format_goals_for_prompt, format_category_tree_for_prompt,format_log_items_for_prompt
from lifewatch.llm.langchain_test.mock_data import mock_log_items, mock_goals, mock_app_registry
from lifewatch.llm.langchain_test.state_define import classifyState, LogItem, Goal, AppInFo
from lifewatch.llm.langchain_test.data_loader import get_real_data,filter_by_duration,deduplicate_log_items
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# 创建chatmodel
chat_model = create_ChatTongyiModel()

# 定义router


# 定义node

def mock_app_description(state: classifyState) -> classifyState:
    """
    使用预定义的描述填充 app_registry，避免每次测试都调用 LLM
    
    Args:
        state: 输入的 classifyState
        
    Returns:
        classifyState: 更新了 app 描述的新状态
    """
    # 预定义的 app 描述（从之前的 LLM 查询结果中获取）
    predefined_descriptions = {
        'doubao': '字节跳动推出的AI助手，支持多模态内容生成与智能对话',
        'lockapp': '基于生物识别与密码的手机应用锁屏工具，保障隐私安全',
        'affine': '基于Web的协作式文档与项目管理平台，支持实时协同编辑',
        'clash for windows': '跨平台网络代理工具，支持规则分流与科学上网配置',
        'msedge': '微软开发的基于Chromium的网页浏览器，集成AI功能与高效浏览体验',
        'antigravity': '专为开发者设计的AI原生代码生成与自动化编程工具',
    }
    
    # 更新 app_registry 中的描述
    for app, app_info in state.app_registry.items():
        if app in predefined_descriptions:
            # 更新 description，保持 is_multipurpose 不变
            state.app_registry[app] = AppInFo(
                description=predefined_descriptions[app],
                is_multipurpose=app_info.is_multipurpose
            )
    
    return state


def get_app_description(state: classifyState):
    # 判断那些app没有描述
    app_to_web_search = []
    for app, app_info in state.app_registry.items():
        if app_info.description == None or app_info.description == "":
            app_to_web_search.append(app)
    if app_to_web_search:
        system_message = SystemMessage(content="""
        你是一个软件识别专家。你的任务是通过 web 搜索识别软件应用程序，并提供准确、精炼的描述。
        **输出要求：**
        - 返回 JSON 数组格式
        - 每个软件用一句话（不超过20字）描述核心功能
        - 描述要准确、专业，突出主要用途
        - 如果搜索后仍无法确定，返回 None
        """)
        user_message = HumanMessage(content=f"""
        请通过 web 搜索识别以下软件应用程序，并用一句简短的话描述每个软件的核心功能和用途。
        待识别的软件列表：
        {app_to_web_search}
        返回格式JSON：
            {{"<软件名称>": "<精炼的功能描述>"}}
        示例：
        输入: ["weixin", "vscode"]
        输出: {{"weixin": "腾讯开发的即时通讯和社交平台","Antigravity": "谷歌推出的AI原生集成开发环境"}}
        """)
        messages = [system_message, user_message]
        results = chat_model.invoke(messages)
        
        # 提取 token 使用情况
        token_usage = results.response_metadata.get('token_usage', {})
        state.node_token_usage['get_app_description'] = token_usage
        # 更新state
        try:
           app_description = json.loads(results.content)
        except:
            print("get_app_description 输出格式错误, results.content : {results.content}")
            return state
        for app in app_to_web_search:
            desc = app_description.get(app, None)
            if desc:
                # 更新 description，保持 is_multipurpose 不变
                state.app_registry[app] = AppInFo(
                    description=desc,
                    is_multipurpose=state.app_registry[app].is_multipurpose
                )
    return state

def easy_app_to_classify(state: classifyState):
    """
    简单的app分类
    策略： 极速匹配，不消耗 LLM 推理能力。
    2.1 单用途 App： 直接根据 App 描述分类（如 PyCharm -> 工作）。
    2.2 强关联 Goal：
    检查 Title 是否包含用户设定的 Goal 关键词。
    例子： 用户设定 Goal 为“学习红楼梦”。Title 包含“红楼梦” -> 直接分类为“学习”，并关联该 Goal。
    """
    goal = format_goals_for_prompt(state.goal)
    category_tree = format_category_tree_for_prompt(state.category_tree)
    system_message = SystemMessage(content=f"""
        # 你是一个软件分类专家。你的任务是根据软件名称,描述,Title,将软件进行分类,分类有category和sub_category两级分类。
        # 分类类别
        {category_tree}
        # 用户目标
        {goal}
        # 分类规则
        1. 对于app和title与goal高度相关的条目,使用goal的分类类别,并关联goal,link_to_goal = goal;否则link_to_goal = None
        2. 对于单用途,依据app_description进行分类,若无法分类,则分类为None
        3. 对于多用途,依据title进行分类:
            - 若对于title完全已知,且有且只有一个分类能够匹配,则直接进行分类
            - 若对于title内某些内容未知,给出你需要查询的内容赋值给search_title_query,或无法确定的,各级分类为None
        4. 若category有分类而sub_category无法分类,则sub_category = None
        # 输出格式
        {{<id>:(<category>|None,<sub_category>|None,<link_to_goal>|None,<search_title_query>|None)}}
        """)

    # 按 app 分组 log_items
    app_groups = {}
    for log_item in state.log_items:
        app_name = log_item.app
        if app_name not in app_groups:
            app_groups[app_name] = []
        app_groups[app_name].append(log_item)
    
    # 构建按 app 分组的内容
    app_content = "待分类的软件列表（按应用分组）：\n\n"
    for app_name, items in app_groups.items():
        app_info = state.app_registry.get(app_name)
        if app_info:
            app_description = app_info.description
            is_multipurpose = "多用途" if app_info.is_multipurpose else "单用途"
        else:
            app_description = "无描述"
            is_multipurpose = "未知"
        app_content += f"## {app_name}\n"
        app_content += f"应用描述: {app_description} ({is_multipurpose})\n"
        app_content += "活动记录:\n"
        
        # 第一条记录显示键名
        if items:
            first_item = items[0]
            first_dict = first_item.model_dump(exclude={
                "category", "sub_category", "link_to_goal",
                "search_title_query", "search_title_content", "need_analyze_context",
            })
            # 显示键名
            keys = list(first_dict.keys())
            app_content += f"  {' | '.join(keys)}\n"
            # 显示第一条数据的值
            values = [str(first_dict[k]) for k in keys]
            app_content += f"  {' | '.join(values)}\n"
            
            # 后续记录只显示值
            for item in items[1:]:
                item_dict = item.model_dump(exclude={
                    "category", "sub_category", "link_to_goal",
                    "search_title_query", "search_title_content", "need_analyze_context",
                })
                values = [str(item_dict[k]) for k in keys]
                app_content += f"  {' | '.join(values)}\n"
        
        app_content += "\n"

    user_message = HumanMessage(content=f"""
        请根据软件名称,描述,Title,将软件进行分类。
        {app_content}
        """)
    messages = [system_message, user_message]
    results = chat_model.invoke(messages)
    print(results.content)
    # 提取 token 使用情况
    token_usage = results.response_metadata.get('token_usage', {})
    state.node_token_usage['easy_app_to_classify'] = token_usage
    
    # 更新state
    try:
        import re
        
        # 创建一个id到log_item的映射，方便快速查找
        log_items_dict = {item.id: item for item in state.log_items}
        
        # LLM返回的格式是多行文本，每行格式为: {id:(category,sub_category,link_to_goal,search_title_query)}
        # 使用正则表达式解析每一行
        content = results.content.strip()
        
        # 正则表达式匹配模式: {数字:(值1,值2,值3,值4)}
        # 注意：值可能包含中文、英文、空格、None等
        pattern = r'\{(\d+):\(([^,]+),([^,]+),([^,]+),([^)]+)\)\}'
        
        matches = re.findall(pattern, content)
        
        if not matches:
            print(f"警告: 无法解析LLM返回的内容")
            print(f"返回内容: {content}")
            return state
        
        # 遍历所有匹配结果
        for match in matches:
            item_id, category, sub_category, link_to_goal, search_title_query = match
            item_id = int(item_id)  # 转换为整数
            
            if item_id in log_items_dict:
                # 处理每个字段，去除首尾空格，并将 "None" 或 "无" 转换为 None
                def clean_value(value):
                    value = value.strip()
                    if value in ["None", "无", "null", ""]:
                        return None
                    return value
                
                # 更新log_item的分类信息
                log_items_dict[item_id].category = clean_value(category)
                log_items_dict[item_id].sub_category = clean_value(sub_category)
                log_items_dict[item_id].link_to_goal = clean_value(link_to_goal)
                
                # search_title_query 可能包含 "搜索: xxx" 格式
                search_query = clean_value(search_title_query)
                if search_query and search_query.startswith("搜索:"):
                    search_query = search_query[3:].strip().strip('"')
                log_items_dict[item_id].search_title_query = search_query
            else:
                print(f"警告: 找不到ID为 {item_id} 的log_item")
        
        print(f"成功更新了 {len(matches)} 个log_item的分类信息")
        
    except Exception as e:
        print(f"更新state时发生错误: {e}")
        print(f"results.content: {results.content}")
    
    return state




def test_get_app_description():
    state = classifyState(
        app_registry = {"Antigravity": AppInFo(description=None, is_multipurpose=False)},
        goal = mock_goals,
        log_items = mock_log_items,
    )
    state = get_app_description(state)
    print(state.app_registry)

    
def test_easy_app_to_classify():
    state = classifyState(
        app_registry = mock_app_registry,
        goal = mock_goals,
        log_items = mock_log_items,
        category_tree = category_tree
    )
    easy_app_to_classify(state)


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



def multi_app_to_classify(state: classifyState) -> classifyState:
    







category_tree = {
        "工作/学习": ["编程", "学习AI相关知识", "记笔记"],
        "娱乐": ["游戏", "看电视"],
        "其他": None,
    }

if __name__ == "__main__":
    state = get_state(hours=36)
    state = mock_app_description(state)
    state = get_app_description(state)
    state = split_by_purpose(state)[0]
    state = easy_app_to_classify(state)
    # 格式化输出分类结果
    print("\n" + "="*120)
    print("分类结果汇总")
    print("="*120)
    print(f"{'ID':<8} {'应用':<20} {'分类':<15} {'子分类':<15} {'关联目标':<20} {'搜索查询':<30}")
    print("-"*120)
    
    for item in state.log_items:
        # 截断过长的字段
        app = item.app[:18] if len(item.app) > 18 else item.app
        category = (item.category[:13] if item.category and len(item.category) > 13 else item.category) or "未分类"
        sub_category = (item.sub_category[:13] if item.sub_category and len(item.sub_category) > 13 else item.sub_category) or "-"
        link_to_goal = (item.link_to_goal[:18] if item.link_to_goal and len(item.link_to_goal) > 18 else item.link_to_goal) or "-"
        search_query = (item.search_title_query[:28] if item.search_title_query and len(item.search_title_query) > 28 else item.search_title_query) or "-"
        title = item.title[:28] if item.title and len(item.title) > 28 else item.title
        print(f"{item.id:<8} {app:<20} {title:<28}{category:<15} {sub_category:<15} {link_to_goal:<20} {search_query:<30}")
    
    print("="*120)
    
    # 统计信息
    classified_count = sum(1 for item in state.log_items if item.category is not None)
    has_search_query = sum(1 for item in state.log_items if item.search_title_query is not None)
    linked_to_goal = sum(1 for item in state.log_items if item.link_to_goal is not None)
    
    print(f"\n统计信息:")
    print(f"  总记录数: {len(state.log_items)}")
    print(f"  已分类: {classified_count} ({classified_count/len(state.log_items)*100:.1f}%)")
    print(f"  需要搜索: {has_search_query}")
    print(f"  关联目标: {linked_to_goal}")
    
    # 测试分离功能
    print("\n" + "="*120)
    print("测试分离单用途和多用途")
    print("="*120)
    single_state, multi_state = split_by_purpose(state)
    
    print(f"\n单用途 state:")
    print(f"  - log_items: {len(single_state.log_items)} 条")
    print(f"  - app_registry: {len(single_state.app_registry)} 个应用")
    print(f"  - 应用列表: {list(single_state.app_registry.keys())}")
    
    print(f"\n多用途 state:")
    print(f"  - log_items: {len(multi_state.log_items)} 条")
    print(f"  - app_registry: {len(multi_state.app_registry)} 个应用")
    print(f"  - 应用列表: {list(multi_state.app_registry.keys())}")
    print()