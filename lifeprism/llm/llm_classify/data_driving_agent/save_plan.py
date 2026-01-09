"""
保存执行计划为 JSON 模板 (V2 - 适配新 schemas)

支持新的节点字段：
- node_type: llm-first, tool-first, planning
- thread_id: 线程隔离
- data_in_thread / data_in_slice: 从父线程或指定线程获取输入数据
- data_out / data_out_description: 输出到父线程
- initial_tool_name / initial_tool_args: tool-first 节点专用
- enable_tool_loop: 是否启用工具调用循环
"""
import json
import re
from pathlib import Path
from typing import Any
from lifeprism.llm.llm_classify.tests.data_driving_agent_v2.data_driving_schemas import ExecutionPlan


def save_plan_as_template(
    plan: ExecutionPlan,
    date: str,
    output_path: str | Path,
    pattern_name: str = "llm_generate_pattern",
    tools_limit: dict[str, int] | None = None,
    placeholders: dict[str, str] | None = None
) -> None:
    """
    将 ExecutionPlan 保存为 JSON 模板，将具体日期等值替换为占位符
    
    Args:
        plan: 执行计划对象
        date: 需要被替换的具体日期，格式 YYYY-MM-DD，替换为 {date}
        output_path: 输出 JSON 文件路径
        pattern_name: 模式名称，默认 "llm_generate_pattern"
        tools_limit: 可选的工具调用次数限制
        placeholders: 可选的额外占位符替换，格式 {"实际值": "占位符名"}
            例如 {"main": "main_thread_id"} 会将 "main" 替换为 "{main_thread_id}"
    
    Example:
        >>> save_plan_as_template(
        ...     plan=plan,
        ...     date="2026-01-05",
        ...     output_path="patterns/daily.json",
        ...     pattern_name="simple",
        ...     tools_limit={"get_daily_stats": 1},
        ...     placeholders={"main": "main_thread_id"}
        ... )
    """
    if isinstance(output_path, str):
        output_path = Path(output_path)
    
    # 将 ExecutionPlan 转为 dict (exclude_none 排除 None 值，减少模板冗余)
    plan_dict = plan.model_dump(exclude_none=True, exclude_defaults=True)
    
    # 重新添加必要的默认值字段（部分关键字段即使是默认值也保留）
    for node in plan_dict.get("nodes", []):
        # 确保 thread_id 存在
        if "thread_id" not in node:
            node["thread_id"] = "main"
        # 确保 data_out_thread 字段存在（用于多级嵌套）
        if "data_out_thread" not in node:
            node["data_out_thread"] = None
        # 确保 tools 字段存在（即使是 None）
        if "tools" not in node:
            node["tools"] = None
        # data_in 字段：如果未指定则保持默认行为（不写入模板）
        # data_in_thread 和 data_in_slice 仅在显式设置时保留
    
    # 如果有 tools_limit，添加到 plan_dict
    if tools_limit:
        plan_dict["tools_limit"] = tools_limit
    
    # 转为 JSON 字符串
    plan_json_str = json.dumps(plan_dict, ensure_ascii=False, indent=2)
    
    # 替换日期为占位符
    plan_json_str = plan_json_str.replace(date, "{date}")
    
    # 替换额外的占位符
    if placeholders:
        for actual_value, placeholder_name in placeholders.items():
            plan_json_str = plan_json_str.replace(
                f'"{actual_value}"', 
                f'"{{{placeholder_name}}}"'
            )
    
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
    
    print(f"✅ 计划已保存到: {output_path} (pattern: {pattern_name})")
    print(f"   节点数量: {len(plan_dict.get('nodes', []))}")
    if tools_limit:
        print(f"   工具限制: {tools_limit}")


def load_plan_from_template(
    json_path: str | Path,
    pattern_name: str,
    date: str,
    extra_replacements: dict[str, str] | None = None
) -> tuple[ExecutionPlan, dict[str, int] | None]:
    """
    从 JSON 模板加载执行计划
    
    Args:
        json_path: JSON 模板文件路径
        pattern_name: 要加载的模式名称
        date: 替换 {date} 占位符的实际日期
        extra_replacements: 额外的占位符替换，格式 {"{placeholder}": "actual_value"}
    
    Returns:
        tuple[ExecutionPlan, dict | None]: (执行计划, 工具限制配置)
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
    
    # 替换占位符
    plan_json_str = json.dumps(plan_data, ensure_ascii=False)
    plan_json_str = plan_json_str.replace("{date}", date)
    
    # 替换额外的占位符
    if extra_replacements:
        for placeholder, actual_value in extra_replacements.items():
            plan_json_str = plan_json_str.replace(placeholder, actual_value)
    
    plan_data = json.loads(plan_json_str)
    
    # 提取 tools_limit
    tools_limit = plan_data.pop("tools_limit", None)
    
    return ExecutionPlan(**plan_data), tools_limit


# 示例用法
if __name__ == "__main__":
    from lifeprism.llm.llm_classify.tests.data_driving_agent_v2.plan_generator import plan_generator
    from lifeprism.llm.llm_classify.tests.data_driving_agent_v2.data_driving_schemas import NodeDefinition
    
    # 示例1：手动创建计划并保存
    example_plan = ExecutionPlan(
        task="每日行为总结 {date}",
        nodes=[
            NodeDefinition(
                node_type="tool-first",
                node_name="获取每日统计",
                task_prompt="",
                initial_tool_name="get_daily_stats",
                initial_tool_args={"date": "2026-01-05"},
                thread_id="main",
                data_out_thread=None,  # 主线程，无父线程
                data_out=False
            ),
            NodeDefinition(
                node_type="llm-first",
                node_name="生成总结",
                task_prompt="根据上述统计数据，生成用户行为总结",
                thread_id="main",
                data_out_thread=None,  # 主线程，无父线程
                enable_tool_loop=False,
                data_out=True,
                data_out_description="用户行为总结: "
            )
        ]
    )
    
    # 保存为模板
    save_plan_as_template(
        plan=example_plan,
        date="2026-01-05",
        output_path=r"D:\desktop\软件开发\LifeWatch-AI\lifeprism\llm\llm_classify\tests\data_driving_agent_v2\patterns\example_daily_plan.json",
        pattern_name="simple",
        tools_limit={"get_daily_stats": 1}
    )
    
    # 示例2：从 LLM 生成的计划保存
    # plan = plan_generator("2026-01-01", skill_path)
    # save_plan_as_template(plan, date="2026-01-01", output_path="...", pattern_name="complex")
