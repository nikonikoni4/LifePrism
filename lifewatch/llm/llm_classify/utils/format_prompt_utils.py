from lifewatch.llm.llm_classify.schemas.classify_shemas import Goal,LogItem
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

def format_app_log_items_for_prompt(log_items: list[LogItem], app_registry: dict) -> str:
    """
    将单用途应用的 log_items 按应用分组格式化为 prompt
    
    Args:
        log_items: LogItem 列表
        app_registry: 应用注册表（字典），key为app名称，value为AppInfo对象
        
    Returns:
        格式化后的字符串，按应用分组展示
    """
    if not log_items:
        return "暂无待分类数据"
    
    # 按 app 分组 log_items
    app_groups = {}
    for log_item in log_items:
        app_name = log_item.app
        if app_name not in app_groups:
            app_groups[app_name] = []
        app_groups[app_name].append(log_item)
    
    # 构建按 app 分组的内容
    app_content = "待分类的软件列表（按应用分组）：\n\n"
    for app_name, items in app_groups.items():
        app_info = app_registry.get(app_name)
        if app_info:
            app_description = app_info.description
        else:
            app_description = "无描述"
        app_content += f"## {app_name}\n"
        app_content += f"应用描述: {app_description}\n"
        app_content += "活动记录:\n"
        
        # 第一条记录显示键名
        if items:
            first_item = items[0]
            first_dict = first_item.model_dump(exclude={
                "category", "sub_category", "link_to_goal",
                "search_title_query", "search_title_content", "need_analyze_context",
                "multi_node_result"
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
                    "multi_node_result"
                })
                values = [str(item_dict[k]) for k in keys]
                app_content += f"  {' | '.join(values)}\n"
        
        app_content += "\n"
    
    return app_content.strip()
