"""
保存执行计划为 JSON 模板
"""
import json
import re
from pathlib import Path
from lifeprism.llm.llm_classify.schemas.data_driving_schemas import ExecutionPlan


def save_plan_as_template(
    plan: ExecutionPlan,
    date: str,
    output_path: str | Path,
    pattern_name: str = "llm_generate_pattern",
    tools_limit: dict[str, int] | None = None
) -> None:
    """
    将 ExecutionPlan 保存为 JSON 模板，将具体日期替换为 {date} 占位符
    
    Args:
        plan: 执行计划对象
        date: 需要被替换的具体日期，格式 YYYY-MM-DD
        output_path: 输出 JSON 文件路径
        pattern_name: 模式名称，默认 "custom"
        tools_limit: 可选的工具调用次数限制
    """
    if isinstance(output_path, str):
        output_path = Path(output_path)
    
    # 将 ExecutionPlan 转为 dict
    plan_dict = plan.model_dump()
    
    # 如果有 tools_limit，添加到 plan_dict
    if tools_limit:
        plan_dict["tools_limit"] = tools_limit
    
    # 转为 JSON 字符串，替换具体日期为占位符
    plan_json_str = json.dumps(plan_dict, ensure_ascii=False, indent=2)
    plan_json_str = plan_json_str.replace(date, "{date}")
    
    # 读取现有文件（如果存在），否则创建新的
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            all_patterns = json.load(f)
    else:
        all_patterns = {}
    
    # 将替换后的 JSON 解析回 dict，更新到 patterns
    plan_data = json.loads(plan_json_str)
    all_patterns[pattern_name] = plan_data
    
    # 保存到文件
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_patterns, f, ensure_ascii=False, indent=2)
    
    print(f"计划已保存到: {output_path} (pattern: {pattern_name})")


# 示例用法
if __name__ == "__main__":
    from lifeprism.llm.llm_classify.data_driving_agent.plan_generator import plan_generator
    
    # 假设生成了一个计划
    plan = plan_generator("2026-01-01", r"D:\desktop\软件开发\LifeWatch-AI\lifeprism\llm\custom_prompt\skills\user_behavior_summary\skill.md")
    
    # 保存为模板
    save_plan_as_template(
        plan=plan,
        date="2026-01-01",
        output_path=r"D:\desktop\软件开发\LifeWatch-AI\lifeprism\llm\custom_prompt\skills\user_behavior_summary\pattern\daily_summary_plan copy.json",
        tools_limit={"query_usage_logs": 7}
    )
    pass
