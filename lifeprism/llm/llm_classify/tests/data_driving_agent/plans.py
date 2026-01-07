"""
预定义的执行计划
"""
import json
from pathlib import Path
from schemas import ExecutionPlan, NodeDefinition
from typing import Literal
# 获取当前文件所在目录
_CURRENT_DIR = Path(__file__).parent
_PATTERN_DIR = _CURRENT_DIR / "pattern"


def get_daily_summary_plan(date: str,json_path: Path, pattern_name: Literal["simple", "complex", "custom"] = "complex") -> tuple[ExecutionPlan, dict[str, int] | None]:
    """
    获取每日总结的执行计划
    
    Args:
        date: 日期，格式 YYYY-MM-DD
        pattern_name: 执行计划模式名称，可选值: "simple", "complex", "custom"
    
    Returns:
        ExecutionPlan: 执行计划
    """
    if isinstance(json_path, str):
        json_path = Path(json_path)
    if not json_path.exists():
        raise FileNotFoundError(f"JSON 文件不存在: {json_path}")
    # 读取 JSON 模板
    with open(json_path, "r", encoding="utf-8") as f:
        all_patterns = json.load(f)
    
    # 获取指定的 pattern
    if pattern_name not in all_patterns:
        raise ValueError(f"未知的 pattern_name: {pattern_name}，可用: {list(all_patterns.keys())}")
    
    plan_data = all_patterns[pattern_name]
    
    # 替换日期占位符
    plan_json_str = json.dumps(plan_data, ensure_ascii=False)
    plan_json_str = plan_json_str.replace("{date}", date)
    plan_data = json.loads(plan_json_str)
    tools_limit = plan_data.pop("tools_limit", None)
    return ExecutionPlan(**plan_data),tools_limit


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
