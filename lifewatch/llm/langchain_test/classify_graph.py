
from lifewatch.llm.langchain_test.creat_model import create_ChatTongyiModel 
from langgraph.graph import StateGraph, MessagesState, START, END
from typing_extensions import TypedDict
# Mock data based on actual database records


class LogItem(TypedDict):
    # 基础数据
    id: int
    app: str
    duration: int # 时长
    title: str | None
    is_multipurpose: bool
    # 分类结果
    category: str | None # 存储分类结果
    sub_category: str | None # 存储分类结果
    # 搜索标题
    search_title_query: str | None # 搜索标题的查询
    search_title_content: str | None # 搜索标题的结果
    # 上一条数据
    need_analyze_context: bool # 是否需要获取上一条数据信息
class Goal(TypedDict):
    goal: str # 用户的目标
    category: str # 用户的目标绑定的分类, Goal必须有第一个类别
    sub_category: str | None # 用户的目标绑定的子分类


# 定义状态\
class classifyState(TypedDict):
    app_registry: dict[str, str | None] # app : app_description
    log_items: list[LogItem] # 分类数据 
    goal: list[Goal] # 用户的目标
    
# App registry - mapping app names to their descriptions
mock_app_registry = {
    "antigravity": "代码编辑器，用于软件开发",
    "affine": "笔记和知识管理应用",
    "msedge": "Microsoft Edge浏览器",
    "chrome": "Google Chrome浏览器",
    "code": "Visual Studio Code编辑器",
    "shellhost": "Windows系统设置界面",
    "explorer": "Windows文件资源管理器",
    "weixin": "微信聊天应用",
    "wps": "WPS Office办公软件",
}

# Mock log items based on actual user_app_behavior_log data
mock_log_items: list[LogItem] = [
    {
        "id": 1,
        "app": "shellhost",
        "duration": 15,
        "title": "快速设置",
        "is_multipurpose": False,
        "category": None,
        "sub_category": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
        "last_log_item": None,
    },
    {
        "id": 2,
        "app": "affine",
        "duration": 14,
        "title": "AFFiNE",
        "is_multipurpose": False,
        "category": None,
        "sub_category": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
        "last_log_item": None,
    },
    {
        "id": 3,
        "app": "antigravity",
        "duration": 12,
        "title": "LifeWatch-AI - Antigravity - ActivitySummaryHeader.tsx",
        "is_multipurpose": False,
        "category": None,
        "sub_category": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
        "last_log_item": None,
    },
    {
        "id": 4,
        "app": "antigravity",
        "duration": 19,
        "title": "LifeWatch-AI - Antigravity - ActivitySummaryHeader.tsx",
        "is_multipurpose": False,
        "category": None,
        "sub_category": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
        "last_log_item": None,
    },
    {
        "id": 5,
        "app": "affine",
        "duration": 161,
        "title": "AFFiNE",
        "is_multipurpose": False,
        "category": None,
        "sub_category": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
        "last_log_item": None,
    },
    {
        "id": 6,
        "app": "antigravity",
        "duration": 234,
        "title": "LifeWatch-AI - Antigravity - activity_summary_schemas.py",
        "is_multipurpose": False,
        "category": None,
        "sub_category": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
        "last_log_item": None,
    },
    {
        "id": 7,
        "app": "affine",
        "duration": 575,
        "title": "AFFiNE",
        "is_multipurpose": False,
        "category": None,
        "sub_category": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
        "last_log_item": None,
    },
    {
        "id": 8,
        "app": "msedge",
        "duration": 57,
        "title": "Google Gemini",
        "is_multipurpose": True,
        "category": None,
        "sub_category": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
        "last_log_item": None,
    },
    {
        "id": 9,
        "app": "antigravity",
        "duration": 99,
        "title": "LifeWatch-AI - Antigravity - dashboard.py",
        "is_multipurpose": False,
        "category": None,
        "sub_category": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
        "last_log_item": None,
    },
    {
        "id": 10,
        "app": "msedge",
        "duration": 23,
        "title": "Google Gemini",
        "is_multipurpose": True,
        "category": None,
        "sub_category": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
        "last_log_item": None,
    },
    {
        "id": 11,
        "app": "antigravity",
        "duration": 31,
        "title": "LifeWatch-AI - Antigravity - ActivitySummaryHeader.tsx",
        "is_multipurpose": False,
        "category": None,
        "sub_category": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
        "last_log_item": None,
    },
    {
        "id": 12,
        "app": "msedge",
        "duration": 14,
        "title": "LifeWatchAI",
        "is_multipurpose": True,
        "category": None,
        "sub_category": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
        "last_log_item": None,
    },
    {
        "id": 13,
        "app": "antigravity",
        "duration": 80,
        "title": "LifeWatch-AI - Antigravity - ActivitySummaryHeader.tsx",
        "is_multipurpose": False,
        "category": None,
        "sub_category": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
        "last_log_item": None,
    },
]

# Mock user goals
mock_goals: list[Goal] = [
    {
        "goal": "完成LifeWatch-AI项目开发",
        "category": "工作/学习",
        "sub_category": "编程",
    },
    {
        "goal": "学习新技术",
        "category": "工作/学习",
        "sub_category": "学习",
    },
]




if __name__ == "__main__":
    
    
    # Create initial state
    initial_state: classifyState = {
        "app_registry": mock_app_registry,
        "log_items": mock_log_items,
        "goal": mock_goals,
    }
    
    print("=== Mock Data Created ===")
    print(f"App Registry: {len(initial_state['app_registry'])} apps")
    print(f"Log Items: {len(initial_state['log_items'])} items")
    print(f"Goals: {len(initial_state['goal'])} goals")
    print("\nSample log items:")
    for item in initial_state['log_items'][:3]:
        print(f"  - {item['app']}: {item['title']} ({item['duration']}s)")
