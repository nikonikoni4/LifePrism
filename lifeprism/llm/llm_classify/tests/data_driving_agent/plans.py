"""
预定义的执行计划
"""
from schemas import ExecutionPlan, NodeDefinition


def get_daily_summary_plan(date: str) -> ExecutionPlan:
    """
    获取每日总结的执行计划：这个大概3w tokens
    
    Args:
        date: 日期，格式 YYYY-MM-DD
    
    Returns:
        ExecutionPlan: 执行计划
    """
    return ExecutionPlan(
        task=f"总结 {date} 我做了什么",
        nodes=[
            NodeDefinition(
                node_name="收集核心统计数据",
                task_prompt=f"""请调用 get_daily_stats 获取 {date} 的电脑使用统计数据，同时调用 query_goals 获取用户设定的目标信息，以及 query_psychological_assessment 获取心理测评数据。这些数据将用于分析任务完成情况、行为规律和心理状态关联性。""",
                tools=["get_daily_stats", "query_goals", "query_psychological_assessment"]
            ),
            NodeDefinition(
                node_name="获取详细行为日志",
                task_prompt=f"""根据核心统计数据中的活跃时间段分布，调用 query_behavior_logs 查询 {date} 的详细应用使用记录。重点关注用户备注标记的时段、工作类应用集中使用时段，以及可能与目标关联的时间块，用于分时段行为推断。""",
                tools=["query_behavior_logs"]
            ),
            NodeDefinition(
                node_name="生成行为总结",
                task_prompt=f"""整合所有收集的数据，按照每日总结格式生成 {date} 的行为摘要。需包含：
1) 分时段行为推断（结合应用记录与用户备注）
2) 作息规律分析
3) 目标任务完成情况评估
4) 综合亮点总结

注意使用 '可能' '推测' 等限定词，明确标注数据局限性，并给出具体可行的改进建议。""",
                tools=None,

            )
        ]
    )


def get_weekly_summary_plan(start_date: str, end_date: str) -> ExecutionPlan:
    """
    获取周总结的执行计划
    
    Args:
        start_date: 开始日期，格式 YYYY-MM-DD
        end_date: 结束日期，格式 YYYY-MM-DD
    
    Returns:
        ExecutionPlan: 执行计划
    """
    return ExecutionPlan(
        task=f"总结 {start_date} 到 {end_date} 这周我做了什么",
        nodes=[
            NodeDefinition(
                node_name="收集多日统计数据",
                task_prompt=f"""请调用 get_multi_days_stats 获取 {start_date} 到 {end_date} 的多日统计数据，同时调用 query_goals 获取用户目标信息。这些数据将用于分析趋势变化和目标进展。""",
                tools=["get_multi_days_stats", "query_goals"]
            ),
            NodeDefinition(
                node_name="生成周总结",
                task_prompt=f"""整合收集的数据，按照多日总结格式生成 {start_date} 到 {end_date} 的周总结。需包含：
1) 分类投入时间趋势分析
2) 目标投入时间趋势分析
3) 使用规律与作息分析
4) 任务完成情况分析
5) 综合总结与趋势洞察

注意识别趋势变化，给出具体的改进建议。""",
                tools=None
            )
        ]
    )


def get_monthly_summary_plan(start_date: str, end_date: str) -> ExecutionPlan:
    """
    获取月总结的执行计划
    
    Args:
        start_date: 开始日期，格式 YYYY-MM-DD
        end_date: 结束日期，格式 YYYY-MM-DD
    
    Returns:
        ExecutionPlan: 执行计划
    """
    return ExecutionPlan(
        task=f"总结 {start_date} 到 {end_date} 这个月我做了什么",
        nodes=[
            NodeDefinition(
                node_name="收集月度统计数据",
                task_prompt=f"""请调用 get_multi_days_stats 获取 {start_date} 到 {end_date} 的月度统计数据，同时调用 query_goals 和 query_psychological_assessment 获取目标和心理测评信息。""",
                tools=["get_multi_days_stats", "query_goals", "query_psychological_assessment"]
            ),
            NodeDefinition(
                node_name="生成月总结",
                task_prompt=f"""整合收集的数据，生成 {start_date} 到 {end_date} 的月度总结。需包含：
1) 月度整体趋势分析
2) 目标完成情况和进展
3) 作息规律变化
4) 心理状态与行为关联分析
5) 下月改进建议

注意突出月度变化和长期趋势。""",
                tools=None
            )
        ]
    )


# 示例用法
if __name__ == "__main__":
    # 测试生成每日总结计划
    plan = get_daily_summary_plan("2026-01-05")
    print(plan.model_dump_json(indent=2))
