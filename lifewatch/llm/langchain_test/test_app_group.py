from lifewatch.llm.langchain_test.classify_graph import easy_app_to_classify
from lifewatch.llm.langchain_test.state_define import classifyState
from lifewatch.llm.langchain_test.mock_data import mock_log_items, mock_goals, mock_app_registry

# 创建测试 state
category_tree = {
    "工作/学习": ["编程", "学习AI相关知识", "记笔记"],
    "娱乐": ["游戏", "看电视"],
    "其他": [],
}

state = classifyState(
    app_registry=mock_app_registry,
    log_items=mock_log_items[:5],  # 只测试前5条
    goal=mock_goals,
    category_tree=category_tree
)

# 测试按 app 分组的格式
app_groups = {}
for log_item in state.log_items:
    app_name = log_item.app
    if app_name not in app_groups:
        app_groups[app_name] = []
    app_groups[app_name].append(log_item)

app_content = "待分类的软件列表（按应用分组）：\n\n"
for app_name, items in app_groups.items():
    app_description = state.app_registry.get(app_name, "无描述")
    app_content += f"## {app_name}\n"
    app_content += f"应用描述: {app_description}\n"
    app_content += "活动记录:\n"
    for item in items:
        item_dict = item.model_dump(exclude={
            "category", "sub_category", "link_to_goal",
            "search_title_query", "search_title_content", "need_analyze_context"
        })
        app_content += f"  {item_dict}\n"
    app_content += "\n"

print(app_content)
