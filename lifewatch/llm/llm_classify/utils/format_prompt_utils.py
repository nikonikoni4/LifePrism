from lifewatch.llm.llm_classify.schemas.classify_shemas import Goal,LogItem
def format_goals_for_prompt(goals: list[Goal]) -> str:
    """将 goals 列表格式化为易于 AI 理解的字符串"""
    if not goals:
        return ""
    
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
            formatted += f"\n"
    return formatted.strip()


def format_log_items_table(
    log_items: list[LogItem],
    fields: list[str],
    app_registry: dict = None,
    group_by_app: bool = False,
    show_app_description: bool = False
) -> str:
    """
    通用的 log_items 表格格式化函数
    
    Args:
        log_items: LogItem 列表
        fields: 要显示的字段列表，如 ["id", "app", "title"]
        app_registry: 应用注册表（group_by_app=True 时需要）
        group_by_app: 是否按应用分组（用于 single_classify）
        show_app_description: 是否显示应用描述（group_by_app=True 时有效）
        
    Returns:
        格式化后的表格字符串
        
    Example:
        >>> # single_classify 用法
        >>> format_log_items_table(
        ...     items, 
        ...     fields=["id", "app", "title"],
        ...     app_registry=app_registry,
        ...     group_by_app=True,
        ...     show_app_description=True
        ... )
        
        >>> # multi_classify 用法
        >>> format_log_items_table(items, fields=["id", "app", "title", "title_analysis"])
    """
    if not log_items:
        return "暂无待分类数据"
    
    def get_field_value(item: LogItem, field: str) -> str:
        """获取 LogItem 的字段值"""
        value = getattr(item, field, None)
        if value is None:
            return "N/A"
        # 限制长度，避免表格过宽
        str_value = str(value)
        if len(str_value) > 80:
            return str_value[:77] + "..."
        return str_value
    
    if group_by_app:
        # 按应用分组模式
        app_groups = {}
        for item in log_items:
            app_name = item.app
            if app_name not in app_groups:
                app_groups[app_name] = []
            app_groups[app_name].append(item)
        
        result = "待分类的软件列表（按应用分组）：\n\n"
        for app_name, items in app_groups.items():
            result += f"## {app_name}\n"
            
            if show_app_description and app_registry:
                app_info = app_registry.get(app_name)
                description = app_info.description if app_info else "无描述"
                result += f"应用描述: {description}\n"
            
            result += "活动记录:\n"
            # 表头
            result += f"  {' | '.join(fields)}\n"
            # 数据行
            for item in items:
                values = [get_field_value(item, f) for f in fields]
                result += f"  {' | '.join(values)}\n"
            result += "\n"
        
        return result.strip()
    else:
        # 简单表格模式
        result = "待分类的活动记录：\n"
        # 表头
        result += f"  {' | '.join(fields)}\n"
        # 数据行
        for item in log_items:
            values = [get_field_value(item, f) for f in fields]
            result += f"  {' | '.join(values)}\n"
        
        return result.strip()


if __name__ == "__main__":
    data = [i for i in range(50)]
    print(data_spliter(data,51))