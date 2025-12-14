from lifewatch.llm.langchain_test.state_define import LogItem, Goal, classifyState, AppInFo

# App registry - mapping app names to their descriptions and multipurpose status
mock_app_registry = {
    "antigravity": AppInFo(description="代码编辑器，用于软件开发", is_multipurpose=False),
    "affine": AppInFo(description="笔记和知识管理应用", is_multipurpose=False),
    "msedge": AppInFo(description="Microsoft Edge浏览器", is_multipurpose=True),
    "shellhost": AppInFo(description="Windows系统设置界面", is_multipurpose=False),
}

# Mock log items based on actual user_app_behavior_log data
mock_log_items: list[LogItem] = [
    {
        "id": 1,
        "app": "shellhost",
        "duration": 15,
        "title": "快速设置",        "category": None,
        "sub_category": None,
        "link_to_goal": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
    },
    {
        "id": 2,
        "app": "affine",
        "duration": 14,
        "title": "AFFiNE",        "category": None,
        "sub_category": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
        
    },
    {
        "id": 3,
        "app": "antigravity",
        "duration": 12,
        "title": "LifeWatch-AI - Antigravity - ActivitySummaryHeader.tsx",        "category": None,
        "sub_category": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
        
    },
    {
        "id": 4,
        "app": "antigravity",
        "duration": 19,
        "title": "LifeWatch-AI - Antigravity - ActivitySummaryHeader.tsx",        "category": None,
        "sub_category": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
        
    },
    {
        "id": 5,
        "app": "affine",
        "duration": 161,
        "title": "AFFiNE",        "category": None,
        "sub_category": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
        
    },
    {
        "id": 6,
        "app": "antigravity",
        "duration": 234,
        "title": "LifeWatch-AI - Antigravity - activity_summary_schemas.py",        "category": None,
        "sub_category": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
        
    },
    {
        "id": 7,
        "app": "affine",
        "duration": 575,
        "title": "AFFiNE",        "category": None,
        "sub_category": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
        
    },
    {
        "id": 8,
        "app": "msedge",
        "duration": 57,
        "title": "Google Gemini",        "category": None,
        "sub_category": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
        
    },
    {
        "id": 9,
        "app": "antigravity",
        "duration": 99,
        "title": "LifeWatch-AI - Antigravity - dashboard.py",        "category": None,
        "sub_category": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
        
    },
    {
        "id": 10,
        "app": "msedge",
        "duration": 23,
        "title": "Google Gemini",        "category": None,
        "sub_category": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
        
    },
    {
        "id": 11,
        "app": "antigravity",
        "duration": 31,
        "title": "LifeWatch-AI - Antigravity - ActivitySummaryHeader.tsx",        "category": None,
        "sub_category": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
        
    },
    {
        "id": 12,
        "app": "msedge",
        "duration": 14,
        "title": "LifeWatchAI",        "category": None,
        "sub_category": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
        
    },
    {
        "id": 13,
        "app": "antigravity",
        "duration": 80,
        "title": "LifeWatch-AI - Antigravity - ActivitySummaryHeader.tsx",        "category": None,
        "sub_category": None,
        "search_title_query": None,
        "search_title_content": None,
        "need_analyze_context": False,
        
    },
]

# 转换为 Pydantic 对象，为缺少的字段添加默认值
mock_log_items = [LogItem(**{**item, 'link_to_goal': item.get('link_to_goal', None)}) for item in mock_log_items]

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

# 转换为 Pydantic 对象
mock_goals = [Goal(**goal) for goal in mock_goals]
