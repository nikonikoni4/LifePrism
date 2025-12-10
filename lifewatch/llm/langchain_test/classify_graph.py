from lifewatch.llm.langchain_test.creat_model import create_ChatTongyiModel 
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage
import json
from lifewatch.llm.langchain_test.utils import format_goals_for_prompt, format_category_tree_for_prompt,format_log_items_for_prompt
from lifewatch.llm.langchain_test.mock_data import mock_log_items, mock_goals, mock_app_registry
from lifewatch.llm.langchain_test.state_define import classifyState, LogItem, Goal, AppInFo


# 创建chatmodel
chat_model = create_ChatTongyiModel()

# 定义router


# 定义node
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
        # 你是一个软件分类专家。你的任务是根据软件名称,描述,Title,将软件进行分类。
        # 分类类别
        {category_tree}
        # 用户目标
        {goal}
        # 分类规则
        1. 对于单用途,依据app_description进行分类
        2. 对于app和title与goal高度相关的条目,使用goal的分类类别,并关联goal,link_to_goal = goal
        3. 对于多用途,依据title进行分类:
            - 若对于title完全已知,且有且只有一个分类能够匹配,则直接进行分类
            - 若对于title内某些内容未知,给出你需要查询的内容赋值给search_title_query,或无法确定的,各级分类为None
        4. 若无法分类,则分类为None
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
    print(system_message.content)
    #results = chat_model.invoke(messages)
    
    # 提取 token 使用情况
    # token_usage = results.response_metadata.get('token_usage', {})
    # state.node_token_usage['easy_app_to_classify'] = token_usage
    return state



def test_get_app_description():
    state = classifyState(
        app_registry = {"Antigravity": AppInFo(description=None, is_multipurpose=False)},
        goal = mock_goals,
        log_items = mock_log_items,
    )
    state = get_app_description(state)
    print(state.app_registry)
category_tree = {
        "工作/学习": ["编程", "学习AI相关知识", "记笔记"],
        "娱乐": ["游戏", "看电视"],
        "其他": None,
    }
    
def test_easy_app_to_classify():
    state = classifyState(
        app_registry = mock_app_registry,
        goal = mock_goals,
        log_items = mock_log_items,
        category_tree = category_tree
    )
    easy_app_to_classify(state)


if __name__ == "__main__":
    # graph = StateGraph(classifyState)
    test_easy_app_to_classify()

    # # 格式化输出
    # print("=" * 50)
    # print(format_goals_for_prompt(mock_goals))
    # print("\n" + "=" * 50)
    # print(format_category_tree_for_prompt(category_tree))
    # print("=" * 50)