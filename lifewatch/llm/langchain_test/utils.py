from lifewatch.llm.langchain_test.state_define import Goal,classifyState,LogItem
def format_goals_for_prompt(goals: list[Goal]) -> str:
    """将 goals 列表格式化为易于 AI 理解的字符串"""
    if not goals:
        return "用户暂未设定目标"
    
    formatted = "用户目标列表：\n"
    for i, goal in enumerate(goals, 1):
        formatted += f"{i}. 目标：{goal.goal}\n"
        formatted += f"   分类：{goal.category}"
        if goal.sub_category:
            formatted += f" > {goal.sub_category}"
        formatted += "\n"
    return formatted.strip()

def format_category_tree_for_prompt(category_tree: dict[str, list[str] | None]) -> str:
    """将 category_tree 字典格式化为易于 AI 理解的字符串"""
    if not category_tree:
        return "暂无分类体系"
    
    formatted = "分类体系：category -> sub_category\n"
    for category, sub_categories in category_tree.items():
        formatted += f"• {category}\n"
        if sub_categories:
            for sub in sub_categories:
                formatted += f"  - {sub}\n"
        else:
            formatted += f"  - (无子分类)\n"
    return formatted.strip()

def format_log_items_for_prompt(log_items: list[LogItem]) -> str:
    """
    返回LogItem中的非输出字段,并按照
    id app duration title  的顺序转化为str
    """ 
    if not log_items:
        return "暂无待分类数据"
    
    formatted = "待分类的活动记录：\n"
    for log_item in log_items:
        # 提取需要的字段
        item_dict = log_item.model_dump(exclude={
            "category", 
            "sub_category", 
            "link_to_goal",
            "search_title_query",
            "search_title_content",
            "need_analyze_context",
            "is_multipurpose"
        })
        formatted += f"{item_dict}\n"
    
    return formatted.strip()

if __name__ == "__main__":
    from lifewatch.llm.langchain_test.mock_data import mock_log_items
    print(format_log_items_for_prompt(mock_log_items))
    category_tree = {
        "工作/学习": ["编程", "学习AI相关知识", "记笔记"],
        "娱乐": ["游戏", "看电视"],
        "其他": None,
    }
    print(format_category_tree_for_prompt(category_tree))
